import os
import json
import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # your telegram user id
DATA_FILE = "users.json"

BONUS_MIN = 10
BONUS_MAX = 100
COOLDOWN_HOURS = 24
REFERRAL_BONUS = 25  # bonus for referrer
WELCOME_BONUS = 50   # bonus for new user

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- STORAGE ----------
def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(users, user_id):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "balance": 0,
            "last_claim": None,
            "referrals": 0,
            "referred_by": None,
            "joined": datetime.utcnow().isoformat(),
        }
    return users[uid]

# ---------- HELPERS ----------
def main_menu():
    kb = [
        [InlineKeyboardButton("🎁 Claim Bonus", callback_data="claim")],
        [
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
            InlineKeyboardButton("👥 Refer", callback_data="refer"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(kb)

def time_left(last_claim_iso):
    last = datetime.fromisoformat(last_claim_iso)
    next_claim = last + timedelta(hours=COOLDOWN_HOURS)
    now = datetime.utcnow()
    if now >= next_claim:
        return None
    delta = next_claim - now
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    data = get_user(users, user.id)
    is_new = data["balance"] == 0 and data["last_claim"] is None

    # Handle referral
    if context.args and is_new:
        ref_id = context.args[0]
        if ref_id.isdigit() and ref_id != str(user.id):
            if ref_id in users:
                data["referred_by"] = ref_id
                users[ref_id]["balance"] += REFERRAL_BONUS
                users[ref_id]["referrals"] += 1
                try:
                    await context.bot.send_message(
                        chat_id=int(ref_id),
                        text=f"🎉 Someone joined using your link! +{REFERRAL_BONUS} bonus added.",
                    )
                except Exception:
                    pass

    if is_new and data["referred_by"] is None:
        data["balance"] += WELCOME_BONUS

    save_users(users)

    text = (
        f"👋 Welcome <b>{user.first_name}</b> to <b>VIP Promo Bot</b>!\n\n"
        f"💰 Balance: <b>{data['balance']}</b> points\n"
        f"👥 Referrals: <b>{data['referrals']}</b>\n\n"
        f"Tap a button below to get started 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="HTML")

async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    data = get_user(users, user.id)

    if data["last_claim"]:
        left = time_left(data["last_claim"])
        if left:
            msg = f"⏳ You already claimed today!\nCome back in <b>{left}</b>."
            if update.callback_query:
                await update.callback_query.answer("Cooldown active", show_alert=True)
                await update.callback_query.message.reply_text(msg, parse_mode="HTML")
            else:
                await update.message.reply_text(msg, parse_mode="HTML")
            return

    reward = random.randint(BONUS_MIN, BONUS_MAX)
    data["balance"] += reward
    data["last_claim"] = datetime.utcnow().isoformat()
    save_users(users)

    msg = (
        f"🎁 <b>Bonus Claimed!</b>\n\n"
        f"You received <b>{reward}</b> points.\n"
        f"💰 New balance: <b>{data['balance']}</b>\n\n"
        f"Come back in {COOLDOWN_HOURS}h for more!"
    )
    if update.callback_query:
        await update.callback_query.answer("Bonus claimed!")
        await update.callback_query.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_menu())

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    data = get_user(users, user.id)
    save_users(users)
    text = (
        f"💰 <b>Your Wallet</b>\n\n"
        f"Balance: <b>{data['balance']}</b> points\n"
        f"Referrals: <b>{data['referrals']}</b>\n"
        f"Joined: {data['joined'][:10]}"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user.id}"
    text = (
        f"👥 <b>Invite & Earn</b>\n\n"
        f"Share your link and earn <b>{REFERRAL_BONUS}</b> points per friend!\n\n"
        f"🔗 Your link:\n<code>{link}</code>"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ <b>Help</b>\n\n"
        "/start — Register & main menu\n"
        "/claim — Claim daily bonus\n"
        "/balance — Check balance\n"
        "/refer — Get referral link\n"
        "/help — This menu\n\n"
        f"Claim every {COOLDOWN_HOURS}h. Earn {REFERRAL_BONUS} pts per referral."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast your message")
        return
    msg = " ".join(context.args)
    users = load_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 {msg}")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Sent: {sent} | ❌ Failed: {failed}")

# ---------- CALLBACK ROUTER ----------
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "claim":
        await claim(update, context)
    elif q.data == "balance":
        await balance(update, context)
    elif q.data == "refer":
        await refer(update, context)
    elif q.data == "help":
        await help_cmd(update, context)

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("claim", claim))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_router))

    logger.info("VIP Promo Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
