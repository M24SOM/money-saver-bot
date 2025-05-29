import os
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
POCKETBASE_URL = os.getenv("POCKETBASE_URL")

# --- Health Check Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(("0.0.0.0", 8000), HealthCheckHandler)
    server.serve_forever()

# --- Bot Logic ---
def register_user(telegram_id, name):
    res = requests.get(
        f"{POCKETBASE_URL}/api/collections/users/records",
        params={"filter": f"telegram_id='{telegram_id}'"}
    ).json()
    if res['items']:
        return res['items'][0]
    payload = {"telegram_id": telegram_id, "name": name, "points": 0}
    return requests.post(f"{POCKETBASE_URL}/api/collections/users/records", json=payload).json()

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    amount = int(context.args[0]) if context.args else 10
    points = amount // 10
    user = register_user(user_id, name)

    new_points = user['points'] + points
    requests.patch(f"{POCKETBASE_URL}/api/collections/users/records/{user['id']}", json={"points": new_points})

    txn = {"user_id": user['id'], "type": "save", "amount": amount, "points": points}
    requests.post(f"{POCKETBASE_URL}/api/collections/transactions/records", json=txn)

    await update.message.reply_text(f"💰 Saved ${amount} (+{points} points)\nTotal Points: {new_points}")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    amount = int(context.args[0]) if context.args else 10
    points = amount // 10
    user = register_user(user_id, name)

    new_points = max(user['points'] - points, 0)
    requests.patch(f"{POCKETBASE_URL}/api/collections/users/records/{user['id']}", json={"points": new_points})

    txn = {"user_id": user['id'], "type": "withdraw", "amount": amount, "points": -points}
    requests.post(f"{POCKETBASE_URL}/api/collections/transactions/records", json=txn)

    await update.message.reply_text(f"❌ Withdrawn ${amount} (-{points} points)\nTotal Points: {new_points}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = requests.get(
        f"{POCKETBASE_URL}/api/collections/users/records",
        params={"filter": f"telegram_id='{user_id}'"}
    ).json()['items'][0]
    points = user['points']
    title = get_title(points)
    await update.message.reply_text(f"📊 Dhibcaha: {points}\n🏅 Heerka: {title}\n💵 Lacagta: ${points * 10}")

def get_title(points):
    if points >= 100:
        return "Guuleystaha Dhaqaale"
    elif points >= 75:
        return "Ilaaliyaha Qasnadda"
    elif points >= 50:
        return "Xeeldheere Maaliyadeed"
    elif points >= 25:
        return "Kala-Bar Hantile"
    elif points >= 10:
        return "Badbaadiye Yar"
    else:
        return "Eber"

def main():
    # Start health check server in background
    threading.Thread(target=start_health_server, daemon=True).start()

    # Start the Telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("save", save))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()

if __name__ == "__main__":
    main()
