import logging
import sqlite3
import time
import os
import csv
import re
from datetime import datetime, timedelta
from threading import Thread
import telebot
from telebot import types

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
API_TOKEN = "8428320400:AAFeExw8eyMiFv-l2TiHXaILKBzc_rBhMcM"
ADMIN_IDS = [7868585904, 6577308099]
MAIN_CHANNEL = '@atik_method_zone'
BACKUP_CHANNEL = '-1003096164193'
BACKUP_CHANNEL_LINK = 'https://t.me/+8REFroGEWNM5ZjE9'
OTP_CHANNEL = '@atik_methodzone_Otp'

if ':' not in API_TOKEN:
    raise ValueError('Invalid bot token format.')

bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=4)

# Database setup with connection pooling
class Database:
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._connection = sqlite3.connect('numbers.db', check_same_thread=False)
            cls._connection.row_factory = sqlite3.Row
            cls.init_db()
        return cls._instance
    
    @classmethod
    def init_db(cls):
        c = cls._connection.cursor()
        
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
        
        cls._connection.commit()
    
    @classmethod
    def get_connection(cls):
        return cls._connection
    
    @classmethod
    def execute(cls, query, params=()):
        try:
            c = cls._connection.cursor()
            c.execute(query, params)
            cls._connection.commit()
            return c
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            try:
                cls._connection = sqlite3.connect('numbers.db', check_same_thread=False)
                cls._connection.row_factory = sqlite3.Row
                c = cls._connection.cursor()
                c.execute(query, params)
                cls._connection.commit()
                return c
            except sqlite3.Error as e2:
                logger.error(f"Database reconnection failed: {e2}")
                raise e2

# Initialize database
db = Database()

