from dotenv import load_dotenv
import os
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import secrets
from telegram import BotCommand

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


async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("save", "Save money (e.g., /save 50)"),
        BotCommand("withdraw", "Withdraw money (e.g., /withdraw 20)"),
        BotCommand("status", "Check your points and title"),
        BotCommand("clear", "Clear all transactions and reset"),
        BotCommand("help", "Show command guide"),
    ]
    await application.bot.set_my_commands(commands)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Money Saving Game Bot!\n\n"
        "Here’s how to get started:\n"
        "💰 /save 50 — Save $50 (and earn points)\n"
        "❌ /withdraw 30 — Withdraw $30 (lose points)\n"
        "📊 /status — Check your current points and rank\n"
        "🧹 /clear — Clear all your transactions and reset points\n\n"
        "Start saving and climb the financial ladder! 💸🔥"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Get the user record
    res = requests.get(
        f"{POCKETBASE_URL}/api/collections/users/records",
        params={"filter": f"telegram_id='{user_id}'"}
    ).json()
    
    if not res['items']:
        await update.message.reply_text("❌ You are not registered yet. Use /save to start saving!")
        return
    
    user = res['items'][0]
    user_record_id = user['id']
    
    # Delete all transactions for this user
    txns_res = requests.get(
        f"{POCKETBASE_URL}/api/collections/transactions/records",
        params={"filter": f"user_id='{user_record_id}'"}
    ).json()
    
    for txn in txns_res.get('items', []):
        requests.delete(f"{POCKETBASE_URL}/api/collections/transactions/records/{txn['id']}")
    
    # Reset user points to 0
    requests.patch(
        f"{POCKETBASE_URL}/api/collections/users/records/{user_record_id}",
        json={"points": 0}
    )
    
    await update.message.reply_text("🧹 All transactions cleared and your points have been reset to 0.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Available Commands:\n"
        "/save [amount] — Save money\n"
        "/withdraw [amount] — Withdraw money\n"
        "/status — Check your savings progress\n"
        "/clear — Reset your account\n"
        "/start — Get started guide\n"
    )

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("save", "Save money"),
        BotCommand("withdraw", "Withdraw money"),
        BotCommand("status", "Check your status"),
        BotCommand("clear", "Clear all data"),
        BotCommand("help", "Show help menu"),
    ])

def main():
    threading.Thread(target=start_health_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("save", save))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()

if __name__ == "__main__":
    main()
