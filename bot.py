import os
import logging
import io
import asyncio
import html
import time
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from huggingface_hub import InferenceClient

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Initialize the official Hugging Face Inference Client
# This handles connection pooling and network drops much better than raw requests
client = InferenceClient(
    model="stabilityai/stable-diffusion-xl-base-1.0",
    token=HF_TOKEN
)

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
    """Handles user messages, sends them to Hugging Face, and returns the image."""
    user_prompt = update.message.text
    processing_msg = await update.message.reply_text("🔄 <i>Designing your logo... Please wait a few seconds.</i>", parse_mode="HTML")

    safe_prompt = html.escape(user_prompt)
    enhanced_prompt = f"Professional logo design, {safe_prompt}, clean vector graphic, minimalist, modern branding, isolated background, high resolution, 8k"

    try:
        # Run the network-bound image generation in a background thread to prevent blocking the async loop
        def call_hf():
            return client.text_to_image(enhanced_prompt)

        # Execute the generation safely
        image = await asyncio.to_thread(call_hf)
        
        # Convert PIL Image directly to bytes for Telegram upload
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)
        image_file.name = 'logo.png'

        await update.message.reply_photo(photo=image_file, caption="✨ Here is your generated logo! ✨")

    except Exception as e:
        logger.error(f"Error occurred during generation: {str(e)}")
        await update.message.reply_text("❌ An error occurred while generating your logo. Please try again.")
    
    finally:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg.message_id)
        except Exception:
            pass

def main():
    """Start the bot with automated conflict recovery."""
    if not TOKEN or not HF_TOKEN:
        logger.error("Missing environment variables! Ensure TELEGRAM_TOKEN and HF_TOKEN are set.")
        return

    # Python 3.14 asyncio loop initializer
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("New event loop created and set successfully.")

    # Build the Application
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_logo))

    logger.info("Bot is starting up...")
    while True:
        try:
            application.run_polling(close_loop=False)
            break 
        except Conflict:
            logger.warning("Telegram token conflict detected! An old Render instance is still shutting down. Retrying in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
