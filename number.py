import telebot
from telebot import types
import os
import csv

API_TOKEN = "8428320400:AAHvjFBNkpjAvsYEzkl4LX17qCAXGjoTOpM"
bot = telebot.TeleBot(API_TOKEN)

# Admin
ADMIN_PASSWORD = "Atik@112230"
ADMIN_ID = None

# Channels
MAIN_CHANNEL_ID = 3002931027
BACKUP_CHANNEL_ID = -1003096164193

# Data storage
DATA_DIR = "number_bot_data"
COUNTRIES_FILE = os.path.join(DATA_DIR, "countries.csv")  # Store country list and assigned numbers

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- Helper Functions ---
def load_countries():
    countries = {}
    if os.path.exists(COUNTRIES_FILE):
        with open(COUNTRIES_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                country = row["Country"]
                numbers = row["Numbers"].split("|") if row["Numbers"] else []
                assigned = row["Assigned"].split("|") if row["Assigned"] else []
                countries[country] = {"numbers": numbers, "assigned": assigned}
    return countries

def save_countries(countries):
    with open(COUNTRIES_FILE, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["Country", "Numbers", "Assigned"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for country, data in countries.items():
            writer.writerow({
                "Country": country,
                "Numbers": "|".join(data["numbers"]),
                "Assigned": "|".join(data["assigned"])
            })

def get_number_for_user(country, user_id):
    countries = load_countries()
    if country not in countries:
        return None
    available_numbers = [n for n in countries[country]["numbers"] if n not in countries[country]["assigned"]]
    if not available_numbers:
        return None
    number = available_numbers[0]
    countries[country]["assigned"].append(number)
    save_countries(countries)
    return number

# --- Start Command ---
@bot.message_handler(commands=["start"])
def start_message(message):
    # Check if user joined main channel
    try:
        member = bot.get_chat_member(MAIN_CHANNEL_ID, message.from_user.id)
        if member.status in ["left", "kicked"]:
            bot.send_message(message.chat.id,
                             "❌ You must join the main channel to use the bot.\n🔗 https://t.me/atik_method_zone")
            return
    except:
        pass

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("🤖 Get Number", callback_data="get_number")
    btn2 = types.InlineKeyboardButton("🔗 Main Channel", url="https://t.me/atik_method_zone")
    btn3 = types.InlineKeyboardButton("🔗 BackUp Channel", url="https://t.me/+8REFroGEWNM5ZjE9")
    markup.add(btn1)
    markup.add(btn2, btn3)
    bot.send_message(message.chat.id, "Welcome to Number Bot! Choose an option:", reply_markup=markup)

# --- Inline Buttons ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    countries = load_countries()
    if call.data == "get_number":
        if not countries:
            bot.send_message(call.message.chat.id, "No countries available yet. Admin will add them soon.")
            return
        markup = types.InlineKeyboardMarkup()
        for country in countries.keys():
            markup.add(types.InlineKeyboardButton(country, callback_data=f"country_{country}"))
        bot.send_message(call.message.chat.id, "🌎 Select Country:", reply_markup=markup)
    
    elif call.data.startswith("country_"):
        country_name = call.data.split("_")[1]
        number = get_number_for_user(country_name, call.from_user.id)
        if not number:
            bot.send_message(call.message.chat.id, f"No available numbers for {country_name}.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("♻️ Change Number", callback_data="get_number"))
        markup.add(types.InlineKeyboardButton("🌎 Country", callback_data=f"country_{country_name}"))
        bot.send_message(call.message.chat.id, f"Your number:\n{number}", reply_markup=markup)

    # --- Delete Country/File Inline ---
    elif call.data.startswith("del_"):
        country_name = call.data[4:]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirmdel_{country_name}"))
        markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=f"Are you sure you want to delete country '{country_name}'? This will remove all files and data.",
                              reply_markup=markup)

    elif call.data.startswith("confirmdel_"):
        country_name = call.data.split("_")[1]
        countries = load_countries()
        if country_name not in countries:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text=f"❌ Country '{country_name}' not found.")
            return
        # Remove from CSV
        countries.pop(country_name)
        save_countries(countries)
        # Remove related files
        for filename in os.listdir(DATA_DIR):
            if filename.lower().startswith(country_name.lower()):
                os.remove(os.path.join(DATA_DIR, filename))
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=f"✅ Country '{country_name}' and related files have been deleted.")

    elif call.data == "cancel":
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text="❌ Deletion cancelled.")

# --- Admin Commands ---
@bot.message_handler(commands=["atik"])
def admin_login(message):
    msg = bot.send_message(message.chat.id, "Enter admin password:")
    bot.register_next_step_handler(msg, check_admin_password)

def check_admin_password(message):
    global ADMIN_ID
    if message.text == ADMIN_PASSWORD:
        ADMIN_ID = message.from_user.id
        bot.send_message(message.chat.id,
                         "✅ Admin login successful!\nAvailable commands:\n- /addfile\n- /status\n- /deletefile")
    else:
        bot.send_message(message.chat.id, "❌ Wrong password!")

# --- Add File ---
@bot.message_handler(commands=["addfile"])
def add_file_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Send file in txt/csv format and type Country Name as caption:")
    bot.register_next_step_handler(msg, process_file)

def process_file(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.document:
        bot.send_message(message.chat.id, "❌ Please send a valid file.")
        return
    country_name = message.caption
    if not country_name:
        bot.send_message(message.chat.id, "❌ Please type country name in caption.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_path = os.path.join(DATA_DIR, message.document.file_name)
    with open(file_path, "wb") as f:
        f.write(downloaded_file)
    
    # Load numbers from file
    numbers = []
    ext = message.document.file_name.split(".")[-1].lower()
    if ext == "txt":
        numbers = downloaded_file.decode().splitlines()
    elif ext == "csv":
        reader = csv.reader(downloaded_file.decode().splitlines())
        for row in reader:
            if row: numbers.append(row[0])
    else:
        bot.send_message(message.chat.id, "❌ Unsupported file type. Use txt or csv.")
        return
    
    countries = load_countries()
    if country_name in countries:
        countries[country_name]["numbers"].extend(numbers)
    else:
        countries[country_name] = {"numbers": numbers, "assigned": []}
    save_countries(countries)
    bot.send_message(message.chat.id, f"✅ Numbers added for {country_name}. Total numbers: {len(numbers)}")

# --- Status ---
@bot.message_handler(commands=["status"])
def status_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    countries = load_countries()
    if not countries:
        bot.send_message(message.chat.id, "No countries added yet.")
        return
    text = "🌍 Country Status:\n"
    for country, data in countries.items():
        total = len(data["numbers"])
        assigned = len(data["assigned"])
        available = total - assigned
        text += f"{country}: Total={total}, Assigned={assigned}, Available={available}\n"
    bot.send_message(message.chat.id, text)

# --- Delete File / Country ---
@bot.message_handler(commands=["deletefile"])
def delete_file_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    countries = load_countries()
    if not countries:
        bot.send_message(message.chat.id, "No countries available to delete.")
        return
    markup = types.InlineKeyboardMarkup()
    for country in countries.keys():
        markup.add(types.InlineKeyboardButton(country, callback_data=f"del_{country}"))
    bot.send_message(message.chat.id, "Select country/file to delete:", reply_markup=markup)

# --- Run Bot ---
print("Number Bot is running...")
bot.infinity_polling()
