from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import threading

from config import BOT_TOKEN
from db import init_db, set_city, get_user
from monitor import run_monitor


# 🌍 GEOCODING
def geocode(city):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=it"
    r = requests.get(url, timeout=20).json()

    if "results" not in r:
        return None

    r = r["results"][0]

    return r["name"], r["latitude"], r["longitude"]


# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌩 Meteo Radar Bot\n\n"
        "/citta Milano\n"
        "/status"
    )


# 📍 SET CITY
async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    city = " ".join(context.args)

    if not city:
        await update.message.reply_text("Uso: /citta Milano")
        return

    geo = geocode(city)

    if not geo:
        await update.message.reply_text("Città non trovata")
        return

    name, lat, lon = geo

    set_city(chat_id, name, lat, lon)

    await update.message.reply_text(
        f"📍 Attivo su {name}\nLat {lat}, Lon {lon}"
    )


# 📊 STATUS
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = get_user(update.effective_chat.id)

    if not user:
        await update.message.reply_text("Nessuna città impostata")
        return

    await update.message.reply_text(f"📍 {user[0]}")


# ▶ MAIN
def main():

    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("citta", setcity))
    app.add_handler(CommandHandler("status", status))

    # monitor in background
    threading.Thread(
        target=run_monitor,
        args=(app.bot,),
        daemon=True
    ).start()

    app.run_polling()


if __name__ == "__main__":
    main()
    