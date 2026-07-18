import time
import requests
import asyncio
import math
from datetime import date, datetime, timedelta, timezone

from db import get_all_users
from config import CHECK_INTERVAL


# 🌍 METEO
def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation_probability,cape,weather_code,freezing_level_height",
        "forecast_days": 2,
        # "auto" allinea l'array orario al fuso orario del posto,
        # invece di restituirlo in UTC (altrimenti l'indice [0]
        # corrisponde a mezzanotte UTC, non a "ora")
        "timezone": "auto",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


from datetime import datetime, timezone, timedelta


def current_hour_index(data):
    """
    Trova l'indice dell'ora locale corrente nei dati hourly di Open-Meteo.
    """

    times = data["hourly"]["time"]

    offset = data.get("utc_offset_seconds", 0)

    local_now = (
        datetime.now(timezone.utc)
        + timedelta(seconds=offset)
    )

    target = local_now.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    parsed = [
        datetime.strptime(t, "%Y-%m-%dT%H:%M")
        for t in times
    ]

    # match esatto
    for i, t in enumerate(parsed):
        if t == target:
            return i

    # fallback: ultima ora disponibile precedente
    previous = [
        i for i, t in enumerate(parsed)
        if t <= target
    ]

    if previous:
        return previous[-1]

    return 0


# 🛰 RADAR LIVE
def _latlon_to_tile(lat, lon, zoom):
    """Converte coordinate lat/lon nel sistema di tile (slippy map),
    lo stesso usato da RainViewer/Google Maps/OSM."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def get_radar_image(lat, lon, zoom=7):
    """
    Restituisce l'URL del tile radar centrato sulla città dell'utente.
    Con zoom=0 (come nella versione precedente) esiste un solo tile al
    mondo: l'immagine mostrava l'intero pianeta, con la propria città
    invisibile su quella scala. zoom=7 inquadra circa 100-150 km,
    una scala utile per vedere un fronte di temporale in arrivo.
    """
    try:
        r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=20)
        r.raise_for_status()
        data = r.json()

        host = data.get("host", "https://tilecache.rainviewer.com")
        path = data["radar"]["nowcast"][0]["path"]
        x, y = _latlon_to_tile(lat, lon, zoom)
        return f"{host}{path}/512/{zoom}/{x}/{y}/0/0_0.png"

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


def _schedule(coro, loop, label):
    """
    Wrapper attorno a run_coroutine_threadsafe che NON lascia sparire gli
    errori nel nulla.

    run_coroutine_threadsafe ritorna una concurrent.futures.Future: se
    nessuno la legge (col vecchio codice non veniva mai letta), qualsiasi
    eccezione sollevata dentro la coroutine resta intrappolata nella
    Future e non viene mai stampata. E' esattamente quello che succedeva
    con send_photo: se Telegram rifiuta l'URL (timeout nello scaricarla,
    "wrong file identifier/HTTP URL specified", host non raggiungibile
    dai server Telegram, ecc.) l'errore non arrivava mai in console e la
    foto sembrava "non partire mai" senza nessun indizio del perche'.
    """
    future = asyncio.run_coroutine_threadsafe(coro, loop)

    def _log_if_failed(f):
        exc = f.exception()
        if exc:
            print(f"[MONITOR] invio fallito ({label}):", repr(exc))

    future.add_done_callback(_log_if_failed)
    return future


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

                # orario a cui si riferisce la previsione usata per lo score,
                # es. "2026-07-17T15:00" -> "15:00". Senza questo il messaggio
                # non specifica MAI a che ora e' previsto il rischio.
                orario = h["time"][idx].split("T")[1]

                score = hail_score(cape, precip, wc, freezing)
                print(
                    f"[DEBUG] {city} @ {orario} -> score {score} "
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

                radar = get_radar_image(lat, lon)

                msg = (
                    f"🌩 RISCHIO GRANDINE {level}\n\n"
                    f"📍 {city}\n"
                    f"🕒 Orario previsto: {orario}\n"
                    f"🎯 Score: {score}/100\n\n"
                    f"🌧 Pioggia: {precip}%\n"
                    f"⚡ CAPE: {cape}\n"
                    f"❄️ Zero termico: {freezing} m"
                )

                _schedule(
                    bot.send_message(chat_id=chat_id, text=msg), loop, "testo"
                )

                if radar:
                    _schedule(
                        bot.send_photo(chat_id=chat_id, photo=radar), loop, "radar"
                    )
                else:
                    print(f"[MONITOR] nessuna immagine radar disponibile per {city}")

                sent[key] = (level, today)

            except Exception as e:
                print("[MONITOR] errore:", e)

        time.sleep(CHECK_INTERVAL)