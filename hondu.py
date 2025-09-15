import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry

import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Cache for sent messagesimport time
import re
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry
import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Cache for sent messages to avoid duplicates
last_messages = set()


def mask_number(number: str) -> str:
    """Mask phone number middle digits"""
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
    """Detect country name + flag from phone number"""
    try:
        parsed_number = phonenumbers.parse("+" + number, None)
        region = region_code_for_number(parsed_number)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name, country_to_flag(region)
    except Exception:
        pass
    return "Unknown", "🏳️"


def extract_otp(message: str) -> str:
    """Extract OTP code from message with multiple regex patterns"""
    patterns = [
        r'\b\d{3}-\d{3}\b',   # 111-111 format
        r'\b\d{3} \d{3}\b',   # 111 111 format
        r'\b\d{6}\b',         # 6-digit
        r'\b\d{4}\b',         # 4-digit
        r'\b\d{5}\b',         # 5-digit
        r'\b\d{7}\b',         # 7-digit
        r'\b\d{8}\b',         # 8-digit
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return re.sub(r'\D', '', match.group(0))
    return "N/A"


def send_to_telegram(text: str):
    """Send message to Telegram group with inline buttons"""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🤖 Number Buy", "url": "https://t.me/atik203412"},
                {"text": "✨ Support Group", "url": "https://t.me/atikmethod_zone"}
            ],
            [
                {"text": "🔗 Main Channel", "url": "https://t.me/atik_method_zone"},
                {"text": "🔗 Backup Channel", "url": "https://t.me/+8REFroGEWNM5ZjE9"}
            ]
        ]
    }
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
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
    """Extract new SMS messages using Selenium for JS-rendered table"""
    global last_messages
    try:
        driver.get(config.SMS_URL)
        driver.implicitly_wait(5)  # wait for JS to render table

        # Scroll table to load more rows if necessary
        scrollable_div = driver.find_element(By.CSS_SELECTOR, "div[role='grid']")  # adjust if needed
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(2)

        # Find all rows
        rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")  # adjust according to panel
        if not rows:
            print("[⚠️] No rows found. Make sure the table is rendered.")
            return

        for row in rows:
            try:
                number = row.find_element(By.CSS_SELECTOR, "div[data-column-id='4']").text.strip()
                sender = row.find_element(By.CSS_SELECTOR, "div[data-column-id='6']").text.strip()
                message = row.find_element(By.CSS_SELECTOR, "div[data-column-id='7']").text.strip()
            except:
                continue  # Skip rows that don't have all columns

            if not message or message in last_messages:
                continue
            last_messages.add(message)

            # Format and send
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            otp_code = extract_otp(message)
            country_name, country_flag = detect_country(number)
            masked_number = mask_number(number)

            formatted = (
                f"🔥 **New OTP Captured! ({sender}) {country_flag}**\n\n"
                f"🕒 **Time:** {timestamp}\n"
                f"{country_flag} **Country:** {country_name}\n"
                f"🌐 **Sender:** {sender}\n"
                f"📞 **Number:** `{masked_number}`\n"
                f"🔐 **OTP:** `{otp_code}`\n\n"
                f"💬 **Full Message:**\n"
                f"```{message}```"
            )

            send_to_telegram(formatted)

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")


if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # chrome_options.add_argument("--headless=new")  # optional

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("[*] SMS Extractor running. Press Ctrl+C to stop.")
        while True:
            extract_sms(driver)
            time.sleep(10)  # refresh every 10s
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    finally:
        driver.quit()
        print("[*] Browser closed.")
