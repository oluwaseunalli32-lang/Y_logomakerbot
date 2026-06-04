import os
import logging
import requests
import io
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Text-to-image AI model
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    welcome_text = (
        "🎨 **Welcome to Y_logomakerbot!** 🎨\n\n"
        "I am your personal AI logo designer. Just type in what you want your logo to look like, "
        "and I'll generate it for you in seconds!\n\n"
        "**Example:** `A minimalist geometric logo for a coffee shop, vector, blue and gold` \n\n"
        "Ready? Go ahead and send me your brand name or design prompt!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def generate_logo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages, sends them to Hugging Face, and returns the image."""
    user_prompt = update.message.text
    processing_msg = await update.message.reply_text("🔄 *Designing your logo... Please wait a few seconds.*", parse_mode="Markdown")

    enhanced_prompt = f"Professional logo design, {user_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"

    try:
        response = requests.post(API_URL, headers=HEADERS, json={"inputs": enhanced_prompt})
        
        if response.status_code == 200:
            image_bytes = response.content
            image_file = io.BytesIO(image_bytes)
            image_file.name = 'logo.png'

            await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")
        else:
            logger.error(f"HF API Error: {response.status_code} - {response.text}")
            await update.message.reply_text("⚠️ Sorry, the AI server is busy right now. Please try again in a moment!")

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        await update.message.reply_text("❌ An error occurred while generating your logo. Please try again.")
    
    finally:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)

def main():
    """Start the bot."""
    if not TOKEN or not HF_TOKEN:
        logger.error("Missing environment variables! Ensure TELEGRAM_TOKEN and HF_TOKEN are set.")
        return

    # FIX FOR PYTHON 3.14+: Explicitly get or create the event loop before building the application
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, so we create one and set it as current
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("New event loop created and set successfully.")

    # Build the Application
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_logo))

    # Run the bot
    logger.info("Bot is starting up...")
    application.run_polling()

if __name__ == '__main__':
    main()
