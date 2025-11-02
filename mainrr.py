import time
import re
import requests
import os
import sys
import logging
import random
import json
from datetime import datetime
from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import phonenumbers
from phonenumbers import region_code_for_number
import pycountry

try:
    import config
except ImportError:
    print("❌ config.py file not found! Please create config.py first.")
    config = type('Config', (), {})()
    # Set default values
    config.BOT_TOKEN = "YOUR_BOT_TOKEN"
    config.CHAT_ID = "YOUR_CHAT_ID"
    config.LOGIN_URL = "https://www.orangecarrier.com/login"
    config.CALL_URL = "https://www.orangecarrier.com/live/calls"
    config.BASE_URL = "https://www.orangecarrier.com"
    config.DOWNLOAD_FOLDER = "recordings"
    config.CHECK_INTERVAL = 10
    config.MAX_ERRORS = 10
    config.RECORDING_RETRY_DELAY = 30
    config.MAX_RECORDING_WAIT = 600
    print("⚠️ Using default config. Please create config.py with your actual values.")

# Global variables
active_calls = {}
pending_recordings = {}

def setup_directories():
    """Ensure all necessary directories exist"""
    directories = [
        config.DOWNLOAD_FOLDER,
        "logs",
        "screenshots",
        "profiles",
        "session"
    ]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Directory created: {directory}")
        except Exception as e:
            print(f"❌ Failed to create directory {directory}: {e}")

setup_directories()

def setup_logging():
    """Setup comprehensive logging"""
    try:
        logger = logging.getLogger('call_monitor')
        logger.setLevel(logging.INFO)
        
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler('logs/monitor.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        class ColorFormatter(logging.Formatter):
            grey = "\x1b[38;21m"
            yellow = "\x1b[33;21m"
            red = "\x1b[31;21m"
            green = "\x1b[32;21m"
            blue = "\x1b[34;21m"
            reset = "\x1b[0m"

            def format(self, record):
                log_fmt = self.grey + '%(asctime)s - ' + self.reset
                if record.levelno == logging.INFO:
                    log_fmt += self.green + '%(levelname)s' + self.reset
                elif record.levelno == logging.WARNING:
                    log_fmt += self.yellow + '%(levelname)s' + self.reset
                elif record.levelno >= logging.ERROR:
                    log_fmt += self.red + '%(levelname)s' + self.reset
                else:
                    log_fmt += self.blue + '%(levelname)s' + self.reset
                log_fmt += ' - %(message)s'
                formatter = logging.Formatter(log_fmt)
                return formatter.format(record)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColorFormatter())
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    except Exception as e:
        print(f"❌ Logging setup failed: {e}")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        return logging.getLogger('call_monitor')

logger = setup_logging()

def country_to_flag(country_code):
    """Convert country code to flag emoji"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    try:
        return "".join(chr(127397 + ord(c)) for c in country_code.upper())
    except:
        return "🏳️"

def detect_country(number):
    """Detect country from phone number"""
    try:
        clean_number = re.sub(r"\D", "", number)
        if clean_number:
            parsed = phonenumbers.parse("+" + clean_number, None)
            region = region_code_for_number(parsed)
            country = pycountry.countries.get(alpha_2=region)
            if country:
                return country.name, country_to_flag(region)
    except Exception as e:
        logger.debug(f"Country detection error: {e}")
    return "Unknown", "🏳️"

def mask_number(number):
    """Mask phone number for privacy"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "****" + digits[-3:]
    return number

