import time
import re
import requests
import os
import threading
import schedule
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

active_calls = {}
processing_calls = set()

# Statistics tracking
daily_stats = {
    'total_calls': 0,
    'successful_calls': 0,
    'failed_calls': 0,
    'start_time': datetime.now(),
    'last_captcha_alert': None
}

os.makedirs(config.DOWNLOAD_FOLDER, exist_ok=True)

def animate_dots():
    """Animated dots for notifications"""
    animations = [
        "⚡", "✨", "🌟", "💫", "🔥",
        "🔄", "📞", "🎙️", "📱", "💬"
    ]
    return animations[int(time.time()) % len(animations)]

def send_animated_message(text):
    """Send message with animated emoji"""
    animated_text = f"{animate_dots()} {text} {animate_dots()}"
    return send_message(animated_text)

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

def check_captcha(driver):
    """Check if CAPTCHA is present on the page"""
    try:
        captcha_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            ".g-recaptcha",
            "#captcha",
            ".captcha",
            "img[src*='captcha']"
        ]
        
        for selector in captcha_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return True
                
        # Check for CAPTCHA in page source
        page_source = driver.page_source.lower()
        if 'captcha' in page_source or 'recaptcha' in page_source:
            return True
            
    except Exception as e:
        print(f"[⚠️] CAPTCHA check error: {e}")
    
    return False

def handle_captcha_alert(driver, context="page"):
    """Send CAPTCHA alert to Telegram"""
    global daily_stats
    
    current_time = datetime.now()
    
    # Avoid spamming - only send alert every 10 minutes
    if (daily_stats['last_captcha_alert'] and 
        (current_time - daily_stats['last_captcha_alert']).total_seconds() < 600):
        return
    
    alert_message = (
        f"🚨 **CAPTCHA DETECTED** 🚨\n\n"
        f"📍 Context: {context}\n"
        f"⏰ Time: {current_time.strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
        f"👨‍💻 @professor_cry - Please solve CAPTCHA manually!\n\n"
        f"🔄 Bot is waiting for CAPTCHA completion..."
    )
    
    send_animated_message(alert_message)
    daily_stats['last_captcha_alert'] = current_time
    
    # Wait for CAPTCHA to be solved (check every 30 seconds)
    for i in range(60):  # Wait maximum 30 minutes
        time.sleep(30)
        if not check_captcha(driver):
            success_message = (
                f"✅ **CAPTCHA SOLVED** ✅\n\n"
                f"🔄 Resuming monitoring...\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}"
            )
            send_animated_message(success_message)
            return True
            
    # If CAPTCHA not solved in 30 minutes
    timeout_message = (
        f"⏰ **CAPTCHA TIMEOUT** ⏰\n\n"
        f"CAPTCHA was not solved in 30 minutes.\n"
        f"Please check the browser and solve manually."
    )
    send_animated_message(timeout_message)
    return False

def check_website_status(driver):
    """Check if website is accessible"""
    try:
        driver.execute_script("return document.readyState;")
        return True
    except:
        return False

def handle_website_down():
    """Handle website down situation"""
    alert_message = (
        f"🌐 **WEBSITE DOWN** 🌐\n\n"
        f"❌ Orange Carrier website is not accessible!\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
        f"🔧 Please check:\n"
        f"• Internet connection\n"
        f"• Website status\n"
        f"• Server maintenance\n\n"
        f"🔄 Bot will retry automatically..."
    )
    send_animated_message(alert_message)

def send_daily_report():
    """Send daily report at 6 AM"""
    global daily_stats
    
    report_message = (
        f"📊 **DAILY CALL REPORT** 📊\n\n"
        f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"⏰ Report Time: 6:00 AM\n\n"
        f"📞 Total Calls: {daily_stats['total_calls']}\n"
        f"✅ Successful: {daily_stats['successful_calls']}\n"
        f"❌ Failed: {daily_stats['failed_calls']}\n"
        f"📈 Success Rate: {calculate_success_rate()}%\n\n"
        f"⏱️ Uptime: {calculate_uptime()}\n"
        f"🚀 Status: **ACTIVE**\n\n"
        f"🌟 Configured by @professor_cry"
    )
    
    send_animated_message(report_message)
    
    # Reset daily stats
    daily_stats['total_calls'] = 0
    daily_stats['successful_calls'] = 0
    daily_stats['failed_calls'] = 0

def calculate_success_rate():
    """Calculate success rate percentage"""
    total = daily_stats['total_calls']
    if total == 0:
        return 0
    success = daily_stats['successful_calls']
    return round((success / total) * 100, 2)

def calculate_uptime():
    """Calculate bot uptime"""
    uptime = datetime.now() - daily_stats['start_time']
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    return f"{uptime.days}d {hours}h {minutes}m"

