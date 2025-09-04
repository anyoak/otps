import time, re, requests, json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import phonenumbers
from phonenumbers import geocoder
import config

# Cache for sent messages
last_messages = set()

# Telegram send function
def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print(f"[✅] Telegram message sent.")
        else:
            print(f"[❌] Failed: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")

# Mask number like 88017****566
def mask_number(number: str) -> str:
    number = str(number)
    if len(number) > 8:
        return number[:5] + "****" + number[-3:]
    elif len(number) > 5:
        return number[:2] + "****" + number[-2:]
    else:
        return number

# Auto country detection + flag
def get_country_info(number: str):
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
    except:
        return "🏳️", "Unknown"

# Extract SMS and send
def extract_sms(driver):
    global last_messages
    try:
        driver.get(config.SMS_URL)
        time.sleep(2)

        # Save cookies automatically
        with open("cookies.json", "w") as f:
            json.dump(driver.get_cookies(), f)

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
            timestamp = datetime.utcnow() + timedelta(hours=6)

            # Extract OTP code
            match = re.search(r'\b\d{4,8}\b', message)
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

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")
