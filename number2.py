import telebot
from telebot import types
import sqlite3
import time
import os
from datetime import datetime, timedelta

# ------------------------------
# Bot configuration
# ------------------------------
API_TOKEN = "8428320400:AAEjb2Y26wLBKn-6iJByW3SwNssyfF6retM"
ADMIN_IDS = [7868585904, 6577308099]
MAIN_CHANNEL = '@atik_method_zone'
BACKUP_CHANNEL = '-1003096164193'
BACKUP_CHANNEL_LINK = 'https://t.me/+8REFroGEWNM5ZjE9'
OTP_CHANNEL = '@atik_methodzone_Otp'

if ':' not in API_TOKEN:
    raise ValueError('Invalid bot token format.')

bot = telebot.TeleBot(API_TOKEN)

# ------------------------------
# Database setup
# ------------------------------
def init_db():
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                 last_name TEXT, join_date TEXT, is_banned INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS numbers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT UNIQUE,
                 is_used INTEGER DEFAULT 0, used_by INTEGER, use_date TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS countries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, code TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT,
                 numbers_today INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS cooldowns
                 (user_id INTEGER PRIMARY KEY, timestamp INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, notified INTEGER DEFAULT 0)''')

    conn.commit()
    conn.close()

init_db()

# ------------------------------
# Utility functions
# ------------------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS

def check_membership(user_id):
    try:
        main_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        if main_member.status not in ['member', 'administrator', 'creator']:
            return False, "public"

        backup_member = bot.get_chat_member(BACKUP_CHANNEL, user_id)
        if backup_member.status not in ['member', 'administrator', 'creator']:
            return False, "private"

        return True, "both"
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False, "error"

# ------------------------------
# Menu Functions
# ------------------------------
def show_main_menu(chat_id, user_id):
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📱 Get Number", callback_data="get_number"))
        markup.add(types.InlineKeyboardButton("🔄 Change Number", callback_data="change_number"))
        if is_admin(user_id):
            markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        bot.send_message(chat_id, "✅ Main Menu", reply_markup=markup)
    except Exception as e:
        print("Error in show_main_menu:", e)

def admin_panel(chat_id):
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"))
        markup.add(types.InlineKeyboardButton("➕ Add Country", callback_data="admin_add_country"))
        bot.send_message(chat_id, "⚙️ Admin Panel", reply_markup=markup)
    except Exception as e:
        print("Error in admin_panel:", e)

# ------------------------------
# Callback query handler (SAFE)
# ------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        # --- First acknowledge query to avoid timeout ---
        try:
            bot.answer_callback_query(call.id)
        except Exception as e:
            print("Callback ack error:", e)

        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # ------------------------------
        # Membership Check
        # ------------------------------
        if call.data == "check_membership":
            is_member, channel_type = check_membership(user_id)
            if is_member:
                bot.delete_message(chat_id, message_id)
                show_main_menu(chat_id, user_id)
            else:
                if channel_type == "public":
                    bot.answer_callback_query(call.id, "❌ You haven't joined the main channel yet!")
                elif channel_type == "private":
                    bot.answer_callback_query(call.id, "❌ You haven't joined the backup channel yet!")
                else:
                    bot.answer_callback_query(call.id, "❌ You haven't joined our channels yet!")
            return

        # ------------------------------
        # Main Menu Buttons
        # ------------------------------
        if call.data == "get_number":
            bot.send_message(chat_id, "📱 Sending a number... (demo)")
            return

        if call.data == "change_number":
            bot.send_message(chat_id, "🔄 Changing number... (demo)")
            return

        if call.data == "admin_panel":
            if is_admin(user_id):
                admin_panel(chat_id)
            else:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            return

        # ------------------------------
        # Admin Panel Buttons
        # ------------------------------
        if call.data == "admin_stats":
            bot.send_message(chat_id, "📊 Stats: (demo)")
            return

        if call.data == "admin_add_country":
            bot.send_message(chat_id, "➕ Send me country name (demo)")
            return

    except Exception as e:
        # Prevent bot crash
        print("Callback handler error:", e)

# ------------------------------
# Start command
# ------------------------------
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        is_member, _ = check_membership(user_id)
        if is_member:
            show_main_menu(message.chat.id, user_id)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ I've Joined", callback_data="check_membership"))
            bot.send_message(message.chat.id,
                             "👉 Please join our channels first.\n\n"
                             f"Main: {MAIN_CHANNEL}\nBackup: {BACKUP_CHANNEL_LINK}",
                             reply_markup=markup)
    except Exception as e:
        print("Error in /start:", e)

# ------------------------------
# Bot polling (with auto-restart)
# ------------------------------
if __name__ == "__main__":
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(5)  # restart after delay
