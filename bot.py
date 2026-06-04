import os
import logging
import urllib3
import io
import asyncio
import html
from urllib.parse import quote
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

# Global PoolManager for handling connections cleanly
http = urllib3.PoolManager(retries=urllib3.Retry(connect=3, read=3, redirect=3))

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
    """Handles user messages, pulls the image from Pollinations AI, and sends it back."""
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
            
            # Send photo back safely
            await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")
        else:
            logger.error(f"Image generation failed with status code: {res.status}")
            await update.message.reply_text("⚠️ The image server is busy right now. Please try sending your text again!")

    except Exception as e:
        logger.error(f"Network error caught: {str(e)}")
        await update.message.reply_text("❌ Connection timeout. Let's try that prompt one more time.")
    
    finally:
        # Gracefully clear the loading text placeholder
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        except Exception:
            pass

def main():
    """Start the bot using Webhooks to completely eliminate duplicate/conflict instances."""
    if not TOKEN:
        logger.error("Missing TELEGRAM_TOKEN environment variable!")
        return

    # Fix for RuntimeError: There is no current event loop in thread 'MainThread'
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_logo))

    # Port is required by Render web services
    port = int(os.environ.get("PORT", 8443))

    if RENDER_EXTERNAL_URL:
        logger.info(f"Starting webhook on port {port} via URL: {RENDER_EXTERNAL_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            # FIX: Only allow alphanumeric characters and underscores (removed the '!')
            secret_token="ASecureSecretToken123", 
            webhook_url=f"{RENDER_EXTERNAL_URL}/webhook"
        )
    else:
        logger.info("No Render environment found. Falling back to local polling...")
        application.run_polling()

if __name__ == '__main__':
    main()
