import time
import re
import requests
import json
import os
import tempfile
from datetime import datetime
from seleniumbase import Driver, SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8371638048:AAEHGvy-vYHmUFPXslg-2toZgOA_14osM9k"
CHAT_ID = "-1002287664519"
BASE_URL = "https://proton-sms-panel.com/"
LOGIN_URL = "https://proton-sms-panel.com/user-management/auth/login"
SMS_URL = "https://proton-sms-panel.com/SMSCDRReports"
REFRESH_INTERVAL = 5
MAX_MESSAGES_STORE = 2000
SCROLL_ATTEMPTS = 3
# =======================================================

# Store sent messages to avoid duplicates
last_messages = set()
driver = None

# ------------------- Source Name Detection from CLI -------------------

def detect_source_from_cli(cli_number: str) -> str:
    """
    Detect source name from CLI number patterns first
    """
    if not cli_number:
        return "Unknown"
    
    cli_clean = re.sub(r'\D', '', cli_number)
    
    # Known service numbers patterns
    service_patterns = {
        "Telegram": [
            r'^42777', r'^8777', r'^999', r'^45474',  # Telegram numbers
        ],
        "WhatsApp": [
            r'^447', r'^316', r'^491', r'^346', r'^393',  # WhatsApp numbers
        ],
        "Google": [
            r'^22000', r'^22669', r'^325', r'^829',  # Google verification
        ],
        "Facebook": [
            r'^32665', r'^256', r'^22333',  # Facebook numbers
        ],
        "Instagram": [
            r'^32665', r'^256',  # Instagram (often same as Facebook)
        ],
        "Twitter": [
            r'^40404', r'^456', r'^898',  # Twitter numbers
        ],
        "Apple": [
            r'^484', r'^487', r'^2255',  # Apple verification
        ],
        "Amazon": [
            r'^262966', r'^267', r'^292',  # Amazon numbers
        ],
        "Microsoft": [
            r'^245', r'^246', r'^247',  # Microsoft verification
        ],
        "Binance": [
            r'^88209', r'^88210', r'^88211',  # Binance verification
        ],
        "PayPal": [
            r'^297', r'^298', r'^299',  # PayPal numbers
        ],
        "Uber": [
            r'^89303', r'^89304',  # Uber verification
        ],
        "Grab": [
            r'^87872', r'^87873',  # Grab verification
        ],
        "1xBet": [
            r'^903', r'^904', r'^905',  # 1xBet numbers
        ],
        "Twilio": [
            r'^415', r'^650', r'^832',  # Twilio numbers
        ],
        "Bank": [
            r'^4546', r'^5218', r'^5525',  # Bank OTP numbers
        ]
    }
    
    for service_name, patterns in service_patterns.items():
        for pattern in patterns:
            if re.match(pattern, cli_clean):
                print(f"[🔍] CLI Detected source: {service_name} from {cli_number}")
                return service_name
    
    return "Unknown"

def detect_source_name(message: str, cli_number: str) -> str:
    """
    Detect source name - FIRST from CLI, then from message content
    """
    # First try to detect from CLI number
    source_from_cli = detect_source_from_cli(cli_number)
    if source_from_cli != "Unknown":
        return source_from_cli
    
    # If CLI detection fails, try from message content
    message_lower = message.lower()
    
    # Service patterns for message content
    service_patterns = {
        "Telegram": [
            r'telegram', r'tg\.me', r't\.me', r'@', r'username', 
            r'login code', r'verification code', r'confirm your phone',
            r'telegram code', r'tg code'
        ],
        "WhatsApp": [
            r'whatsapp', r'wa\.me', r'whats app', r'whatsapp code',
            r'whatsapp verification', r'your whatsapp code'
        ],
        "Twilio": [
            r'twilio', r'twilio verification', r'twilio code',
            r'your twilio code'
        ],
        "Apple": [
            r'apple', r'apple id', r'icloud', r'appstore',
            r'your apple id code', r'apple verification',
            r'use this code to reset your apple id password'
        ],
        "1xBet": [
            r'1xbet', r'1x bet', r'1xbet code', r'1xbet verification',
            r'your 1xbet code', r'1xbet confirm'
        ],
        "Facebook": [
            r'facebook', r'fb\.me', r'facebook code', r'facebook login',
            r'your facebook code', r'facebook confirmation'
        ],
        "Google": [
            r'google', r'g-\d{6}', r'google verification', r'your google verification code',
            r'google account', r'gmail'
        ],
        "Instagram": [
            r'instagram', r'insta', r'ig', r'instagram code',
            r'your instagram code', r'instagram confirmation'
        ],
        "Twitter": [
            r'twitter', r'twitter code', r'twitter verification',
            r'your twitter code'
        ],
        "Amazon": [
            r'amazon', r'amazon code', r'amazon otp',
            r'your amazon verification code'
        ],
        "Microsoft": [
            r'microsoft', r'windows', r'outlook', r'hotmail',
            r'microsoft verification', r'your microsoft code'
        ],
        "Binance": [
            r'binance', r'crypto', r'bitcoin', r'bnb',
            r'binance verification', r'your binance code'
        ],
        "PayPal": [
            r'paypal', r'payment', r'pay pal',
            r'paypal verification', r'your paypal code'
        ],
        "Bank": [
            r'bank', r'visa', r'mastercard', r'card', r'transaction',
            r'payment', r'otp', r'one time password', r'secure code'
        ]
    }
    
    for service_name, patterns in service_patterns.items():
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                print(f"[🔍] Message Detected source: {service_name}")
                return service_name
    
    return "Unknown Service"

