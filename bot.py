from dotenv import load_dotenv
import os
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import secrets

load_dotenv()

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
    try:
        res = requests.get(
            f"{POCKETBASE_URL}/api/collections/users/records",
            params={"filter": f"telegram_id='{telegram_id}'"}
        ).json()

        if res.get('items'):
            return res['items'][0]

        random_password = secrets.token_urlsafe(8)
        payload = {
            "telegram_id": telegram_id,
            "name": name,
            "points": 0,
            "password": random_password,
            "passwordConfirm": random_password
        }

        res = requests.post(f"{POCKETBASE_URL}/api/collections/users/records", json=payload)
        if res.status_code in (200, 201):
            return res.json()
        else:
            print("Failed to create user:", res.text)
            return {"id": None, "points": 0}
    except Exception as e:
        print("Error registering user:", e)
        return {"id": None, "points": 0}

async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    amount = int(context.args[0]) if context.args else 10
    points = amount // 10

    user = register_user(user_id, name)
    current_points = user.get('points', 0)
    new_points = current_points + points

    if user.get("id"):
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
    current_points = user.get('points', 0)
    new_points = max(current_points - points, 0)

    if user.get("id"):
        requests.patch(f"{POCKETBASE_URL}/api/collections/users/records/{user['id']}", json={"points": new_points})

        txn = {"user_id": user['id'], "type": "withdraw", "amount": amount, "points": -points}
        requests.post(f"{POCKETBASE_URL}/api/collections/transactions/records", json=txn)

    await update.message.reply_text(f"❌ Withdrawn ${amount} (-{points} points)\nTotal Points: {new_points}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    res = requests.get(
        f"{POCKETBASE_URL}/api/collections/users/records",
        params={"filter": f"telegram_id='{user_id}'"}
    ).json()

    if not res.get('items'):
        await update.message.reply_text("❌ Ma jiro diiwaan kuu jira (You are not registered yet). Use /save to start saving!")
        return

    user = res['items'][0]
    points = user.get('points', 0)
    title = get_title(points)
    await update.message.reply_text(f"📊 Dhibcaha: {points}\n🏅 Heerka: {title}\n💵 Lacagta: ${points * 10}")

def get_title(points):
    if points >= 1000:
        return "Financial Champion"
    elif points >= 750:
        return "Guardian of the Vault"
    elif points >= 500:
        return "Financial Expert"
    elif points >= 250:
        return "Halfway Wealthy"
    elif points >= 100:
        return "Junior Saver"
    else:
        return "Keep Up"


def main():
    threading.Thread(target=start_health_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("save", save))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("status", status))
    app.run_polling()

if __name__ == "__main__":
    main()
