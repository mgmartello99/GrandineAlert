import time
import requests
import asyncio

from db import get_all_users
from config import CHECK_INTERVAL


# 🌍 METEO
def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=precipitation_probability,cape,weather_code,freezing_level_height"
        "&forecast_days=1"
    )

    return requests.get(url, timeout=20).json()


# 🛰 RADAR LIVE
def get_radar_image():
    try:
        r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=20)
        data = r.json()

        path = data["radar"]["nowcast"][0]["path"]
        return f"https://tilecache.rainviewer.com{path}/512/0/0/0/0_0.png"

    except:
        return None


# 🧠 SCORE GRANDINE 0–100
def hail_score(cape, precip, weather_code, freezing):
    score = 0

    if precip > 70:
        score += 15
    if precip > 85:
        score += 10

    if cape > 800:
        score += 20
    if cape > 1500:
        score += 25

    if freezing < 3500:
        score += 10

    if weather_code in [95, 96, 99]:
        score += 30

    return min(score, 100)

def send_message_sync(bot, chat_id, text):
    asyncio.run(bot.send_message(chat_id=chat_id, text=text))


def send_photo_sync(bot, chat_id, photo):
    asyncio.run(bot.send_photo(chat_id=chat_id, photo=photo))


# 🔔 MONITOR LOOP
def run_monitor(bot):

    sent = set()

    while True:

        users = get_all_users()

        print(f"[MONITOR] utenti attivi: {len(users)}")

        for chat_id, city, lat, lon in users:

            try:
                data = get_weather(lat, lon)
                h = data["hourly"]

                cape = h["cape"][0] or 0
                precip = h["precipitation_probability"][0] or 0
                wc = h["weather_code"][0] or 0
                freezing = h["freezing_level_height"][0] or 9999

                score = hail_score(cape, precip, wc, freezing)

                print(f"[DEBUG] {city} -> score {score}")

                # 🔥 soglia realistica
                if score < 60:
                    continue

                key = f"{chat_id}_{city}_{score}"
                if key in sent:
                    continue

                level = "MEDIO"
                if score >= 70:
                    level = "ALTO"
                if score >= 85:
                    level = "CRITICO"

                radar = get_radar_image()

                msg = (
                    f"🌩 RISCHIO GRANDINE {level}\n\n"
                    f"📍 {city}\n"
                    f"🎯 Score: {score}/100\n\n"
                    f"🌧 Pioggia: {precip}%\n"
                    f"⚡ CAPE: {cape}\n"
                    f"❄️ Zero termico: {freezing} m"
                )

                send_message_sync(bot, chat_id, msg)

                if radar:
                    send_photo_sync(bot, chat_id, radar)

                sent.add(key)

            except Exception as e:
                print("monitor error:", e)

        time.sleep(CHECK_INTERVAL)