def send_message(text):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
        payload = {"chat_id": config.CHAT_ID, "text": text, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info("📤 Telegram message sent successfully")
            return res.json().get("result", {}).get("message_id")
        else:
            logger.warning(f"Telegram API error: {res.status_code}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
    return None

def delete_message(msg_id):
    """Delete Telegram message"""
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage"
        response = requests.post(url, data={"chat_id": config.CHAT_ID, "message_id": msg_id}, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Failed to delete message {msg_id}: {response.status_code}")
    except Exception as e:
        logger.debug(f"Delete message warning: {e}")

def send_voice_with_caption(voice_path, caption):
    """Send voice recording to Telegram"""
    try:
        if not os.path.exists(voice_path):
            logger.error(f"File not found: {voice_path}")
            return False
            
        file_size = os.path.getsize(voice_path)
        if file_size < 1000:
            logger.error(f"File too small: {file_size} bytes")
            return False
            
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendVoice"
        with open(voice_path, "rb") as voice:
            payload = {"chat_id": config.CHAT_ID, "caption": caption, "parse_mode": "HTML"}
            files = {"voice": voice}
            response = requests.post(url, data=payload, files=files, timeout=60)
            
        if response.status_code == 200:
            logger.info("🎵 Voice message sent successfully")
            return True
        else:
            logger.error(f"Telegram voice upload failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send voice: {e}")
        return False

def get_authenticated_session(driver):
    """Get authenticated session from Selenium cookies"""
    try:
        session = requests.Session()
        selenium_cookies = driver.get_cookies()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        return session
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        return requests.Session()

def construct_recording_url(did_number, call_uuid):
    """Construct recording URL"""
    return f"https://www.orangecarrier.com/live/calls/sound?did={did_number}&uuid={call_uuid}"

def simulate_play_button(driver, did_number, call_uuid):
    """Simulate play button click using JavaScript"""
    try:
        script = f"""
        try {{
            if (typeof window.Play === 'function') {{
                window.Play("{did_number}", "{call_uuid}");
                return "Play function executed successfully";
            }} else {{
                // Try alternative methods
                var playButtons = document.querySelectorAll('[onclick*="{call_uuid}"], [onclick*="{did_number}"]');
                if (playButtons.length > 0) {{
                    playButtons[0].click();
                    return "Alternative play button clicked";
                }} else {{
                    return "Play function not found and no alternative buttons";
                }}
            }}
        }} catch (e) {{
            return "Play function error: " + e.message;
        }}
        """
        result = driver.execute_script(script)
        logger.info(f"🔘 Play button simulated: {result}")
        return "successfully" in result.lower() or "clicked" in result.lower()
    except Exception as e:
        logger.error(f"Play simulation failed: {e}")
        return False

def download_recording(driver, did_number, call_uuid, file_path):
    """Download recording file with enhanced error handling"""
    try:
        logger.info(f"🎬 Starting download for {did_number}, UUID: {call_uuid}")
        
        if not simulate_play_button(driver, did_number, call_uuid):
            logger.warning("Play button simulation failed")
            return False
            
        time.sleep(10)
        
        recording_url = construct_recording_url(did_number, call_uuid)
        session = get_authenticated_session(driver)
        
        headers = {
            'User-Agent': driver.execute_script("return navigator.userAgent;"),
            'Referer': config.CALL_URL,
            'Accept': 'audio/mpeg, audio/*, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Range': 'bytes=0-'
        }
        
        for attempt in range(3):
            try:
                logger.info(f"📥 Download attempt {attempt+1} for {did_number}")
                response = session.get(recording_url, headers=headers, timeout=30, stream=True)
                
                logger.info(f"📊 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        content_length = int(content_length)
                        logger.info(f"📏 Content length: {content_length} bytes")
                    
                    content_type = response.headers.get('Content-Type', '')
                    if 'audio' not in content_type and 'mpeg' not in content_type:
                        logger.warning(f"📄 Unexpected content type: {content_type}")
                    
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    file_size = os.path.getsize(file_path)
                    logger.info(f"💾 File saved: {file_size} bytes")
                    
                    if file_size > 5000:
                        logger.info(f"✅ Download successful: {file_size} bytes")
                        return True
                    else:
                        logger.warning(f"📦 Downloaded file too small: {file_size} bytes")
                        
                elif response.status_code == 404:
                    logger.warning("🔍 Recording not found (404)")
                elif response.status_code == 403:
                    logger.warning("🚫 Access forbidden (403)")
                else:
                    logger.warning(f"🌐 HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.error(f"⏰ Download timeout on attempt {attempt+1}")
            except requests.exceptions.ConnectionError:
                logger.error(f"🔌 Connection error on attempt {attempt+1}")
            except Exception as e:
                logger.error(f"❌ Download attempt {attempt+1} failed: {e}")
            
            time.sleep(5)
            
        if os.path.exists(file_path) and os.path.getsize(file_path) < 5000:
            try:
                os.remove(file_path)
            except:
                pass
                
        return False
        
    except Exception as e:
        logger.error(f"💥 Download process failed: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        return False

def take_screenshot(driver, name):
    """Take screenshot for debugging"""
    try:
        screenshot_path = f"screenshots/{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"📸 Screenshot saved: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None

def save_cookies(driver):
    """Save cookies to file for persistence"""
    try:
        cookies = driver.get_cookies()
        with open('session/cookies.json', 'w') as f:
            json.dump(cookies, f)
        logger.info("🍪 Cookies saved successfully")
    except Exception as e:
        logger.warning(f"Could not save cookies: {e}")

def load_cookies(driver):
    """Load cookies from file"""
    try:
        with open('session/cookies.json', 'r') as f:
            cookies = json.load(f)
        
        driver.delete_all_cookies()
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.debug(f"Could not add cookie: {e}")
        
        logger.info("🍪 Cookies loaded successfully")
        return True
    except FileNotFoundError:
        logger.info("📭 No saved cookies found")
        return False
    except Exception as e:
        logger.warning(f"Could not load cookies: {e}")
        return False

def detect_captcha(driver):
    """Detect various types of CAPTCHA on the page"""
    captcha_indicators = [
        # Cloudflare CAPTCHA
        ("//div[contains(@class, 'cf-challenge')]", "Cloudflare Challenge"),
        ("//div[contains(text(), 'Checking your browser')]", "Cloudflare Verification"),
        ("//div[contains(text(), 'DDoS protection')]", "Cloudflare DDoS Protection"),
        ("//div[contains(@id, 'cf-content')]", "Cloudflare Content"),
        
        # reCAPTCHA
        ("//div[contains(@class, 'g-recaptcha')]", "Google reCAPTCHA"),
        ("//iframe[contains(@src, 'google.com/recaptcha')]", "Google reCAPTCHA Iframe"),
        ("//div[contains(@class, 'recaptcha')]", "reCAPTCHA"),
        
        # hCAPTCHA
        ("//div[contains(@class, 'h-captcha')]", "hCAPTCHA"),
        ("//iframe[contains(@src, 'hcaptcha.com')]", "hCAPTCHA Iframe"),
        
        # Generic CAPTCHA
        ("//input[contains(@name, 'captcha')]", "Generic CAPTCHA Input"),
        ("//img[contains(@src, 'captcha')]", "CAPTCHA Image"),
        ("//div[contains(text(), 'captcha')]", "CAPTCHA Text"),
        ("//div[contains(text(), 'robot')]", "Robot Verification"),
        ("//div[contains(text(), 'verify')]", "Verification Required")
    ]
    
    for xpath, captcha_type in captcha_indicators:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                if element.is_displayed():
                    logger.warning(f"🚫 CAPTCHA Detected: {captcha_type}")
                    return True, captcha_type
        except:
            continue
    
    return False, None

def bypass_captcha(sb):
    """Attempt to bypass detected CAPTCHA"""
    try:
        logger.info("🛡️ Attempting CAPTCHA bypass...")
        
        # Method 1: Use SeleniumBase's built-in CAPTCHA bypass
        try:
            sb.uc_gui_click_captcha()
            logger.info("✅ SeleniumBase CAPTCHA bypass attempted")
            time.sleep(3)
        except Exception as e:
            logger.warning(f"SeleniumBase CAPTCHA bypass failed: {e}")
        
        # Method 2: Try to reload the page with different parameters
        try:
            current_url = sb.driver.current_url
            if "?" in current_url:
                reload_url = current_url + "&bypass=1"
            else:
                reload_url = current_url + "?bypass=1"
            
            sb.driver.get(reload_url)
            logger.info("🔄 Page reloaded with bypass parameters")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Page reload bypass failed: {e}")
        
        # Method 3: Try to wait for CAPTCHA to auto-solve
        logger.info("⏳ Waiting for potential auto-CAPTCHA solving...")
        time.sleep(10)
        
        # Method 4: Check if CAPTCHA is still present
        captcha_detected, captcha_type = detect_captcha(sb.driver)
        if not captcha_detected:
            logger.info("✅ CAPTCHA appears to be bypassed!")
            return True
        else:
            logger.warning(f"❌ CAPTCHA still present: {captcha_type}")
            return False
            
    except Exception as e:
        logger.error(f"CAPTCHA bypass error: {e}")
        return False

def wait_for_captcha_solution(sb, max_wait=120):
    """Wait for CAPTCHA to be solved (auto or manual)"""
    logger.info(f"⏳ Waiting for CAPTCHA solution (max {max_wait} seconds)...")
    
    start_time = time.time()
    last_captcha_check = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            # Check for CAPTCHA every 10 seconds
            if time.time() - last_captcha_check > 10:
                captcha_detected, captcha_type = detect_captcha(sb.driver)
                
                if not captcha_detected:
                    logger.info("✅ CAPTCHA has been solved!")
                    return True
                
                logger.info(f"⏳ Still waiting... CAPTCHA type: {captcha_type}")
                last_captcha_check = time.time()
                
                # Try to bypass again every 30 seconds
                if int(time.time() - start_time) % 30 == 0:
                    bypass_captcha(sb)
            
            # Check if we're on the target page (CAPTCHA solved)
            current_url = sb.driver.current_url
            if (current_url.startswith(config.BASE_URL) and 
                not any(x in current_url for x in ['captcha', 'challenge', 'verify'])):
                logger.info("✅ Successfully passed CAPTCHA protection!")
                return True
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error while waiting for CAPTCHA: {e}")
            time.sleep(5)
    
    logger.error("⏰ CAPTCHA wait timeout")
    return False

def extract_calls(driver):
    """Extract call information from the page - FIXED VERSION"""
    global active_calls, pending_recordings
    
    try:
        # Wait for calls table
        calls_table = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "LiveCalls"))
        )
        
        rows = calls_table.find_elements(By.TAG_NAME, "tr")
        current_call_ids = set()
        
        logger.info(f"📊 Found {len(rows)} rows in calls table")
        
        for row in rows:
            try:
                row_id = row.get_attribute('id')
                if not row_id or 'call_' not in row_id:
                    continue
                    
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:  # Adjusted for actual table structure
                    continue
                
                # Extract phone number from second cell (index 1)
                did_element = cells[1]
                did_text = did_element.text.strip()
                did_number = re.sub(r"\D", "", did_text)
                
                if not did_number:
                    continue
                
                current_call_ids.add(row_id)
                
                if row_id not in active_calls:
                    logger.info(f"📞 New call detected: {did_number}")
                    
                    country_name, flag = detect_country(did_number)
                    masked = mask_number(did_number)
                    
                    alert_text = f"📞 **New Call Detected**\n\n📍 **From:** {flag} {masked}\n🌍 **Country:** {country_name}\n⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n🔄 Waiting for call to end..."
                    
                    msg_id = send_message(alert_text)
                    active_calls[row_id] = {
                        "msg_id": msg_id,
                        "flag": flag,
                        "country": country_name,
                        "masked": masked,
                        "did_number": did_number,
                        "detected_at": datetime.now(),
                        "last_seen": datetime.now()
                    }
                    
                    take_screenshot(driver, f"new_call_{did_number}")
                    
                else:
                    active_calls[row_id]["last_seen"] = datetime.now()
                    
            except StaleElementReferenceException:
                continue
            except Exception as e:
                logger.debug(f"Row processing error: {e}")
                continue
        
        # Check for completed calls
        current_time = datetime.now()
        completed_calls = []
        
        for call_id, call_info in list(active_calls.items()):
            if (call_id not in current_call_ids) or \
               ((current_time - call_info["last_seen"]).total_seconds() > 20):
                if call_id not in pending_recordings:
                    logger.info(f"✅ Call completed: {call_info['did_number']}")
                    completed_calls.append(call_id)
        
        # Process completed calls
        for call_id in completed_calls:
            call_info = active_calls[call_id]
            
            pending_recordings[call_id] = {
                **call_info,
                "completed_at": datetime.now(),
                "checks": 0,
                "last_check": datetime.now()
            }
            
            wait_text = f"🎯 **Call Processing**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n⏳ Downloading recording..."
            
            if call_info["msg_id"]:
                delete_message(call_info["msg_id"])
            
            new_msg_id = send_message(wait_text)
            if new_msg_id:
                pending_recordings[call_id]["msg_id"] = new_msg_id
            
            del active_calls[call_id]
            
        logger.info(f"📈 Active calls: {len(active_calls)}, Pending recordings: {len(pending_recordings)}")
                
    except TimeoutException:
        logger.warning("📭 No active calls table found within timeout")
    except Exception as e:
        logger.error(f"💥 Call extraction error: {e}")
        take_screenshot(driver, "extraction_error")

def process_pending_recordings(driver):
    """Process pending recordings with enhanced error handling"""
    global pending_recordings
    
    current_time = datetime.now()
    processed_calls = []
    
    for call_id, call_info in list(pending_recordings.items()):
        try:
            time_since_check = (current_time - call_info["last_check"]).total_seconds()
            if time_since_check < getattr(config, 'RECORDING_RETRY_DELAY', 30):
                continue
            
            call_info["checks"] += 1
            call_info["last_check"] = current_time
            
            logger.info(f"🔍 Check #{call_info['checks']} for recording: {call_info['did_number']}")
            
            max_checks = getattr(config, 'MAX_RECORDING_CHECKS', 15)
            if call_info["checks"] > max_checks:
                logger.warning(f"⏰ Max checks exceeded for: {call_info['did_number']}")
                timeout_text = f"❌ **Recording Timeout**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Recording not available after multiple attempts"
                if call_info.get("msg_id"):
                    delete_message(call_info["msg_id"])
                send_message(timeout_text)
                processed_calls.append(call_id)
                continue
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_did = re.sub(r'[^0-9]', '', call_info['did_number'])[-10:]
            file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_{safe_did}_{timestamp}.mp3")
            
            if download_recording(driver, call_info['did_number'], call_id, file_path):
                logger.info(f"✅ Recording downloaded successfully for {call_info['did_number']}")
                process_recording_file(call_info, file_path)
                processed_calls.append(call_id)
            else:
                logger.warning(f"⏳ Recording not available yet (attempt {call_info['checks']}): {call_info['did_number']}")
                wait_text = f"🔄 **Processing Recording**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n📊 **Attempt:** {call_info['checks']}/{max_checks}"
                if call_info.get("msg_id"):
                    delete_message(call_info["msg_id"])
                new_msg_id = send_message(wait_text)
                if new_msg_id:
                    pending_recordings[call_id]["msg_id"] = new_msg_id
            
            max_wait = getattr(config, 'MAX_RECORDING_WAIT', 600)
            time_since_complete = (current_time - call_info["completed_at"]).total_seconds()
            if time_since_complete > max_wait:
                logger.warning(f"⏰ Recording timeout for: {call_info['did_number']}")
                timeout_text = f"❌ **Recording Failed**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Recording download timeout"
                
                if call_info.get("msg_id"):
                    delete_message(call_info["msg_id"])
                
                send_message(timeout_text)
                processed_calls.append(call_id)
                
        except Exception as e:
            logger.error(f"💥 Recording processing error for {call_info['did_number']}: {e}")
    
    for call_id in processed_calls:
        if call_id in pending_recordings:
            del pending_recordings[call_id]

def process_recording_file(call_info, file_path):
    """Process and send recording file with enhanced error handling"""
    try:
        if call_info.get("msg_id"):
            delete_message(call_info["msg_id"])
        
        if not os.path.exists(file_path):
            logger.error(f"📭 Recording file not found: {file_path}")
            error_text = f"❌ **File Missing**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Recording file not found"
            send_message(error_text)
            return
            
        file_size = os.path.getsize(file_path)
        if file_size < 2000:
            logger.warning(f"📦 Recording file too small: {file_size} bytes")
        
        call_time = call_info['detected_at'].strftime('%Y-%m-%d %I:%M:%S %p')
        
        caption = (
            "🔥 **NEW CALL RECEIVED** ✨\n\n"
            f"⏰ **Time:** {call_time}\n"
            f"🌍 **Country:** {call_info['country']} {call_info['flag']}\n"
            f"📞 **Number:** {call_info['masked']}\n\n"
            f"🌟 **System:** Privately Secure\n"
            f"🛡️ **Status:** Successfully Recorded"
        )
        
        if file_size >= 2000 and send_voice_with_caption(file_path, caption):
            logger.info(f"✅ Recording sent successfully: {call_info['did_number']}")
            
            try:
                os.remove(file_path)
                logger.info("🗑️ Local file cleaned up")
            except Exception as e:
                logger.warning(f"File cleanup failed: {e}")
        else:
            if file_size < 2000:
                logger.error("📦 Recording file too small, not sending")
                error_text = f"❌ **Recording Too Short**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Recording file is too small"
            else:
                logger.error("🎵 Voice file sending failed")
                error_text = f"❌ **Upload Failed**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Failed to upload recording to Telegram"
            
            send_message(error_text)
            
    except Exception as e:
        logger.error(f"💥 File processing error: {e}")
        error_text = f"❌ **Processing Error**\n\n📞 **Number:** {call_info['flag']} {call_info['masked']}\n🌍 **Country:** {call_info['country']}\n\n💡 Error processing recording file"
        send_message(error_text)

def check_telegram_connection():
    """Check Telegram bot connection with enhanced message"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        test_msg = (
            "🤖 **Call Monitor Process Started Successfully!**\n\n"
            "🔐 **System:** Privately Secure\n"
            f"⏰ **Time:** {current_time}\n"
            "🛡️ **CAPTCHA Bypass:** Enabled\n"
            "✅ **Status:** Monitoring calls..."
        )
        
        msg_id = send_message(test_msg)
        if msg_id:
            logger.info("✅ Telegram connection test: SUCCESS")
            return True
        else:
            logger.error("❌ Telegram connection test: FAILED")
            return False
    except Exception as e:
        logger.error(f"Telegram connection error: {e}")
        return False

def handle_captcha_protection(sb, url, step_name):
    """Handle CAPTCHA protection for any page with enhanced logging"""
    logger.info(f"🛡️ Checking CAPTCHA protection for {step_name}...")
    
    # Navigate to the page
    sb.driver.get(url)
    time.sleep(5)
    
    # Check for CAPTCHA
    captcha_detected, captcha_type = detect_captcha(sb.driver)
    
    if captcha_detected:
        logger.warning(f"🚫 CAPTCHA detected on {step_name}: {captcha_type}")
        take_screenshot(sb.driver, f"captcha_{step_name}")
        
        # Send enhanced alert to Telegram
        alert_msg = (
            f"🛡️ **CAPTCHA Detected**\n\n"
            f"📋 **Step:** {step_name}\n"
            f"🔍 **Type:** {captcha_type}\n"
            f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
            f"🔄 **Action:** Attempting automatic bypass..."
        )
        send_message(alert_msg)
        
        # Attempt to bypass CAPTCHA
        if bypass_captcha(sb):
            success_msg = (
                f"✅ **CAPTCHA Bypassed**\n\n"
                f"📋 **Step:** {step_name}\n"
                f"🔍 **Type:** {captcha_type}\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                f"🎯 **Status:** Proceeding to next step"
            )
            send_message(success_msg)
            logger.info("✅ CAPTCHA bypass successful!")
            return True
        else:
            logger.warning("❌ Automatic CAPTCHA bypass failed, waiting for manual solution...")
            manual_msg = (
                f"❌ **Manual CAPTCHA Required**\n\n"
                f"📋 **Step:** {step_name}\n"
                f"🔍 **Type:** {captcha_type}\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                f"💡 **Action:** Please solve CAPTCHA manually in the browser"
            )
            send_message(manual_msg)
            
            # Wait for manual CAPTCHA solution
            if wait_for_captcha_solution(sb):
                solved_msg = (
                    f"✅ **CAPTCHA Solved**\n\n"
                    f"📋 **Step:** {step_name}\n"
                    f"🔍 **Type:** {captcha_type}\n"
                    f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                    f"🎯 **Status:** Manually solved, proceeding..."
                )
                send_message(solved_msg)
                logger.info("✅ CAPTCHA solved manually!")
                return True
            else:
                logger.error("❌ CAPTCHA not solved within timeout")
                return False
    else:
        logger.info(f"✅ No CAPTCHA detected on {step_name}")
        return True

def wait_for_manual_login(sb):
    """Wait for manual login with enhanced monitoring"""
    logger.info("🔐 Waiting for manual login after CAPTCHA bypass...")
    
    login_msg = (
        "🔐 **Manual Login Required**\n\n"
        "🛡️ **Status:** CAPTCHA bypass completed\n"
        f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
        "💡 **Action:** Please login manually in the browser\n"
        "🎯 **Next:** Auto-redirect to calls page after login"
    )
    send_message(login_msg)
    
    start_time = time.time()
    last_status_update = time.time()
    
    while time.time() - start_time < 600:  # 10 minutes timeout
        current_url = sb.driver.current_url
        
        # Check if login successful (redirected to base URL)
        if current_url == "https://www.orangecarrier.com/" or current_url.startswith(config.BASE_URL + "/"):
            logger.info("✅ Login successful detected!")
            
            success_msg = (
                "✅ **Login Successful**\n\n"
                "🔐 **Status:** Successfully authenticated\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                "🔄 **Next:** Auto-navigating to calls page..."
            )
            send_message(success_msg)
            
            # Save cookies for future sessions
            save_cookies(sb.driver)
            
            # Take screenshot of successful login
            take_screenshot(sb.driver, "login_success")
            
            return True
        
        # Check for CAPTCHA during login wait
        captcha_detected, captcha_type = detect_captcha(sb.driver)
        if captcha_detected:
            logger.warning(f"CAPTCHA appeared during login: {captcha_type}")
            captcha_msg = (
                f"🛡️ **CAPTCHA Reappeared**\n\n"
                f"📋 **During:** Login Process\n"
                f"🔍 **Type:** {captcha_type}\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                f"🔄 **Action:** Attempting bypass..."
            )
            send_message(captcha_msg)
            handle_captcha_protection(sb, current_url, "Login CAPTCHA")
        
        # Send status update every 30 seconds
        if time.time() - last_status_update > 30:
            status_msg = (
                "⏳ **Login Status Update**\n\n"
                "🔐 **Status:** Waiting for manual login\n"
                f"⏰ **Elapsed:** {int(time.time() - start_time)} seconds\n"
                f"📅 **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                "💡 **Reminder:** Please complete login in browser"
            )
            send_message(status_msg)
            last_status_update = time.time()
        
        time.sleep(5)
    
    logger.error("⏰ Login timeout")
    timeout_msg = (
        "❌ **Login Timeout**\n\n"
        "🔐 **Status:** Manual login not completed\n"
        f"⏰ **Timeout:** 10 minutes exceeded\n"
        f"📅 **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
        "💡 **Action:** Please check browser and restart script"
    )
    send_message(timeout_msg)
    return False

def main():
    """Main monitoring function with enhanced step-by-step process"""
    logger.info("🚀 Starting Enhanced Call Monitoring System...")
    
    if not check_telegram_connection():
        logger.error("❌ Cannot start without Telegram connection")
        return
    
    # Enhanced SeleniumBase configuration
    sb_config = {
        'uc': True,              # Undetected Chrome mode
        'headed': True,          # Show browser window
        'uc_cdp': True,          # Chrome DevTools Protocol
        'block_images': False,   # Load images for realism
        'disable_js': False,     # Enable JavaScript
    }
    
    with SB(**sb_config) as sb:
        try:
            logger.info("✅ SeleniumBase UC Mode activated successfully!")
            
            # Set user agent manually after driver initialization
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
            ]
            
            selected_ua = random.choice(user_agents)
            sb.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": selected_ua})
            logger.info(f"🌐 User Agent set: {selected_ua[:50]}...")
            
            # Step 1: Handle CAPTCHA protection for login page
            logger.info("🔐 Step 1: Accessing login page with CAPTCHA protection...")
            if not handle_captcha_protection(sb, config.LOGIN_URL, "Login Page"):
                logger.error("❌ Failed to bypass CAPTCHA on login page")
                return
            
            # Step 2: Try to load existing session
            if os.path.exists('session/cookies.json'):
                logger.info("🔄 Step 2: Attempting to restore previous session...")
                if load_cookies(sb.driver):
                    sb.driver.refresh()
                    time.sleep(3)
                    
                    # Check if we're automatically logged in
                    if sb.driver.current_url == "https://www.orangecarrier.com/" or sb.driver.current_url.startswith(config.BASE_URL + "/"):
                        logger.info("✅ Session restored successfully!")
                        session_msg = (
                            "✅ **Session Restored**\n\n"
                            "🔐 **Status:** Auto-login successful\n"
                            f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                            "🔄 **Next:** Proceeding to calls page..."
                        )
                        send_message(session_msg)
                    else:
                        logger.info("❌ Session expired, proceeding with manual login")
            
            # Step 3: Manual login handling
            if config.LOGIN_URL in sb.driver.current_url:
                logger.info("🔐 Step 3: Manual login required...")
                if not wait_for_manual_login(sb):
                    logger.error("❌ Manual login failed")
                    return
            
            # Step 4: Auto-navigate to calls page
            logger.info("📊 Step 4: Auto-navigating to calls page...")
            calls_msg = (
                "🔄 **Auto-Navigation**\n\n"
                "📋 **Step:** Redirecting to calls page\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                "🎯 **Next:** Starting call monitoring..."
            )
            send_message(calls_msg)
            
            # Handle CAPTCHA protection for calls page
            if not handle_captcha_protection(sb, config.CALL_URL, "Calls Page"):
                logger.error("❌ Failed to access calls page")
                return
            
            # Step 5: Wait for calls table and start monitoring
            logger.info("🎯 Step 5: Starting call monitoring...")
            try:
                WebDriverWait(sb.driver, 30).until(
                    EC.presence_of_element_located((By.ID, "LiveCalls"))
                )
                logger.info("✅ Active Calls page loaded successfully!")
                
                monitoring_msg = (
                    "🎯 **Call Monitoring Active**\n\n"
                    "📋 **Status:** System ready\n"
                    f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n"
                    "🌐 **Page:** Calls dashboard loaded\n\n"
                    "🔍 **Action:** Monitoring for incoming calls..."
                )
                send_message(monitoring_msg)
                
            except TimeoutException:
                logger.warning("⚠️ Calls table not found immediately, but continuing...")
                take_screenshot(sb.driver, "calls_table_missing")
            
            take_screenshot(sb.driver, "monitoring_active")
            
            # Enhanced monitoring loop
            error_count = 0
            last_recording_check = datetime.now()
            last_refresh = datetime.now()
            last_health_check = datetime.now()
            last_status_report = datetime.now()
            
            logger.info("🚀 Enhanced monitoring started with real-time CAPTCHA protection!")
            
            while error_count < getattr(config, 'MAX_ERRORS', 10):
                try:
                    current_time = datetime.now()
                    
                    # Health check every 5 minutes
                    if (current_time - last_health_check).total_seconds() > 300:
                        logger.info("💚 System health check: OK")
                        last_health_check = current_time
                    
                    # Status report every 10 minutes
                    if (current_time - last_status_report).total_seconds() > 600:
                        status_report = (
                            "📊 **System Status Report**\n\n"
                            "💚 **Health:** System running normally\n"
                            f"📞 **Active Calls:** {len(active_calls)}\n"
                            f"⏳ **Pending Recordings:** {len(pending_recordings)}\n"
                            f"⏰ **Uptime:** {int((current_time - last_status_report).total_seconds() / 60)} minutes\n"
                            f"📅 **Time:** {current_time.strftime('%I:%M:%S %p')}"
                        )
                        send_message(status_report)
                        last_status_report = current_time
                    
                    # Refresh page periodically
                    if (current_time - last_refresh).total_seconds() > random.randint(1200, 1800):
                        logger.info("🔄 Refreshing page...")
                        refresh_msg = (
                            "🔄 **Page Refresh**\n\n"
                            "📋 **Action:** Refreshing calls page\n"
                            f"⏰ **Time:** {current_time.strftime('%I:%M:%S %p')}\n\n"
                            "💡 **Reason:** Maintain session and update data"
                        )
                        send_message(refresh_msg)
                        
                        if not handle_captcha_protection(sb, config.CALL_URL, "Refresh CAPTCHA"):
                            logger.error("❌ CAPTCHA blocking page refresh")
                        else:
                            last_refresh = current_time
                    
                    # Check session
                    if config.LOGIN_URL in sb.driver.current_url:
                        logger.warning("🔐 Session expired, re-logging...")
                        session_msg = (
                            "🔐 **Session Expired**\n\n"
                            "📋 **Status:** Re-authentication required\n"
                            f"⏰ **Time:** {current_time.strftime('%I:%M:%S %p')}\n\n"
                            "🔄 **Action:** Attempting auto-login..."
                        )
                        send_message(session_msg)
                        
                        if not handle_captcha_protection(sb, config.LOGIN_URL, "Re-login CAPTCHA"):
                            break
                    
                    # Extract and process calls
                    extract_calls(sb.driver)
                    
                    # Process pending recordings
                    if (current_time - last_recording_check).total_seconds() >= getattr(config, 'CHECK_INTERVAL', 10):
                        process_pending_recordings(sb.driver)
                        last_recording_check = current_time
                    
                    error_count = 0
                    time.sleep(getattr(config, 'CHECK_INTERVAL', 10))
                    
                except KeyboardInterrupt:
                    logger.info("🛑 Monitoring stopped by user")
                    stop_msg = (
                        "🛑 **Monitoring Stopped**\n\n"
                        "📋 **Reason:** User interrupt\n"
                        f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                        "💡 **Action:** Manual stop requested"
                    )
                    send_message(stop_msg)
                    break
                except Exception as e:
                    error_count += 1
                    logger.error(f"Monitoring error ({error_count}/{getattr(config, 'MAX_ERRORS', 10)}): {e}")
                    
                    if error_count >= getattr(config, 'MAX_ERRORS', 10):
                        error_msg = (
                            "💥 **Maximum Errors Reached**\n\n"
                            "📋 **Status:** Monitoring stopped\n"
                            f"❌ **Errors:** {error_count} consecutive errors\n"
                            f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                            "💡 **Action:** Please check system and restart"
                        )
                        send_message(error_msg)
                        break
                    
                    time.sleep(10)
                    
        except Exception as e:
            logger.error(f"💥 Fatal error in SeleniumBase: {e}")
            fatal_msg = (
                "💥 **Fatal System Error**\n\n"
                f"📋 **Error:** {str(e)}\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                "🚨 **Action:** System shutdown required"
            )
            send_message(fatal_msg)
        
        finally:
            logger.info("🔚 Closing SeleniumBase...")
            shutdown_msg = (
                "🔚 **System Shutdown**\n\n"
                "📋 **Status:** Monitoring stopped\n"
                f"⏰ **Time:** {datetime.now().strftime('%I:%M:%S %p')}\n\n"
                "💡 **Action:** Call monitoring ended"
            )
            send_message(shutdown_msg)

    logger.info("🛑 Monitoring stopped")

if __name__ == "__main__":
    print("🚀 Enhanced Call Monitor with CAPTCHA Bypass Starting...")
    print("=" * 60)
    print("🛡️  Features: Real-time CAPTCHA Detection, Auto Bypass")
    print("📞 Enhanced: Call Detection, Voice Recording, Telegram Notifications")
    print("🔐 Secure: Private System, Session Persistence")
    print("=" * 60)
    
    try:
        import seleniumbase
    except ImportError:
        print("📦 Installing SeleniumBase...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "seleniumbase"])
        print("✅ SeleniumBase installed successfully!")
    
    main()