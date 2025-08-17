

import os
import httpx
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import io


TELEGRAM_TOKEN = "7998202742:AAFTHFAQLWIGPCfqreuLlgZZ9-_SXTY8S6w"

# User's Gemini API key ko store karne ke liye ek simple dictionary.
# Ek real application mein, iski jagah database ka istemal karna chahiye.
user_api_keys = {}

# --- Helper Functions (Backend se copy kiya gaya) ---

def create_gemini_prompt(file_content: str, file_type: str) -> str:
    """Gemini ke liye file type ke anusaar ek specific prompt banata hai."""
    if file_type == 'srt':
        return f"""
        Translate the following SRT subtitle text to Hinglish (a mix of Hindi and English).
        **CRITICAL RULES:**
        1. **DO NOT** change the timestamps.
        2. **DO NOT** change the sequence numbers.
        3. **PRESERVE** all original line breaks exactly as they are.
        4. Only translate the dialogue text.
        ---
        Here is the SRT content to translate:
        ---
        {file_content}
        """
    elif file_type == 'ass':
        return f"""
        Translate the dialogue in the following ASS subtitle text to Hinglish.
        **CRITICAL RULES:**
        1. **DO NOT** change anything except the dialogue text after the final comma in "Dialogue:" lines.
        2. **PRESERVE** all formatting tags like {{\\i1}}, {{\\b1}}, etc.
        3. Keep all other lines ([Script Info], etc.) exactly the same.
        ---
        Here is the ASS content to translate:
        ---
        {file_content}
        """
    elif file_type == 'vtt':
        return f"""
        Translate the following WebVTT subtitle text to Hinglish.
        **CRITICAL RULES:**
        1. **DO NOT** change the "WEBVTT" header or timestamps.
        2. **PRESERVE** all original line breaks.
        3. Only translate the dialogue text.
        ---
        Here is the VTT content to translate:
        ---
        {file_content}
        """
    return f"Translate the following text to Hinglish:\n\n{file_content}"

# --- Telegram Bot Commands ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab user /start type karega to yeh message bhejega."""
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"Hello {user_name}! 👋\n\n"
        "Main ek Subtitle Translator Bot hoon.\n\n"
        "1. Sabse pehle, apni Gemini API key set karein. Type karein:\n"
        "`/setkey AAPKI_API_KEY_YAHAN`\n\n"
        "2. Fir mujhe koi bhi .srt, .vtt, ya .ass file bhejein aur main use translate kar dunga."
    )

async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ki Gemini API key ko save karega."""
    chat_id = update.message.chat_id
    try:
        # Command se key ko alag karein
        api_key = context.args[0]
        user_api_keys[chat_id] = api_key
        await update.message.reply_text("✅ Aapki Gemini API key save ho gayi hai. Ab aap file bhej sakte hain.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Galat format. Aise istemal karein:\n`/setkey AAPKI_API_KEY_YAHAN`")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab user koi file bhejega to yeh function chalega."""
    chat_id = update.message.chat_id

    # Check karein ki user ne API key set ki hai ya nahi
    if chat_id not in user_api_keys:
        await update.message.reply_text(
            "⚠️ Kripya pehle apni Gemini API key set karein.\n"
            "Type karein: `/setkey AAPKI_API_KEY_YAHAN`"
        )
        return

    document = update.message.document
    file_name = document.file_name
    
    try:
        file_extension = file_name.split('.')[-1].lower()
        if file_extension not in ['srt', 'vtt', 'ass']:
            await update.message.reply_text("❌ Galat file format. Sirf .srt, .vtt, ya .ass file bhejein.")
            return
    except IndexError:
        await update.message.reply_text("❌ File ka naam theek nahi hai.")
        return

    await update.message.reply_text("⏳ File mil gayi hai. Translate kar raha hoon... Ismein thoda time lag sakta hai.")

    try:
        # File ko download karein
        file = await document.get_file()
        file_content_bytes = await file.download_as_bytearray()
        file_content_str = file_content_bytes.decode('utf-8')

        # Gemini API ko call karein
        api_key = user_api_keys[chat_id]
        prompt = create_gemini_prompt(file_content_str, file_extension)
        gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(gemini_api_url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            translated_text = result['candidates'][0]['content']['parts'][0]['text']

        # Translated text ko file ki tarah wapas bhejein
        translated_bytes = translated_text.encode('utf-8')
        output_file = io.BytesIO(translated_bytes)
        
        original_name_without_ext = "".join(file_name.rsplit(f'.{file_extension}', 1))
        new_filename = f"{original_name_without_ext}_translated.{file_extension}"

        await update.message.reply_document(
            document=InputFile(output_file, filename=new_filename),
            caption="✅ Yeh rahi aapki translated file!"
        )

    except httpx.HTTPStatusError:
        await update.message.reply_text("❌ Translation fail ho gayi. Aapki Gemini API key galat ho sakti hai. Kripya `/setkey` se dobara set karein.")
    except Exception as e:
        await update.message.reply_text(f"😥 Ek error aa gayi: {e}")


def main():
    """Bot ko start karega."""
    print("Bot start ho raha hai...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("setkey", setkey_command))

    # File handler
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    # Bot ko start karein
    print("Bot live hai!")
    app.run_polling()

if __name__ == "__main__":
    main()

