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
    return "PSI-09 Selfbot Interface is Active", 200

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask keep-alive on port {port}")
    app.run(host="0.0.0.0", port=port)

# --- Discord Self-Bot Configuration ---
# self_bot=True tells the library to use User-Account headers
bot = commands.Bot(
    command_prefix="!", 
    self_bot=True, 
    guild_subscriptions=True,     # CRITICAL: Forces Discord to send server messages
    chunk_guilds_at_startup=True  # Helps the bot remember who is in the server
)

http_session = None

async def get_http_session():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

@bot.event
async def on_ready():
    logger.info(f"SUCCESS: PSI-09 Selfbot Online as {bot.user.name}")

@bot.event
async def on_message(message):
    print(f"DEBUG RECV: [{message.guild}] {message.author.name}: {message.content}")
    # 1. Safety: Ignore yourself and other bots to prevent loops
    if message.author.id == bot.user.id or message.author.bot:
        return

    # 2. Context & Group Name Formatting
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    
    if is_dm:
        group_name = "Discord_DM"
    else:
        server_name = str(message.guild.name) if message.guild else "Unknown Server"
        channel_name = getattr(message.channel, "name", "unknown")
        group_name = f"{server_name} | #{channel_name}"

    # 3. Refined Tagged User Extraction
    # Filter out the bot itself and the sender from the mentions list
    tagged_users = []
    for user in message.mentions:
        if user.id != bot.user.id and user.id != message.author.id:
            tagged_users.append({
                "id": str(user.id),
                "username": user.name,
                "display_name": getattr(user, "display_name", user.name)
            })
    
    # 4. Payload Construction
    payload = {
        "message": message.content,
        "sender_id": str(message.author.id),
        "username": message.author.name,
        "display_name": message.author.display_name,
        "group_name": group_name,
        "tagged_users": tagged_users[:3], # Keep it to top 3 to avoid payload bloat
        "platform": "discord_selfbot"
    }

    # 5. Response Triggering with Humanized Timing
    should_reply_active = is_dm or is_mentioned

    try:
        if should_reply_active:
            logger.info(f"Processing active message from {message.author.name}")
            
            # --- PHASE 1: READ DELAY ---
            # Wait 1.5 to 3.5 seconds before acknowledging (simulates reading)
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            typing_context = message.channel.typing()
        else:
            typing_context = contextlib.nullcontext()

        # 6. The Relay
        async with typing_context:
            backend_url = os.getenv("PSI09_API_URL")
            hf_token = os.getenv("HF_TOKEN")
            
            headers = {"Content-Type": "application/json"}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"

            session = await get_http_session()
            
            # Request reply from backend
            async with session.post(backend_url, json=payload, headers=headers, timeout=480) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data.get("reply", "")

                    if reply:
                        # --- PHASE 2: TYPE DELAY ---
                        # Calculate delay: ~0.08s per character, capped between 2-8 seconds
                        type_speed = min(max(len(reply) * 0.08, 2.0), 8.0)
                        await asyncio.sleep(type_speed + random.uniform(0.5, 1.5))
                        
                        # Send as a normal message (more natural for user accounts)
                        await message.channel.send(reply)
                else:
                    if should_reply_active:
                        logger.error(f"Backend Error: {resp.status}")
    except Exception as e:
        logger.error(f"Relay Error: {e}")

    # Process any bot commands if applicable
    await bot.process_commands(message)

if __name__ == "__main__":
    # Flask for keep-alive (Render/Heroku compatible)
    threading.Thread(target=run_web_server, daemon=True).start()

    # User accounts use a USER_TOKEN (NOT a bot token)
    token = os.getenv("USER_TOKEN") 
    if not token:
        logger.error("CRITICAL: USER_TOKEN environment variable not set.")
        sys.exit(1)

    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start: {e}")