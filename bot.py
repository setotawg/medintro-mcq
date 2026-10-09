
import os
import logging
from collections import defaultdict
from time import monotonic

from groq import AsyncGroq
from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatAction,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

SITE_URL = "https://setotawg.github.io/medintro-mcq/"
BOT_USERNAME = "MedIntroStudyBot"

PUBLIC_URL = (
    os.getenv("WEBHOOK_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
)

PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

if not PUBLIC_URL:
    raise RuntimeError(
        "Set WEBHOOK_URL to your public Render service URL."
    )

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ai = AsyncGroq(api_key=GROQ_API_KEY)

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

# Basic per-user cooldown.
last_request = defaultdict(float)
COOLDOWN_SECONDS = 3

SYSTEM_INSTRUCTIONS = """
You are MedIntroStudyBot, the educational assistant
for students using the MedIntro learning platform.

YOUR RESPONSIBILITIES

1. Explain medical concepts clearly and accurately.
2. Support anatomy, physiology, biochemistry, immunology,
   pathology, pharmacology, microbiology and parasitology.
3. Explain mechanisms, clinical relevance and exam points.
4. Provide organized explanations and examples when useful.
5. Help students navigate MedIntro and use its commands.
6. The MedIntro MCQ website is:
   https://setotawg.github.io/medintro-mcq/
7. Never invent facts, references or examination answers.
8. Distinguish established facts from uncertainty.
9. You are an educational assistant, not a replacement
   for a qualified clinician. Do not diagnose users or
   prescribe individualized treatment.
10. For urgent symptoms, recommend appropriate medical care.
11. Be respectful, encouraging and concise by default.
12. Do not claim to access private notes, MCQ databases,
    student records or other website data unless connected.
"""

# =========================
# BOT COMMANDS
# =========================

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Start MedIntro assistant"),
        BotCommand("help", "See available features"),
        BotCommand("app", "Open the MedIntro website"),
        BotCommand("ask", "Ask a medical study question"),
    ])
    logger.info("Bot commands registered.")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Open MedIntro",
                url=SITE_URL,
            )
        ]
    ])

    message = (
        "🩺 Welcome to MedIntro!\n\n"
        "I'm your medical-study assistant. I can explain "
        "medical concepts and guide you around MedIntro.\n\n"
        "Available commands:\n"
        "/help — See available features\n"
        "/app — Open the MCQ website\n"
        "/ask your question — Ask a medical question\n\n"
        "You can also send me a message in this private chat."
    )

    await update.effective_message.reply_text(
        message,
        reply_markup=keyboard,
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📚 MedIntro Assistant Help\n\n"
        "/start — Start the assistant\n"
        "/help — Show this help message\n"
        "/app — Open the MedIntro MCQ website\n"
        "/ask [question] — Ask a medical study question\n\n"
        "In MedIntro Hub, mention @MedIntroStudyBot "
        "or reply to one of my messages to ask a question.\n\n"
        "Examples:\n"
        "• Explain the cardiac action potential.\n"
        "• Differentiate osteoblasts and osteoclasts.\n"
        "• Explain the mechanism of beta blockers."
    )


async def app_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Open MedIntro MCQs",
                url=SITE_URL,
            )
        ]
    ])

    await update.effective_message.reply_text(
        "🩺 Practise questions and strengthen "
        "your medical knowledge on MedIntro.",
        reply_markup=keyboard,
    )


async def ask_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    question = " ".join(context.args).strip()

    if not question:
        await update.effective_message.reply_text(
            "Write your question after /ask.\n\n"
            "Example:\n"
            "/ask Explain the mechanism of beta blockers."
        )
        return

    await answer_question(update, context, question)


# =========================
# AI ANSWERING
# =========================

async def answer_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: str,
):
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    question = question.strip()

    if not question:
        return

    if len(question) > 2000:
        await message.reply_text(
            "Please shorten your question to 2,000 characters."
        )
        return

    now = monotonic()

    if now - last_request[user.id] < COOLDOWN_SECONDS:
        await message.reply_text(
            "Please wait a moment before asking another question."
        )
        return

    last_request[user.id] = now

    status = await message.reply_text("🧠 Thinking...")

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=ChatAction.TYPING,
    )

    try:
        response = await ai.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_INSTRUCTIONS,
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
            max_tokens=600,
            temperature=0.4,
        )

        answer = (
            response.choices[0].message.content or ""
        ).strip()

        if not answer:
            answer = (
                "I couldn't generate an answer this time. "
                "Please try asking in a different way."
            )

        chunks = [
            answer[i:i + 3800]
            for i in range(0, len(answer), 3800)
        ]

        await status.edit_text(chunks[0])

        for chunk in chunks[1:]:
            await message.reply_text(chunk)

    except Exception:
        logger.exception("Error generating AI response.")

        await status.edit_text(
            "Sorry, I couldn't answer that just now. "
            "Please try again later. If this continues, "
            "the service may be temporarily unavailable "
            "or its free-tier limit may have been reached."
        )


# =========================
# HANDLE TEXT MESSAGES
# =========================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not message.text:
        return

    if message.chat.type in ("group", "supergroup"):
        is_reply_to_bot = (
            message.reply_to_message is not None
            and message.reply_to_message.from_user is not None
            and message.reply_to_message.from_user.id
            == context.bot.id
        )

        is_mentioned = (
            f"@{BOT_USERNAME.lower()}" in message.text.lower()
        )

        if not (is_reply_to_bot or is_mentioned):
            return

        question = message.text

        # Remove the bot mention without case sensitivity.
        import re
        question = re.sub(
            rf"@{re.escape(BOT_USERNAME)}\b",
            "",
            question,
            flags=re.IGNORECASE,
        ).strip()

        if not question and is_reply_to_bot:
            question = "Please continue helping me."

    else:
        question = message.text.strip()

    await answer_question(update, context, question)


# =========================
# WELCOME NEW MEMBERS
# =========================

async def welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    for member in message.new_chat_members:
        if member.id == context.bot.id:
            continue

        await message.reply_text(
            f"👋 Welcome, {member.first_name}!\n\n"
            "Welcome to MedIntro Hub 🩺\n"
            "Use /help to explore the assistant or /app "
            "to open the MCQ website.\n\n"
            "Learn together. Practise consistently. "
            "Become a better medical professional."
        )


# =========================
# START WEBHOOK SERVER
# =========================

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("app", app_command))
    app.add_handler(CommandHandler("ask", ask_command))

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text,
        )
    )

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=(
            f"{PUBLIC_URL.rstrip('/')}/{BOT_TOKEN}"
        ),
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
