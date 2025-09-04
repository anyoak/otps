import time
import re
import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import phonenumbers
from phonenumbers import geocoder
import config

# Cache for sent messages
LAST_MESSAGES_FILE = "last_messages.json"
MAX_MESSAGES = 1000  # Limit memory usage

def load_last_messages():
    """Load cached messages from file."""
    try:
        if os.path.exists(LAST_MESSAGES_FILE):
            with open(LAST_MESSAGES_FILE, "r") as f:
                return set(json.load(f))
        return set()
    except Exception as e:
        print(f"[⚠️] Failed to load last messages: {e}")
        return set()

def save_last_messages(messages):
    """Save cached messages to file."""
    try:
        with open(LAST_MESSAGES_FILE, "w") as f:
            json.dump(list(messages)[:MAX_MESSAGES], f)
        print("[✅] Last messages saved.")
    except Exception as e:
        print(f"[⚠️] Failed to save last messages: {e}")

last_messages = load_last_messages()

def send_to_telegram(text: str):
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print("[✅] Telegram message sent.")
        else:
            print(f"[❌] Telegram failed: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")

def mask_number(number: str) -> str:
    """Mask phone number for privacy."""
    number = str(number)
    if len(number) > 8:
        return number[:5] + "****" + number[-3:]
    elif len(number) > 5:
        return number[:2] + "****" + number[-2:]
    return number

def get_country_info(number: str):
    """Get country flag and name from phone number."""
    try:
        if not number.startswith('+'):
            number = '+' + number
        parsed = phonenumbers.parse(number, None)
        country_name = geocoder.description_for_number(parsed, "en")
        country_code = phonenumbers.region_code_for_number(parsed)
        if country_code:
            code = country_code.upper()
            flag = chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))
        else:
            flag = "🏳️"
        return flag, country_name
    except phonenumbers.NumberParseException as e:
        print(f"[⚠️] Failed to parse number {number}: {e}")
        return "🏳️", "Unknown"

def extract_sms(driver):
    """Extract SMS from page and send to Telegram."""
    global last_messages
    for attempt in range(3):
        try:
            driver.get(config.SMS_URL)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            headers = soup.find_all('th')

            number_idx = service_idx = sms_idx = None
            for idx, th in enumerate(headers):
                label = th.get('aria-label', '').lower() or th.get_text(strip=True).lower()
                if 'number' in label:
                    number_idx = idx
                elif 'cli' in label or 'service' in label:
                    service_idx = idx
                elif 'sms' in label or 'message' in label:
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
                if len(last_messages) > MAX_MESSAGES:
                    last_messages.pop()  # Remove oldest message
                save_last_messages(last_messages)

                timestamp = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)

                match = re.search(r'\b[A-Za-z0-9]{4,8}\b', message)
                otp_code = match.group(0) if match else "Unknown"

                masked_number = mask_number(number)
                country_flag, country_name = get_country_info(number)

                html_message = f"""
<b>🔐 New OTP Captured</b>
<pre>──────────────────────────</pre>
<b>🕒 Time:</b> <code>{timestamp.strftime('%Y-%m-%d %H:%M:%S')}</code>
<b>🔗 Service:</b> <code>{service}</code>
<b>📞 Number:</b> <code>{masked_number}</code>
<b>{country_flag} Country:</b> <code>{country_name}</code>
<b>✅ OTP Code:</b> <code>{otp_code}</code>
<b>💬 Full Message:</b>
<tg-spoiler>{message.strip()}</tg-spoiler>
<pre>──────────────────────────</pre>
<i>🤖 Powered by Incognito</i>
"""
                send_to_telegram(html_message)
            return
        except Exception as e:
            print(f"[ERR] Failed to extract SMS (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                print("[❌] Max retries reached.")
