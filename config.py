import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non impostato. Controlla il file .env")