import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry

import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Cache for sent messages
last_messages = set()

def mask_number(number: str) -> str:
    """Mask phone number middle 3 digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "***" + digits[-3:]
    return number

def country_to_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def detect_country(number: str):
    """Detect country name + flag from number"""
    try:
        parsed_number = phonenumbers.parse("+" + number, None)
        region = region_code_for_number(parsed_number)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name, country_to_flag(region)
    except:
        pass
    return "Unknown", "🏳️"

def extract_otp(message: str) -> str:
    """Extract OTP code from message with improved pattern matching"""
    # First try to find WhatsApp-style codes (3 digits - 3 digits) - KEEP ORIGINAL FORMAT
    whatsapp_patterns = [
        r'\b\d{3}-\d{3}\b',  # 111-111 format - KEEP THE DASH
        r'\b\d{3} \d{3}\b',  # 111 111 format - KEEP THE SPACE
        r'\b\d{6}\b',        # 111111 format
    ]
    
    for pattern in whatsapp_patterns:
        match = re.search(pattern, message)
        if match:
            # RETURN ORIGINAL FORMAT WITHOUT REMOVING ANY CHARACTERS
            return match.group(0)
    
    # Then try to find other common OTP patterns
    common_patterns = [
        r'\b\d{4}\b',  # 4-digit codes
        r'\b\d{5}\b',  # 5-digit codes
        r'\b\d{6}\b',  # 6-digit codes
        r'\b\d{7}\b',  # 7-digit codes
        r'\b\d{8}\b',  # 8-digit codes
    ]
    
    for pattern in common_patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(0)
    
    return "N/A"

def send_to_telegram(number, country_name, country_flag, service, masked_number, otp_code, message, timestamp):
    """Send message with updated format as requested"""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"

    keyboard = {
        "inline_keyboard": [
            # প্রথম সারি - Number Channel
            [{"text": "🚀 Number Channel", "url": "https://t.me/number_group_kr"}],
            # দ্বিতীয় সারি - দুইটা বাটন পাশাপাশি
            [
                {"text": "🔗 Main Channel", "url": "https://t.me/+BYBSV6960Ds5OGM9"},
                {"text": "💬 Support Group", "url": "https://t.me/kr_support_group"}
            ]
        ]
    }

    # আপনার চেয়ে মোড়া ফরম্যাট - FIXED SYNTAX
    formatted = (
        f"{country_flag} {country_name} {service} OTP RECEIVED\n"
        f"⏰ **Time:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{country_flag} **Country:** {country_name}\n"
        f"⚙️ **CLI:** `{service}`\n"
        f"☎️ **Number:** `{masked_number}`\n\n"
        f"🔑 **OTP:** `{otp_code}`\n\n"
        f"📩 **Full Message:**\n"
        f"```{message.strip()}```"
    )

    payload = {
        "chat_id": config.CHAT_ID,
        "text": formatted,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("[✅] Telegram message sent.")
        else:
            print(f"[❌] Failed: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")

def extract_sms(driver):
    global last_messages
    try:
        driver.get(config.SMS_URL)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # HTML structure অনুযায়ী টেবিল থেকে ডেটা এক্সট্র্যাক্ট করুন
        table = soup.find('table', {'class': 'data-tbl-boxy'})
        if not table:
            print("[⚠️] Could not find SMS table.")
            return

        # টেবিলের হেডার থেকে কলাম ইনডেক্স খুঁজে বের করুন
        headers = table.find_all('th')
        column_indices = {}
        
        for idx, header in enumerate(headers):
            header_text = header.get_text(strip=True)
            if header_text == "Number":
                column_indices['number'] = idx
            elif header_text == "CLI":
                column_indices['service'] = idx
            elif header_text == "SMS":
                column_indices['sms'] = idx
            elif header_text == "Date":
                column_indices['date'] = idx

        # প্রয়োজনীয় কলামগুলো পাওয়া গেছে কিনা চেক করুন
        required_columns = ['number', 'service', 'sms']
        if not all(col in column_indices for col in required_columns):
            print(f"[⚠️] Missing required columns. Found: {list(column_indices.keys())}")
            return

        # টেবিলের row গুলো প্রসেস করুন
        rows = table.find_all('tr')[1:]  # প্রথম row (হেডার) বাদ দিন
        
        for row in rows:
            cols = row.find_all('td')
            
            # যদি row-এ পর্যাপ্ত কলাম না থাকে, তাহলে skip করুন
            if len(cols) <= max(column_indices.values()):
                continue

            # ডেটা এক্সট্র্যাক্ট করুন
            number = cols[column_indices['number']].get_text(strip=True) or "Unknown"
            service = cols[column_indices['service']].get_text(strip=True) or "Unknown"
            message = cols[column_indices['sms']].get_text(strip=True)
            date = cols[column_indices['date']].get_text(strip=True) if 'date' in column_indices else "Unknown"

            # ভ্যালিডেশন চেক
            if not message or message in last_messages:
                continue
            if message.strip() in ("0", "Unknown") or (
                number in ("0", "Unknown") and service in ("0", "Unknown")
            ):
                continue

            # ডুপ্লিকেট মেসেজ এড়াতে মেসেজ স্টোর করুন
            last_messages.add(message)
            
            # টাইমস্ট্যাম্প তৈরি করুন
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time

            # OTP এক্সট্র্যাক্ট করুন
            otp_code = extract_otp(message)
            
            # কান্ট্রি ডিটেক্ট করুন
            country_name, country_flag = detect_country(number)
            
            # নাম্বার মাস্ক করুন
            masked_number = mask_number(number)

            # টেলিগ্রামে মেসেজ পাঠান
            send_to_telegram(
                number=number,
                country_name=country_name,
                country_flag=country_flag,
                service=service,
                masked_number=masked_number,
                otp_code=otp_code,
                message=message,
                timestamp=timestamp
            )

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("[*] SMS Extractor running. Press Ctrl+C to stop.")
        while True:
            extract_sms(driver)
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    finally:
        driver.quit()
        print("[*] Browser closed.")
