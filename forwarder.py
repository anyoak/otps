import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import config  # BOT_TOKEN, CHAT_ID, SMS_URL
import re
import phonenumbers
from phonenumbers import geocoder

# Cache for sent messages
last_messages = set()

def mask_number(number):
    """
    Mask the middle digits of a number
    Example: 880171234566 -> 88017**566
    """
    number = re.sub(r'\D', '', number)  # remove non-digit chars
    if len(number) >= 8:
        return number[:5] + '**' + number[-3:]
    return number

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "HTML"  # HTML mode for spoiler & code
    }
    try:
        res = requests.post(url, data=payload, timeout=10)
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

        rows = soup.find_all('tr')[1:]  # Skip header row
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
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time

            code_match = re.search(r'\b\d{4,8}\b', message)
            otp_code = code_match.group(0) if code_match else "N/A"

            # Detect country from number
            try:
                parsed_number = phonenumbers.parse("+" + number, None)
                country_name = geocoder.description_for_number(parsed_number, "en")
                country_flag = {
                    "Côte d'Ivoire": "🇨🇮",
                    "Venezuela": "🇻🇪",
                    "Bangladesh": "🇧🇩",
                    "United States": "🇺🇸",
                    "India": "🇮🇳",
                    "Nigeria": "🇳🇬",
                    "Pakistan": "🇵🇰",
                    "Indonesia": "🇮🇩",
                    "Brazil": "🇧🇷",
                    "Mexico": "🇲🇽"
                }.get(country_name, "🏳️")
            except:
                country_name = "Unknown"
                country_flag = "🏳️"

            masked_number = mask_number(number)

            html_message = f"""
<b>🔐 New OTP Captured</b>
<pre>──────────────────────────</pre>
<b>🕒 Time:</b> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
<b>📱 Service:</b> {service}
<b>📞 Number:</b> <code>{masked_number}</code>
<b>{country_flag} Country:</b> {country_name}
<b>✅ OTP Code:</b> <code>{otp_code}</code>

<b>💬 Full Message:</b>
<tg-spoiler>{message.strip()}</tg-spoiler>
<pre>──────────────────────────</pre>
<i>🤖 Powered by Incognito</i>
"""
            send_to_telegram(html_message)

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")


if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless=new")  # GUI না থাকলেও run হবে

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
