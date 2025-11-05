import time
import re
import requests
import os
from datetime import datetime
from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import phonenumbers
from phonenumbers import region_code_for_number
import pycountry
import config

active_calls = {}
processing_calls = set()

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
            if response.status_code == 200:
                return True
            else:
                print(f"[DEBUG] Telegram response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[❌] Failed to send voice: {e}")
    return False

def extract_calls(driver):
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
                
                if row_id not in active_calls:
                    print(f"[📞] New call detected: {did_number}")
                    
                    country_name, flag = detect_country(did_number)
                    masked = mask_number(did_number)
                    
                    alert_text = f"📞 New call from {flag} {masked}. Monitoring..."
                    
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
                else:
                    active_calls[row_id]["last_seen"] = datetime.now()
                    
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"[❌] Row processing error: {e}")
                continue
        
        current_time = datetime.now()
        completed_calls = []
        
        # Find completed calls
        for call_id, call_info in list(active_calls.items()):
            if (call_id not in current_call_ids) and (call_id not in processing_calls):
                print(f"[✅] Call completed: {call_info['did_number']}")
                completed_calls.append(call_id)
        
        # Process completed calls immediately
        for call_id in completed_calls:
            call_info = active_calls[call_id]
            
            # Mark as processing to avoid duplicate processing
            processing_calls.add(call_id)
            
            # Delete the monitoring message
            if call_info["msg_id"]:
                delete_message(call_info["msg_id"])
            
            # Send immediate processing message
            processing_text = f"🔄 Processing recording for {call_info['flag']} {call_info['masked']}..."
            processing_msg_id = send_message(processing_text)
            
            # Start recording process in a separate thread to avoid blocking
            import threading
            thread = threading.Thread(
                target=record_audio_from_browser,
                args=(driver, call_info, call_id, processing_msg_id)
            )
            thread.daemon = True
            thread.start()
            
            # Remove from active calls
            del active_calls[call_id]
                
    except TimeoutException:
        print("[⏱️] No active calls table found")
    except Exception as e:
        print(f"[❌] Error extracting calls: {e}")

def record_audio_from_browser(driver, call_info, call_uuid, processing_msg_id):
    """Record audio directly from browser using JavaScript audio capture"""
    try:
        print(f"[🎙️] Starting audio recording for: {call_info['did_number']}")
        
        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_{call_info['did_number']}_{timestamp}.mp3")
        
        # JavaScript code to capture audio and convert to blob
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
        
        # Execute recording script
        print("[🔴] Starting audio recording...")
        result = driver.execute_script(record_script)
        print(f"[📝] Recording result: {result}")
        
        # Wait for recording to complete
        time.sleep(35)  # Wait 35 seconds for recording
        
        # Get recorded audio data
        print("[💾] Retrieving recorded audio...")
        audio_data = driver.execute_script("return window.recordedAudioData || null;")
        
        if audio_data:
            # Save audio file
            print("[💾] Saving audio file...")
            import base64
            audio_bytes = base64.b64decode(audio_data.split(',')[1])
            with open(file_path, 'wb') as f:
                f.write(audio_bytes)
            
            file_size = os.path.getsize(file_path)
            print(f"[✅] Audio recorded successfully: {file_size} bytes")
            
            # Delete processing message
            if processing_msg_id:
                delete_message(processing_msg_id)
            
            # Send to Telegram
            send_successful_recording(call_info, file_path)
        else:
            print("[❌] No audio data recorded")
            # Fallback to direct download method
            if direct_download_fallback(driver, call_info, call_uuid, file_path, processing_msg_id):
                print("[✅] Fallback download successful")
            else:
                # Final fallback - send text notification
                if processing_msg_id:
                    delete_message(processing_msg_id)
                error_text = f"❌ Failed to record call from {call_info['flag']} {call_info['masked']}"
                send_message(error_text)
        
        # Clean up processing set
        if call_uuid in processing_calls:
            processing_calls.remove(call_uuid)
            
    except Exception as e:
        print(f"[💥] Recording error: {e}")
        # Try fallback method
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
        
        # Simulate play button first
        play_script = f'window.Play("{call_info["did_number"]}", "{call_uuid}"); return true;'
        driver.execute_script(play_script)
        time.sleep(5)
        
        # Get all cookies and session data
        cookies = driver.get_cookies()
        session = requests.Session()
        
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        # Enhanced headers
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
            # Fallback with text message
            send_message(caption + "\n⚠️ Voice file upload failed, but call was recorded.")
            
        # Clean up file
        try:
            os.remove(file_path)
        except:
            pass
            
    except Exception as e:
        print(f"[❌] Error sending recording: {e}")

def handle_captcha_protection(sb, url, step_name):
    """Handle CAPTCHA protection"""
    print(f"🛡️ CAPTCHA protection check for {step_name}...")
    sb.driver.uc_open_with_reconnect(url, reconnect_time=3)
    sb.uc_gui_click_captcha()
    print(f"✅ CAPTCHA handling completed for {step_name}")

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
    with SB(uc=True, headed=True, incognito=True) as sb:
        try:
            if not wait_for_login(sb):
                return
            
            handle_captcha_protection(sb, config.CALL_URL, "Calls Page")
            WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
            print("✅ Active Calls page loaded!")
            print("[*] Real-time monitoring started...")

            error_count = 0
            last_refresh = datetime.now()
            
            while error_count < config.MAX_ERRORS:
                try:
                    # Refresh page every 30 minutes
                    if (datetime.now() - last_refresh).total_seconds() > 43200:
                        sb.driver.refresh()
                        WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
                        last_refresh = datetime.now()
                        print("[🔄] Page refreshed to maintain session")
                    
                    # Check if still logged in
                    if config.LOGIN_URL in sb.driver.current_url:
                        print("[⚠️] Session expired, re-logging in")
                        if not wait_for_login(sb):
                            break
                        handle_captcha_protection(sb, config.CALL_URL, "Re-login Calls Page")
                    
                    # Extract and process calls immediately
                    extract_calls(sb.driver)
                    
                    error_count = 0
                    time.sleep(config.CHECK_INTERVAL)
                    
                except KeyboardInterrupt:
                    print("\n[🛑] Stopped by user")
                    break
                except Exception as e:
                    error_count += 1
                    print(f"[❌] Main loop error ({error_count}/{config.MAX_ERRORS}): {e}")
                    time.sleep(3)
                    
        except Exception as e:
            print(f"[💥] Fatal error: {e}")
    
    print("[*] Monitoring stopped")

if __name__ == "__main__":
    main()
