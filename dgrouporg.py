import time
import re
import requests
import json
import os
import tempfile
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8371638048:AAEHGvy-vYHmUFPXslg-2toZgOA_14osM9k"
CHAT_ID = "-1002287664519"
BASE_URL = "https://d-group.stats.direct/dashboard"
LOGIN_URL = "https://d-group.stats.direct/user-management/auth/login"
SMS_URL = "https://d-group.stats.direct/sms-records/index"
REFRESH_INTERVAL = 3  # Reduced from 5 to 3 seconds
MAX_MESSAGES_STORE = 2000
SCROLL_ATTEMPTS = 2  # Reduced from 3 to 2
# =======================================================

# Store sent messages to avoid duplicates
last_messages = set()
driver = None

# ------------------- Source Name Detection -------------------

def detect_source_name(message: str, website_source: str) -> str:
    """
    Detect source name from message content for popular services
    """
    message_lower = message.lower()
    
    # Telegram patterns
    telegram_patterns = [
        r'telegram', r'tg\.me', r't\.me', r'@', r'username', 
        r'login code', r'verification code', r'confirm your phone',
        r'telegram code', r'tg code'
    ]
    
    # WhatsApp patterns - ENHANCED
    whatsapp_patterns = [
        r'whatsapp', r'wa\.me', r'whats app', r'whatsapp code',
        r'whatsapp verification', r'your whatsapp code',
        r'whatsapp.*code', r'code.*whatsapp', r'whatsapp.*verify',
        r'verification.*whatsapp', r'whatsapp.*security'
    ]
    
    # Twilio patterns
    twilio_patterns = [
        r'twilio', r'twilio verification', r'twilio code',
        r'your twilio code'
    ]
    
    # Apple patterns
    apple_patterns = [
        r'apple', r'apple id', r'icloud', r'appstore',
        r'your apple id code', r'apple verification',
        r'use this code to reset your apple id password'
    ]
    
    # 1xBet patterns
    xbet_patterns = [
        r'1xbet', r'1x bet', r'1xbet code', r'1xbet verification',
        r'your 1xbet code', r'1xbet confirm'
    ]
    
    # Facebook patterns
    facebook_patterns = [
        r'facebook', r'fb\.me', r'facebook code', r'facebook login',
        r'your facebook code', r'facebook confirmation'
    ]
    
    # Google patterns
    google_patterns = [
        r'google', r'g-\d{6}', r'google verification', r'your google verification code',
        r'google account', r'gmail'
    ]
    
    # Instagram patterns
    instagram_patterns = [
        r'instagram', r'insta', r'ig', r'instagram code',
        r'your instagram code', r'instagram confirmation'
    ]
    
    # Twitter patterns
    twitter_patterns = [
        r'twitter', r'twitter code', r'twitter verification',
        r'your twitter code'
    ]
    
    # Amazon patterns
    amazon_patterns = [
        r'amazon', r'amazon code', r'amazon otp',
        r'your amazon verification code'
    ]
    
    # Bank patterns
    bank_patterns = [
        r'bank', r'visa', r'mastercard', r'card', r'transaction',
        r'payment', r'otp', r'one time password', r'secure code'
    ]
    
    # Check each service
    services = [
        ("WhatsApp", whatsapp_patterns),  # WhatsApp first for priority
        ("Telegram", telegram_patterns),
        ("Twilio", twilio_patterns),
        ("Apple", apple_patterns),
        ("1xBet", xbet_patterns),
        ("Facebook", facebook_patterns),
        ("Google", google_patterns),
        ("Instagram", instagram_patterns),
        ("Twitter", twitter_patterns),
        ("Amazon", amazon_patterns),
        ("Bank", bank_patterns),
    ]
    
    for service_name, patterns in services:
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                print(f"[🔍] Detected source: {service_name}")
                return service_name
    
    # If no specific service detected, use website source or generic
    if website_source and website_source.strip():
        return website_source.strip()
    else:
        return "Unknown Service"

