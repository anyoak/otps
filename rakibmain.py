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
import config  # BOT_TOKEN, CHAT_ID, SMS_URL, LOGIN_URL, TIMEZONE_OFFSET

# Cache for sent messages
last_messages = set()

def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "**" + digits[-4:]
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
    patterns = [
        r'\b\d{3}-\d{3}\b',
        r'\b\d{3}\s\d{3}\b',
        r'\b\d{6}\b',
        r'\b\d{4,8}\b'
    ]
    for p in patterns:
        m = re.search(p, message)
        if m:
            return re.sub(r'\D', '', m.group(0))
    return "N/A"

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "🚀 Number Channel", "url": "https://t.me/number_group_kr"}],
            [
                {"text": "🔗 Main Channel", "url": "https://t.me/+BYBSV6960Ds5OGM9"},
                {"text": "💬 Support Group", "url": "https://t.me/kr_support_group"}
            ]
        ]
    }

import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry
import config  # BOT_TOKEN, CHAT_ID, SMS_URL, LOGIN_URL, TIMEZONE_OFFSET

# Cache to prevent duplicate messages
last_messages = set()

def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "**" + digits[-4:]
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
    patterns = [
        r'\b\d{6}\b',
        r'\b\d{5}\b',
        r'\b\d{4}\b',
        r'\b\d{3}-\d{3}\b',
        r'\b\d{3}\s\d{3}\b'
    ]
    for p in patterns:
        m = re.search(p, message)
        if m:
            return re.sub(r'\D', '', m.group(0))
    return "N/A"

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [{"text": "🚀 Number Channel", "url": "https://t.me/number_group_kr"}],
            [
                {"text": "🔗 Main Channel", "url": "https://t.me/+BYBSV6960Ds5OGM9"},
                {"text": "💬 Support Group", "url": "https://t.me/kr_support_group"}
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
            print(f"[❌] Telegram error: {res.status_code} {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request failed: {e}")

def wait_for_manual_login(driver):
    print("[🔐] Opening login page for manual login...")
    driver.get(config.LOGIN_URL)
    print("[🕒] Please log in manually in the browser window.")
    while True:
        current_url = driver.current_url
        if "login" not in current_url.lower():
            print("[✅] Login detected, continuing...")
            break
        time.sleep(2)

def extract_sms(driver):
    global last_messages
    try:
        driver.get(config.SMS_URL)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find("table")
        if not table:
            print("[⚠️] SMS table not found")
            return

        headers = table.find_all("th")
        number_idx = service_idx = sms_idx = None
        for idx, th in enumerate(headers):
            label = th.get_text(strip=True).lower()
            if "number" in label:
                number_idx = idx
            elif "cli" in label or "service" in label:
                service_idx = idx
            elif "sms" in label or "message" in label:
                sms_idx = idx

        if None in (number_idx, service_idx, sms_idx):
            print("[⚠️] Could not detect table columns.")
            return

        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True)
            service = cols[service_idx].get_text(strip=True)
            message = cols[sms_idx].get_text(strip=True)

            if not message or message in last_messages or message.strip() in ("0", "Unknown"):
                continue

            last_messages.add(message)
            timestamp = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)

            otp = extract_otp(message)
            country, flag = detect_country(number)
            masked = mask_number(number)

            formatted = (
                f"{flag} **{country.upper()} [{service.upper()} OTP] RECEIVED**\n"
                f"🕒 **Time:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🌍 **Country:** {country} {flag}\n"
                f"⚙️ **Service / CLI:** {service}\n"
                f"📞 **Number:** `{masked}`\n"
                f"🔑 **OTP:** `{otp}`\n\n"
                f"💬 **Full Message:**\n"
                f"```{message.strip()}```"
            )

            send_to_telegram(formatted)

    except Exception as e:
        print(f"[ERR] SMS extraction failed: {e}")

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except WebDriverException as e:
        print(f"[❌] WebDriver error: {e}")
        exit(1)

    try:
        wait_for_manual_login(driver)
        print("[*] SMS Extractor running. Press Ctrl+C to stop.")

        # Send last 3 messages for testing after login
        for _ in range(3):
            extract_sms(driver)
            time.sleep(1)

        # Main loop - 24/7 monitoring
        while True:
            extract_sms(driver)
            time.sleep(5)  # adjust frequency as needed

    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    except Exception as e:
        print(f"[❌] Unexpected error: {e}")
    finally:
        driver.quit()
        print("[*] Browser closed.")
