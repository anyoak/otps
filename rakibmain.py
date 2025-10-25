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

import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Cache for sent messages to avoid duplicates
sent_messages_cache = set()
last_processed_hash = None

def mask_number(number: str) -> str:
    """Mask phone number middle digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "**" + digits[-4:]
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

def create_message_hash(number: str, message: str) -> str:
    """Create unique hash for message to avoid duplicates"""
    content = f"{number}_{message.strip()}"
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

    # New message format as requested with code block for message
    formatted = (
        f"{country_flag} {country_name} {service.upper()} OTP RECEIVED \n"
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

def extract_sms(driver):
    global sent_messages_cache, last_processed_hash
    
    try:
        driver.get(config.SMS_URL)
        time.sleep(3)  # Wait for page to load completely
        
        # Refresh the page to get latest messages
        driver.refresh()
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Find the SMS table
        table = soup.find('table', {'class': 'data-tbl-boxy'})
        if not table:
            print("[⚠️] Could not find SMS table.")
            return

        # Extract column indices from table header
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

        # Check if we have required columns
        required_columns = ['number', 'service', 'sms']
        if not all(col in column_indices for col in required_columns):
            print(f"[⚠️] Missing required columns. Found: {list(column_indices.keys())}")
            return

        # Process table rows
        rows = table.find_all('tr')[1:]  # Skip header row
        
        current_batch_hash = ""
        new_messages_found = False
        
        for row in rows:
            cols = row.find_all('td')
            
            # Skip if not enough columns
            if len(cols) <= max(column_indices.values()):
                continue

            # Extract data
            number = cols[column_indices['number']].get_text(strip=True) or "Unknown"
            service = cols[column_indices['service']].get_text(strip=True) or "Unknown"
            message = cols[column_indices['sms']].get_text(strip=True)
            
            # Skip invalid messages
            if (not message or 
                message.strip() in ("0", "Unknown", "") or
                number in ("0", "Unknown") or
                service in ("0", "Unknown")):
                continue
            
            # Create unique hash for this message
            message_hash = create_message_hash(number, message)
            current_batch_hash += message_hash
            
            # Skip if already processed
            if message_hash in sent_messages_cache:
                continue
                
            new_messages_found = True
            
            # Extract OTP
            otp_code = extract_otp(message)
            
            # Detect country
            country_name, country_flag = detect_country(number)
            
            # Mask number
            masked_number = mask_number(number)
            
            # Create timestamp
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time
            
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
                
            # Small delay between messages to avoid rate limiting
            time.sleep(1)
        
        # Update last processed hash if new messages were found
        if new_messages_found:
            last_processed_hash = hashlib.md5(current_batch_hash.encode()).hexdigest()
            print(f"[📊] Processed batch with {len(rows)} rows")
        
    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")

def cleanup_old_cache():
    """Clean up old cache entries to prevent memory issues"""
    global sent_messages_cache
    if len(sent_messages_cache) > 1000:
        # Keep only the last 500 entries
        sent_messages_cache = set(list(sent_messages_cache)[-500:])
        print("[🧹] Cleaned up old cache entries")

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # For faster performance, you can enable headless after testing
    # chrome_options.add_argument("--headless=new")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        print("[*] 🚀 Advanced SMS Extractor Started!")
        print("[*] 📱 Monitoring for new messages...")
        print("[*] ⏰ Press Ctrl+C to stop.")
        
        processed_count = 0
        
        while True:
            extract_sms(driver)
            processed_count += 1
            
            # Cleanup cache every 10 cycles
            if processed_count % 10 == 0:
                cleanup_old_cache()
            
            # Faster polling for new messages
            time.sleep(5)  # Check every 5 seconds for new messages
            
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    except Exception as e:
        print(f"\n[💥] Unexpected error: {e}")
    finally:
        driver.quit()
        print("[*] Browser closed.")
        print(f"[📊] Total unique messages processed: {len(sent_messages_cache)}")
