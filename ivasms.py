import time
import re
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry
import config  # BOT_TOKEN, CHAT_ID

# Store sent messages to avoid duplicates
last_messages = set()
monitoring_started = False

# ------------------- Helper Functions -------------------

def mask_number(number: str) -> str:
    """Mask phone number for privacy"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "***" + digits[-3:]
    return number

def country_to_flag(country_code: str) -> str:
    """Convert country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def detect_country(number: str):
    """Detect country from phone number"""
    try:
        # Clean the number and add + if missing
        clean_number = re.sub(r'\D', '', number)
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
            
        parsed = phonenumbers.parse(clean_number, None)
        region = region_code_for_number(parsed)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name, country_to_flag(region)
    except Exception as e:
        print(f"[⚠️] Country detection error for {number}: {e}")
    return "Unknown", "🏳️"

def extract_otp(message: str) -> str:
    """Extract OTP code from message"""
    patterns = [
        r'\b\d{3}-\d{3}\b',  # 123-456
        r'\b\d{3} \d{3}\b',  # 123 456
        r'\b\d{6}\b',        # 123456
        r'\b\d{4}\b',        # 1234
        r'\b\d{5}\b',        # 12345
        r'\b\d{7}\b',        # 1234567
        r'\b\d{8}\b',        # 12345678
        r'code[:\s]*(\d+)',  # code: 123456
        r'Code[:\s]*(\d+)',  # Code: 123456
        r'CODE[:\s]*(\d+)',  # CODE: 123456
        r'verification[:\s]*(\d+)',  # verification: 123456
        r'password[:\s]*(\d+)',      # password: 123456
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            # Extract numbers from the matched group
            numbers = re.findall(r'\d+', match.group(0))
            if numbers:
                return numbers[0]
    return "N/A"

def send_to_telegram(text: str, is_log=False):
    """Send message to Telegram channel"""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    
    # For logs, no buttons. For SMS, two buttons side by side
    if not is_log:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🤖 Buy Number", "url": "https://t.me/atik203412"},
                    {"text": "✨ Support", "url": "https://t.me/atikmethod_zone"}
                ]
            ]
        }
        payload = {
            "chat_id": config.CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        }
    else:
        payload = {
            "chat_id": config.CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            if is_log:
                print(f"[📋] Log sent to Telegram")
            else:
                print("[✅] SMS sent to Telegram")
            return True
        else:
            print(f"[❌] Telegram failed: {res.status_code}")
            return False
    except Exception as e:
        print(f"[❌] Telegram error: {e}")
        return False

# ------------------- Login Detection -------------------

def wait_for_login_and_redirect(driver):
    """Wait for user to login manually and detect successful login"""
    global monitoring_started
    
    print("=" * 50)
    print("🤖 iVASMS SMS EXTRACTOR")
    print("=" * 50)
    print("[*] Please login manually to iVASMS...")
    print("[*] URL: https://www.ivasms.com/login")
    print("[*] Waiting for you to complete login...")
    print("=" * 50)
    
    # Navigate to login page
    driver.get(config.LOGIN_URL)
    
    # Wait for user to reach portal (successful login)
    try:
        WebDriverWait(driver, 300).until(  # 5 minutes timeout
            EC.url_contains("/portal")
        )
        print("[✅] Login detected! Redirecting to SMS page...")
        
        # Send log to group
        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"🔔 **iVASMS Monitor Started**\n\n🕒 **Login Time:** `{login_time}`\n📱 **Status:** `Monitoring Active`\n🔄 **Auto Refresh:** `Every 5 minutes`"
        send_to_telegram(log_message, is_log=True)
        
        # Navigate to SMS page
        driver.get(config.SMS_URL)
        time.sleep(3)
        
        monitoring_started = True
        return True
        
    except Exception as e:
        print(f"[❌] Login timeout or failed: {e}")
        return False

# ------------------- Core Extraction for iVASMS -------------------

def extract_phone_number_from_text(text: str) -> str:
    """Extract phone number from text containing country and number"""
    # Look for phone number patterns
    patterns = [
        r'\+\d{10,15}',  # +123456789012
        r'\d{10,15}',    # 123456789012
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US format
        r'\b\d{2}[-.]?\d{4}[-.]?\d{4}\b',  # International
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    # If no pattern found, return the text as is
    return text.strip()

def extract_ivasms_sms(driver):
    """Extract SMS messages from iVASMS live SMS page"""
    global last_messages
    
    try:
        # Check if we're on the SMS page, if not navigate
        current_url = driver.current_url
        if "live/my_sms" not in current_url:
            print("[*] Navigating to Live SMS page...")
            driver.get(config.SMS_URL)
            time.sleep(5)
        
        # Wait for the live SMS table to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "LiveTestSMS"))
        )
        
        # Get all SMS rows from the table
        rows = driver.find_elements(By.CSS_SELECTOR, "#LiveTestSMS tr")
        
        if not rows:
            print("[⚠️] No SMS rows found in table.")
            return
        
        new_count = 0
        
        for row in rows:
            try:
                # Extract data from each column in the row
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:
                    continue
                
                # Column 0: Live SMS (Country + Number)
                country_number_cell = cells[0]
                country_number_text = country_number_cell.text.strip()
                
                # Extract phone number from the text
                number = extract_phone_number_from_text(country_number_text)
                
                # Column 1: SID (Sender)
                sender_cell = cells[1]
                sender = sender_cell.text.strip() if sender_cell.text else "Unknown"
                
                # Column 4: Message content
                message_cell = cells[4]
                message = message_cell.text.strip()
                
                # Skip if no message or already processed
                if not message:
                    continue
                    
                # Create unique identifier for this message
                message_id = f"{sender}_{number}_{message[:50]}"
                if message_id in last_messages:
                    continue
                
                last_messages.add(message_id)
                new_count += 1
                
                # Process and send the message
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                otp_code = extract_otp(message)
                
                # Detect country from phone number
                country_name, country_flag = detect_country(number)
                masked_number = mask_number(number)
                
                # Format the message for Telegram
                formatted = (
                    f"🔥 **New SMS Captured! ({sender}) {country_flag}**\n\n"
                    f"🕒 **Time:** `{timestamp}`\n"
                    f"{country_flag} **Country:** `{country_name}`\n"
                    f"🌐 **Sender:** `{sender}`\n"
                    f"📞 **Number:** `{masked_number}`\n"
                    f"🔐 **OTP:** `{otp_code}`\n\n"
                    f"💬 **Full Message:**\n"
                    f"```{message}```"
                )
                
                # Send to Telegram
                if send_to_telegram(formatted):
                    print(f"[✅] Sent: {sender} - OTP: {otp_code}")
                else:
                    print(f"[❌] Failed to send: {sender}")
                
                # Small delay between messages
                time.sleep(1)
                
            except Exception as e:
                print(f"[⚠️] Error processing row: {e}")
                continue
        
        if new_count > 0:
            print(f"[ℹ️] Processed {new_count} new messages.")
        
    except Exception as e:
        print(f"[❌] Failed to extract SMS: {e}")

# ------------------- Session Management -------------------

def check_session_active(driver):
    """Check if user session is still active"""
    try:
        # Check if we're still on portal or redirected to login
        current_url = driver.current_url
        if "/portal" in current_url:
            return True
        else:
            return False
    except:
        return False

def refresh_browser(driver):
    """Refresh browser every 5 minutes for stability"""
    try:
        print("[🔄] Auto-refreshing browser for stability...")
        driver.refresh()
        time.sleep(5)
        
        # Send refresh log to group
        refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"🔄 **Browser Refreshed**\n\n🕒 **Time:** `{refresh_time}`\n📱 **Status:** `Monitoring Active`\n✅ **Stability:** `Maintained`"
        send_to_telegram(log_message, is_log=True)
        
        return True
    except Exception as e:
        print(f"[⚠️] Error refreshing browser: {e}")
        return False

# ------------------- Main Program -------------------

def main():
    """Main function to run the SMS extractor"""
    global monitoring_started
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # User agent to look more human
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Initialize driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Wait for manual login and auto-redirect
        if not wait_for_login_and_redirect(driver):
            print("[❌] Cannot proceed without login.")
            return
        
        print("\n[*] iVASMS SMS Monitor is now ACTIVE")
        print("[*] Monitoring Live SMS every 10 seconds")
        print("[*] Auto-refresh every 5 minutes")
        print("[*] Press Ctrl+C to stop\n")
        
        check_count = 0
        last_refresh = time.time()
        
        while True:
            check_count += 1
            
            # Check session every 10 cycles
            if check_count % 10 == 0:
                if not check_session_active(driver):
                    print("[❌] Session expired. Please login again.")
                    send_to_telegram("🔴 **Session Expired**\n\nPlease login again to continue monitoring.", is_log=True)
                    if not wait_for_login_and_redirect(driver):
                        break
            
            # Auto-refresh every 5 minutes (300 seconds)
            current_time = time.time()
            if current_time - last_refresh >= 300:  # 5 minutes
                refresh_browser(driver)
                last_refresh = current_time
            
            # Extract SMS
            extract_ivasms_sms(driver)
            
            print(f"[⏳] Monitoring... (Cycle {check_count})")
            time.sleep(10)  # Check every 10 seconds
            
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
        # Send stop notification
        stop_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stop_message = f"🛑 **Monitoring Stopped**\n\n🕒 **Time:** `{stop_time}`\n📱 **Status:** `Inactive`"
        send_to_telegram(stop_message, is_log=True)
    except Exception as e:
        print(f"[❌] Unexpected error: {e}")
        error_message = f"❌ **System Error**\n\n🕒 **Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n💻 **Error:** `{str(e)}`"
        send_to_telegram(error_message, is_log=True)
    finally:
        driver.quit()
        print("[*] Browser closed.")
        print("[👋] iVASMS SMS Monitor stopped.")

if __name__ == "__main__":
    main()