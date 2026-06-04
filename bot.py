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
HF_TOKEN = os.getenv("HF_TOKEN")

# Robust PoolManager to bypass DNS level drops common on Render containers
http = urllib3.PoolManager(retries=urllib3.Retry(connect=3, read=3, redirect=3))

# Production fallback endpoint for the Stable Diffusion model
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

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
    """Handles user messages, sends them to AI endpoint, and returns the image."""
    user_prompt = update.message.text
    processing_msg = await update.message.reply_text("🔄 <i>Designing your logo... Please wait a few seconds.</i>", parse_mode="HTML")

    safe_prompt = html.escape(user_prompt)
    enhanced_prompt = f"Professional logo design, {safe_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"

    try:
        # Use a synchronous block wrapping urllib3 inside an execution thread
        def fetch_image():
            headers = {
                "Authorization": f"Bearer {HF_TOKEN}",
                "Content-Type": "application/json"
            }
            # Explicitly post JSON payload using pool management
            response = http.request(
                "POST", 
                API_URL, 
                headers=headers, 
                json={"inputs": enhanced_prompt},
                timeout=30.0
            )
            return response

        # Execute network call safely away from the primary async loop
        res = await asyncio.to_thread(fetch_image)
        
        if res.status == 200:
            image_file = io.BytesIO(res.data)
            image_file.name = 'logo.png'
            await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")
        else:
            logger.error(f"API Connection responded with status: {res.status}")
            await update.message.reply_text("⚠️ The AI engine is waking up. Please send your prompt one more time!")

    except Exception as e:
        logger.error(f"Network error caught: {str(e)}")
        await update.message.reply_text("❌ Connection timeout. Let's try that prompt again.")
    
    finally:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        except Exception:
            pass

def main():
    """Start the bot."""
    if not TOKEN or not HF_TOKEN:
        logger.error("Missing environment variables! Ensure TELEGRAM_TOKEN and HF_TOKEN are set.")
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
            logger.warning("Token conflict detected. Waiting out old worker deployment instance...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected loop drop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
