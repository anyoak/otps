import time
import re
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry
import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Store sent messages to avoid duplicates
last_messages = set()

# ------------------- Helper Functions -------------------

def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "***" + digits[-3:]
    return number

def country_to_flag(country_code: str) -> str:
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def detect_country(number: str):
    try:
        parsed = phonenumbers.parse("+" + number, None)
        region = region_code_for_number(parsed)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name, country_to_flag(region)
    except:
        pass
    return "Unknown", "🏳️"

def extract_otp(message: str) -> str:
    patterns = [r'\b\d{3}-\d{3}\b', r'\b\d{3} \d{3}\b', r'\b\d{6}\b',
                r'\b\d{4}\b', r'\b\d{5}\b', r'\b\d{7}\b', r'\b\d{8}\b']
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return re.sub(r'\D', '', match.group(0))
    return "N/A"

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "🤖 Number Buy", "url": "https://t.me/atik203412"},
             {"text": "✨ Support Group", "url": "https://t.me/atikmethod_zone"}],
            [{"text": "🔗 Main Channel", "url": "https://t.me/atik_method_zone"},
             {"text": "🔗 Backup Channel", "url": "https://t.me/+8REFroGEWNM5ZjE9"}]
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
    except Exception as e:
        print(f"[❌] Telegram error: {e}")

# ------------------- Core Extraction -------------------

def detect_columns(header_row):
    """Map NUMBER, SENDER, MESSAGE column dynamically"""
    mapping = {"number": 0, "sender": 0, "message": 0}  # default
    try:
        cells = header_row.find_elements(By.CSS_SELECTOR, "div[role='columnheader'], div[role='cell']")
        for idx, cell in enumerate(cells):
            text = cell.text.lower()
            if "number" in text:
                mapping["number"] = idx
            elif "sender" in text:
                mapping["sender"] = idx
            elif "message" in text:
                mapping["message"] = idx
    except:
        pass
    return mapping

def extract_sms(driver):
    global last_messages
    try:
        # Wait for table
        scrollable_div = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='table']"))
        )

        # Scroll table fully
        last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
        while True:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
            time.sleep(1)
            new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            if new_height == last_height:
                break
            last_height = new_height

        # Fetch all rows
        rows = scrollable_div.find_elements(By.CSS_SELECTOR, "div[role='row']")
        if not rows:
            print("[⚠️] No rows found.")
            return

        mapping = detect_columns(rows[0])
        new_count = 0

        for row in rows[1:]:
            try:
                cells = row.find_elements(By.CSS_SELECTOR, "div[role='cell']")
                if len(cells) < 7:
                    continue

                number = cells[mapping["number"]].text.strip()
                sender = cells[mapping["sender"]].text.strip()
                message = cells[mapping["message"]].text.strip()

                if not message or message in last_messages:
                    continue
                last_messages.add(message)
                new_count += 1

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
            except:
                continue

        print(f"[ℹ️] {new_count} new messages processed.")

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")

# ------------------- Main -------------------

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # chrome_options.add_argument("--headless=new")  # optional

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(config.SMS_URL)

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
