import time
import re
import requests
import os
from datetime import datetime, timedelta
from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import phonenumbers
from phonenumbers import region_code_for_number
import pycountry
import config
import json

active_calls = {}
pending_recordings = {}
processed_recordings = set()

os.makedirs(config.DOWNLOAD_FOLDER, exist_ok=True)

def country_to_flag(country_code):
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def detect_country(number):
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
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "****" + digits[-3:]
    return number

def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
        payload = {"chat_id": config.CHAT_ID, "text": text, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload, timeout=10)
        if res.ok:
            return res.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[❌] Failed to send message: {e}")
    return None

def delete_message(msg_id):
    try:
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/deleteMessage"
        requests.post(url, data={"chat_id": config.CHAT_ID, "message_id": msg_id}, timeout=5)
    except:
        pass

def send_voice_with_caption(voice_path, caption):
    try:
        if os.path.getsize(voice_path) < 1000:
            raise ValueError("File too small or empty")
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendVoice"
        with open(voice_path, "rb") as voice:
            payload = {"chat_id": config.CHAT_ID, "caption": caption, "parse_mode": "HTML"}
            files = {"voice": voice}
            response = requests.post(url, data=payload, files=files, timeout=60)
            time.sleep(2)
            if response.status_code == 200:
                return True
            else:
                print(f"[DEBUG] Telegram response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[❌] Failed to send voice: {e}")
    return False

def get_authenticated_session(driver):
    session = requests.Session()
    selenium_cookies = driver.get_cookies()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    
    # Add common headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': config.CALL_URL,
        'X-Requested-With': 'XMLHttpRequest'
    })
    return session

def get_activity_data(driver, session):
    """Get call activity data from the activity API"""
    try:
        # Try to get activity data via API call
        activity_url = config.ACTIVITY_CHECK_URL
        params = {
            'draw': '1',
            'start': '0', 
            'length': '50',
            'search[value]': '',
            'search[regex]': 'false'
        }
        
        response = session.get(activity_url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"[❌] Activity API error: {e}")
    
    return None

def find_recording_in_activity(driver, session, call_uuid, did_number):
    """Find recording in activity data"""
    try:
        activity_data = get_activity_data(driver, session)
        if activity_data and 'data' in activity_data:
            for call in activity_data['data']:
                if len(call) > 0:
                    # Check if this call matches our UUID or DID number
                    call_info = str(call).lower()
                    if call_uuid.lower() in call_info or did_number in call_info:
                        # Look for play button in the call data
                        if any('play' in str(item).lower() for item in call):
                            print(f"[✅] Found recording in activity for {did_number}")
                            return True
    except Exception as e:
        print(f"[❌] Error searching activity: {e}")
    
    return False

