import time
import re
import requests
import os
import random
from datetime import datetime, timedelta
from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
import phonenumbers
from phonenumbers import region_code_for_number
import pycountry
import config
import threading
from concurrent.futures import ThreadPoolExecutor
import base64

# Global variables
active_calls = {}
processing_calls = set()
refresh_pattern_index = 0
bot_start_time = None
monitoring_active = True
executor = ThreadPoolExecutor(max_workers=5)

# Refresh pattern in seconds
REFRESH_PATTERN = [300, 245, 310, 250, 350]

os.makedirs(config.DOWNLOAD_FOLDER, exist_ok=True)

def human_like_delay(min_seconds=1, max_seconds=3):
    """Human-like random delay"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_like_mouse_movement(driver, element):
    """Simulate human-like mouse movement"""
    try:
        location = element.location
        size = element.size
        
        offset_x = random.randint(0, size['width'] // 2)
        offset_y = random.randint(0, size['height'] // 2)
        
        action = ActionChains(driver)
        action.move_to_element_with_offset(element, offset_x, offset_y)
        action.pause(random.uniform(0.1, 0.3))
        action.click()
        action.perform()
    except:
        element.click()

def get_next_refresh_time():
    """Get next refresh time using the specified pattern"""
    global refresh_pattern_index
    
    interval = REFRESH_PATTERN[refresh_pattern_index]
    refresh_pattern_index = (refresh_pattern_index + 1) % len(REFRESH_PATTERN)
    
    print(f"[🔄] Next refresh in {interval} seconds ({interval//60} minutes {interval%60} seconds)")
    return interval

def country_to_flag(country_code):
    """Convert country code to flag emoji"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

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
    except:
        pass
    return "Unknown", "🏳️"