# Utility functions
def update_user_stats(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    
    c = db.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    
    if result:
        db.execute("UPDATE user_stats SET numbers_today = numbers_today + 1 WHERE user_id = ? AND date = ?", 
                   (user_id, today))
    else:
        db.execute("INSERT INTO user_stats (user_id, date, numbers_today) VALUES (?, ?, 1)", 
                   (user_id, today))  # Fixed: Correct number of parameters

# Other utility functions (unchanged for brevity)
def is_admin(user_id):
    return user_id in ADMIN_IDS

def check_membership(user_id):
    try:
        cache_key = f"member_{user_id}"
        if hasattr(check_membership, 'cache') and cache_key in check_membership.cache:
            if time.time() - check_membership.cache[cache_key]['time'] < 300:
                return check_membership.cache[cache_key]['result']
        
        main_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        if main_member.status not in ['member', 'administrator', 'creator']:
            result = (False, "public")
            if not hasattr(check_membership, 'cache'):
                check_membership.cache = {}
            check_membership.cache[cache_key] = {'result': result, 'time': time.time()}
            return result
        
        backup_member = bot.get_chat_member(BACKUP_CHANNEL, user_id)
        if backup_member.status not in ['member', 'administrator', 'creator']:
            result = (False, "private")
            if not hasattr(check_membership, 'cache'):
                check_membership.cache = {}
            check_membership.cache[cache_key] = {'result': result, 'time': time.time()}
            return result
        
        result = (True, "both")
        if not hasattr(check_membership, 'cache'):
            check_membership.cache = {}
        check_membership.cache[cache_key] = {'result': result, 'time': time.time()}
        return result
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return (False, "error")

def get_today_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    c = db.execute("SELECT COUNT(*) FROM numbers WHERE use_date LIKE ?", (f"{today}%",))
    total_used = c.fetchone()[0]
    
    c = db.execute("SELECT COUNT(DISTINCT user_id) FROM user_stats WHERE date = ?", (today,))
    active_users = c.fetchone()[0]
    
    return total_used, active_users

def get_country_stats():
    c = db.execute("SELECT country, COUNT(*) as total, SUM(is_used) as used FROM numbers GROUP BY country")
    return c.fetchall()

def get_user_stats(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    c = db.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    return result[0] if result else 0

def check_low_numbers():
    c = db.execute("SELECT country, COUNT(*) as available FROM numbers WHERE is_used = 0 GROUP BY country")
    results = c.fetchall()
    
    low_countries = []
    for country, available in results:
        if available < 5:
            low_countries.append((country, available))
    
    return low_countries

def check_country_availability(country):
    c = db.execute("SELECT COUNT(*) FROM numbers WHERE country = ? AND is_used = 0", (country,))
    return c.fetchone()[0]

def notify_admins_country_empty(country):
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"⚠️ COUNTRY EMPTY: {country} has run out of numbers!")
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")

def check_and_notify_country_empty(country):
    c = db.execute("SELECT notified FROM notifications WHERE country = ?", (country,))
    result = c.fetchone()
    
    available = check_country_availability(country)
    
    if available == 0:
        if not result:
            notify_admins_country_empty(country)
            db.execute("INSERT INTO notifications (country, notified) VALUES (?, 1)", (country,))
        elif result[0] == 0:
            notify_admins_country_empty(country)
            db.execute("UPDATE notifications SET notified = 1 WHERE country = ?", (country,))
    else:
        if result:
            db.execute("UPDATE notifications SET notified = 0 WHERE country = ?", (country,))

def set_cooldown(user_id):
    timestamp = int(time.time())
    db.execute("REPLACE INTO cooldowns (user_id, timestamp) VALUES (?, ?)", (user_id, timestamp))

def check_cooldown(user_id):
    c = db.execute("SELECT timestamp FROM cooldowns WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        elapsed = int(time.time()) - result[0]
        if elapsed < 10:
            return 10 - elapsed
    return 0

def extract_numbers_from_content(content, filename):
    numbers = set()
    file_ext = os.path.splitext(filename)[1].lower() if filename else '.txt'
    
    if file_ext == '.csv':
        try:
            csv_content = content.decode('utf-8').splitlines()
            reader = csv.reader(csv_content)
            for row in reader:
                for item in row:
                    found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', item)
                    numbers.update(found_numbers)
        except:
            text_content = content.decode('utf-8', errors='ignore')
            found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', text_content)
            numbers.update(found_numbers)
    else:
        try:
            text_content = content.decode('utf-8')
        except:
            text_content = content.decode('utf-8', errors='ignore')
        
        found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', text_content)
        numbers.update(found_numbers)
    
    cleaned_numbers = set()
    for number in numbers:
        cleaned = re.sub(r'(?!^\+)[^\d]', '', number)
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        cleaned_numbers.add(cleaned)
    
    return list(cleaned_numbers)

def admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup()
    
    btn1 = types.InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_numbers")
    btn2 = types.InlineKeyboardButton("🗑️ Remove Numbers", callback_data="admin_remove_numbers")
    btn3 = types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton("👤 User Management", callback_data="admin_users")
    btn5 = types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    markup.row(btn5)
    
    bot.send_message(chat_id, "🔧 Admin Panel\n\nSelect an option:", reply_markup=markup)

# Start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    c = db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result and result[0] == 1:
        bot.send_message(message.chat.id, "❌ You are banned from using this bot.")
        return
    
    if not result:
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                 (user_id, username, first_name, last_name, join_date))
    
    is_member, channel_type = check_membership(user_id)
    
    if not is_member:
        if channel_type == "public":
            error_msg = "❌ You need to join our main channel to use this bot."
        elif channel_type == "private":
            error_msg = "❌ You need to join our backup channel to use this bot."
        else:
            error_msg = "❌ You need to join our channels to use this bot."
        
        markup = types.InlineKeyboardMarkup()
        main_btn = types.InlineKeyboardButton("📢 Main Channel", url=f"https://t.me/{MAIN_CHANNEL[1:]}")
        backup_btn = types.InlineKeyboardButton("🔗 Backup Channel", url=BACKUP_CHANNEL_LINK)
        check_btn = types.InlineKeyboardButton("✅ Check Membership", callback_data="check_membership")
        
        markup.row(main_btn)
        markup.row(backup_btn)
        markup.row(check_btn)
        
        bot.send_message(message.chat.id, 
                        f"{error_msg}\n\n"
                        f"✅ Main Channel: {MAIN_CHANNEL}\n"
                        f"✅ Backup Channel: Join via the button below\n\n"
                        "After joining both channels, click 'Check Membership'.",
                        reply_markup=markup)
        return
    
    show_main_menu(message.chat.id, user_id)

def show_main_menu(chat_id, user_id):
    markup = types.InlineKeyboardMarkup()
    
    c = db.execute("SELECT DISTINCT country FROM numbers WHERE is_used = 0")
    countries = c.fetchall()
    
    for country in countries:
        country_name = country[0]
        btn = types.InlineKeyboardButton(f" {country_name}", callback_data=f"country_{country_name}")
        markup.add(btn)
    
    if is_admin(user_id):
        admin_btn = types.InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel")
        markup.add(admin_btn)
    
    bot.send_message(chat_id, 
                    "🌍 Select a country:\n\n"
                    "Choose a country to get a number from the available options.",
                    reply_markup=markup)

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)
        Thread(target=process_callback, args=(call,)).start()
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")