def download_recording_from_api(driver, did_number, call_uuid, file_path):
    """Download recording using API call"""
    try:
        session = get_authenticated_session(driver)
        
        # Method 1: Try the original URL
        recording_url = f"https://www.orangecarrier.com/live/calls/sound?did={did_number}&uuid={call_uuid}"
        
        # Method 2: Alternative API endpoint
        alt_url = f"https://www.orangecarrier.com/live/calls/recording?call_id={call_uuid}"
        
        for url in [recording_url, alt_url]:
            try:
                print(f"[🔍] Trying URL: {url}")
                response = session.get(url, timeout=30, stream=True)
                
                if response.status_code == 200:
                    content_length = int(response.headers.get('Content-Length', 0))
                    print(f"[DEBUG] Response status: {response.status_code}, Size: {content_length}")
                    
                    if content_length > 1000:
                        with open(file_path, "wb") as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        file_size = os.path.getsize(file_path)
                        if file_size > 1000:
                            print(f"[✅] Recording downloaded: {file_size} bytes")
                            return True
                        else:
                            os.remove(file_path)
                            print(f"[❌] File too small: {file_size} bytes")
                    else:
                        print(f"[❌] Content too small: {content_length}")
                else:
                    print(f"[❌] HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                print(f"[❌] Download attempt failed: {e}")
                continue
                
        # Method 3: Wait for recording to appear in activity and retry
        print(f"[⏳] Waiting for recording to be available...")
        for attempt in range(5):
            time.sleep(10)
            if find_recording_in_activity(driver, session, call_uuid, did_number):
                # Retry download after recording appears in activity
                response = session.get(recording_url, timeout=30, stream=True)
                if response.status_code == 200 and int(response.headers.get('Content-Length', 0)) > 1000:
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return True
                    
    except Exception as e:
        print(f"[❌] API download failed: {e}")
    
    return False

def extract_calls(driver):
    global active_calls, pending_recordings
    
    try:
        # Wait for calls table
        calls_table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "LiveCalls"))
        )
        
        rows = calls_table.find_elements(By.TAG_NAME, "tr")
        current_call_ids = set()
        
        for row in rows:
            try:
                row_id = row.get_attribute('id')
                if not row_id or 'call-' not in row_id:
                    continue
                    
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 5:
                    continue
                
                # Extract phone number
                did_element = cells[1]
                did_text = did_element.text.strip()
                did_number = re.sub(r"\D", "", did_text)
                
                if not did_number:
                    continue
                
                current_call_ids.add(row_id)
                
                if row_id not in active_calls:
                    print(f"[📞] New call: {did_number}")
                    
                    country_name, flag = detect_country(did_number)
                    masked = mask_number(did_number)
                    
                    alert_text = f"📞 New call detected from {flag} {masked}. Waiting for it to end."
                    
                    msg_id = send_message(alert_text)
                    active_calls[row_id] = {
                        "msg_id": msg_id,
                        "flag": flag,
                        "country": country_name,
                        "masked": masked,
                        "did_number": did_number,
                        "detected_at": datetime.now(),
                        "last_seen": datetime.now(),
                        "call_uuid": row_id.replace('call-', '')
                    }
                else:
                    active_calls[row_id]["last_seen"] = datetime.now()
                    
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"[❌] Row error: {e}")
                continue
        
        # Check for completed calls
        current_time = datetime.now()
        completed_calls = []
        
        for call_id, call_info in list(active_calls.items()):
            if (call_id not in current_call_ids) or \
               ((current_time - call_info["last_seen"]).total_seconds() > 15):
                if call_id not in pending_recordings:
                    print(f"[✅] Call completed: {call_info['did_number']}")
                    completed_calls.append(call_id)
        
        # Move completed calls to pending recordings
        for call_id in completed_calls:
            call_info = active_calls[call_id]
            
            pending_recordings[call_id] = {
                **call_info,
                "completed_at": datetime.now(),
                "checks": 0,
                "last_check": datetime.now()
            }
            
            wait_text = f"{call_info['flag']} {call_info['masked']} — Processing recording..."
            
            if call_info["msg_id"]:
                delete_message(call_info["msg_id"])
            
            new_msg_id = send_message(wait_text)
            if new_msg_id:
                pending_recordings[call_id]["msg_id"] = new_msg_id
            
            del active_calls[call_id]
                
    except TimeoutException:
        print("[⏱️] No active calls table")
    except Exception as e:
        print(f"[❌] Extract error: {e}")

def process_pending_recordings(driver):
    global pending_recordings, processed_recordings
    
    current_time = datetime.now()
    processed_calls = []
    
    for call_id, call_info in list(pending_recordings.items()):
        try:
            # Skip if already processed
            if call_id in processed_recordings:
                processed_calls.append(call_id)
                continue
            
            time_since_check = (current_time - call_info["last_check"]).total_seconds()
            if time_since_check < config.RECORDING_RETRY_DELAY:
                continue
            
            call_info["checks"] += 1
            call_info["last_check"] = current_time
            
            print(f"[🔍] Check #{call_info['checks']} for: {call_info['did_number']}")
            
            # Max checks limit
            if call_info["checks"] > 15:
                print("[⏰] Max checks exceeded for recording")
                timeout_text = f"❌ Recording not available for {call_info['flag']} {call_info['masked']}"
                if call_info.get("msg_id"):
                    delete_message(call_info["msg_id"])
                send_message(timeout_text)
                processed_calls.append(call_id)
                continue
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_{call_info['did_number']}_{timestamp}.mp3")
            
            # Try to download recording
            if download_recording_from_api(driver, call_info['did_number'], call_info['call_uuid'], file_path):
                if process_recording_file(call_info, file_path):
                    processed_recordings.add(call_id)
                    processed_calls.append(call_id)
                else:
                    print(f"[❌] Failed to process recording file: {call_info['did_number']}")
            else:
                print(f"[❌] Recording not available yet: {call_info['did_number']}")
            
            # Check timeout
            time_since_complete = (current_time - call_info["completed_at"]).total_seconds()
            if time_since_complete > config.MAX_RECORDING_WAIT:
                print(f"[⏰] Timeout: {call_info['did_number']}")
                timeout_text = f"❌ Recording timeout for {call_info['flag']} {call_info['masked']}"
                
                if call_info.get("msg_id"):
                    delete_message(call_info["msg_id"])
                
                send_message(timeout_text)
                processed_calls.append(call_id)
                
        except Exception as e:
            print(f"[❌] Processing error: {e}")
    
    # Clean up processed calls
    for call_id in processed_calls:
        if call_id in pending_recordings:
            del pending_recordings[call_id]

