"""
Telegram Joke Bot — использует Groq (бесплатный AI)
Зависимости:
    pip install python-telegram-bot groq

Настройка:
    1. Создай бота у @BotFather → получи TELEGRAM_TOKEN
    2. Зарегистрируйся на https://console.groq.com → получи GROQ_API_KEY (бесплатно)
    3. Вставь оба ключа ниже или задай через переменные окружения
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from groq import Groq

# ─── КОНФИГУРАЦИЯ ────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8724306925:AAGFiCdxUg2Dv_APKTT72uxPyQlTRBIHTE8")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY",   "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")

groq_client = Groq(api_key=GROQ_API_KEY)

# ─── СОСТОЯНИЯ РАЗГОВОРА ─────────────────────────────────────────────────────
WAITING_TOPIC = 1

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── ХРАНИЛИЩЕ ID СООБЩЕНИЙ ДЛЯ ОЧИСТКИ ─────────────────────────────────────
# { chat_id: [msg_id, msg_id, ...] }
chat_messages: dict[int, list[int]] = {}


def track_message(chat_id: int, message_id: int) -> None:
    """Запоминаем ID сообщения для последующей очистки."""
    chat_messages.setdefault(chat_id, []).append(message_id)


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def generate_joke(topic: str) -> str:
    """Генерирует жёсткий анекдот через Groq (llama-3.1-8b-instant — бесплатно)."""
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты дерзкий стендап-комик с чёрным юмором. "
                    "Твои анекдоты жёсткие, саркастичные, с острым чёрным юмором — без цензуры и без соплей. "
                    "Шути про смерть, тупость людей, жизненные провалы, бедность и прочую суровую реальность. "
                    "Анекдот должен быть коротким (3-6 предложений), с убойным панчлайном в конце. "
                    "Никаких предисловий — сразу анекдот. Пиши только на русском языке."
                ),
            },
            {
                "role": "user",
                "content": f"Расскажи жёсткий анекдот про {topic}.",
            },
        ],
        temperature=1.0,
        max_tokens=350,
    )
    return response.choices[0].message.content.strip()


def main_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😈 Сгенерировать анекдот", callback_data="generate")],
        [InlineKeyboardButton("🗑 Очистить чат",          callback_data="clear")],
    ])


# ─── ОБРАБОТЧИКИ ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start."""
    sent = await update.message.reply_text(
        "😈 Добро пожаловать в бот жёстких анекдотов!\n"
        "Нажми кнопку — получи анекдот. Нежных не держим.",
        reply_markup=main_keyboard(),
    )
    track_message(update.effective_chat.id, update.message.message_id)
    track_message(update.effective_chat.id, sent.message_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка нажатий кнопок."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    if query.data == "clear":
        # ── Очистка чата ──────────────────────────────────────────────────────
        ids_to_delete = chat_messages.pop(chat_id, [])
        deleted = 0
        for msg_id in ids_to_delete:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted += 1
            except Exception:
                pass  # сообщение уже удалено или слишком старое (>48ч)

        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=f"🗑 Удалено сообщений: {deleted}\nЧат очищен — начинаем заново!",
            reply_markup=main_keyboard(),
        )
        track_message(chat_id, sent.message_id)
        return ConversationHandler.END

    # ── Запрос темы для анекдота ──────────────────────────────────────────────
    sent = await query.message.reply_text(
        "💀 Про что анекдот?\n"
        "Пиши тему: *начальник*, *понедельник*, *диета*, *кот*…",
        parse_mode="Markdown",
    )
    track_message(chat_id, sent.message_id)
    return WAITING_TOPIC


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем тему и отправляем жёсткий анекдот."""
    chat_id = update.effective_chat.id
    topic = update.message.text.strip()

    track_message(chat_id, update.message.message_id)

    if not topic:
        sent = await update.message.reply_text("Напиши тему нормально 🙄")
        track_message(chat_id, sent.message_id)
        return WAITING_TOPIC

    wait_msg = await update.message.reply_text("⚡ Готовлю что-то жёсткое…")
    track_message(chat_id, wait_msg.message_id)

    try:
        joke = generate_joke(topic)
        sent = await update.message.reply_text(
            f"😂 *Анекдот про {topic}:*\n\n{joke}",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        track_message(chat_id, sent.message_id)
    except Exception as e:
        logger.error("Groq error: %s", e)
        sent = await update.message.reply_text(
            "💀 Groq сдох. Попробуй ещё раз.",
            reply_markup=main_keyboard(),
        )
        track_message(chat_id, sent.message_id)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sent = await update.message.reply_text("Окей, в другой раз.", reply_markup=main_keyboard())
    track_message(update.effective_chat.id, update.message.message_id)
    track_message(update.effective_chat.id, sent.message_id)
    return ConversationHandler.END


# ─── ТОЧКА ВХОДА ─────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(generate|clear)$")],
        states={
            WAITING_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topic)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    logger.info("Бот запущен…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()