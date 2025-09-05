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
    # Remove common special characters that might be used as separators
    cleaned_message = re.sub(r'[\.\-\s\(\)\[\]\{\}]', '', message)
    
    # Look for OTP patterns in multiple languages
    patterns = [
        r'(?<=codeis)\d{4,8}',  # English variants
        r'(?<=codice)\d{4,8}',   # Italian
        r'(?<=codigo)\d{4,8}',   # Spanish/Portuguese
        r'(?<=代码)\d{4,8}',      # Chinese
        r'(?<=コード)\d{4,8}',    # Japanese
        r'\b\d{4,8}(?=isyourcode)',  # English reverse pattern
        r'\b\d{4,8}(?=istihrkod)',   # German
        r'\b\d{4,8}(?=codevalide)',  # French
        r'\b\d{4,8}(?=seucodigo)',   # Portuguese
        r'(?<=otp[:]?)\d{4,8}',      # OTP prefix
        r'(?<=密码[:]?)\d{4,8}',      # Chinese password
        r'\b\d{4,8}(?=验证码)',       # Chinese verification code
        r'\b\d{4,8}(?=是你的验证码)',  # Chinese verification code
        r'\b\d{3}[-]\d{3}\b',        # WhatsApp-style 111-111 format
        r'\b\d{3}[\s]\d{3}\b',       # WhatsApp-style 111 111 format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            # Remove any non-digit characters for consistent formatting
            return re.sub(r'\D', '', match.group(0))
    
    # Final fallback - any 3-3 or 4-8 digit sequence
    digits = re.findall(r'\b\d{3}[- ]\d{3}\b|\d{4,8}', message)
    if digits:
        # Return the first match without any separators
        return re.sub(r'\D', '', digits[0])
    
    return "N/A"


def send_to_telegram(text: str, otp_code: str):
    """Send message with inline buttons including Copy OTP button"""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🤖 Number Bot", "url": "https://t.me/Atik_number_bot"},
                {"text": "✨ Support Group", "url": "https://t.me/atikmethod_zone"}
            ],
            [
                {"text": "🔗 BackUp Channel", "url": "https://t.me/+8REFroGEWNM5ZjE9"},
                {"text": "🔗 Main Channel", "url": "https://t.me/atik_method_zone"}
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
    global last_messages
    try:
        driver.get(config.SMS_URL)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headers = soup.find_all("th")

        number_idx = service_idx = sms_idx = None
        for idx, th in enumerate(headers):
            label = th.get("aria-label", "").lower()
            if "number" in label:
                number_idx = idx
            elif "cli" in label or "service" in label:
                service_idx = idx
            elif "sms" in label:
                sms_idx = idx

        if None in (number_idx, service_idx, sms_idx):
            print("[⚠️] Could not detect all required columns.")
            return

        rows = soup.find_all("tr")[1:]  # skip header row
        for row in rows:
            cols = row.find_all("td")
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True) or "Unknown"
            service = cols[service_idx].get_text(strip=True) or "Unknown"
            message = cols[sms_idx].get_text(strip=True)

            if not message or message in last_messages:
                continue
            if message.strip() in ("0", "Unknown") or (
                number in ("0", "Unknown") and service in ("0", "Unknown")
            ):
                continue

            last_messages.add(message)
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time

            otp_code = extract_otp(message)
            country_name, country_flag = detect_country(number)
            masked_number = mask_number(number)

            formatted = (
                f"🔥 **New OTP Captured! {service} of {country_flag}**\n\n"
                f"🕒 **Time:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{country_flag} **Country:** {country_name}\n"
                f"🌐 **Service:** {service}\n"
                f"📞 **Number:** `{masked_number}`\n"
                f"🔐 **OTP:** `{otp_code}`\n\n"
                f"💬 **Full Message:**\n"
                f"```{message.strip()}```"
            )

            send_to_telegram(formatted, otp_code)

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
