import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import config
import re
import phonenumbers
from phonenumbers import geocoder, timezone
import pytz

# Cache for sent messages
last_messages = set()

def get_country_flag(region_code: str) -> str:
    """Convert ISO region code (e.g. 'US', 'IN') into emoji flag."""
    if not region_code or len(region_code) != 2:
        return "🏳️"
    try:
        return chr(127397 + ord(region_code[0].upper())) + chr(127397 + ord(region_code[1].upper()))
    except:
        return "🏳️"

def get_local_time(region_code: str) -> str:
    """Return local time based on region code."""
    try:
        timezones = timezone.time_zones_for_country(region_code)
        if timezones:
            tz = pytz.timezone(timezones[0])
            return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    # fallback → UTC
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🤖 Number Bot", "url": "https://t.me/Atik_number_bot"},
                    {"text": "🔑 GET OTP", "url": "https://t.me/atik_methodzone_Otp"}
                ],
                [
                    {"text": "🔗 Main Channel", "url": "https://t.me/atik_method_zone"},
                    {"text": "🔗 Backup Channel", "url": "https://t.me/+8REFroGEWNM5ZjE9"}
                ]
            ]
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"[✅] Telegram message sent.")
        else:
            print(f"[❌] Failed to send Telegram message: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")

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

        rows = soup.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True) or "Unknown"
            service = cols[service_idx].get_text(strip=True) or "Unknown"
            message = cols[sms_idx].get_text(strip=True)

            if not message or message in last_messages:
                continue

            last_messages.add(message)

            # OTP detect (any language)
            code_match = re.search(r'\b\d{4,8}\b', message)
            otp_code = code_match.group(0) if code_match else "N/A"

            # Detect country + flag + local time
            try:
                parsed_number = phonenumbers.parse("+" + number, None)
                country_name = geocoder.description_for_number(parsed_number, "en")
                region_code = phonenumbers.region_code_for_number(parsed_number)
                country_flag = get_country_flag(region_code)
                local_time = get_local_time(region_code)
            except:
                country_name = "Unknown"
                country_flag = "🏳️"
                local_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            formatted = (
                f"🔥 {country_name} OTP RECEIVED! ✨\n\n"
                f"🕒 Time: {local_time}\n"
                f"{country_flag} Country: {country_name}\n"
                f"📱 Service: {service}\n"
                f"📞 Number: {number}\n"
                f"🔑 OTP:\n```{otp_code}```\n\n"
                f"💬 Full Message:\n{message.strip()}"
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
