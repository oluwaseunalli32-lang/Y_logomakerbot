import os
import logging
import urllib3
import io
import asyncio
import html
import time
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Global PoolManager for handling outbound connections cleanly
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
    """Handles user messages, pulls the image from an ultra-stable mirror route, and sends it back."""
    user_prompt = update.message.text
    processing_msg = await update.message.reply_text("🔄 <i>Designing your logo... Please wait a few seconds.</i>", parse_mode="HTML")

    # Clean the input and craft a prompt optimized for logo assets
    safe_prompt = html.escape(user_prompt)
    clean_prompt = f"Professional logo design, {safe_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"
    
    # URL encode the prompt so spaces and special characters don't break the web address
    encoded_prompt = urllib3.util.parse_url(clean_prompt).url
    
    # We use a globally recognized endpoint that avoids Hugging Face's DNS sub-domain blocks
    # This calls a blazing-fast Stable Diffusion engine completely free without token requirements
    api_url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&nologo=true"

    try:
        def fetch_image():
            # Standard GET request to fetch the image binary stream
            response = http.request("GET", api_url, timeout=45.0)
            return response

        # Run the image download in a background thread
        res = await asyncio.to_thread(fetch_image)
        
        if res.status == 200:
            image_file = io.BytesIO(res.data)
            image_file.name = 'logo.png'
            await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")
        else:
            logger.error(f"Image generation failed with status code: {res.status}")
            await update.message.reply_text("⚠️ The generation pipeline is busy. Please try sending your prompt again!")

    except Exception as e:
        logger.error(f"Network error caught: {str(e)}")
        await update.message.reply_text("❌ Connection timeout. Let's try that prompt one more time.")
    
    finally:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        except Exception:
            pass

def main():
    """Start the bot with error-resilient long polling loops."""
    if not TOKEN:
        logger.error("Missing TELEGRAM_TOKEN environment variable!")
        return

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_logo))

    logger.info("Bot is starting up...")
    while True:
        try:
            application.run_polling(close_loop=False)
            break 
        except Conflict:
            logger.warning("Token conflict detected. Waiting for old Render worker to release the connection...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected loop drop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