def send_bot_status(status):
    """Send bot status updates"""
    status_messages = {
        'start': (
            f"🤖 **BOT STARTED** 🤖\n\n"
            f"✅ Call monitoring system activated!\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
            f"🌐 Monitoring: Orange Carrier\n"
            f"📞 Ready for calls...\n\n"
            f"🌟 @professor_cry"
        ),
        'stop': (
            f"🛑 **BOT STOPPED** 🛑\n\n"
            f"❌ Monitoring system stopped!\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
            f"📊 Final Stats:\n"
            f"• Total Calls: {daily_stats['total_calls']}\n"
            f"• Successful: {daily_stats['successful_calls']}\n"
            f"• Failed: {daily_stats['failed_calls']}\n\n"
            f"🔧 Please restart the bot."
        ),
        'restart': (
            f"🔄 **BOT RESTARTED** 🔄\n\n"
            f"✅ Monitoring system recovered!\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
            f"🛠️ Auto-recovery successful\n"
            f"📞 Resuming call monitoring..."
        )
    }
    
    if status in status_messages:
        send_animated_message(status_messages[status])

def schedule_daily_tasks():
    """Schedule daily automated tasks"""
    # Daily report at 6 AM
    schedule.every().day.at("06:00").do(send_daily_report)
    
    # Status update every 6 hours
    schedule.every(6).hours.do(lambda: send_animated_message("🤖 Bot is running... 24/7 Active ✅"))
    
    print("[📅] Daily tasks scheduled")

def run_scheduler():
    """Run the scheduler in background"""
    while True:
        schedule.run_pending()
        time.sleep(60)

def extract_calls(driver):
    global active_calls, processing_calls, daily_stats
    
    try:
        # Check for CAPTCHA first
        if check_captcha(driver):
            if handle_captcha_alert(driver, "Active Calls Page"):
                time.sleep(5)  # Wait after CAPTCHA solved
            else:
                return
        
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
                    daily_stats['total_calls'] += 1
                    
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
    """Record audio directly from browser"""
    global daily_stats
    
    try:
        print(f"[🎙️] Starting audio recording for: {call_info['did_number']}")
        
        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(config.DOWNLOAD_FOLDER, f"call_{call_info['did_number']}_{timestamp}.mp3")
        
        # Simulate play button first
        play_script = f'window.Play("{call_info["did_number"]}", "{call_uuid}"); return true;'
        driver.execute_script(play_script)
        time.sleep(8)  # Wait for audio to load
        
        # Try direct download method
        if direct_download_recording(driver, call_info, call_uuid, file_path):
            # Delete processing message
            if processing_msg_id:
                delete_message(processing_msg_id)
            
            # Send successful recording
            send_successful_recording(call_info, file_path)
            daily_stats['successful_calls'] += 1
            
        else:
            # Fallback method
            print("[🔄] Trying fallback method...")
            if fallback_download_method(driver, call_info, call_uuid, file_path):
                if processing_msg_id:
                    delete_message(processing_msg_id)
                send_successful_recording(call_info, file_path)
                daily_stats['successful_calls'] += 1
            else:
                # Final failure
                if processing_msg_id:
                    delete_message(processing_msg_id)
                error_text = f"❌ Failed to record call from {call_info['flag']} {call_info['masked']}"
                send_message(error_text)
                daily_stats['failed_calls'] += 1
        
        # Clean up processing set
        if call_uuid in processing_calls:
            processing_calls.remove(call_uuid)
            
    except Exception as e:
        print(f"[💥] Recording error: {e}")
        if processing_msg_id:
            delete_message(processing_msg_id)
        error_text = f"❌ Recording failed for {call_info['flag']} {call_info['masked']}"
        send_message(error_text)
        daily_stats['failed_calls'] += 1
        
        if call_uuid in processing_calls:
            processing_calls.remove(call_uuid)

def direct_download_recording(driver, call_info, call_uuid, file_path):
    """Direct download method with enhanced headers"""
    try:
        print("[🔍] Attempting direct download...")
        
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
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > 1000:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(file_path)
                print(f"[✅] Direct download successful: {file_size} bytes")
                return True
            else:
                print(f"[❌] Content too small: {content_length} bytes")
        else:
            print(f"[❌] HTTP Error: {response.status_code}")
        
        return False
        
    except Exception as e:
        print(f"[❌] Direct download error: {e}")
        return False

