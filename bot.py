import logging
import os
import re
import sys
from urllib.parse import urlparse

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.env import load_local_env


load_local_env()

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


def get_optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def extract_instagram_urls(text: str) -> list[str]:
    if not text:
        return []
    return INSTAGRAM_URL_RE.findall(text)


def backend_base_url(api_url: str) -> str:
    parsed = urlparse(api_url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    telegram_user = update.effective_user
    args = context.args or []
    if not args:
        await message.reply_text(
            "This bot saves reels into your private library. First sign in on the website, tap Connect Telegram, then come back here and press Start from that link."
        )
        return

    link_code = args[0].strip()
    complete_url = context.application.bot_data["telegram_link_complete_url"]
    try:
        response = requests.post(
            complete_url,
            json={
                "code": link_code,
                "telegram_user_id": str(telegram_user.id),
                "telegram_username": telegram_user.username or "",
                "telegram_display_name": telegram_user.full_name or "",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = ""
        if getattr(exc, "response", None) is not None:
            try:
                detail = exc.response.json().get("detail", "")
            except Exception:
                detail = exc.response.text[:200]
        await message.reply_text(detail or "That link could not be completed. Go back to the website and tap Connect Telegram again.")
        return

    await message.reply_text(
        "Telegram connected. From now on, just send me any Instagram reel and it will go straight into your own library."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = message.text or message.caption or ""
    urls = extract_instagram_urls(text)

    if not urls:
        return

    api_url = context.application.bot_data["api_url"]
    telegram_user = update.effective_user
    ingest_secret = context.application.bot_data.get("ingest_secret", "")

    for url in urls:
        logging.info("Received URL: %s", url)
        try:
            response = requests.post(
                api_url,
                json={
                    "url": url,
                    "telegram_user_id": str(telegram_user.id),
                    "telegram_username": telegram_user.username or "",
                    "telegram_display_name": telegram_user.full_name or "",
                    "source": "telegram",
                },
                headers={"X-Ingest-Token": ingest_secret} if ingest_secret else None,
                timeout=20,
            )
            response.raise_for_status()
            logging.info("POST success: %s -> %s", url, response.status_code)
            await message.reply_text("Saved. I’m processing this reel for your library now.")
        except requests.RequestException as exc:
            logging.error("POST failed: %s -> %s", url, exc)
            detail = ""
            if getattr(exc, "response", None) is not None:
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:
                    detail = exc.response.text[:200]
            await message.reply_text(detail or "I couldn't save that reel right now. Please try again in a moment.")


def main() -> None:
    try:
        token = get_env("TELEGRAM_BOT_TOKEN")
        api_url = get_env("API_URL")
    except RuntimeError as exc:
        logging.error("%s", exc)
        sys.exit(1)

    application = Application.builder().token(token).build()
    application.bot_data["api_url"] = api_url
    application.bot_data["telegram_link_complete_url"] = f"{backend_base_url(api_url)}/auth/telegram-link/complete"
    application.bot_data["ingest_secret"] = get_optional_env("TELEGRAM_INGEST_SECRET", "")
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.ALL, handle_message))

    logging.info("Bot started (multi-user Telegram-link mode)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
