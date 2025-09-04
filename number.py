import telebot
from telebot import types
import sqlite3
import time
import threading
import os
import csv
from datetime import datetime

# Bot configuration
API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
ADMIN_IDS = [7868585904, 6577308099]  # Admin user IDs
MAIN_CHANNEL = '@your_main_channel'
BACKUP_CHANNEL = '@your_backup_channel'

bot = telebot.TeleBot(API_TOKEN)

# Database setup
def init_db():
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                 last_name TEXT, join_date TEXT, is_banned INTEGER DEFAULT 0)''')
    
    # Numbers table
    c.execute('''CREATE TABLE IF NOT EXISTS numbers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, number TEXT UNIQUE, 
                 is_used INTEGER DEFAULT 0, used_by INTEGER, use_date TEXT)''')
    
    # Countries table
    c.execute('''CREATE TABLE IF NOT EXISTS countries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, code TEXT)''')
    
    # User stats table
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, 
                 numbers_today INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

init_db()

# Utility functions
def is_admin(user_id):
    return user_id in ADMIN_IDS

def check_membership(user_id):
    try:
        main_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        backup_member = bot.get_chat_member(BACKUP_CHANNEL, user_id)
        
        if main_member.status not in ['member', 'administrator', 'creator'] or \
           backup_member.status not in ['member', 'administrator', 'creator']:
            return False
        return True
    except:
        return False

def get_today_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    
    # Get total numbers used today
    c.execute("SELECT COUNT(*) FROM numbers WHERE use_date = ?", (today,))
    total_used = c.fetchone()[0]
    
    # Get user count
    c.execute("SELECT COUNT(DISTINCT user_id) FROM user_stats WHERE date = ?", (today,))
    active_users = c.fetchone()[0]
    
    conn.close()
    return total_used, active_users

def get_country_stats():
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT country, COUNT(*) as total, SUM(is_used) as used FROM numbers GROUP BY country")
    stats = c.fetchall()
    conn.close()
    return stats

def get_user_stats(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_user_stats(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    
    # Check if record exists
    c.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    
    if result:
        c.execute("UPDATE user_stats SET numbers_today = numbers_today + 1 WHERE user_id = ? AND date = ?", 
                 (user_id, today))
    else:
        c.execute("INSERT INTO user_stats (user_id, date, numbers_today) VALUES (?, ?, 1)", 
                 (user_id, today))
    
    conn.commit()
    conn.close()

def check_low_numbers():
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT country, COUNT(*) as available FROM numbers WHERE is_used = 0 GROUP BY country")
    results = c.fetchall()
    conn.close()
    
    low_countries = []
    for country, available in results:
        if available < 5:  # Threshold for low numbers
            low_countries.append((country, available))
    
    return low_countries

# Admin panel functions
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
    
    # Check if user is banned
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result and result[0] == 1:
        bot.send_message(message.chat.id, "❌ You are banned from using this bot.")
        conn.close()
        return
    
    # Add user to database if not exists
    if not result:
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                 (user_id, username, first_name, last_name, join_date))
        conn.commit()
    
    conn.close()
    
    # Check channel membership
    if not check_membership(user_id):
        markup = types.InlineKeyboardMarkup()
        main_btn = types.InlineKeyboardButton("📢 Main Channel", url=f"https://t.me/{MAIN_CHANNEL[1:]}")
        backup_btn = types.InlineKeyboardButton("🔗 Backup Channel", url=f"https://t.me/{BACKUP_CHANNEL[1:]}")
        check_btn = types.InlineKeyboardButton("✅ Check Membership", callback_data="check_membership")
        
        markup.row(main_btn)
        markup.row(backup_btn)
        markup.row(check_btn)
        
        bot.send_message(message.chat.id, 
                        "👋 Welcome!\n\nTo use this bot, please join our channels:\n\n"
                        "✅ Main Channel: {}\n"
                        "✅ Backup Channel: {}\n\n"
                        "After joining both channels, click 'Check Membership'.".format(MAIN_CHANNEL, BACKUP_CHANNEL),
                        reply_markup=markup)
        return
    
    # Show main menu
    show_main_menu(message.chat.id, user_id)

def show_main_menu(chat_id, user_id):
    markup = types.InlineKeyboardMarkup()
    
    # Country selection buttons
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT country FROM numbers WHERE is_used = 0")
    countries = c.fetchall()
    conn.close()
    
    for country in countries:
        country_name = country[0]
        btn = types.InlineKeyboardButton(f"🇺🇳 {country_name}", callback_data=f"country_{country_name}")
        markup.add(btn)
    
    # Admin button for admins
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
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Check membership
    if call.data == "check_membership":
        if check_membership(user_id):
            bot.delete_message(chat_id, call.message.message_id)
            show_main_menu(chat_id, user_id)
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined the channels yet!")
        return
    
    # Admin panel
    if call.data == "admin_panel":
        if is_admin(user_id):
            admin_panel(chat_id)
        else:
            bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    # Country selection
    if call.data.startswith("country_"):
        country = call.data.split("_")[1]
        
        if not check_membership(user_id):
            bot.answer_callback_query(call.id, "❌ Please join our channels first!")
            return
        
        # Get a number for the selected country
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("SELECT number FROM numbers WHERE country = ? AND is_used = 0 LIMIT 1", (country,))
        result = c.fetchone()
        
        if not result:
            bot.answer_callback_query(call.id, f"❌ No numbers available for {country}!")
            conn.close()
            return
        
        number = result[0]
        
        # Mark number as used
        use_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE numbers SET is_used = 1, used_by = ?, use_date = ? WHERE number = ?",
                 (user_id, use_date, number))
        conn.commit()
        conn.close()
        
        # Update user stats
        update_user_stats(user_id)
        
        # Create keyboard with copy button
        markup = types.InlineKeyboardMarkup()
        copy_btn = types.InlineKeyboardButton("📋 Copy Number", callback_data=f"copy_{number}")
        change_btn = types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{country}")
        markup.row(copy_btn, change_btn)
        
        bot.edit_message_text(f"✅ Your number for {country}:\n\n`{number}`", 
                              chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        return
    
    # Copy number
    if call.data.startswith("copy_"):
        number = call.data.split("_")[1]
        bot.answer_callback_query(call.id, f"📋 Copied: {number}")
        return
    
    # Change number
    if call.data.startswith("change_"):
        country = call.data.split("_")[1]
        
        # Show loading message
        loading_msg = bot.send_message(chat_id, "🔄 Loading new number...").message_id
        
        # Get a new number
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("SELECT number FROM numbers WHERE country = ? AND is_used = 0 LIMIT 1", (country,))
        result = c.fetchone()
        
        if not result:
            bot.delete_message(chat_id, loading_msg)
            bot.answer_callback_query(call.id, f"❌ No numbers available for {country}!")
            conn.close()
            return
        
        new_number = result[0]
        
        # Mark number as used
        use_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE numbers SET is_used = 1, used_by = ?, use_date = ? WHERE number = ?",
                 (user_id, use_date, new_number))
        conn.commit()
        conn.close()
        
        # Update user stats
        update_user_stats(user_id)
        
        # Create keyboard with copy button
        markup = types.InlineKeyboardMarkup()
        copy_btn = types.InlineKeyboardButton("📋 Copy Number", callback_data=f"copy_{new_number}")
        change_btn = types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{country}")
        markup.row(copy_btn, change_btn)
        
        # Update the message
        bot.delete_message(chat_id, loading_msg)
        bot.edit_message_text(f"✅ Your new number for {country}:\n\n`{new_number}`", 
                              chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        return
    
    # Admin functions
    if call.data == "admin_add_numbers":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        msg = bot.send_message(chat_id, "📤 Send me a CSV file with numbers. Format should be: country,number")
        bot.register_next_step_handler(msg, process_number_file)
        return
    
    if call.data == "admin_remove_numbers":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("SELECT DISTINCT country FROM numbers")
        countries = c.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup()
        for country in countries:
            btn = types.InlineKeyboardButton(country[0], callback_data=f"remove_{country[0]}")
            markup.add(btn)
        
        bot.send_message(chat_id, "Select a country to remove all its numbers:", reply_markup=markup)
        return
    
    if call.data.startswith("remove_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        country = call.data.split("_")[1]
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("DELETE FROM numbers WHERE country = ?", (country,))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, f"✅ All numbers for {country} have been removed.")
        return
    
    if call.data == "admin_stats":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        # Get today's stats
        total_used, active_users = get_today_stats()
        
        # Get country stats
        country_stats = get_country_stats()
        
        stats_text = f"📊 Today's Stats:\n\n• Numbers Used: {total_used}\n• Active Users: {active_users}\n\n"
        stats_text += "📈 Country-wise Stats:\n"
        
        for country, total, used in country_stats:
            available = total - used
            stats_text += f"• {country}: {used}/{total} (Available: {available})\n"
        
        # Check for low numbers
        low_numbers = check_low_numbers()
        if low_numbers:
            stats_text += "\n⚠️ Low Numbers Alert:\n"
            for country, available in low_numbers:
                stats_text += f"• {country}: Only {available} numbers left!\n"
        
        bot.send_message(chat_id, stats_text)
        return
    
    if call.data == "admin_users":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
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
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to find:")
        bot.register_next_step_handler(msg, find_user)
        return
    
    if call.data == "admin_ban_user":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to ban:")
        bot.register_next_step_handler(msg, ban_user)
        return
    
    if call.data == "admin_unban_user":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        msg = bot.send_message(chat_id, "Send the user ID to unban:")
        bot.register_next_step_handler(msg, unban_user)
        return
    
    if call.data == "admin_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Access denied!")
            return
        
        msg = bot.send_message(chat_id, "Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, broadcast_message)
        return

# Admin functions
def process_number_file(message):
    if not message.document:
        bot.send_message(message.chat.id, "❌ Please send a CSV file.")
        return
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Save the file temporarily
    with open('temp_numbers.csv', 'wb') as f:
        f.write(downloaded_file)
    
    # Process the CSV file
    added = 0
    skipped = 0
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    
    with open('temp_numbers.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
                
            country = row[0].strip()
            number = row[1].strip()
            
            # Check if number already exists
            c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
            if c.fetchone():
                skipped += 1
                continue
            
            # Insert the number
            try:
                c.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country, number))
                added += 1
            except:
                skipped += 1
    
    conn.commit()
    conn.close()
    
    # Remove temporary file
    os.remove('temp_numbers.csv')
    
    bot.send_message(message.chat.id, f"✅ Numbers added successfully!\n\nAdded: {added}\nSkipped (duplicates): {skipped}")

def find_user(message):
    try:
        user_id = int(message.text)
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name, last_name, join_date, is_banned FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        
        if user:
            user_id, username, first_name, last_name, join_date, is_banned = user
            status = "Banned" if is_banned else "Active"
            user_info = f"👤 User Info:\n\nID: {user_id}\nUsername: @{username}\nName: {first_name} {last_name}\nJoin Date: {join_date}\nStatus: {status}"
            
            # Get today's usage
            today = datetime.now().strftime("%Y-%m-%d")
            conn = sqlite3.connect('numbers.db')
            c = conn.cursor()
            c.execute("SELECT numbers_today FROM user_stats WHERE user_id = ? AND date = ?", (user_id, today))
            result = c.fetchone()
            numbers_today = result[0] if result else 0
            conn.close()
            
            user_info += f"\nNumbers Today: {numbers_today}"
            
            bot.send_message(message.chat.id, user_info)
        else:
            bot.send_message(message.chat.id, "❌ User not found.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def ban_user(message):
    try:
        user_id = int(message.text)
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ User {user_id} has been banned.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def unban_user(message):
    try:
        user_id = int(message.text)
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ User {user_id} has been unbanned.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Please enter a valid user ID.")

def broadcast_message(message):
    text = message.text
    conn = sqlite3.connect('numbers.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    conn.close()
    
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
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    bot.send_message(message.chat.id, f"✅ Broadcast completed!\n\nSuccess: {success}\nFailed: {failed}")

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    bot.polling()