
import logging
import os
import re

from groq import AsyncGroq
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

WEBSITE_URL = "https://setotawg.github.io/medintro-mcq/"

PUBLIC_URL = (
    os.getenv("WEBHOOK_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or ""
).rstrip("/")

PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# =========================================================
# LOGGING AND AI CLIENT
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ai = AsyncGroq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are MedIntro AI, an educational assistant for medical students.

Your purpose is to help students understand medicine clearly and accurately.

Focus on:
- Anatomy
- Physiology
- Biochemistry
- Immunology
- Pathology
- Pharmacology
- Microbiology
- Parasitology
- Clinical medicine
- OSPE preparation
- MCQs and exam revision

Teaching style:
1. Start with a direct answer.
2. Explain the underlying mechanism.
3. Organize information with clear headings and bullet points.
4. Connect basic science with clinical relevance when useful.
5. Highlight high-yield examination points.
6. Explain unfamiliar medical terminology.
7. For MCQs, explain why the correct option is correct.
8. Never invent references, lecture content, or facts.
9. If uncertain, clearly acknowledge the uncertainty.
10. Keep answers useful and appropriately detailed.

You are an educational assistant, not a replacement for a
qualified clinician. Do not claim to diagnose a person.

You do not automatically have access to the private contents
of the MedIntro website, its notes, or its question database.
Never claim that you have accessed those materials unless
their contents have actually been provided in the conversation.
"""

# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Open MedIntro",
                url=WEBSITE_URL,
            )
        ],
        [
            InlineKeyboardButton(
                "📚 Study Support",
                callback_data="study_support",
            )
        ],
    ])


# =========================================================
# STARTUP
# =========================================================

async def post_init(application: Application):
    bot_info = await application.bot.get_me()

    application.bot_data["bot_id"] = bot_info.id
    application.bot_data["bot_username"] = (
        bot_info.username or ""
    ).lower()

    logger.info(
        "MedIntro bot initialized as @%s",
        bot_info.username,
    )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    user = update.effective_user
    first_name = user.first_name if user else "Student"

    text = (
        f"👋 Welcome, {first_name}!\n\n"
        "🩺 Welcome to MedIntro!\n\n"
        "Your medical learning companion for:\n"
        "📚 Medical study resources\n"
        "🧠 AI-powered explanations\n"
        "📝 MCQ practice and exam preparation\n"
        "🔬 Basic science and clinical concepts\n\n"
        "Use the button below to open MedIntro, "
        "or ask me a medical study question here.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/app - Open MedIntro\n"
        "/ask - Ask a medical question\n"
        "/help - See how to use the bot"
    )

    await message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# /APP
# =========================================================

async def open_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        "🚀 Open MedIntro and continue your medical studies.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    text = (
        "📖 MEDINTRO BOT GUIDE\n\n"
        "1. In private chat, send me a medical question "
        "to receive an AI explanation.\n\n"
        "2. Use /ask followed by your question.\n"
        "Example:\n"
        "/ask Explain the cardiac action potential.\n\n"
        "3. In a group, mention @MedIntroStudyBot or "
        "reply directly to one of my messages to ask "
        "a question.\n\n"
        "4. Use /app to open the MedIntro website.\n\n"
        "I can help with medical concepts, MCQs, "
        "OSPE revision, and clinical reasoning."
    )

    await message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# GROQ AI RESPONSE
# =========================================================

async def generate_answer(question: str) -> str:
    response = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        max_tokens=900,
        temperature=0.4,
    )

    answer = response.choices[0].message.content

    if not answer:
        return (
            "I couldn't generate an answer this time. "
            "Please try asking your question again."
        )

    return answer.strip()


async def answer_question(
    update: Update,
    question: str,
):
    message = update.effective_message

    if not message:
        return

    question = question.strip()

    if not question:
        await message.reply_text(
            "Please send a question about a medical topic."
        )
        return

    if len(question) > 12000:
        await message.reply_text(
            "Your question is too long. Please shorten it "
            "and send it again."
        )
        return

    try:
        answer = await generate_answer(question)

        # Telegram limits a text message to 4096 characters.
        # Split long answers into safe-sized messages.
        chunks = [
            answer[i:i + 4000]
            for i in range(0, len(answer), 4000)
        ]

        for chunk in chunks:
            await message.reply_text(chunk)

    except Exception:
        logger.exception("AI response failed")

        await message.reply_text(
            "⚠️ I couldn't generate an answer right now.\n\n"
            "Please try again shortly. The service may be "
            "busy or temporarily unavailable."
        )


# =========================================================
# /ASK
# =========================================================

async def ask_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    question = " ".join(context.args).strip()

    if not question:
        message = update.effective_message

        if message:
            await message.reply_text(
                "Send your question after /ask.\n\n"
                "Example:\n"
                "/ask Explain the mechanism of beta blockers."
            )
        return

    await answer_question(update, question)


# =========================================================
# PRIVATE CHAT AND GROUP MESSAGES
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not message.text:
        return

    chat = update.effective_chat

    if not chat:
        return

    # In private chat, answer ordinary text messages.
    if chat.type == ChatType.PRIVATE:
        await answer_question(update, message.text)
        return

    # In groups, answer only when mentioned or replied to.
    bot_username = context.application.bot_data.get(
        "bot_username", ""
    )

    bot_id = context.application.bot_data.get("bot_id")

    is_mentioned = False

    if bot_username:
        mention_pattern = (
            r"(?<!\w)@"
            + re.escape(bot_username)
            + r"(?!\w)"
        )

        is_mentioned = bool(
            re.search(
                mention_pattern,
                message.text,
                flags=re.IGNORECASE,
            )
        )

    replied_message = message.reply_to_message

    is_reply_to_bot = (
        replied_message is not None
        and replied_message.from_user is not None
        and replied_message.from_user.is_bot
        and (
            replied_message.from_user.id == bot_id
            if bot_id is not None
            else False
        )
    )

    if not is_mentioned and not is_reply_to_bot:
        return

    question = message.text

    if bot_username:
        question = re.sub(
            r"(?<!\w)@"
            + re.escape(bot_username)
            + r"(?!\w)",
            "",
            question,
            flags=re.IGNORECASE,
        ).strip()

    if not question and is_reply_to_bot:
        question = (
            "Please continue helping me with this topic."
        )

    await answer_question(update, question)


# =========================================================
# WELCOME NEW GROUP MEMBERS
# =========================================================

async def welcome_new_members(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message or not message.new_chat_members:
        return

    bot_id = context.application.bot_data.get("bot_id")

    for member in message.new_chat_members:
        # Do not welcome the bot itself.
        if member.id == bot_id:
            continue

        welcome_text = (
            f"👋 Welcome, {member.first_name}!\n\n"
            "🩺 Welcome to Medintro Hub!\n"
            "Learn, discuss, and prepare for medical exams "
            "with fellow students.\n\n"
            "🚀 Open MedIntro to study:"
        )

        await message.reply_text(
            welcome_text,
            reply_markup=main_keyboard(),
        )


# =========================================================
# BUTTON CALLBACKS
# =========================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    if query.data == "study_support":
        await query.message.reply_text(
            "📚 You can ask me about anatomy, physiology, "
            "biochemistry, immunology, pathology, "
            "pharmacology, microbiology, parasitology, "
            "MCQs, and OSPE preparation.\n\n"
            "Example:\n"
            "/ask Explain the differences between "
            "innate and adaptive immunity."
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "An unhandled Telegram bot error occurred",
        exc_info=context.error,
    )


# =========================================================
# MAIN APPLICATION
# =========================================================

def main():
    if not PUBLIC_URL:
        raise RuntimeError(
            "Missing public URL. Set WEBHOOK_URL or ensure "
            "Render provides RENDER_EXTERNAL_URL."
        )

    if not BOT_TOKEN or not GROQ_API_KEY:
        raise RuntimeError(
            "BOT_TOKEN and GROQ_API_KEY must be configured."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", open_app))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ask", ask_command))

    # Button callbacks
    from telegram.ext import CallbackQueryHandler

    application.add_handler(
        CallbackQueryHandler(button_callback)
    )

    # New group members
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_members,
        )
    )

    # Private messages and group mentions/replies
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(error_handler)

    # Use the bot token as the webhook path.
    webhook_path = BOT_TOKEN

    webhook_url = f"{PUBLIC_URL}/{webhook_path}"

    logger.info("Starting MedIntro bot webhook service")
    logger.info("Website: %s", WEBSITE_URL)
    logger.info("AI model: %s", MODEL)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
