import os
import logging
import pip
from datetime import datetime
from dotenv import load_dotenv
import psutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils import get_weather, get_prayer_times, get_today_schedule, get_eight_ball, ask_groq, get_ip

# ── Config ──────────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
YOUR_CHAT_ID    = os.getenv("CHAT_ID")
ALLOWED_USER_ID = int(os.getenv("CHAT_ID"))

logging.basicConfig(level=logging.INFO)

# ── Auth Guard ──────────────────────────────────────────────────────────────
def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# ── Scheduled Briefing ──────────────────────────────────────────────────────
async def send_morning_briefing(app):
    try:
        await app.bot.send_message(chat_id=YOUR_CHAT_ID, text=(
            f"🌅 Morning, Affan.\n"
            f"📆 {datetime.now().strftime('%A, %d %B %Y')}\n\n"
            f"{get_prayer_times()}\n\n"
            f"{get_today_schedule()}\n\n"
        ))
    except Exception as e:
        logging.error(f"Briefing error: {e}")

# ── Commands ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(
        "Paideia online. Welcome, Affan. 🤖\n\n"
        "/start — Start bot\n"
        "/stats — PN41 system stats\n"
        "/today — Today's schedule\n"
        "/prayer — Prayer times\n"
        "/weather — Current weather\n"
	"/8ball — Ask a question\n"
        "/shutdown — Shut down PN41\n\n"
        "Type anything to chat."
    )

# -- HANDLERS ---------------------------------------------------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    cpu = psutil.cpu_percent(interval=1)
    ram    = psutil.virtual_memory()
    disk   = psutil.disk_usage('/')
    net    = psutil.net_io_counters()
    uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins = rem // 60
    top = sorted(
    	[p for p in psutil.process_iter(['name', 'cpu_percent'])
     	if p.info['name'] != 'System Idle Process'],
    	key=lambda p: p.info['cpu_percent'], reverse=True
    )[:3]
    top_str = "\n".join([f"  {p.info['name']}" for p in top])
    await update.message.reply_text(
        f"🖥️ PN41 Stats\n\n"
        f" Uptime: {hours}h {mins}m\n\n"
        f" CPU:  {cpu}%\n"
        f" RAM:  {ram.used // (1024**3):.1f} / {ram.total // (1024**3):.1f} GB ({ram.percent}%)\n"
        f" Disk: {disk.used // (1024**3):.1f} / {disk.total // (1024**3):.1f} GB ({disk.percent}%)\n"
        f" Net:  ↑ {net.bytes_sent // (1024**2)} MB  ↓ {net.bytes_recv // (1024**2)} MB\n\n"
        f"📊 Top Processes:\n{top_str}"
    )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(get_today_schedule())

async def prayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(get_prayer_times())

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text(get_weather())

async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text(
            "Ask a question.\nExample: `/8ball will today be good?`",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"❓ {question}\n\n{get_eight_ball()}")

async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text("PN41 is shutting down. Goodbye.")
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

# ── AI Chat Cloud ─────────────────────────────────────────────────────────────────
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    await update.message.reply_text("Fetching data...")
    reply = ask_groq(update.message.text)
    if   "429"   in reply: await update.message.reply_text("⚠️ AI quota reached.")
    elif "401"   in reply: await update.message.reply_text("⚠️ Invalid API key.")
    elif "ERROR" in reply: await update.message.reply_text("❌ AI error.")
    else:                  await update.message.reply_text(reply)


# ── App Entry ────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    scheduler = AsyncIOScheduler(timezone="Asia/Singapore")

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("stats",    stats))
    app.add_handler(CommandHandler("today",    today))
    app.add_handler(CommandHandler("prayer",   prayer))
    app.add_handler(CommandHandler("weather",  weather))
    app.add_handler(CommandHandler("8ball",    eight_ball))
    app.add_handler(CommandHandler("shutdown", shutdown))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    async def on_startup(app):
        scheduler.start()
        scheduler.add_job(send_morning_briefing, 'cron', hour=7, minute=0, args=[app])
        scheduler.add_job(monitor_system, 'interval', minutes=5, args=[app])
        logging.info("Scheduler started")

    app.post_init = on_startup

    print("Paideia is running.")
    app.run_polling()


# -- System alert monitor ---------------------------------------------------------------------

async def monitor_system(app):
    cpu  = psutil.cpu_percent(interval=2)
    ram  = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    alerts = []
    if cpu  > 85: alerts.append(f"🔥 CPU high: {cpu}%")
    if ram  > 90: alerts.append(f"🧠 RAM high: {ram}%")
    if disk > 85: alerts.append(f"💾 Disk high: {disk}%")
    if alerts:
        await app.bot.send_message(chat_id=YOUR_CHAT_ID,
            text="⚠️ PN41 Alert\n\n" + "\n".join(alerts))

if __name__ == "__main__":
    main()