# ------------------- Enhanced OTP Detection -------------------

def extract_otp(message: str) -> str:
    """
    Ultimate OTP detection for all languages and formats
    """
    if not message or len(message.strip()) < 4:
        return "N/A"
        
    clean_message = message.strip()
    
    # Comprehensive OTP patterns
    patterns = [
        # Standard formats (most common first)
        r'\b\d{6}\b',                           # 123456
        r'\b\d{4}\b',                           # 1234
        r'\b\d{5}\b',                           # 12345
        r'\b\d{3}[-\.\s]?\d{3}\b',              # 123-456, 123.456, 123 456
        r'\b\d{4}[-\.\s]?\d{4}\b',              # 1234-5678, 1234.5678, 1234 5678
        r'\b\d{8}\b',                           # 12345678
        
        # OTP with labels (English)
        r'(?i)(?:code|otp|password|verification|pin|passcode)[\s:\-]*[is\-\:\s]*[\{\[\(]?\s*(\d{4,8})\s*[\}\]\)]?',
        r'(?i)(?:code|otp|password|verification|pin|passcode)[\s:\-]*[is\-\:\s]*(\d{3,8})',
        r'(?i)(?:is|code|use)[\s:\-]*(\d{4,8})',
        
        # OTP with labels (Multi-language)
        r'(?i)(?:код|код|密码|驗證碼|コード|코드|codice|codigo|código)[\s:\-]*[is\-\:\s]*[\{\[\(]?\s*(\d{4,8})\s*[\}\]\)]?',
        
        # WhatsApp specific patterns
        r'\*\s*(\d{4,8})\s*\*',                # *123456*
        r'\[\s*(\d{4,8})\s*\]',                # [123456]
        r'\(\s*(\d{4,8})\s*\)',                # (123456)
        
        # Google/Apple format
        r'[GA]\-\s*(\d{6})',                   # G-123456, A-123456
        
        # Telegram common patterns
        r'Your verification code is\s*[\{\[\(]?\s*(\d{4,8})\s*[\}\]\)]?',
        r'verification code[\s:\-]*[\{\[\(]?\s*(\d{4,8})\s*[\}\]\)]?',
        
        # Common SMS patterns
        r'use[\s]+(\d{4,8})[\s]+to',
        r'enter[\s]+(\d{4,8})[\s]+',
        r'code[\s]+(\d{4,8})[\s]+',
        
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
                    otp_candidate = re.sub(r'\D', '', str(match))
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
    
    # No inline keyboard as requested
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
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

# ------------------- Browser Management -------------------

def setup_browser():
    global driver
    try:
        print("[🔧] Setting up SeleniumBase with UC Mode for CAPTCHA bypass...")
        
        # Use SeleniumBase Driver with UC mode for undetected browsing
        driver = Driver(uc=True, headless=False)
        
        print("[✅] SeleniumBase UC Mode setup successful")
        return driver
        
    except Exception as e:
        print(f"[❌] SeleniumBase setup failed: {e}")
        raise

def wait_for_manual_login():
    """Wait for user to manually login"""
    print("[🔐] Please login manually in the browser...")
    print("[⏳] Waiting for you to complete login...")
    
    # Navigate to login page
    driver.get(LOGIN_URL)
    time.sleep(2)
    
    # Wait for user to login - detect when URL changes to dashboard
    print("[🎯] Waiting for dashboard page...")
    try:
        WebDriverWait(driver, 300).until(
            lambda driver: "dashboard" in driver.current_url.lower() or driver.current_url == BASE_URL
        )
        print("[✅] Login successful! Detected dashboard page.")
        return True
        
    except TimeoutException:
        print("[❌] Login timeout. Please check your login.")
        return False

def navigate_to_sms_page():
    """Navigate to SMS CDR reports page after successful login"""
    try:
        print("[🔄] Navigating to SMS CDR reports page...")
        driver.get(SMS_URL)
        
        # Wait for SMS page to load - Proton SMS uses "data-tbl-boxy" class
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "data-tbl-boxy"))
        )
        print("[✅] SMS CDR reports page loaded successfully.")
        return True
        
    except Exception as e:
        print(f"[❌] Failed to navigate to SMS page: {e}")
        return False

def check_login_status():
    """Check if still logged in"""
    try:
        current_url = driver.current_url
        if "dashboard" in current_url.lower() or "smscdr" in current_url.lower():
            return True
        else:
            # Try to access dashboard
            driver.get(BASE_URL)
            time.sleep(2)
            if "dashboard" in driver.current_url.lower():
                return True
        return False
    except:
        return False

# ------------------- SMS Extraction for Proton SMS -------------------

