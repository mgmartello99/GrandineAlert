# 🌩 GrandineAlert

Un bot Telegram che monitora automaticamente il rischio di grandine per una città scelta dall'utente, inviando notifiche quando le condizioni meteorologiche diventano favorevoli allo sviluppo di temporali grandinigeni.

Il progetto utilizza le API gratuite di **Open-Meteo** per le previsioni meteorologiche e **RainViewer** per mostrare l'immagine radar più recente.

---

## ✨ Funzionalità

* 📍 Impostazione della città tramite comando Telegram
* 🌍 Geocodifica automatica della località
* ⛈️ Calcolo di un indice di rischio grandine (0–100)
* 🔔 Invio automatico di notifiche quando il rischio supera una soglia
* 🛰️ Invio dell'ultima immagine radar disponibile
* 💾 Memorizzazione delle città associate agli utenti
* ⚙️ Intervallo di controllo configurabile

---

## Come funziona

Ogni utente seleziona una città tramite il comando:

```
/citta Milano
```

Il bot salva le coordinate geografiche della località e avvia un monitoraggio continuo.

Ogni `CHECK_INTERVAL` secondi vengono scaricati i dati meteorologici da Open-Meteo.

L'algoritmo valuta diversi parametri:

* probabilità di precipitazioni
* CAPE (energia convettiva)
* quota dello zero termico
* codici meteo relativi ai temporali

Da questi valori viene calcolato uno **score di rischio grandine** compreso tra 0 e 100.

Se il punteggio supera la soglia di allerta, il bot invia automaticamente:

* messaggio di avviso
* livello di rischio (Medio / Alto / Critico)
* immagine radar aggiornata

---

## Struttura del progetto

```
GrandineAlert/
│
├── bot.py             # Bot Telegram
├── monitor.py         # Monitor meteo e notifiche
├── config.py          # Configurazione
├── db.py              # Gestione database utenti
├── .env               # Variabili d'ambiente
├── requirements.txt
└── README.md
```

---

## Installazione

Clonare il repository:

```bash
git clone https://github.com/<username>/GrandineAlert.git

cd GrandineAlert
```

Installare le dipendenze:

```bash
pip install -r requirements.txt
```

---

## Configurazione

Creare un file `.env`:

```env
BOT_TOKEN=IL_TUO_TOKEN
CHECK_INTERVAL=300
```

dove:

* **BOT_TOKEN** è il token ottenuto da BotFather
* **CHECK_INTERVAL** è il tempo (in secondi) tra due controlli consecutivi

---

## Avvio

Eseguire:

```bash
python bot.py
```

Il bot inizierà a ricevere comandi Telegram e, in background, verrà avviato automaticamente il monitor delle condizioni meteorologiche.

---

## Comandi Telegram

| Comando               | Descrizione                            |
| --------------------- | -------------------------------------- |
| `/start`              | Avvia il bot                           |
| `/citta <nome città>` | Imposta la città da monitorare         |
| `/status`             | Mostra la città attualmente monitorata |

---

## Algoritmo di rischio grandine

Lo score viene calcolato combinando diversi indicatori atmosferici.

Tra i principali:

* probabilità di precipitazione
* CAPE
* altezza dello zero termico
* presenza di temporali

Il risultato è uno score da **0 a 100**.

Classificazione:

| Score  | Livello         |
| ------ | --------------- |
| 0–59   | Nessuna allerta |
| 60–69  | 🟡 Medio        |
| 70–84  | 🟠 Alto         |
| 85–100 | 🔴 Critico      |

---

## API utilizzate

### Open-Meteo

* Geocoding API
* Forecast API

Utilizzate per ottenere:

* coordinate della città
* probabilità di precipitazione
* CAPE
* quota dello zero termico
* weather code

---

### RainViewer

Utilizzata per recuperare l'ultima immagine radar disponibile.

---

## Possibili miglioramenti

* supporto a più città per utente
* notifiche differenziate per livello di rischio
* previsioni a 24–48 ore
* mappe radar geolocalizzate
* dashboard web
* Docker
* deploy su VPS o Raspberry Pi
* logging avanzato
* test automatici

---

## Tecnologie utilizzate

* Python 3
* python-telegram-bot
* Requests
* Open-Meteo API
* RainViewer API
* SQLite

---

## Licenza

Questo progetto è distribuito con licenza MIT.

---

## Autore

Sviluppato come progetto personale per il monitoraggio automatico del rischio di grandine tramite Telegram.
