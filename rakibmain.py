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
import hashlib
import json
import os

import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Persistent cache for sent messages
CACHE_FILE = "sent_messages_cache.json"

def load_cache():
    """Load cache from file"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_cache(cache):
    """Save cache to file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(list(cache), f)
    except Exception as e:
        print(f"[⚠️] Cache save error: {e}")

def mask_number(number: str) -> str:
    """Mask phone number middle digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "**" + digits[-4:]
    return number

def country_to_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🇺🇳"
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
    return "Unknown", "🇺🇳"

def extract_otp(message: str) -> str:
    """Extract OTP code from message with improved pattern matching"""
    # WhatsApp style codes
    whatsapp_patterns = [
        r'\b\d{3}-\d{3}\b',  # 111-111 format
        r'\b\d{3} \d{3}\b',  # 111 111 format
        r'\b\d{6}\b',        # 111111 format
    ]
    
    for pattern in whatsapp_patterns:
        match = re.search(pattern, message)
        if match:
            clean_code = re.sub(r'\D', '', match.group(0))
            if len(clean_code) == 6:
                return clean_code
    
    # Other common OTP patterns
    common_patterns = [
        r'\b\d{4}\b',  # 4-digit codes
        r'\b\d{5}\b',  # 5-digit codes
        r'\b\d{6}\b',  # 6-digit codes
    ]
    
    for pattern in common_patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(0)
    
    return "N/A"

def create_message_hash(number: str, message: str, timestamp: str = "") -> str:
    """Create unique hash for message to avoid duplicates"""
    content = f"{number}_{message.strip()}_{timestamp}"
    return hashlib.md5(content.encode()).hexdigest()

def send_to_telegram(number, country_name, country_flag, service, masked_number, otp_code, message, timestamp):
    """Send message with the new format"""
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

    formatted = (
        f"{country_flag} {country_name} {service.upper()} RECEIVED \n"
        f"⏰ Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🌍 Country: {country_name} {country_flag}\n"
        f"⚙️ Service: {service.upper()}\n"
        f"☎️ Number: {masked_number}\n\n"
        f"🔑 OTP: {otp_code}\n\n"
        f"📩 Full Message:\n"
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
            print(f"[✅] Telegram message sent for {service} - {otp_code}")
            return True
        else:
            print(f"[❌] Failed: {res.status_code} - {res.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")
        return False

def extract_sms(driver, sent_messages_cache):
    """Extract SMS with improved duplicate detection"""
    
    try:
        driver.get(config.SMS_URL)
        time.sleep(3)
        
        # Refresh for latest messages
        driver.refresh()
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        table = soup.find('table', {'class': 'data-tbl-boxy'})
        
        if not table:
            print("[⚠️] Could not find SMS table.")
            return sent_messages_cache, False

        # Get column indices
        headers = table.find_all('th')
        column_indices = {}
        
        for idx, header in enumerate(headers):
            header_text = header.get_text(strip=True)
            if "Number" in header_text:
                column_indices['number'] = idx
            elif "CLI" in header_text:
                column_indices['service'] = idx
            elif "SMS" in header_text:
                column_indices['sms'] = idx
            elif "Date" in header_text:
                column_indices['date'] = idx

        required_columns = ['number', 'service', 'sms']
        if not all(col in column_indices for col in required_columns):
            print(f"[⚠️] Missing required columns. Found: {list(column_indices.keys())}")
            return sent_messages_cache, False

        # Process rows
        rows = table.find_all('tr')[1:]
        cache_updated = False
        new_messages_count = 0
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) <= max(column_indices.values()):
                continue

            number = cols[column_indices['number']].get_text(strip=True) or "Unknown"
            service = cols[column_indices['service']].get_text(strip=True) or "Unknown"
            message = cols[column_indices['sms']].get_text(strip=True)
            date_text = cols[column_indices['date']].get_text(strip=True) if 'date' in column_indices else ""
            
            # Skip invalid messages
            if (not message or message.strip() in ("0", "Unknown", "") or
                number in ("0", "Unknown") or service in ("0", "Unknown")):
                continue
            
            # Create unique hash with date to avoid duplicates
            message_hash = create_message_hash(number, message, date_text)
            
            # Skip if already processed
            if message_hash in sent_messages_cache:
                continue
                
            # New message found
            cache_updated = True
            new_messages_count += 1
            
            # Extract OTP and other details
            otp_code = extract_otp(message)
            country_name, country_flag = detect_country(number)
            masked_number = mask_number(number)
            timestamp = datetime.utcnow() + timedelta(hours=6)
            
            # Send to Telegram
            success = send_to_telegram(
                number=number,
                country_name=country_name,
                country_flag=country_flag,
                service=service,
                masked_number=masked_number,
                otp_code=otp_code,
                message=message,
                timestamp=timestamp
            )
            
            if success:
                sent_messages_cache.add(message_hash)
            
            time.sleep(1)  # Rate limiting
        
        if new_messages_count > 0:
            print(f"[📊] {new_messages_count} new messages processed")
        
        return sent_messages_cache, cache_updated
        
    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")
        return sent_messages_cache, False

def cleanup_old_cache(cache):
    """Clean up old cache entries"""
    if len(cache) > 1000:
        # Convert to list, keep last 500, convert back to set
        new_cache = set(list(cache)[-500:])
        print(f"[🧹] Cleaned up cache: {len(cache)} -> {len(new_cache)}")
        return new_cache
    return cache

if __name__ == "__main__":
    # Load existing cache
    sent_messages_cache = load_cache()
    print(f"[📁] Loaded {len(sent_messages_cache)} previously sent messages from cache")
    
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # chrome_options.add_argument("--headless=new")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print("[*] 🚀 Smart SMS Extractor Started!")
        print("[*] 📱 Monitoring for NEW messages only...")
        print("[*] ⏰ Press Ctrl+C to stop.")
        
        processed_count = 0
        
        while True:
            # Process messages and get updated cache
            sent_messages_cache, cache_updated = extract_sms(driver, sent_messages_cache)
            
            # Save cache if updated
            if cache_updated:
                save_cache(sent_messages_cache)
                print("[💾] Cache saved to file")
            
            processed_count += 1
            
            # Cleanup cache periodically
            if processed_count % 10 == 0:
                old_size = len(sent_messages_cache)
                sent_messages_cache = cleanup_old_cache(sent_messages_cache)
                if len(sent_messages_cache) != old_size:
                    save_cache(sent_messages_cache)
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    except Exception as e:
        print(f"\n[💥] Unexpected error: {e}")
    finally:
        # Save cache before exiting
        save_cache(sent_messages_cache)
        driver.quit()
        print("[*] Browser closed.")
        print(f"[📊] Total unique messages in cache: {len(sent_messages_cache)}")
