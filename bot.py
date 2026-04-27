import logging
import os
import re
import sys

import requests
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters


INSTAGRAM_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|p)/[A-Za-z0-9_-]+/?(?:\?[^\s]+)?",
    re.IGNORECASE,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def get_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def extract_instagram_urls(text: str) -> list[str]:
    if not text:
        return []
    return INSTAGRAM_URL_RE.findall(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = message.text or message.caption or ""
    urls = extract_instagram_urls(text)

    if not urls:
        return

    api_url = context.application.bot_data["api_url"]

    for url in urls:
        logging.info("Received URL: %s", url)
        try:
            response = requests.post(
                api_url,
                json={
                    "url": url,
                    "user_id": str(update.effective_user.id) if update.effective_user else "default",
                    "source": "telegram",
                },
                timeout=20,
            )
            response.raise_for_status()
            logging.info("POST success: %s -> %s", url, response.status_code)
        except requests.RequestException as exc:
            logging.error("POST failed: %s -> %s", url, exc)


def main() -> None:
    try:
        token = get_env("TELEGRAM_BOT_TOKEN")
        api_url = get_env("API_URL")
    except RuntimeError as exc:
        logging.error("%s", exc)
        sys.exit(1)

    application = Application.builder().token(token).build()
    application.bot_data["api_url"] = api_url
    application.add_handler(MessageHandler(filters.ALL, handle_message))

    logging.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
