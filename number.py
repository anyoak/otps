import telebot
from telebot import types
import sqlite3
import time
import os
import csv
import re
from datetime import datetime

# Bot configuration - REPLACE WITH YOUR ACTUAL BOT TOKEN
# Format should be: "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
API_TOKEN = "8428320400:AAHvjFBNkpjAvsYEzkl4LX17qCAXGjoTOpM"  # Get from @BotFather - must contain a colon
ADMIN_IDS = [7868585904, 6577308099]  # Admin user IDs
MAIN_CHANNEL = '@atik_method_zone'  # Public channel
BACKUP_CHANNEL = '-1003096164193'  # Private channel ID
BACKUP_CHANNEL_LINK = 'https://t.me/+8REFroGEWNM5ZjE9'  # Private channel invite link

# Validate token format
if ':' not in API_TOKEN:
    raise ValueError('Invalid bot token format. Token must contain a colon (e.g., "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")')

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
    """
    Check if user is member of both public and private channels
    """
    try:
        # Check public channel
        main_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        if main_member.status not in ['member', 'administrator', 'creator']:
            return False, "public"
        
        # Check private channel
        backup_member = bot.get_chat_member(BACKUP_CHANNEL, user_id)
        if backup_member.status not in ['member', 'administrator', 'creator']:
            return False, "private"
        
        return True, "both"
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False, "error"

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

def extract_numbers_from_content(content, filename):
    """
    Extract phone numbers from various file formats and content
    """
    numbers = set()  # Use set to avoid duplicates
    
    # Try to detect file type by extension
    file_ext = os.path.splitext(filename)[1].lower() if filename else '.txt'
    
    if file_ext == '.csv':
        # Process as CSV
        try:
            csv_content = content.decode('utf-8').splitlines()
            reader = csv.reader(csv_content)
            for row in reader:
                for item in row:
                    # Extract numbers using regex
                    found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', item)
                    numbers.update(found_numbers)
        except:
            # If CSV parsing fails, try text extraction
            text_content = content.decode('utf-8', errors='ignore')
            found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', text_content)
            numbers.update(found_numbers)
    else:
        # Process as text file
        try:
            text_content = content.decode('utf-8')
        except:
            text_content = content.decode('utf-8', errors='ignore')
        
        # Extract numbers using regex
        found_numbers = re.findall(r'\+?[0-9][0-9\s\-\(\)\.]{7,}[0-9]', text_content)
        numbers.update(found_numbers)
    
    # Clean numbers (remove spaces, hyphens, parentheses, dots) and ensure they start with +
    cleaned_numbers = set()
    for number in numbers:
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'(?!^\+)[^\d]', '', number)
        
        # Ensure number starts with +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        cleaned_numbers.add(cleaned)
    
    return list(cleaned_numbers)

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
        is_member, channel_type = check_membership(user_id)
        
        if is_member:
            bot.delete_message(chat_id, call.message.message_id)
            show_main_menu(chat_id, user_id)
        else:
            if channel_type == "public":
                error_msg = "❌ You haven't joined the main channel yet!"
            elif channel_type == "private":
                error_msg = "❌ You haven't joined the backup channel yet!"
            else:
                error_msg = "❌ You haven't joined our channels yet!"
            
            bot.answer_callback_query(call.id, error_msg)
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
        
        # Check membership again
        is_member, channel_type = check_membership(user_id)
        if not is_member:
            if channel_type == "public":
                error_msg = "❌ Please join our main channel first!"
            else:
                error_msg = "❌ Please join our backup channel first!"
            
            bot.answer_callback_query(call.id, error_msg)
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
        
        # Check membership again
        is_member, channel_type = check_membership(user_id)
        if not is_member:
            if channel_type == "public":
                error_msg = "❌ Please join our main channel first!"
            else:
                error_msg = "❌ Please join our backup channel first!"
            
            bot.answer_callback_query(call.id, error_msg)
            return
        
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
        
        msg = bot.send_message(chat_id, "📤 Send me a file with numbers and include the country name in the caption.")
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
        bot.send_message(message.chat.id, "❌ Please send a file.")
        return
    
    country_name = message.caption
    if not country_name:
        bot.send_message(message.chat.id, "❌ Please specify a country name in the caption.")
        return
    
    # Download file
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error downloading file: {str(e)}")
        return
    
    # Extract numbers from file
    try:
        numbers = extract_numbers_from_content(downloaded_file, message.document.file_name)
        
        if not numbers:
            bot.send_message(message.chat.id, "❌ No valid phone numbers found in the file.")
            return
        
        # Add numbers to database
        added = 0
        skipped = 0
        conn = sqlite3.connect('numbers.db')
        c = conn.cursor()
        
        for number in numbers:
            # Check if number already exists
            c.execute("SELECT id FROM numbers WHERE number = ?", (number,))
            if c.fetchone():
                skipped += 1
                continue
            
            # Insert the number
            try:
                c.execute("INSERT INTO numbers (country, number) VALUES (?, ?)", (country_name, number))
                added += 1
            except:
                skipped += 1
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        f"✅ Numbers added successfully for {country_name}!\n\n"
                        f"Added: {added}\nSkipped (duplicates): {skipped}\n"
                        f"Total processed: {len(numbers)}")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error processing file: {str(e)}")

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
    try:
        bot.polling()
    except Exception as e:
        print(f"Error starting bot: {e}")
