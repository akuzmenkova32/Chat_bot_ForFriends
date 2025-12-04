import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "change-me")
TZ = os.getenv("TZ", "Europe/Berlin")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
