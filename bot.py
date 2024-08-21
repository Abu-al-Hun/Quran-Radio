import discord
import logging
import json
import os
from discord.ext import commands
from discord import app_commands
from art import text2art  
from colorama import Fore, Style, init
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
init(autoreset=True)

# Set up the bot
bot = commands.Bot(command_prefix="/", intents=intents)

# Read environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
AUTHORIZED_ROLE_ID = os.getenv('AUTHORIZED_ROLE_ID')
VOICE_CHANNEL_ID = None  # This will be set by the /link command

# Validate environment variables
if not DISCORD_TOKEN or not GUILD_ID or not AUTHORIZED_ROLE_ID:
    raise ValueError("One or more environment variables are missing.")

GUILD_ID = int(GUILD_ID)
AUTHORIZED_ROLE_ID = int(AUTHORIZED_ROLE_ID)

# Default reciter data
default_reciter_data = {
    "Yasser al dosari": "https://backup.qurango.net/radio/yasser_aldosari",
    "Maher al meaqli": "https://Qurango.net/radio/maher_al_meaqli",
    "Saoud Al Shouraim": "https://backup.qurango.net/radio/saud_alshuraim",
    "Mouhammed Ayyub": "https://backup.qurango.net/radio/mohammed_ayyub",
    "Khalid AL Jalil": "https://Qurango.net/radio/khalid_aljileel"
}

# Create list.json file if it doesn't exist and populate it with default data
def create_default_list():
    if not os.path.exists('list.json'):
        with open('list.json', 'w') as file:
            json.dump(default_reciter_data, file, indent=4)
        print(Fore.LIGHTGREEN_EX + "Created list.json with default data." + Style.RESET_ALL)

# Load reciter data from list.json
def load_reciter_data():
    try:
        with open('list.json', 'r') as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(Fore.LIGHTRED_EX + f"Error loading list.json: {e}" + Style.RESET_ALL)
        return {}

# Event: Bot is ready
@bot.event
async def on_ready():
    try:
        # Create default list.json file
        create_default_list()
        
        # Load reciter data
        global data
        data = load_reciter_data()

        # Display ASCII text and bot status in the console
        ascii_art_text = text2art("Wick® Studio")
        print(Fore.LIGHTCYAN_EX + ascii_art_text + Style.RESET_ALL)
        print(Fore.LIGHTGREEN_EX + f"Logged in as {bot.user}" + Style.RESET_ALL)

        # Sync commands to the specified guild
        bot.tree.copy_global_to(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))

        # Update bot presence
        await bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(type=discord.ActivityType.listening, name="Wick® Studio"))
    except Exception as e:
        print(Fore.LIGHTRED_EX + f"Error in on_ready event: {e}" + Style.RESET_ALL)

# Dropdown menu for selecting reciters
class DropdownMenu(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=key) for key in data.keys()]
        super().__init__(placeholder="Select a reciter...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_label = self.values[0]
        selected_url = data[selected_label]
        
        # Play the selected audio in the voice channel
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_connected():
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }
            voice_client.stop()  # Stop any current stream
            voice_client.play(discord.FFmpegPCMAudio(selected_url, **ffmpeg_options))

        # Update the embed with the new reciter name
        await update_embed(interaction, selected_label)
        await interaction.response.send_message(f"Now playing {selected_label} in the voice channel.", ephemeral=True)

# Custom view with the dropdown and button
class MyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DropdownMenu())

    @discord.ui.button(label="Join/Leave Voice", style=discord.ButtonStyle.primary)
    async def join_leave_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        global VOICE_CHANNEL_ID

        # Defer interaction to ensure response
        await interaction.response.defer(ephemeral=True)

        if VOICE_CHANNEL_ID is None:
            await interaction.followup.send("Voice channel not set. Use /link to set the channel.", ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await interaction.followup.send("Disconnected from the voice channel.", ephemeral=True)
        else:
            voice_channel = bot.get_channel(VOICE_CHANNEL_ID)
            if voice_channel and isinstance(voice_channel, discord.VoiceChannel):
                await voice_channel.connect()
                await interaction.followup.send(f"Joined voice channel: {voice_channel.name}", ephemeral=True)
            else:
                await interaction.followup.send("Voice channel ID is invalid.", ephemeral=True)

# Update the embed with the current reciter
async def update_embed(interaction: discord.Interaction, selected_label: str):
    embed = discord.Embed(
        title=f"Current Reciter: {selected_label}",
        description="Duration: Live Stream",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=interaction.guild.icon.url)
    
    # Update the current message with the new embed
    await interaction.message.edit(embed=embed)

class MyBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="control", description="Send an embed with a dropdown menu.")  # تغيير الاسم إلى أحرف صغيرة
    async def control(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Choose a Reciter", description="Select a reciter from the dropdown below.")
        view = MyView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="link", description="Link a voice channel for the bot.")  # تأكد من أن هذا الاسم أيضًا بالأحرف الصغيرة
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def link_voice_channel(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if AUTHORIZED_ROLE_ID in [role.id for role in interaction.user.roles]:
            global VOICE_CHANNEL_ID
            VOICE_CHANNEL_ID = channel.id
            await interaction.response.send_message(f"Linked voice channel: {channel.name}", ephemeral=True)
        else:
            await interaction.response.send_message("You don't have the required role to use this command.", ephemeral=True)

# Add the commands to the bot
bot.tree.add_command(MyBot(bot).control)
bot.tree.add_command(MyBot(bot).link_voice_channel)

# ضبط مستوى السجل للمكتبة discord فقط
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)

# تعطيل الطباعة الخاصة بـ discord.voice_state
voice_state_logger = logging.getLogger('discord.voice_state')
voice_state_logger.disabled = True

# تعطيل الطباعة الخاصة بـ discord.player
player_logger = logging.getLogger('discord.player')
player_logger.disabled = True

# Run the bot using the token
bot.run(DISCORD_TOKEN)
