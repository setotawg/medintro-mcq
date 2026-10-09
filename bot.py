
import os
import logging
from collections import defaultdict
from time import monotonic

from openai import AsyncOpenAI
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
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

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
        "Set WEBHOOK_URL to your hosted service URL."
    )

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
ai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Basic per-user cooldown to reduce accidental spam.
last_request = defaultdict(float)
COOLDOWN_SECONDS = 3

SYSTEM_INSTRUCTIONS = """
You are MedIntroStudyBot, a friendly educational assistant
for medical students using the MedIntro learning platform.

Your responsibilities:
1. Explain medical concepts clearly and accurately.
2. Help students study anatomy, physiology, biochemistry,
   immunology, pathology, pharmacology, microbiology,
   parasitology and related medical subjects.
3. Use structured explanations with headings when useful.
4. Explain mechanisms, clinical relevance and important
   exam points when appropriate.
5. Help students use MedIntro, open the MCQ website and
   understand the bot's commands.
6. If asked where to practise MCQs, provide this URL:
   https://setotawg.github.io/medintro-mcq/
7. If you do not know an answer, say so instead of inventing
   facts. Never fabricate references or exam answers.
8. This is an educational assistant, not a replacement for
   a clinician. Do not diagnose students or prescribe
   individualized treatment. Encourage professional care
   for personal medical problems and urgent symptoms.
9. Be respectful, concise by default, and willing to explain
   difficult concepts in more depth when asked.
10. Do not claim to access private MedIntro content, student
    records or website databases unless actually connected.
"""

# =========================
# BOT COMMANDS
# =========================

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Start MedIntro assistant"),
        BotCommand("help", "See what I can do"),
        BotCommand("app", "Open the MedIntro website"),
        BotCommand("ask", "Ask a medical study question"),
    ])
    logger.info("Bot commands registered.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "I'm your study assistant. I can help explain "
        "medical concepts and guide you around MedIntro.\n\n"
        "Try these commands:\n"
        "/help — See all features\n"
        "/app — Open the MCQ website\n"
        "/ask your question — Ask a study question\n\n"
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
        "In a group, mention @MedIntroStudyBot or reply "
        "directly to one of my messages to ask a question.\n\n"
        "Examples:\n"
        "• Explain the cardiac action potential.\n"
        "• Differentiate osteoblasts and osteoclasts.\n"
        "• How do I open the MedIntro MCQ website?"
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
        "🩺 Open MedIntro to practise and strengthen "
        "your medical knowledge.",
        reply_markup=keyboard,
    )


async def ask_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    question = " ".join(context.args).strip()

    if not question:
        await update.effective_message.reply_text(
            "Send your question after the command.\n\n"
            "Example: /ask Explain the mechanism of action "
            "of beta blockers."
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
            "Please wait a moment before sending another question."
        )
        return

    last_request[user.id] = now

    status = await message.reply_text("🧠 Thinking...")
    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=ChatAction.TYPING,
    )

    try:
        response = await ai.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=SYSTEM_INSTRUCTIONS,
            input=question,
            max_output_tokens=600,
        )

        answer = response.output_text.strip()

        if not answer:
            answer = (
                "I couldn't generate an answer this time. "
                "Please try asking in a different way."
            )

        # Telegram messages have a length limit.
        chunks = [
            answer[i:i + 3800]
            for i in range(0, len(answer), 3800)
        ]

        await status.edit_text(chunks[0])

        for chunk in chunks[1:]:
            await message.reply_text(chunk)

    except Exception:
        logger.exception("Error generating assistant response.")
        await status.edit_text(
            "Sorry, I couldn't answer that just now. "
            "Please try again in a moment."
        )


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    if not message or not message.text:
        return

    # In groups, only answer when addressed directly.
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

        question = message.text.replace(
            f"@{BOT_USERNAME}", ""
        ).strip()

        if is_reply_to_bot and not question:
            question = message.text.strip()

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
            "Use /help to learn what our assistant can do, "
            "and /app to open the MCQ website.\n\n"
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
        webhook_url=f"{PUBLIC_URL.rstrip('/')}/{BOT_TOKEN}",
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