def process_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if call.data == "check_membership":
        is_member, channel_type = check_membership(user_id)
        
        if is_member:
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            show_main_menu(chat_id, user_id)
        else:
            if channel_type == "public":
                error_msg = "❌ You haven't joined the main channel yet!"
            elif channel_type == "private":
                error_msg = "❌ You haven't joined the backup channel yet!"
            else:
                error_msg = "❌ You haven't joined our channels yet!"
            
            try:
                bot.answer_callback_query(call.id, error_msg)
            except:
                pass
        return
    
    if call.data == "admin_panel":
        if is_admin(user_id):
            admin_panel(chat_id)
        else:
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
        return
    
    if call.data.startswith("country_"):
        country = call.data.split("_")[1]
        
        is_member, channel_type = check_membership(user_id)
        if not is_member:
            if channel_type == "public":
                error_msg = "❌ Please join our main channel first!"
            else:
                error_msg = "❌ Please join our backup channel first!"
            
            try:
                bot.answer_callback_query(call.id, error_msg)
            except:
                pass
            return
        
        c = db.execute("SELECT number FROM numbers WHERE country = ? AND is_used = 0 LIMIT 1", (country,))
        result = c.fetchone()
        
        if not result:
            try:
                bot.answer_callback_query(call.id, f"❌ No numbers available for {country}!")
            except:
                pass
            return
        
        number = result[0]
        
        use_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE numbers SET is_used = 1, used_by = ?, use_date = ? WHERE number = ?",
                 (user_id, use_date, number))
        
        update_user_stats(user_id)
        set_cooldown(user_id)
        check_and_notify_country_empty(country)
        
        markup = types.InlineKeyboardMarkup()
        change_btn = types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{country}")
        otp_btn = types.InlineKeyboardButton("🔑 SEE OTP", url=f"https://t.me/{OTP_CHANNEL[1:]}")
        back_btn = types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_countries")
        
        markup.row(change_btn)
        markup.row(otp_btn)
        markup.row(back_btn)
        
        message_text = f"✅ Your Unique {country} Number:\n\n\t\t> `{number}` <\n\n"
        message_text += "• Tap on the number to copy it to clipboard\n"
        message_text += "• This is your personal one-time use number\n"
        message_text += "• Please do NOT use this number for any illegal activities"
        
        try:
            bot.edit_message_text(message_text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
        return
    
    if call.data.startswith("change_"):
        country = call.data.split("_")[1]
        
        cooldown = check_cooldown(user_id)
        if cooldown > 0:
            try:
                bot.answer_callback_query(call.id, f"⏳ Please wait {cooldown} seconds before changing number")
            except:
                pass
            return
        
        is_member, channel_type = check_membership(user_id)
        if not is_member:
            if channel_type == "public":
                error_msg = "❌ Please join our main channel first!"
            else:
                error_msg = "❌ Please join our backup channel first!"
            
            try:
                bot.answer_callback_query(call.id, error_msg)
            except:
                pass
            return
        
        c = db.execute("SELECT number FROM numbers WHERE country = ? AND used_by = ? ORDER BY use_date DESC LIMIT 1", 
                 (country, user_id))
        old_number = c.fetchone()
        if old_number:
            db.execute("UPDATE numbers SET is_used = 2 WHERE number = ?", (old_number[0],))
        
        c = db.execute("SELECT number FROM numbers WHERE country = ? AND is_used = 0 LIMIT 1", (country,))
        result = c.fetchone()
        
        if not result:
            try:
                bot.answer_callback_query(call.id, f"❌ No numbers available for {country}!")
            except:
                pass
            return
        
        new_number = result[0]
        
        use_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE numbers SET is_used = 1, used_by = ?, use_date = ? WHERE number = ?",
                 (user_id, use_date, new_number))
        
        update_user_stats(user_id)
        set_cooldown(user_id)
        check_and_notify_country_empty(country)
        
        markup = types.InlineKeyboardMarkup()
        change_btn = types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{country}")
        otp_btn = types.InlineKeyboardButton("🔑 SEE OTP", url=f"https://t.me/{OTP_CHANNEL[1:]}")
        back_btn = types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_countries")
        
        markup.row(change_btn)
        markup.row(otp_btn)
        markup.row(back_btn)
        
        message_text = f"✅ Your Unique {country} Number:\n\n\t\t> `{new_number}` <\n\n"
        message_text += "• Tap on the number to copy it to clipboard\n"
        message_text += "• This is your personal one-time use number\n"
        message_text += "• Please do NOT use this number for any illegal activities"
        
        try:
            bot.edit_message_text(message_text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
        return
    
    if call.data == "back_to_countries":
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        show_main_menu(chat_id, user_id)
        return
    
    if call.data == "admin_add_numbers":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        msg = bot.send_message(chat_id, "🌍 Please send the country name with flag (e.g., 🇺🇸 United States):")
        bot.register_next_step_handler(msg, process_country_name)
        return
    
    if call.data == "admin_remove_numbers":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        c = db.execute("SELECT DISTINCT country FROM numbers")
        countries = c.fetchall()
        
        markup = types.InlineKeyboardMarkup()
        for country in countries:
            btn = types.InlineKeyboardButton(country[0], callback_data=f"remove_{country[0]}")
            markup.add(btn)
        
        bot.send_message(chat_id, "Select a country to remove all its numbers:", reply_markup=markup)
        return
    
    if call.data.startswith("remove_"):
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        country = call.data.split("_")[1]
        
        markup = types.InlineKeyboardMarkup()
        confirm_btn = types.InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_remove_{country}")
        cancel_btn = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_remove")
        markup.row(confirm_btn, cancel_btn)
        
        bot.send_message(chat_id, f"Are you sure you want to delete ALL numbers for {country}?", reply_markup=markup)
        return
    
    if call.data.startswith("confirm_remove_"):
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        country = call.data.split("_")[2]
        db.execute("DELETE FROM numbers WHERE country = ?", (country,))
        
        bot.send_message(chat_id, f"✅ All numbers for {country} have been removed.")
        return
    
    if call.data == "cancel_remove":
        bot.send_message(chat_id, "❌ Deletion cancelled.")
        return
    
    if call.data == "admin_stats":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        total_used, active_users = get_today_stats()
        country_stats = get_country_stats()
        
        stats_text = f"📊 Today's Stats:\n\n• Numbers Used: {total_used}\n• Active Users: {active_users}\n\n"
        stats_text += "📈 Country-wise Stats:\n"
        
        for country, total, used in country_stats:
            available = total - used
            stats_text += f"• {country}: {used}/{total} (Available: {available})\n"
        
        low_numbers = check_low_numbers()
        if low_numbers:
            stats_text += "\n⚠️ Low Numbers Alert:\n"
            for country, available in low_numbers:
                stats_text += f"• {country}: Only {available} numbers left!\n"
        
        bot.send_message(chat_id, stats_text)
        return
    
    if call.data == "admin_users":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("👤 Find User", callback_data="admin_find_user")
        btn2 = types.InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban_user")
        btn3 = types.InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_user")
        markup.row(btn1)
        markup.row(btn2, btn3)
        
        bot.send_message(chat_id, "👤 User Management\n\nSelect an option:", reply_markup=markup)
        return
    
    if call.data == "admin_find_user":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to find:")
        bot.register_next_step_handler(msg, find_user)
        return
    
    if call.data == "admin_ban_user":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to ban:")
        bot.register_next_step_handler(msg, ban_user)
        return
    
    if call.data == "admin_unban_user":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to unban:")
        bot.register_next_step_handler(msg, unban_user)
        return
    
    if call.data == "admin_broadcast":
        if not is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "❌ Access denied!")
            except:
                pass
            return
        
        msg = bot.send_message(chat_id, "Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, broadcast_message)
        return

# Admin functions
def process_country_name(message):
    country_name = message.text
    msg = bot.send_message(message.chat.id, f"📤 Now send me a file with numbers for {country_name}")
    bot.register_next_step_handler(msg, process_number_file, country_name)

def process_number_file(message, country_name):
    if not message.document:
        bot.send_message(message.chat.id, "❌ Please send a file.")
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error downloading file: {str(e)}")
        return
    
    try:
        numbers = extract_numbers_from_content(downloaded_file, message.document.file_name)
        
        if not numbers:
            bot.send_message(message.chat.id, "❌ No valid phone numbers found in the file.")
            return
        
        added = 0
        skipped = 0
        
        for number in numbers:
            c = db.execute("SELECT id FROM numbers WHERE number = ?", (number,))
            if c.fetchone():
                skipped += 1
                continue
            
            try:
                db.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country_name, number))
                added += 1
            except:
                skipped += 1
        
        c = db.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = c.fetchall()
        
        for user in users:
            try:
                bot.send_message(user[0], f"🆕 New numbers added for {country_name}! Use /start to get one.")
            except:
                pass
        
        bot.send_message(message.chat.id, 
                        f"✅ Numbers added successfully for {country_name}!\n\n"
                        f"Added: {added}\nSkipped (duplicates): {skipped}\n"
                        f"Total processed: {len(numbers)}")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error processing file: {str(e)}")