# ------------------- Enhanced OTP Detection -------------------

def extract_otp(message: str) -> str:
    """
    Ultimate OTP detection for all languages and formats
    """
    if not message or len(message.strip()) < 4:
        return "N/A"
        
    clean_message = message.strip()
    
    # Comprehensive OTP patterns - ENHANCED FOR WHATSAPP
    patterns = [
        # WhatsApp specific patterns with dashes (111-111 type)
        r'\b\d{3}[-\.\s]\d{3}\b',               # 111-111, 111.111, 111 111
        r'\b\d{4}[-\.\s]\d{4}\b',               # 1111-1111, 1111.1111, 1111 1111
        r'\b\d{5}[-\.\s]\d{5}\b',               # 11111-11111, etc.
        
        # Standard formats (most common first)
        r'\b\d{6}\b',                           # 123456
        r'\b\d{4}\b',                           # 1234
        r'\b\d{5}\b',                           # 12345
        r'\b\d{3}[-\.\s]?\d{3}\b',              # 123-456, 123.456, 123 456
        r'\b\d{4}[-\.\s]?\d{4}\b',              # 1234-5678, 1234.5678, 1234 5678
        r'\b\d{8}\b',                           # 12345678
        
        # OTP with labels (English)
        r'(?i)(?:code|otp|password|verification|pin|passcode)[\s:\-]*[is\-\:\s]*[\{\[\(]?\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*[\}\]\)]?',
        r'(?i)(?:code|otp|password|verification|pin|passcode)[\s:\-]*[is\-\:\s]*(\d{3}[-\.\s]?\d{3}|\d{3,8})',
        r'(?i)(?:is|code|use)[\s:\-]*(\d{3}[-\.\s]?\d{3}|\d{4,8})',
        
        # OTP with labels (Multi-language)
        r'(?i)(?:код|код|密码|驗證碼|コード|코드|codice|codigo|código)[\s:\-]*[is\-\:\s]*[\{\[\(]?\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*[\}\]\)]?',
        
        # WhatsApp specific patterns
        r'\*\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*\*',                # *123456*, *123-456*
        r'\[\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*\]',                # [123456], [123-456]
        r'\(\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*\)',                # (123456), (123-456)
        
        # Google/Apple format
        r'[GA]\-\s*(\d{6})',                   # G-123456, A-123456
        
        # Telegram common patterns
        r'Your verification code is\s*[\{\[\(]?\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*[\}\]\)]?',
        r'verification code[\s:\-]*[\{\[\(]?\s*(\d{3}[-\.\s]?\d{3}|\d{4,8})\s*[\}\]\)]?',
        
        # Common SMS patterns
        r'use[\s]+(\d{3}[-\.\s]?\d{3}|\d{4,8})[\s]+to',
        r'enter[\s]+(\d{3}[-\.\s]?\d{3}|\d{4,8})[\s]+',
        r'code[\s]+(\d{3}[-\.\s]?\d{3}|\d{4,8})[\s]+',
        
        # Bank OTP patterns
        r'OTP[\s:\-]*(\d{6})',
        r'one time password[\s:\-]*(\d{6})',
        r'transaction password[\s:\-]*(\d{6})',
        
        # Social media patterns
        r'Facebook[\s\S]*?code[\s:\-]*(\d{5})',
        r'Instagram[\s\S]*?code[\s:\-]*(\d{6})',
        r'Twitter[\s\S]*?code[\s:\-]*(\d{6})',
        
        # Emergency fallback - any 4-8 digit number not surrounded by other digits
        r'(?<!\d)(\d{4,8})(?!\d)',
    ]
    
    # First pass: try all patterns
    for pattern in patterns:
        try:
            matches = re.findall(pattern, clean_message, re.IGNORECASE | re.MULTILINE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Handle dash-separated OTPs (like 111-111)
                    otp_candidate = re.sub(r'[-\.\s]', '', str(match))  # Remove dashes, dots, spaces
                    
                    if 4 <= len(otp_candidate) <= 8 and otp_candidate.isdigit():
                        # Additional validation to avoid false positives
                        if not is_likely_date(otp_candidate) and not is_likely_time(otp_candidate):
                            print(f"[🔍] OTP Found: {otp_candidate} with pattern: {pattern}")
                            return otp_candidate
        except Exception as e:
            continue
    
    # Second pass: look for any standalone 4-8 digit numbers
    standalone_nums = re.findall(r'\b\d{4,8}\b', clean_message)
    for num in standalone_nums:
        if 4 <= len(num) <= 8 and num.isdigit():
            if not is_likely_date(num) and not is_likely_time(num) and not is_sequential(num):
                print(f"[🔍] OTP Found (standalone): {num}")
                return num
    
    # Third pass: specifically look for dash-separated patterns
    dash_patterns = [
        r'\b\d{3}-\d{3}\b',
        r'\b\d{4}-\d{4}\b',
        r'\b\d{3}\s\d{3}\b',
        r'\b\d{4}\s\d{4}\b'
    ]
    
    for pattern in dash_patterns:
        dash_matches = re.findall(pattern, clean_message)
        for match in dash_matches:
            otp_candidate = re.sub(r'[-\s]', '', match)
            if 6 <= len(otp_candidate) <= 8 and otp_candidate.isdigit():
                print(f"[🔍] OTP Found (dash-separated): {otp_candidate}")
                return otp_candidate
    
    return "N/A"

def is_likely_date(num: str) -> bool:
    """Check if number looks like a date"""
    if len(num) == 4:
        # Check if it's a valid time (e.g., 1234 -> 12:34)
        if 0 <= int(num[:2]) <= 23 and 0 <= int(num[2:]) <= 59:
            return True
        # Check if it's a year in reasonable range
        if 1900 <= int(num) <= 2100:
            return True
    elif len(num) == 6:
        # Check if it's a date (e.g., 010123 -> 01/01/23)
        if 1 <= int(num[:2]) <= 31 and 1 <= int(num[2:4]) <= 12:
            return True
    elif len(num) == 8:
        # Check if it's a full date (e.g., 01012023 -> 01/01/2023)
        if 1 <= int(num[:2]) <= 31 and 1 <= int(num[2:4]) <= 12 and 1900 <= int(num[4:]) <= 2100:
            return True
    return False

def is_likely_time(num: str) -> bool:
    """Check if number looks like a time"""
    if len(num) == 4:
        # HHMM format
        if 0 <= int(num[:2]) <= 23 and 0 <= int(num[2:]) <= 59:
            return True
    return False

def is_sequential(num: str) -> bool:
    """Check if number is sequential (1234, 4321, etc)"""
    if len(num) >= 4:
        # Check ascending
        if all(int(num[i]) + 1 == int(num[i+1]) for i in range(len(num)-1)):
            return True
        # Check descending
        if all(int(num[i]) - 1 == int(num[i+1]) for i in range(len(num)-1)):
            return True
        # Check same digits
        if len(set(num)) == 1:
            return True
    return False

# ------------------- Helper Functions -------------------

def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "***" + digits[-4:]
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

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Simple inline keyboard without copy button
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📢 Main Channel", "url": "https://t.me/+MahUeaLBpDcxNGJl"},
                {"text": "📋 Get Number", "url": "https://t.me/XRNUMBERCHANNEL"}
            ]
        ]
    }
    
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"[✅] Telegram message sent successfully")
            return True
        else:
            print(f"[❌] Failed: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"[❌] Telegram error: {e}")
        return False

# ------------------- Login & Navigation -------------------

def wait_for_manual_login():
    """Wait for user to manually login and detect successful login"""
    print("[🔐] Please login manually in the browser...")
    print("[⏳] Waiting for you to complete login...")
    
    # Navigate to login page first
    driver.get(LOGIN_URL)
    time.sleep(2)
    
    # Wait for user to login - detect when URL changes to dashboard
    print("[🎯] Waiting for dashboard page...")
    try:
        WebDriverWait(driver, 300).until(  # 5 minutes timeout for manual login
            EC.url_contains("/dashboard")
        )
        print("[✅] Login successful! Detected dashboard page.")
        
        # Additional check for dashboard elements
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "page-sidebar"))
        )
        print("[✅] Dashboard loaded completely.")
        
        return True
        
    except TimeoutException:
        print("[❌] Login timeout. Please check your login.")
        return False

