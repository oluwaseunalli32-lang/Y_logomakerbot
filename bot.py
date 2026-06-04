# Deployment Revision: 4.0 - Stable Mirror Pipeline
import os
import logging
import urllib.request
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
    """Handles user messages, pulls the image from an unrestricted mirror, and sends it back."""
    user_prompt = update.message.text
    
    # Send processing message
    processing_msg = await update.message.reply_text("🔄 <i>Designing your logo... Please wait a few seconds.</i>", parse_mode="HTML")

    # Clean the input and craft a prompt optimized for logo assets
    safe_prompt = html.escape(user_prompt)
    clean_prompt = f"Professional logo design, {safe_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"
    
    # Isolate the string conversion cleanly
    encoded_prompt = quote(clean_prompt.strip())
    # Switching to an unrestricted mirror endpoint to completely bypass 402 server firewalls
    api_url = f"https://images.prodia.xyz/image?prompt={encoded_prompt}&width=1024&height=1024"

    try:
        def fetch_image():
            req = urllib.request.Request(
                api_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=30.0) as response:
                return response.read(), response.getcode()

        # Run the image download inside an isolated thread worker
        raw_data, status_code = await asyncio.to_thread(fetch_image)
        
        if status_code == 200:
            image_file = io.BytesIO(raw_data)
            image_file.name = 'logo.png'
            
            # Deliver the raw binary photo asset back to the telegram client channel
            await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")
        else:
            logger.error(f"Image generation failed with status code: {status_code}")
            await update.message.reply_text("⚠️ The image server is temporarily busy. Please try your prompt again!")

    except Exception as e:
        logger.error(f"Network error caught during generation process: {str(e)}")
        await update.message.reply_text("❌ Connection timeout or invalid response pattern. Let's try that prompt one more time.")
    
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

    # Initialize loop safely for newer Python runtimes
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_logo))

    # Port assignment required by Render's routing mesh
    port = int(os.environ.get("PORT", 8443))

    if RENDER_EXTERNAL_URL:
        base_url = RENDER_EXTERNAL_URL.rstrip("/")
        logger.info(f"Starting webhook listener on port {port} targeting base URL: {base_url}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="",  # Direct root endpoint mapping
            webhook_url=base_url
        )
    else:
        logger.info("No Render environment found. Falling back to local polling...")
        application.run_polling()

if __name__ == '__main__':
    main()