def process_recording_file(call_info, file_path):
    try:
        # Delete waiting message
        if call_info.get("msg_id"):
            delete_message(call_info["msg_id"])
        
        # Format call time
        call_time = call_info['detected_at'].strftime('%Y-%m-%d %I:%M:%S %p')
        
        # Create caption
        caption = (
            "🔥 NEW CALL RECEIVED ✨\n\n"
            f"⏰ Time: {call_time}\n"
            f"{call_info['flag']} Country: {call_info['country']}\n"
            f"🚀 Number: {call_info['masked']}\n\n"
            f"🌟 Configure by @professor_cry"
        )
        
        # Send voice with caption
        if send_voice_with_caption(file_path, caption):
            print(f"[✅] Recording sent: {call_info['did_number']}")
            
            # Clean up file after sending
            try:
                os.remove(file_path)
            except:
                pass
                
            return True
        else:
            # Fallback: send message with error
            error_text = f"❌ Failed to send recording for {call_info['flag']} {call_info['masked']}"
            send_message(error_text)
            return False
            
    except Exception as e:
        print(f"[❌] File processing error: {e}")
        error_text = f"❌ Processing error for {call_info['flag']} {call_info['masked']}"
        send_message(error_text)
        return False

def handle_captcha_protection(sb, url, step_name):
    """Handle CAPTCHA protection"""
    print(f"🛡️ Checking CAPTCHA protection for {step_name}...")
    sb.driver.uc_open_with_reconnect(url, reconnect_time=4)
    sb.uc_gui_click_captcha()
    print(f"✅ CAPTCHA handling attempted for {step_name}")

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

def check_session_valid(sb):
    """Check if session is still valid"""
    try:
        sb.driver.find_element(By.ID, "LiveCalls")
        return True
    except:
        return False

def main():
    with SB(uc=True, headed=True, incognito=True) as sb:
        try:
            # Login
            if not wait_for_login(sb):
                return
            
            # Navigate to calls page
            handle_captcha_protection(sb, config.CALL_URL, "Calls Page")
            
            # Wait for calls table
            WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
            print("✅ Active Calls page loaded!")
            print("[*] Monitoring started...")

            error_count = 0
            last_recording_check = datetime.now()
            last_refresh = datetime.now()
            last_session_check = datetime.now()
            
            while error_count < config.MAX_ERRORS:
                try:
                    current_time = datetime.now()
                    
                    # Check session every 2 minutes
                    if (current_time - last_session_check).total_seconds() > 120:
                        if not check_session_valid(sb):
                            print("[⚠️] Session invalid, refreshing...")
                            sb.driver.refresh()
                            WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
                        last_session_check = current_time
                    
                    # Refresh page every 20 minutes
                    if (current_time - last_refresh).total_seconds() > 1200:
                        sb.driver.refresh()
                        WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
                        last_refresh = current_time
                        print("[🔄] Page refreshed to maintain session")
                    
                    # Check if logged in
                    if config.LOGIN_URL in sb.driver.current_url:
                        print("[⚠️] Session expired, re-logging in")
                        if not wait_for_login(sb):
                            break
                        handle_captcha_protection(sb, config.CALL_URL, "Re-login Calls Page")
                    
                    # Extract active calls
                    extract_calls(sb.driver)
                    
                    # Process pending recordings
                    if (current_time - last_recording_check).total_seconds() >= 10:
                        process_pending_recordings(sb.driver)
                        last_recording_check = current_time
                    
                    error_count = 0
                    time.sleep(config.CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    print("\n[🛑] Stopped by user")
                    break
                except Exception as e:
                    error_count += 1
                    print(f"[❌] Main loop error ({error_count}/{config.MAX_ERRORS}): {e}")
                    time.sleep(5)
                    
        except Exception as e:
            print(f"[💥] Fatal error: {e}")
    
    print("[*] Monitoring stopped")

if __name__ == "__main__":
    main()