def mask_number(number):
    """Mask phone number for privacy"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "****" + digits[-3:]
    return number

def send_message(text, delete_after=None):
    """Send message to Telegram with optional auto-delete"""
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
        payload = {"chat_id": config.CHAT_ID, "text": text, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload, timeout=10)
        if res.ok:
            msg_id = res.json().get("result", {}).get("message_id")
            if delete_after and msg_id:
                threading.Timer(delete_after, delete_message, args=[msg_id]).start()
            return msg_id
    except Exception as e:
        print(f"[❌] Failed to send message: {e}")
    return None

def delete_message(msg_id):
    """Delete message from Telegram"""
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage"
        requests.post(url, data={"chat_id": config.CHAT_ID, "message_id": msg_id}, timeout=5)
        print(f"[🗑️] Message {msg_id} deleted")
    except Exception as e:
        print(f"[❌] Failed to delete message {msg_id}: {e}")

def send_bot_started_message():
    """Send bot started message to group"""
    global bot_start_time
    bot_start_time = datetime.now()
    start_time_str = bot_start_time.strftime("%Y-%m-%d %I:%M:%S %p")
    
    message = (
        "🤖 *Bot Status Update*\n\n"
        "✅ *Bot Started Successfully*\n"
        f"⏰ Start Time: {start_time_str}\n"
        "📊 Monitoring: ACTIVE\n\n"
        "🚀 Ready to monitor calls..."
    )
    
    msg_id = send_message(message)
    print("[🤖] Bot started message sent to group")
    return msg_id

def send_refresh_warning():
    """Send browser refresh warning 10 seconds before refresh"""
    message = (
        "🔄 *Browser Refresh Alert*\n\n"
        "⚠️ Browser will refresh in *10 seconds*\n"
        "📊 Monitoring will pause briefly...\n"
        "⏳ Please wait for completion message"
    )
    
    msg_id = send_message(message, delete_after=10)
    print("[⚠️] Refresh warning sent to group (will delete in 10s)")
    return msg_id

def send_refresh_complete():
    """Send browser refresh completion message"""
    global bot_start_time
    
    current_time = datetime.now()
    uptime = current_time - bot_start_time if bot_start_time else timedelta(0)
    uptime_str = str(uptime).split('.')[0]
    
    message = (
        "✅ *Browser Refresh Complete*\n\n"
        "🔄 Refresh: SUCCESSFUL\n"
        f"⏰ Uptime: {uptime_str}\n"
        "📊 Monitoring: RESUMED\n"
        "🔥 Back to active monitoring..."
    )
    
    msg_id = send_message(message, delete_after=10)
    print("[✅] Refresh complete message sent to group (will delete in 10s)")
    return msg_id

def send_monitoring_stopped(reason="Unknown reason"):
    """Send monitoring stopped alert"""
    global bot_start_time
    
    current_time = datetime.now()
    if bot_start_time:
        uptime = current_time - bot_start_time
        uptime_str = str(uptime).split('.')[0]
    else:
        uptime_str = "Unknown"
    
    message = (
        "❌ *Monitoring Stopped*\n\n"
        f"📛 Reason: {reason}\n"
        f"⏰ Uptime: {uptime_str}\n"
        f"🕒 Time: {current_time.strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
        "⚠️ Attention required!\n"
        "🔄 Please restart the bot..."
    )
    
    msg_id = send_message(message, delete_after=900)
    print(f"[❌] Monitoring stopped alert sent to group (will delete in 15m): {reason}")
    return msg_id

def send_voice_with_caption(voice_path, caption):
    """Send voice recording with caption to Telegram"""
    try:
        if os.path.getsize(voice_path) < 1000:
            raise ValueError("File too small or empty")
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendVoice"
        with open(voice_path, "rb") as voice:
            payload = {"chat_id": config.CHAT_ID, "caption": caption, "parse_mode": "HTML"}
            files = {"voice": voice}
            response = requests.post(url, data=payload, files=files, timeout=60)
            if response.status_code == 200:
                return True
            else:
                print(f"[DEBUG] Telegram response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[❌] Failed to send voice: {e}")
    return False

def solve_cloudflare_captcha_advanced(driver):
    """Advanced CloudFlare CAPTCHA solver with multiple approaches"""
    try:
        print("[🛡️] Advanced CloudFlare CAPTCHA solver activated...")
        
        # Approach 1: Try to find and click the CAPTCHA iframe
        try:
            captcha_iframe = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "iframe[src*='challenges.cloudflare.com'], iframe[title*='challenge'], iframe[src*='recaptcha']"))
            )
            
            if captcha_iframe:
                print("[🔍] CAPTCHA iframe found, attempting auto-completion...")
                driver.switch_to.frame(captcha_iframe)
                
                checkbox_selectors = [
                    "input[type='checkbox']",
                    ".recaptcha-checkbox-border",
                    "#recaptcha-anchor",
                    ".cf-challenge-checkbox",
                    ".h-captcha",
                    ".checkbox"
                ]
                
                for selector in checkbox_selectors:
                    try:
                        checkbox = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        if checkbox:
                            print(f"[✅] CAPTCHA checkbox found with selector: {selector}")
                            human_like_delay(2, 4)
                            human_like_mouse_movement(driver, checkbox)
                            print("[👆] CAPTCHA checkbox clicked, waiting for verification...")
                            human_like_delay(8, 12)
                            
                            try:
                                verified_indicator = driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-checked, .cf-challenge-success")
                                if verified_indicator:
                                    print("[🎉] CAPTCHA verification completed automatically!")
                                    driver.switch_to.default_content()
                                    return True
                            except:
                                pass
                            break
                    except:
                        continue
                
                driver.switch_to.default_content()
                
        except TimeoutException:
            print("[⏱️] No CAPTCHA iframe found with first approach")
            driver.switch_to.default_content()
        
        # Approach 2: Look for challenge form and submit
        try:
            challenge_form = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[action*='challenge'], .challenge-form"))
            )
            
            if challenge_form:
                print("[🔍] Challenge form found, looking for submit button...")
                
                submit_selectors = [
                    "input[type='submit']",
                    "button[type='submit']",
                    ".btn-success",
                    ".button--success",
                    "[type='submit']"
                ]
                
                for selector in submit_selectors:
                    try:
                        submit_btn = challenge_form.find_element(By.CSS_SELECTOR, selector)
                        if submit_btn and submit_btn.is_enabled():
                            human_like_delay(2, 3)
                            human_like_mouse_movement(driver, submit_btn)
                            print("[✅] Challenge form submitted")
                            human_like_delay(5, 8)
                            return True
                    except:
                        continue
                        
        except TimeoutException:
            print("[⏱️] No challenge form found")
        
        # Approach 3: Direct CAPTCHA element detection
        captcha_elements = driver.find_elements(By.CSS_SELECTOR, 
            ".cf-captcha, .captcha, .hcaptcha, .g-recaptcha, [data-sitekey]")
        
        if captcha_elements:
            print(f"[🔍] Found {len(captcha_elements)} CAPTCHA elements, attempting interaction...")
            
            for element in captcha_elements:
                try:
                    if element.is_displayed() and element.is_enabled():
                        human_like_delay(1, 2)
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                        human_like_delay(1, 2)
                        human_like_mouse_movement(driver, element)
                        print("[👆] CAPTCHA element clicked")
                        human_like_delay(6, 10)
                        return True
                except:
                    continue
        
        print("[❌] CAPTCHA auto-completion failed with all approaches")
        return False
        
    except Exception as e:
        print(f"[💥] Advanced CAPTCHA solver error: {e}")
        driver.switch_to.default_content()
        return False

def check_and_solve_captcha(driver):
    """Check for CAPTCHA and attempt to solve it with enhanced detection"""
    try:
        captcha_indicators = [
            "challenges.cloudflare.com",
            "cf-challenge", 
            "recaptcha",
            "hcaptcha",
            "Just a moment",
            "Checking your browser",
            "Verifying you are human",
            "Challenge",
            "Security check"
        ]
        
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()
        page_title = driver.title.lower()
        
        for indicator in captcha_indicators:
            indicator_lower = indicator.lower()
            if (indicator_lower in page_source or 
                indicator_lower in current_url or 
                indicator_lower in page_title):
                print(f"[🛡️] CAPTCHA detected: {indicator}")
                return solve_cloudflare_captcha_advanced(driver)
        
        captcha_selectors = [
            ".cf-captcha",
            ".captcha", 
            ".hcaptcha",
            ".g-recaptcha",
            "[data-sitekey]",
            "iframe[src*='captcha']",
            "iframe[src*='challenge']"
        ]
        
        for selector in captcha_selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    print(f"[🔍] CAPTCHA element found with selector: {selector}")
                    return solve_cloudflare_captcha_advanced(driver)
            except:
                continue
                
        return False
        
    except Exception as e:
        print(f"[❌] Error checking CAPTCHA: {e}")
        return False

def safe_refresh_with_advanced_captcha(driver):
    """Safe page refresh with advanced CAPTCHA handling"""
    max_retries = 2
    retry_count = 0
    
    refresh_warning_msg_id = send_refresh_warning()
    time.sleep(10)
    
    while retry_count <= max_retries:
        try:
            print(f"[🔄] Refreshing page... (Attempt {retry_count + 1})")
            driver.refresh()
            human_like_delay(3, 5)
            
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            human_like_delay(2, 4)
            
            if check_and_solve_captcha(driver):
                print("[✅] CAPTCHA auto-completed successfully")
                human_like_delay(5, 8)
                
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.ID, "LiveCalls"))
                    )
                    print("[✅] Successfully bypassed CAPTCHA and loaded main content")
                    send_refresh_complete()
                    return True
                except TimeoutException:
                    print("[⚠️] Main content not loaded after CAPTCHA, might need retry")
                    retry_count += 1
                    continue
            else:
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.ID, "LiveCalls"))
                    )
                    print("[✅] Page refreshed successfully without CAPTCHA")
                    send_refresh_complete()
                    return True
                except TimeoutException:
                    print("[⚠️] Main content not loaded, might have hidden CAPTCHA")
                    retry_count += 1
                    continue
                    
        except Exception as e:
            print(f"[❌] Refresh attempt {retry_count + 1} failed: {e}")
            retry_count += 1
            human_like_delay(5, 10)
    
    print("[💥] All refresh attempts failed")
    return False

def extract_calls(driver):
    """Extract call information from the calls table with multi-call support"""
    global active_calls, processing_calls
    
    try:
        calls_table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "LiveCalls"))
        )
        
        rows = calls_table.find_elements(By.TAG_NAME, "tr")
        current_call_ids = set()
        
        for row in rows:
            try:
                row_id = row.get_attribute('id')
                if not row_id:
                    continue
                    
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:
                    continue
                
                did_element = cells[1]
                did_text = did_element.text.strip()
                did_number = re.sub(r"\D", "", did_text)
                
                if not did_number:
                    continue
                
                current_call_ids.add(row_id)
                
                if row_id not in active_calls and row_id not in processing_calls:
                    print(f"[📞] New call detected: {did_number}")
                    
                    country_name, flag = detect_country(did_number)
                    masked = mask_number(did_number)
                    
                    alert_text = f"📞 New call from {flag} {masked}. Detected..."
                    
                    msg_id = send_message(alert_text)
                    call_info = {
                        "msg_id": msg_id,
                        "flag": flag,
                        "country": country_name,
                        "masked": masked,
                        "did_number": did_number,
                        "detected_at": datetime.now(),
                        "last_seen": datetime.now()
                    }
                    active_calls[row_id] = call_info
                    
                    # Process call in separate thread for multi-call support
                    executor.submit(process_single_call, driver, call_info, row_id)
                    
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"[❌] Row processing error: {e}")
                continue
                
    except TimeoutException:
        print("[⏱️] No active calls table found")
    except Exception as e:
        print(f"[❌] Error extracting calls: {e}")

def process_single_call(driver, call_info, call_id):
    """Process a single call in separate thread"""
    try:
        processing_calls.add(call_id)
        
        if call_info["msg_id"]:
            delete_message(call_info["msg_id"])
        
        processing_text = f"🔄 Processing uploading for {call_info['flag']} {call_info['masked']}..."
        processing_msg_id = send_message(processing_text)
        
        record_audio_from_browser(driver, call_info, call_id, processing_msg_id)
        
        if call_id in active_calls:
            del active_calls[call_id]
        processing_calls.discard(call_id)
            
    except Exception as e:
        print(f"[💥] Error processing call {call_id}: {e}")
        processing_calls.discard(call_id)

def record_audio_from_browser(driver, call_info, call_uuid, processing_msg_id):
    """Record audio directly from browser using JavaScript audio capture"""
    try:
        print(f"[🎙️] Starting audio recording for: {call_info['did_number']}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_{call_info['did_number']}_{timestamp}.mp3")
        
        record_script = """
        // Function to record audio from an audio element
        function recordAudio(audioElement, duration) {
            return new Promise((resolve, reject) => {
                try {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const source = audioContext.createMediaElementSource(audioElement);
                    const destination = audioContext.createMediaStreamDestination();
                    source.connect(destination);
                    
                    const mediaRecorder = new MediaRecorder(destination.stream);
                    const chunks = [];
                    
                    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
                    mediaRecorder.onstop = () => {
                        const blob = new Blob(chunks, { type: 'audio/mp3' });
                        resolve(blob);
                    };
                    
                    mediaRecorder.start();
                    setTimeout(() => {
                        mediaRecorder.stop();
                        audioContext.close();
                    }, duration);
                    
                } catch (error) {
                    reject(error);
                }
            });
        }
        
        // Find or create audio element
        let audioElement = document.querySelector('audio');
        if (!audioElement) {
            // If no audio element found, try to play the recording first
            try {
                window.Play("%s", "%s");
                // Wait a bit for audio to load
                setTimeout(() => {
                    audioElement = document.querySelector('audio');
                    if (audioElement) {
                        return recordAudio(audioElement, 30000).then(blob => {
                            const reader = new FileReader();
                            reader.onloadend = () => {
                                window.recordedAudioData = reader.result;
                            };
                            reader.readAsDataURL(blob);
                        });
                    }
                }, 3000);
            } catch (e) {
                return "Error: " + e.toString();
            }
        } else {
            return recordAudio(audioElement, 30000).then(blob => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    window.recordedAudioData = reader.result;
                };
                reader.readAsDataURL(blob);
            });
        }
        return "Recording started";
        """ % (call_info['did_number'], call_uuid)
        
        print("[🔴] Starting audio recording...")
        result = driver.execute_script(record_script)
        print(f"[📝] Recording result: {result}")
        
        time.sleep(35)
        
        print("[💾] Retrieving recorded audio...")
        audio_data = driver.execute_script("return window.recordedAudioData || null;")
        
        if audio_data:
            print("[💾] Saving audio file...")
            audio_bytes = base64.b64decode(audio_data.split(',')[1])
            with open(file_path, 'wb') as f:
                f.write(audio_bytes)
            
            file_size = os.path.getsize(file_path)
            print(f"[✅] Audio recorded successfully: {file_size} bytes")
            
            if processing_msg_id:
                delete_message(processing_msg_id)
            
            send_successful_recording(call_info, file_path)
        else:
            print("[❌] No audio data recorded")
            if direct_download_fallback(driver, call_info, call_uuid, file_path, processing_msg_id):
                print("[✅] Fallback download successful")
            else:
                if processing_msg_id:
                    delete_message(processing_msg_id)
                error_text = f"❌ Failed to record call from {call_info['flag']} {call_info['masked']}"
                send_message(error_text)
        
        if call_uuid in processing_calls:
            processing_calls.remove(call_uuid)
            
    except Exception as e:
        print(f"[💥] Recording error: {e}")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_fallback_{call_info['did_number']}_{timestamp}.mp3")
            if direct_download_fallback(driver, call_info, call_uuid, file_path, processing_msg_id):
                print("[✅] Fallback method succeeded")
            else:
                if processing_msg_id:
                    delete_message(processing_msg_id)
                error_text = f"❌ Recording failed for {call_info['flag']} {call_info['masked']}"
                send_message(error_text)
        except Exception as fallback_error:
            print(f"[💥] Fallback also failed: {fallback_error}")
            if processing_msg_id:
                delete_message(processing_msg_id)
        
        if call_uuid in processing_calls:
            processing_calls.remove(call_uuid)

def direct_download_fallback(driver, call_info, call_uuid, file_path, processing_msg_id):
    """Fallback method using direct download with enhanced headers"""
    try:
        print("[🔄] Trying enhanced direct download...")
        
        play_script = f'window.Play("{call_info["did_number"]}", "{call_uuid}"); return true;'
        driver.execute_script(play_script)
        time.sleep(5)
        
        cookies = driver.get_cookies()
        session = requests.Session()
        
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        headers = {
            'User-Agent': driver.execute_script("return navigator.userAgent;"),
            'Accept': 'audio/mpeg, audio/*, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': config.CALL_URL,
            'Origin': 'https://www.orangecarrier.com',
            'Sec-Fetch-Dest': 'audio',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        recording_url = f"https://www.orangecarrier.com/live/calls/sound?did={call_info['did_number']}&uuid={call_uuid}"
        
        response = session.get(recording_url, headers=headers, timeout=30, stream=True)
        
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            if file_size > 1000:
                print(f"[✅] Direct download successful: {file_size} bytes")
                if processing_msg_id:
                    delete_message(processing_msg_id)
                send_successful_recording(call_info, file_path)
                return True
        
        print(f"[❌] Direct download failed: {response.status_code}")
        return False
        
    except Exception as e:
        print(f"[❌] Direct download fallback error: {e}")
        return False

def send_successful_recording(call_info, file_path):
    """Send successful recording to Telegram"""
    try:
        call_time = call_info['detected_at'].strftime('%Y-%m-%d %I:%M:%S %p')
        
        caption = (
            "🔥 NEW CALL RECEIVED ✨\n\n"
            f"⏰ Time: {call_time}\n"
            f"{call_info['flag']} Country: {call_info['country']}\n"
            f"🚀 Number: {call_info['masked']}\n\n"
            f"🌟 Configure by @professor_cry"
        )
        
        if send_voice_with_caption(file_path, caption):
            print(f"[✅] Recording sent successfully: {call_info['did_number']}")
        else:
            send_message(caption + "\n⚠️ Voice file upload failed, but call was recorded.")
            
        try:
            os.remove(file_path)
        except:
            pass
            
    except Exception as e:
        print(f"[❌] Error sending recording: {e}")

def handle_captcha_protection(sb, url, step_name):
    """Handle CAPTCHA protection with advanced auto-solving"""
    print(f"🛡️ CAPTCHA protection check for {step_name}...")
    
    try:
        sb.driver.uc_open_with_reconnect(url, reconnect_time=3)
        human_like_delay(2, 4)
        
        if check_and_solve_captcha(sb.driver):
            print(f"✅ CAPTCHA auto-completion successful for {step_name}")
        else:
            print(f"[🔧] Using enhanced fallback CAPTCHA handling for {step_name}")
            try:
                sb.uc_gui_click_captcha()
            except:
                print("[⚠️] Manual CAPTCHA click failed, continuing...")
        
        human_like_delay(3, 5)
        return True
        
    except Exception as e:
        print(f"[❌] CAPTCHA handling error for {step_name}: {e}")
        return False

def wait_for_login(sb):
    """Wait for manual login"""
    print(f"🔐 Login page: {config.LOGIN_URL}")
    handle_captcha_protection(sb, config.LOGIN_URL, "Login Page")
    print("➡️ Please login manually in the browser...")
    
    try:
        WebDriverWait(sb.driver, 600).until(
            lambda d: d.current_url.startswith(config.BASE_URL) and not d.current_url.startswith(config.LOGIN_URL)
        )
        print("✅ Login successful!")
        return True
    except TimeoutException:
        print("[❌] Login timeout")
        return False

def main():
    global monitoring_active
    
    with SB(uc=True, headed=True, incognito=True) as sb:
        try:
            send_bot_started_message()
            
            if not wait_for_login(sb):
                send_monitoring_stopped("Login failed")
                return
            
            handle_captcha_protection(sb, config.CALL_URL, "Calls Page")
            WebDriverWait(sb.driver, 20).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
            print("✅ Active Calls page loaded!")
            print("[*] Real-time monitoring started...")

            error_count = 0
            last_refresh = datetime.now()
            next_refresh_interval = get_next_refresh_time()
            
            while error_count < config.MAX_ERRORS and monitoring_active:
                try:
                    current_time = datetime.now()
                    time_until_refresh = next_refresh_interval - (current_time - last_refresh).total_seconds()
                    
                    if 0 < time_until_refresh <= 10:
                        send_refresh_warning()
                        time.sleep(time_until_refresh)
                    
                    if (current_time - last_refresh).total_seconds() > next_refresh_interval:
                        print(f"[🔄] Scheduled refresh triggered after {next_refresh_interval} seconds")
                        
                        if safe_refresh_with_advanced_captcha(sb.driver):
                            WebDriverWait(sb.driver, 20).until(
                                EC.presence_of_element_located((By.ID, "LiveCalls"))
                            )
                            last_refresh = current_time
                            next_refresh_interval = get_next_refresh_time()
                            print(f"[✅] Page refreshed successfully at {current_time.strftime('%H:%M:%S')}")
                        else:
                            print("[❌] Page refresh failed, trying to recover...")
                            handle_captcha_protection(sb, config.CALL_URL, "Recovery Refresh")
                            next_refresh_interval = REFRESH_PATTERN[0]
                    
                    if config.LOGIN_URL in sb.driver.current_url:
                        print("[⚠️] Session expired, re-logging in")
                        if not wait_for_login(sb):
                            send_monitoring_stopped("Session expired and re-login failed")
                            break
                        handle_captcha_protection(sb, config.CALL_URL, "Re-login Calls Page")
                    
                    extract_calls(sb.driver)
                    
                    error_count = 0
                    time.sleep(config.CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    print("\n[🛑] Stopped by user")
                    send_monitoring_stopped("Manual interruption by user")
                    break
                except Exception as e:
                    error_count += 1
                    print(f"[❌] Main loop error ({error_count}/{config.MAX_ERRORS}): {e}")
                    
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ["captcha", "cloudflare", "challenge", "security", "verification"]):
                        print("[🛡️] CAPTCHA-related error detected, attempting advanced recovery...")
                        handle_captcha_protection(sb, sb.driver.current_url, "Error Recovery")
                        human_like_delay(10, 15)
                    
                    time.sleep(5)
                    
        except Exception as e:
            print(f"[💥] Fatal error: {e}")
            send_monitoring_stopped(f"Fatal error: {str(e)}")
    
    monitoring_active = False
    executor.shutdown(wait=False)
    print("[*] Monitoring stopped")

if __name__ == "__main__":
    main()