def fallback_download_method(driver, call_info, call_uuid, file_path):
    """Fallback download method"""
    try:
        print("[🔄] Using fallback download method...")
        
        # Alternative approach - refresh and retry
        driver.refresh()
        time.sleep(5)
        
        # Wait for calls table to reload
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
        
        # Retry direct download
        return direct_download_recording(driver, call_info, call_uuid, file_path)
        
    except Exception as e:
        print(f"[❌] Fallback method error: {e}")
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
            success_message = f"✅ Recording sent: {call_info['masked']}"
            send_animated_message(success_message)
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
    """Handle CAPTCHA protection with enhanced detection"""
    print(f"🛡️ CAPTCHA protection check for {step_name}...")
    
    try:
        sb.driver.uc_open_with_reconnect(url, reconnect_time=3)
        
        # Check for CAPTCHA after page load
        time.sleep(5)
        if check_captcha(sb.driver):
            handle_captcha_alert(sb.driver, step_name)
        
        sb.uc_gui_click_captcha()
        print(f"✅ CAPTCHA handling completed for {step_name}")
        
    except Exception as e:
        print(f"[❌] CAPTCHA protection error: {e}")

def wait_for_login(sb):
    """Wait for manual login with CAPTCHA handling"""
    print(f"🔐 Login page: {config.LOGIN_URL}")
    
    # Use UC mode to open login page with CAPTCHA protection
    handle_captcha_protection(sb, config.LOGIN_URL, "Login Page")
    
    print("➡️ Please login manually in the browser...")
    
    try:
        # Wait for successful login (redirect away from login page)
        WebDriverWait(sb.driver, 600).until(
            lambda d: d.current_url.startswith(config.BASE_URL) and not d.current_url.startswith(config.LOGIN_URL)
        )
        
        # Check for CAPTCHA after login
        if check_captcha(sb.driver):
            handle_captcha_alert(sb.driver, "After Login")
        
        print("✅ Login successful!")
        return True
        
    except TimeoutException:
        print("[❌] Login timeout")
        return False

def main():
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Schedule daily tasks
    schedule_daily_tasks()
    
    # Send bot start message
    send_bot_status('start')
    
    # Main bot loop with auto-restart
    while True:
        try:
            with SB(uc=True, headed=not config.BROWSER_HEADLESS, incognito=config.BROWSER_INCOGNITO) as sb:
                try:
                    if not wait_for_login(sb):
                        send_animated_message("❌ Login failed! Restarting bot...")
                        time.sleep(60)
                        continue
                    
                    handle_captcha_protection(sb, config.CALL_URL, "Calls Page")
                    WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
                    
                    print("✅ Active Calls page loaded!")
                    send_animated_message("🌐 Website connected! Starting call monitoring...")
                    
                    error_count = 0
                    last_refresh = datetime.now()
                    last_status_check = datetime.now()
                    
                    while error_count < config.MAX_ERRORS:
                        try:
                            current_time = datetime.now()
                            
                            # Refresh page every 30 minutes
                            if (current_time - last_refresh).total_seconds() > 1800:
                                sb.driver.refresh()
                                WebDriverWait(sb.driver, 15).until(EC.presence_of_element_located((By.ID, "LiveCalls")))
                                last_refresh = current_time
                                print("[🔄] Page refreshed to maintain session")
                            
                            # Check website status every 5 minutes
                            if (current_time - last_status_check).total_seconds() > 300:
                                if not check_website_status(sb.driver):
                                    handle_website_down()
                                last_status_check = current_time
                            
                            # Check if still logged in
                            if config.LOGIN_URL in sb.driver.current_url:
                                print("[⚠️] Session expired, re-logging in")
                                if not wait_for_login(sb):
                                    break
                                handle_captcha_protection(sb, config.CALL_URL, "Re-login Calls Page")
                            
                            # Check for CAPTCHA
                            if check_captcha(sb.driver):
                                handle_captcha_alert(sb.driver, "Monitoring Loop")
                            
                            # Extract and process calls immediately
                            extract_calls(sb.driver)
                            
                            error_count = 0
                            time.sleep(config.CHECK_INTERVAL)
                            
                        except KeyboardInterrupt:
                            print("\n[🛑] Stopped by user")
                            send_bot_status('stop')
                            return
                        except Exception as e:
                            error_count += 1
                            print(f"[❌] Main loop error ({error_count}/{config.MAX_ERRORS}): {e}")
                            time.sleep(3)
                    
                    # If max errors reached, restart
                    send_animated_message("🔄 Max errors reached! Restarting bot...")
                    time.sleep(10)
                            
                except Exception as e:
                    print(f"[💥] Browser session error: {e}")
                    send_animated_message("❌ Browser session crashed! Restarting...")
                    time.sleep(30)
                    
        except Exception as e:
            print(f"[💥] Fatal error: {e}")
            send_animated_message("💥 Critical error! Attempting restart...")
            time.sleep(60)
    
    print("[*] Monitoring stopped")

if __name__ == "__main__":
    main()