def navigate_to_sms_page():
    """Navigate to SMS records page after successful login"""
    try:
        print("[🔄] Navigating to SMS records page...")
        driver.get(SMS_URL)
        
        # Wait for SMS page to load
        WebDriverWait(driver, 10).until(  # Reduced from 15 to 10
            EC.presence_of_element_located((By.CLASS_NAME, "kv-grid-table"))
        )
        print("[✅] SMS records page loaded successfully.")
        return True
        
    except Exception as e:
        print(f"[❌] Failed to navigate to SMS page: {e}")
        return False

def check_login_status():
    """Check if still logged in by verifying dashboard access"""
    try:
        current_url = driver.current_url
        if "/dashboard" in current_url or "/sms-records" in current_url:
            return True
        else:
            # Try to access dashboard
            driver.get(BASE_URL)
            time.sleep(1)  # Reduced from 2 to 1
            if "/dashboard" in driver.current_url:
                return True
        return False
    except:
        return False

# ------------------- SMS Extraction -------------------

def detect_columns(header_row):
    """Map columns based on the actual table structure from source code"""
    mapping = {"date": 0, "source": 2, "destination": 3, "message": 9}
    
    try:
        cells = header_row.find_elements(By.TAG_NAME, "th")
        for idx, cell in enumerate(cells):
            text = cell.text.strip().lower()
            if "date" in text:
                mapping["date"] = idx
            elif "source" in text:
                mapping["source"] = idx
            elif "destination" in text:
                mapping["destination"] = idx
            elif "message" in text:
                mapping["message"] = idx
    except Exception as e:
        print(f"[⚠️] Column detection warning: {e}")
    
    print(f"[📊] Column mapping: Date[{mapping['date']}], Source[{mapping['source']}], Destination[{mapping['destination']}], Message[{mapping['message']}]")
    return mapping

