import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import config  # BOT_TOKEN, CHAT_ID, SMS_URL
import re
import phonenumbers
from phonenumbers import geocoder, region_code_for_number

# Cache for sent messages
last_messages = set()

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print(f"[✅] Telegram new OTP sent.")
        else:
            print(f"[❌] Failed to send Telegram message: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")

def mask_number(number: str) -> str:
    """Mask phone number middle 3 digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return number[:4] + "***" + number[-3:]
    return number

def country_to_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def extract_sms(driver):
    global last_messages

    try:
        driver.get(config.SMS_URL)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        headers = soup.find_all('th')

        number_idx = service_idx = sms_idx = None

        for idx, th in enumerate(headers):
            label = th.get('aria-label', '').lower()
            if 'number' in label:
                number_idx = idx
            elif 'cli' in label or 'service' in label:
                service_idx = idx
            elif 'sms' in label:
                sms_idx = idx

        if None in (number_idx, service_idx, sms_idx):
            print("[⚠️] Could not detect all required columns.")
            return

        rows = soup.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True) or "Unknown"
            service = cols[service_idx].get_text(strip=True) or "Unknown"
            message = cols[sms_idx].get_text(strip=True)

            # Skip blanks
            if not message or message in last_messages:
                continue
            if message.strip() in ("0", "Unknown") or (number in ("0", "Unknown") and service in ("0", "Unknown")):
                continue

            last_messages.add(message)
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time

            # OTP detection
            otp_line = next((line for line in message.split('\n') if 'code' in line.lower()), '')
            code_match = re.search(r'\b\d{4,8}\b', message)
            otp_code = code_match.group(0) if code_match else (otp_line.strip() if otp_line else "N/A")

            # Country detection
            try:
                parsed_number = phonenumbers.parse("+" + number, None)
                country_name = geocoder.description_for_number(parsed_number, "en") or "Unknown"
                region = region_code_for_number(parsed_number)
                country_flag = country_to_flag(region)
            except:
                country_name = "Unknown"
                country_flag = "🏳️"

            masked_number = mask_number(number)

            formatted = (
                f"🔥 *New OTP Captured!{service} of {country_flag}*\n\n"
                f"🕒 *Time:* {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{country_flag} *Country:* {country_name}\n"
                f"🌐 *Service:* {service}\n"
                f"📞 *Number:* `{masked_number}`\n"
                f"🔑 *OTP:* `{otp_code}`\n\n"
                f"💬 *Full Message:*\n"
                f"> {message.strip()}"
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
