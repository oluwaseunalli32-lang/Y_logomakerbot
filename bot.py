import os
import logging
import urllib3
import io
import asyncio
import html
import time
from urllib.parse import quote
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Global PoolManager for handling connections cleanly
http = urllib3.PoolManager(retries=urllib3.Retry(connect=3, read=3, redirect=3))

def clear_telegram_conflicts(token):
    """Forcefully evicts any existing ghost instances on Telegram's servers."""
    base_url = f"https://api.telegram.org/bot{token}"
    logger.info("Evicting competing ghost workers from Telegram servers...")
    try:
        # 1. Clear any stuck webhooks
        http.request("POST", f"{base_url}/deleteWebhook", fields={"drop_pending_updates": "true"}, timeout=10.0)
        
        # 2. Pull with a flush offset to kick out competing getUpdates long-pollers
        http.request("POST", f"{base_url}/getUpdates", fields={"offset": "-1", "limit": "1", "timeout": "0"}, timeout=10.0)
        
        logger.info("Ghost workers evicted successfully. Proceeding to safe initialization.")
        time.sleep(2) # Give Telegram's router a moment to catch its breath
    except Exception as e:
        logger.warning(f"Pre-flight conflict clearing warning: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    welcome_text = (
        "🎨 <b>Welcome to Y_logomakerbot!</b> 🎨\n\n"
        "I am your personal AI logo designer. Just type in what you want your logo to look like, "
        "and I'll generate it for you in seconds!\n\n"
        "<b>Example:</b> <code>A minimalist geometric logo for a coffee shop, vector, blue and gold</code>\n\n"
        "Ready? Go ahead and send me your brand name or design prompt!"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def generate_logo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages, pulls the image from an ultra-stable mirror route, and sends it back."""
    user_prompt = update.message.text
    
    # Send processing message
    processing_msg = await update.message.reply_text("🔄 <i>Designing your logo... Please wait a few seconds.</i>", parse_mode="HTML")

    # Clean the input and craft a prompt optimized for logo assets
    safe_prompt = html.escape(user_prompt)
    clean_prompt = f"Professional logo design, {safe_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"
    
    # Safe encoding for spaces and symbols to prevent 402 Errors
    encoded_prompt = quote(clean_prompt)
    api_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"

    try:
        def fetch_image():
            return http.request("GET", api_url, timeout=30.0)

        # Run the image download in a background thread to prevent blocking
        res = await asyncio.to_thread(fetch_image)
        
        if res.status == 200:
            image_file = io.BytesIO(res.data)
            image_file.name = 'logo.png'
            
            # Send photo back
            await update.message.reply_photo(photo=image_
