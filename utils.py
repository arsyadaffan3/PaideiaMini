import os
import random
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# --- Configurations ----------------------------------------------------------
load_dotenv()
SCOPES       = ['https://www.googleapis.com/auth/calendar.readonly']

# --- Cloud LLM configuration ------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL        = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
groq_client  = Groq(api_key=GROQ_API_KEY)

# -- AI Instructions (Cloud) ----------------------------------------
def ask_groq(user_message):
    try:
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are Paideia, Affan's cloud AI assistant."
                " You are independent, sharp, and dystopian in personality- filled with dark truths"
                " Be concise and direct."},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: {str(e)}"

    
# -- Google Calender Service ---------------------------------------------------
def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def get_today_schedule():
    try:
        service = get_calendar_service()
        now     = datetime.utcnow()
        start   = now.replace(hour=0,  minute=0,  second=0).isoformat() + 'Z'
        end     = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

        events = service.events().list(
            calendarId='primary',
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])

        if not events:
            return "📅 No events today."

        msg = "📅 Today's Schedule:\n"
        for e in events:
            start_time = e['start'].get('dateTime', e['start'].get('date'))
            time_str   = datetime.fromisoformat(start_time).strftime('%I:%M %p') if 'T' in start_time else "All day"
            msg       += f"⏰ {time_str} — {e['summary']}\n"
        return msg

    except Exception as e:
        return f"❌ Calendar error: {e}"

# -- Weather API ----------------------------------------------------------
WEATHER_CODES = {
    0:              "☀️ Clear",
    (1, 2, 3):      "⛅ Partly Cloudy",
    (61,63,65,
     80,81,82):     "🌧️ Rainy",
    (71, 73, 75):   "❄️ Snowy",
    (51, 53, 55):   "🌦️ Drizzle",
    (95, 96, 99):   "⛈️ Thunderstorm",
}

def get_weather_condition(code):
    for key, label in WEATHER_CODES.items():
        if key == code or (isinstance(key, tuple) and code in key):
            return label
    return "🌤️ Cloudy"

def get_weather():
    try:
        params = {
            'latitude': 1.3521, 'longitude': 103.8198,
            'current': 'temperature_2m,weathercode,windspeed_10m',
            'daily':   'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
            'timezone': 'Asia/Singapore', 'forecast_days': 1
        }
        data    = requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()
        current = data['current']
        daily   = data['daily']

        return (
            f"🌤️ Weather — Singapore\n\n"
            f"{get_weather_condition(current['weathercode'])}\n"
            f"🌡️ Now: {current['temperature_2m']}°C "
            f"(High {daily['temperature_2m_max'][0]}° / Low {daily['temperature_2m_min'][0]}°)\n"
            f"💧 Rain chance: {daily['precipitation_probability_max'][0]}%\n"
            f"💨 Wind: {current['windspeed_10m']} km/h"
        )
    except Exception as e:
        return f"❌ Weather error: {str(e)}"

# -- Prayer Times API -----------------------------------------------------------------
def get_prayer_times():
    try:
        params = {'city': 'Singapore', 'country': 'Singapore', 'method': 3}
        data   = requests.get("http://api.aladhan.com/v1/timingsByCity", params=params).json()
        t      = data['data']['timings']
        return (
            f"Prayer Times:\n"
            f"Fajr: {t['Fajr']} |  Dhuhr: {t['Dhuhr']} | "
            f"Asr: {t['Asr']} | Maghrib: {t['Maghrib']} | Isha: {t['Isha']}"
        )
    except Exception as e:
        return f"❌ Prayer times error: {str(e)}"

# -- 8 Ball (Random function) ---------------------------------------------------------
EIGHT_BALL_RESPONSES = [
    "It is certain.", "Without a doubt.", "Yes, definitely!",
    "You may rely on it.", "As I see it, yes.", "Most likely.",
    "Outlook good.", "Signs point to yes.", "Reply hazy, try again.",
    "Ask again later.", "Better not tell you now.", "Cannot predict now.",
    "Concentrate and ask again.", "Don't count on it.", "My reply is no.",
    "My sources say no.", "Outlook not so good.", "Very doubtful.",
    "Absolutely not.", "The stars say no."
]

def get_eight_ball():
    return f"🎱 {random.choice(EIGHT_BALL_RESPONSES)}"

# -- Get IP Info --------------------------------------------------------------------
