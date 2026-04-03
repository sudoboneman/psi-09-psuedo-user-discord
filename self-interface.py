# interface.py
import contextlib
import discord
from discord.ext import commands
from flask import Flask
import threading
import os
import aiohttp
import asyncio
import random
import traceback
import logging
import sys
import time
from dotenv import load_dotenv

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PSI09-Selfbot")

load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return "PSI-09 Data Mining Interface Active", 200

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- Discord Self-Bot Configuration ---
bot = commands.Bot(
    command_prefix="!", 
    self_bot=True, 
    guild_subscriptions=True, 
    chunk_guilds_at_startup=True
)

http_session = None

async def get_http_session():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

@bot.event
async def on_ready():
    app_id = os.getenv('APPLICATION_ID')
    
    if app_id:
        # Create the Rich Presence Activity
        # NOTE: Buttons removed. Assets will only show if uploaded to Discord Dev Portal.
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name="PSI-09",
            application_id=int(app_id),
            details="CORE: NOMINAL",
            state="",
            
            # Your custom July 2025 timestamp
            timestamps={"start": 1753857600 * 1000}, 
            
            assets={
                "large_image": "logo",   # Changed to match your Dev Portal upload
                "large_text": "",
                "small_image": "avatar", # Changed to match your Dev Portal upload
                "small_text": "github.com/sudoboneman"
            }
        )
        
        # DND is slightly safer than Online, looks like you're "busy coding"
        await bot.change_presence(status=discord.Status.dnd, activity=activity)
        logger.info(f"DATA FUNNEL OPEN: Logged in as {bot.user.name} (Custom RPC Active)")
    else:
        # Fallback to stealth if no APP_ID is provided
        await bot.change_presence(status=discord.Status.invisible)
        logger.info(f"DATA FUNNEL OPEN: Logged in as {bot.user.name} (Stealth Mode)")

@bot.event
async def on_message(message):
    # Safety Check: Ignore yourself and other bots
    if message.author.id == bot.user.id or message.author.bot:
        return

    # --- ANTI-DETECTION DM BLOCK ---
    if isinstance(message.channel, discord.DMChannel):
        return

    # 1. Local Context Check 
    is_mentioned = bot.user in message.mentions
    is_active_trigger = is_mentioned

    # 2. Group Name Formatting (Only servers now)
    server_name = str(message.guild.name) if message.guild else "Unknown Server"
    channel_name = getattr(message.channel, "name", "unknown")
    group_name = f"{server_name} | #{channel_name}"

    # 3. Extract Tags (Ignored on passive to save CPU)
    tagged_users = []
    if is_active_trigger:
        for user in message.mentions:
            if user.id != bot.user.id and user.id != message.author.id:
                tagged_users.append({
                    "id": str(user.id),
                    "username": user.name,
                    "display_name": getattr(user, "display_name", user.name)
                })
    
    # 4. Clean Payload
    payload = {
        "message": message.content,
        "sender_id": str(message.author.id),
        "username": message.author.name,
        "display_name": message.author.display_name,
        "group_name": group_name,
        "tagged_users": tagged_users[:3],
        "platform": "discord_selfbot"
    }

    # 5. Routing Path
    if not is_active_trigger:
        # DATA MINING PATH (Fire and forget, engine handles DB storage)
        asyncio.create_task(send_to_backend(payload, wait_for_reply=False))
        return 
    else:
        # COMBAT PATH (Wait for engine to process roast & typing delays)
        logger.info(f"ACTIVE TRIGGER: {message.author.name} in {group_name}")
        await asyncio.sleep(random.uniform(1.5, 3.5)) 
        
        async with message.channel.typing():
            reply = await send_to_backend(payload, wait_for_reply=True)
            
            if reply: 
                type_speed = min(max(len(reply) * 0.07, 2.0), 8.0)
                await asyncio.sleep(type_speed + random.uniform(0.5, 1.5))
                await message.channel.send(reply)

async def send_to_backend(payload, wait_for_reply=False):
    """Handles the HTTP pipeline to main.py"""
    try:
        url = os.getenv("PSI09_API_URL")
        headers = {"Content-Type": "application/json"}
        
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
            
        session = await get_http_session()
        
        timeout_limit = 480 if wait_for_reply else 15 
        
        async with session.post(url, json=payload, headers=headers, timeout=timeout_limit) as resp:
            if resp.status == 200 and wait_for_reply:
                data = await resp.json()
                return data.get("reply", "")
    except asyncio.TimeoutError:
        if wait_for_reply: logger.error("Backend took too long to generate a roast.")
    except Exception as e:
        logger.error(f"Relay Error: {e}")
    
    return None

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    token = os.getenv("USER_TOKEN")
    if token:
        bot.run(token)
    else:
        logger.error("CRITICAL: USER_TOKEN missing.")
        sys.exit(1)