def find_user(message):
    try:
        user_id = int(message.text)
        c = db.execute("SELECT user_id, username, first_name, last_name, join_date, is_banned FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if user:
            user_id, username, first_name, last_name, join_date, is_banned = user
            status = "Banned" if is_banned else "Active"
            user_info = f"👤 User Info:\n\nID: {user_id}\nUsername: @{username}\nName: {first_name} {last_name}\nJoin Date: {join_date}\nStatus: {status}"
            
            today = datetime.now().strftime("%Y-%m-%d")
            c = db.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
            result = c.fetchone()
            numbers_today = result[0] if result else 0
            
            user_info += f"\nNumbers Today: {numbers_today}"
            
            bot.send_message(message.chat.id, user_info)
        else:
            bot.send_message(message.chat.id, "❌ User not found.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def ban_user(message):
    try:
        user_id = int(message.text)
        db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        
        bot.send_message(message.chat.id, f"✅ User {user_id} has been banned.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def unban_user(message):
    try:
        user_id = int(message.text)
        db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        
        bot.send_message(message.chat.id, f"✅ User {user_id} has been unbanned.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def broadcast_message(message):
    text = message.text
    c = db.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    
    total = len(users)
    success = 0
    failed = 0
    
    bot.send_message(message.chat.id, f"📢 Broadcasting to {total} users...")
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 Announcement from Admin:\n\n{text}")
            success += 1
        except:
            failed += 1
        
        time.sleep(0.1)
    
    bot.send_message(message.chat.id, f"✅ Broadcast completed!\n\nSuccess: {success}\nFailed: {failed}")

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        time.sleep(5)  # Brief delay before restarting
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