def scroll_table_to_bottom():
    """Scroll the table to load all messages"""
    try:
        # Find the table container
        table_container = driver.find_element(By.ID, "cdrs-pjax-container")
        
        for attempt in range(SCROLL_ATTEMPTS):
            last_height = driver.execute_script("return arguments[0].scrollHeight", table_container)
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", table_container)
            time.sleep(0.5)  # Reduced from 1 to 0.5
            new_height = driver.execute_script("return arguments[0].scrollHeight", table_container)
            
            if new_height == last_height:
                break
            print(f"[⬇️] Scrolling table... attempt {attempt + 1}")
            
    except Exception as e:
        print(f"[⚠️] Table scrolling issue: {e}")

def extract_sms():
    global last_messages
    try:
        # Wait for the table to be present (exact class from source code)
        WebDriverWait(driver, 10).until(  # Reduced from 15 to 10
            EC.presence_of_element_located((By.CLASS_NAME, "kv-grid-table"))
        )

        # Scroll to load all messages
        scroll_table_to_bottom()
        time.sleep(1)  # Reduced from 2 to 1

        # Find the table
        table = driver.find_element(By.CLASS_NAME, "kv-grid-table")
        
        # Get all rows from tbody
        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
        if not rows:
            print("[⚠️] No data rows found in table.")
            return 0

        # Get header row for column mapping
        header_row = table.find_element(By.CSS_SELECTOR, "thead tr")
        mapping = detect_columns(header_row)
        
        new_count = 0
        processed_count = 0

        print(f"[🔍] Scanning {len(rows)} rows for messages...")

        for row_index, row in enumerate(rows):
            try:
                # Skip empty rows or "no results" rows
                row_html = row.get_attribute("innerHTML").lower()
                if "empty" in row_html or "no results" in row_html:
                    continue
                    
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) <= max(mapping.values()):
                    continue

                # Extract data based on column mapping
                date = cells[mapping["date"]].text.strip()
                website_source = cells[mapping["source"]].text.strip()
                destination = cells[mapping["destination"]].text.strip()
                message = cells[mapping["message"]].text.strip()

                # Skip if no message
                if not message or message == "":
                    continue
                    
                # Create unique message ID (more specific)
                message_id = f"{website_source}_{destination}_{message[:50]}"
                processed_count += 1
                
                # Skip if already processed
                if message_id in last_messages:
                    continue
                    
                last_messages.add(message_id)
                new_count += 1

                # Extract OTP with enhanced detection
                otp_code = extract_otp(message)
                country_name, country_flag = detect_country(destination)
                masked_number = mask_number(destination)
                
                # Detect source name from message content
                source_name = detect_source_name(message, website_source)

                # Format the message for Telegram (new style)
                formatted = (
                    f"{country_flag} {country_name} {source_name} OTP Code Received! 🎉\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"⏳ Time: {date}\n"
                    f"{country_flag} Country: {country_name}\n"
                    f"⚙️ Source: {source_name}\n"
                    f"📞 Number: `{masked_number}`\n\n"
                    f"🔐 OTP: `{otp_code}`\n\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💬 Full Message:\n"
                    f"```{message}```"
                )
                
                print(f"[✅] NEW MESSAGE #{new_count}: {source_name} → {masked_number} | OTP: {otp_code}")
                send_to_telegram(formatted)
                
                # Reduced delay between messages
                time.sleep(0.1)  # Reduced from 0.3 to 0.1
                
            except StaleElementReferenceException:
                print(f"[⚠️] Stale element at row {row_index}, continuing...")
                continue
            except Exception as e:
                print(f"[❌] Error processing row {row_index}: {e}")
                continue

        print(f"[📊] Scan complete: Processed {processed_count} messages, {new_count} new messages sent.")
        return new_count

    except Exception as e:
        print(f"[❌] Failed to extract SMS: {e}")
        return 0

