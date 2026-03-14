#!/usr/bin/env python
"""Popcorn Telegram Bot — run with: python bot/run_bot.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ssl
import httpx
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest
from config import TELEGRAM_BOT_TOKEN
from bot.telegram_notifier import (
    start_command, recommendations_command, help_command,
    add_command, search_command, upcoming_command, similar_command, mystats_command,
    handle_callback, error_handler
)


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    print(f"Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"telegram lib version: {telegram.__version__}")

    # Corporate proxy uses self-signed cert — disable SSL verification
    no_ssl = {"verify": False}
    request = HTTPXRequest(connection_pool_size=8, http_version="1.1", httpx_kwargs=no_ssl)
    get_updates_request = HTTPXRequest(connection_pool_size=8, http_version="1.1", httpx_kwargs=no_ssl)
    app = (Application.builder()
           .token(TELEGRAM_BOT_TOKEN)
           .request(request)
           .get_updates_request(get_updates_request)
           .build())

    print("Registering handlers...")
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("recommendations", recommendations_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("upcoming", upcoming_command))
    app.add_handler(CommandHandler("similar", similar_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    print("[Popcorn] Bot starting... (long-polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