def detect_columns(header_row):
    """Map columns based on Proton SMS table structure"""
    # Default mapping based on Proton SMS table structure
    mapping = {"date": 0, "range": 1, "number": 2, "cli": 3, "client": 4, "message": 5}
    
    try:
        cells = header_row.find_elements(By.TAG_NAME, "th")
        for idx, cell in enumerate(cells):
            text = cell.text.strip().lower()
            if "date" in text:
                mapping["date"] = idx
            elif "range" in text:
                mapping["range"] = idx
            elif "number" in text:
                mapping["number"] = idx
            elif "cli" in text:
                mapping["cli"] = idx
            elif "client" in text:
                mapping["client"] = idx
            elif "sms" in text:
                mapping["message"] = idx
    except Exception as e:
        print(f"[⚠️] Column detection warning: {e}")
    
    print(f"[📊] Column mapping: Date[{mapping['date']}], Range[{mapping['range']}], Number[{mapping['number']}], CLI[{mapping['cli']}], Client[{mapping['client']}], Message[{mapping['message']}]")
    return mapping

def scroll_table_to_bottom():
    """Scroll the table to load all messages"""
    try:
        # Find the table container for Proton SMS
        table_container = driver.find_element(By.ID, "dt_wrapper")
        
        for attempt in range(SCROLL_ATTEMPTS):
            last_height = driver.execute_script("return arguments[0].scrollHeight", table_container)
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", table_container)
            time.sleep(1)
            new_height = driver.execute_script("return arguments[0].scrollHeight", table_container)
            
            if new_height == last_height:
                break
            print(f"[⬇️] Scrolling table... attempt {attempt + 1}")
            
    except Exception as e:
        print(f"[⚠️] Table scrolling issue: {e}")

def extract_sms():
    global last_messages
    try:
        # Wait for the table to be present (Proton SMS uses "data-tbl-boxy" class)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "data-tbl-boxy"))
        )

        # Scroll to load all messages
        scroll_table_to_bottom()
        time.sleep(2)

        # Find the table
        table = driver.find_element(By.CLASS_NAME, "data-tbl-boxy")
        
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
                # Skip empty rows
                if not row.text.strip():
                    continue
                    
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) <= max(mapping.values()):
                    continue

                # Extract data based on column mapping for Proton SMS
                date = cells[mapping["date"]].text.strip()
                range_info = cells[mapping["range"]].text.strip()
                destination = cells[mapping["number"]].text.strip()  # Our number
                cli_number = cells[mapping["cli"]].text.strip()      # Source number
                client_info = cells[mapping["client"]].text.strip()
                message = cells[mapping["message"]].text.strip()

                # Skip if no message
                if not message or message == "":
                    continue
                    
                # Create unique message ID
                message_id = f"{cli_number}_{destination}_{message[:50]}"
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
                masked_cli = mask_number(cli_number)
                
                # Detect source name - FIRST from CLI, then from message
                source_name = detect_source_name(message, cli_number)

                # Format the message for Telegram (clean style without buttons)
                formatted = (
                    f"{country_flag} {country_name} {source_name} OTP Code Received! 🎉\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"⏳ Time: {date}\n"
                    f"{country_flag} Country: {country_name}\n"
                    f"⚙️ Source: {source_name}\n"
                    f"📞 CLI: `{masked_cli}`\n"
                    f"📱 Number: `{masked_number}`\n\n"
                    f"🔐 OTP: `{otp_code}`\n\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💬 Full Message:\n"
                    f"```{message}```"
                )
                
                print(f"[✅] NEW MESSAGE #{new_count}: {source_name} → {masked_number} | OTP: {otp_code}")
                send_to_telegram(formatted)
                
                # Small delay between messages to avoid rate limiting
                time.sleep(0.3)
                
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

# ------------------- Page Management -------------------

def refresh_page():
    """Refresh the page to get new messages"""
    try:
        print("[🔄] Refreshing page for new messages...")
        driver.refresh()
        
        # Wait for page to load completely
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "data-tbl-boxy"))
        )
        
        print("[✅] Page refreshed successfully")
        return True
    except Exception as e:
        print(f"[❌] Failed to refresh page: {e}")
        return False

def check_page_loaded():
    """Check if the SMS page is properly loaded"""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "data-tbl-boxy"))
        )
        return True
    except:
        return False

# ------------------- Main Monitoring Loop -------------------

def main():
    global driver, last_messages
    
    print("[🚀] Starting Proton SMS Monitor Bot")
    print("=" * 60)
    print("[🛡️] ENHANCED FEATURES:")
    print("   ✅ CLI-based Source Detection (Primary)")
    print("   ✅ Message-based Source Detection (Fallback)")
    print("   ✅ No Inline Buttons - Clean Interface")
    print("   ✅ Ultimate OTP detection - NO MISSING OTP")
    print("   ✅ Proton SMS Panel Optimized")
    print("   ✅ 24/7 continuous monitoring with auto-refresh")
    print("=" * 60)
    
    # Setup browser with SeleniumBase
    driver = setup_browser()
    
    # Wait for manual login
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
        print("[📡] Starting 24/7 continuous monitoring...")
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
                
                time.sleep(10)
                
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