# ------------------- Browser Management -------------------

def setup_browser():
    global driver
    chrome_options = Options()
    
    # Create unique user data directory
    user_data_dir = tempfile.mkdtemp(prefix="chrome_profile_")
    
    # VNC-friendly settings with fixes
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # Performance optimizations
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Disable images for faster loading
    chrome_options.add_argument("--disable-javascript")  # Disable JavaScript if not needed
    
    # Remove automation flags detection
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    try:
        # Use webdriver_manager to automatically handle ChromeDriver version
        print("[🔧] Setting up ChromeDriver with automatic version management...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"[✅] Browser setup successful with user data dir: {user_data_dir}")
        return driver
        
    except Exception as e:
        print(f"[❌] ChromeDriver setup failed: {e}")
        print("[🔄] Trying alternative method...")
        
        # Fallback: Try without webdriver_manager
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("[✅] Browser setup successful (fallback method)")
            return driver
        except Exception as e2:
            print(f"[❌] Fallback also failed: {e2}")
            raise

def refresh_page():
    """Refresh the page to get new messages"""
    try:
        print("[🔄] Refreshing page for new messages...")
        driver.refresh()
        
        # Wait for page to load completely
        WebDriverWait(driver, 10).until(  # Reduced from 15 to 10
            EC.presence_of_element_located((By.CLASS_NAME, "kv-grid-table"))
        )
        
        print("[✅] Page refreshed successfully")
        return True
    except Exception as e:
        print(f"[❌] Failed to refresh page: {e}")
        return False

def check_page_loaded():
    """Check if the SMS page is properly loaded"""
    try:
        WebDriverWait(driver, 8).until(  # Reduced from 10 to 8
            EC.presence_of_element_located((By.CLASS_NAME, "kv-grid-table"))
        )
        return True
    except:
        return False

# ------------------- Main Monitoring Loop -------------------

def main():
    global driver, last_messages
    
    print("[🚀] Starting ULTRA-FAST SMS Monitor Bot...")
    print("=" * 50)
    print("[📝] ULTRA-FAST Features:")
    print("   ⚡ Refresh interval: 3 seconds (was 5)")
    print("   ⚡ Faster page loading")
    print("   ⚡ Reduced delays between operations")
    print("   ⚡ Enhanced WhatsApp detection")
    print("   ✅ WhatsApp 111-111 pattern detection")
    print("   ✅ Smart Source Name Detection from Message")
    print("   ✅ New Beautiful Message Style")
    print("   ✅ No Copy Button (Clean Interface)")
    print("   ✅ Ultimate OTP detection - NO MISSING OTP")
    print("   ✅ All languages & formats supported")
    print("   ✅ 24/7 continuous monitoring with auto-refresh")
    print("   ✅ Table scrolling to load all messages")
    print("   ✅ VNC optimized")
    print("   ✅ Auto ChromeDriver version management")
    print("=" * 50)
    
    # Setup browser
    driver = setup_browser()
    
    # Wait for manual login with base URL detection
    if not wait_for_manual_login():
        print("[❌] Login failed or timeout. Exiting.")
        return
    
    # Navigate to SMS page after successful login
    if not navigate_to_sms_page():
        print("[❌] Cannot access SMS page. Exiting.")
        return
    
    # Initial extraction
    print("[🔍] Starting initial comprehensive scan...")
    initial_count = extract_sms()
    print(f"[✅] Initial scan complete. Sent {initial_count} messages to Telegram.")
    
    # Continuous monitoring
    error_count = 0
    max_errors = 10
    total_messages_sent = initial_count
    
    try:
        print("[📡] Starting ULTRA-FAST 24/7 continuous monitoring...")
        monitor_count = 0
        
        while True:
            monitor_count += 1
            print(f"\n[🔄] Monitoring cycle #{monitor_count}")
            
            try:
                # Check login status
                if not check_login_status():
                    print("[⚠️] Login session lost. Please re-login manually.")
                    if not wait_for_manual_login() or not navigate_to_sms_page():
                        error_count += 1
                        if error_count >= max_errors:
                            break
                        continue
                
                # Refresh page to get latest messages
                if not refresh_page():
                    error_count += 1
                    if error_count >= max_errors:
                        break
                    continue
                
                # Extract new messages
                new_count = extract_sms()
                total_messages_sent += new_count
                
                if new_count > 0:
                    print(f"[🎉] Cycle #{monitor_count}: Sent {new_count} new messages (Total: {total_messages_sent})")
                else:
                    print(f"[👀] Cycle #{monitor_count}: No new messages found (Total: {total_messages_sent})")
                
                # Reset error count on success
                error_count = 0
                
                # Wait before next check
                print(f"[⏳] Waiting {REFRESH_INTERVAL} seconds...")
                time.sleep(REFRESH_INTERVAL)
                
            except Exception as e:
                error_count += 1
                print(f"[❌] Error in cycle #{monitor_count} ({error_count}/{max_errors}): {e}")
                
                if error_count >= max_errors:
                    print("[🔄] Too many consecutive errors. Please check the system.")
                    break
                
                time.sleep(5)  # Reduced from 10 to 5
                
    except KeyboardInterrupt:
        print("\n[🛑] Bot stopped by user.")
    except Exception as e:
        print(f"[❌] Critical error: {e}")
    finally:
        if driver:
            print("[🔚] Closing browser...")
            driver.quit()
        print(f"[✅] Bot stopped. Total messages sent: {total_messages_sent}")
        print("[🎯] Ready to restart when needed.")

if __name__ == "__main__":
    main()