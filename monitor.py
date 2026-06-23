import time
import requests
import asyncio
from datetime import date, datetime

from db import get_all_users
from config import CHECK_INTERVAL


# 🌍 METEO
def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation_probability,cape,weather_code,freezing_level_height",
        "forecast_days": 1,
        # "auto" allinea l'array orario al fuso orario del posto,
        # invece di restituirlo in UTC (altrimenti l'indice [0]
        # corrisponde a mezzanotte UTC, non a "ora")
        "timezone": "auto",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def current_hour_index(data):
    """
    Trova nell'array orario l'indice corrispondente all'ora attuale
    (locale, grazie a timezone=auto). Senza questo, leggere sempre [0]
    significa leggere le condizioni di mezzanotte, non quelle di adesso:
    in pieno pomeriggio con lampi in corso lo score puo' uscire 0 perche'
    si stanno guardando dati di tutt'altro momento della giornata.
    """
    times = data["hourly"]["time"]  # es. "2026-06-22T14:00"
    now = datetime.now().strftime("%Y-%m-%dT%H:00")

    if now in times:
        return times.index(now)

    return 0  # fallback se per qualche motivo non si trova l'ora esatta


# 🛰 RADAR LIVE
def get_radar_image():
    try:
        r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=20)
        r.raise_for_status()
        data = r.json()

        path = data["radar"]["nowcast"][0]["path"]
        return f"https://tilecache.rainviewer.com{path}/512/0/0/0/0_0.png"

    except (requests.RequestException, KeyError, IndexError) as e:
        print("[RADAR] errore:", e)
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

    # weather_code WMO:
    # 95 = temporale (senza indicazione di grandine) -> segnale parziale
    # 96 = temporale con grandine debole -> il modello CONFERMA la grandine
    # 99 = temporale con grandine forte -> conferma piu' grave
    #
    # Approccio conservativo: se il modello conferma esplicitamente la
    # grandine (96/99), il punteggio viene forzato sopra la soglia di
    # invio (60) anche se CAPE/pioggia per quell'ora sono bassi.
    # Meglio un avviso in più che perdere una grandine confermata.
    if weather_code == 95:
        score += 20
        # anche senza grandine confermata dal modello, un temporale con
        # instabilita' atmosferica significativa (soglia CAPE piu' bassa
        # di quella usata sopra) basta a far scattare l'alert: meglio un
        # avviso in piu' che perdere un episodio di grandine che il
        # modello non ha classificato come 96/99
        if cape > 400:
            score = max(score, 65)  # supera comunque la soglia di invio
    elif weather_code == 96:
        score = max(score, 65)   # avvisa comunque, ma a livello MEDIO
                                  # ("grandine debole" non e' detto sia
                                  # un rischio serio per l'auto)
    elif weather_code == 99:
        score = max(score, 90)   # forza almeno livello CRITICO ("grandine forte")

    return min(score, 100)


def level_for_score(score):
    if score >= 85:
        return "CRITICO"
    if score >= 70:
        return "ALTO"
    return "MEDIO"


# 🔔 MONITOR LOOP
def run_monitor(bot, loop):
    """
    Gira in un thread separato dal loop asyncio principale.
    `loop` e' il loop di run_polling, passato da main.py: tutte le
    chiamate al bot vengono schedulate su quel loop con
    run_coroutine_threadsafe, MAI eseguite con asyncio.run()
    (che creerebbe un loop nuovo e scollegato dal client HTTP del bot).
    """

    sent = {}  # chiave "chat_id_city" -> (livello, giorno) dell'ultimo alert inviato

    while True:

        users = get_all_users()
        print(f"[MONITOR] utenti attivi: {len(users)}")

        for chat_id, city, lat, lon in users:

            try:
                data = get_weather(lat, lon)
                h = data["hourly"]
                idx = current_hour_index(data)

                cape = h["cape"][idx] or 0
                precip = h["precipitation_probability"][idx] or 0
                wc = h["weather_code"][idx] or 0
                freezing = h["freezing_level_height"][idx] or 9999

                score = hail_score(cape, precip, wc, freezing)
                print(
                    f"[DEBUG] {city} -> score {score} "
                    f"(precip={precip}%, cape={cape}, weather_code={wc}, "
                    f"freezing={freezing}m, idx={idx})"
                )

                # soglia realistica
                if score < 60:
                    continue

                level = level_for_score(score)
                today = date.today()
                key = f"{chat_id}_{city}"

                # evita di rimandare lo stesso livello di alert nello stesso giorno
                # (lo score puo' oscillare di pochi punti tra un check e l'altro)
                if sent.get(key) == (level, today):
                    continue

                radar = get_radar_image()

                msg = (
                    f"🌩 RISCHIO GRANDINE {level}\n\n"
                    f"📍 {city}\n"
                    f"🎯 Score: {score}/100\n\n"
                    f"🌧 Pioggia: {precip}%\n"
                    f"⚡ CAPE: {cape}\n"
                    f"❄️ Zero termico: {freezing} m"
                )

                asyncio.run_coroutine_threadsafe(
                    bot.send_message(chat_id=chat_id, text=msg), loop
                )

                if radar:
                    asyncio.run_coroutine_threadsafe(
                        bot.send_photo(chat_id=chat_id, photo=radar), loop
                    )

                sent[key] = (level, today)

            except Exception as e:
                print("[MONITOR] errore:", e)

        time.sleep(CHECK_INTERVAL)