import asyncio
import time
import re
import logging
import random
import aiosqlite
import requests
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import phonenumbers
from phonenumbers import geocoder, timezone
import pycountry

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"

LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal/"
MONITOR_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
LOGIN_TIMEOUT = 600
REFRESH_INTERVAL = 70

# ----------------------------------------------------------------------
# Global state
# ----------------------------------------------------------------------
posted_keys = set()
driver = None
bot = None
dp = Dispatcher()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ----------------------------------------------------------------------
# Database Setup
# ----------------------------------------------------------------------
async def init_database():
    async with aiosqlite.connect("groups.db") as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def add_group(group_id: str, group_name: str = ""):
    try:
        async with aiosqlite.connect("groups.db") as db:
            await db.execute(
                "INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)",
                (str(group_id), group_name)
            )
            await db.commit()
            logging.info(f"Group added to database: {group_id} - {group_name}")
    except Exception as e:
        logging.error(f"Error adding group to database: {e}")

async def remove_group(group_id: str):
    try:
        async with aiosqlite.connect("groups.db") as db:
            await db.execute("DELETE FROM groups WHERE group_id = ?", (str(group_id),))
            await db.commit()
            logging.info(f"Group removed from database: {group_id}")
    except Exception as e:
        logging.error(f"Error removing group from database: {e}")

async def get_all_groups():
    try:
        async with aiosqlite.connect("groups.db") as db:
            cursor = await db.execute("SELECT group_id, group_name FROM groups")
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logging.error(f"Error getting groups from database: {e}")
        return []

# ----------------------------------------------------------------------
# Country Flag Detection
# ----------------------------------------------------------------------
def get_country_flag(phone_number: str) -> str:
    try:
        parsed_number = phonenumbers.parse(phone_number, None)
        country_code = phonenumbers.region_code_for_number(parsed_number)
        
        if country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                return country_code_to_flag(country.alpha_2)
        
        country_name = geocoder.description_for_number(parsed_number, "en")
        if country_name:
            country = pycountry.countries.get(name=country_name)
            if country:
                return country_code_to_flag(country.alpha_2)
                
    except Exception as e:
        logging.warning(f"Could not detect country for {phone_number}: {e}")
    
    return "🌍"

def country_code_to_flag(country_code: str) -> str:
    if len(country_code) != 2:
        return "🌍"
    base = 0x1F1E6
    flag_emoji = chr(base + ord(country_code[0]) - ord('A')) + chr(base + ord(country_code[1]) - ord('A'))
    return flag_emoji

# ----------------------------------------------------------------------
# Message builder
# ----------------------------------------------------------------------
def build_message(range_name: str, test_number: str, receive_time: str) -> str:
    country_flag = get_country_flag(test_number)
    
    return (
        f"💬 Latest Range Information Logged 🪝\n\n"
        f"Name: `{range_name}`\n"
        f"{country_flag} Test Number: `{test_number}`\n"
        f"SID: `TELEGRAM`\n"
        f"Time: `{receive_time}`\n\n"
        f"🚀 ivasms Latest Update!\n"
        f"```Want this setup for your own community? 🎯\n"
        f"Just add this bot and make it admin — you're all set!```"
    )

def create_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="👨‍💻 @professor_cry", 
                url="https://t.me/professor_cry"
            )]
        ]
    )

# ----------------------------------------------------------------------
# Website Availability Check
# ----------------------------------------------------------------------
def check_website_available():
    """Check if website is accessible via HTTP request"""
    try:
        response = requests.get(LOGIN_URL, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Website check failed: {e}")
        return False

# ----------------------------------------------------------------------
# Enhanced Driver Initialization with Better Error Handling
# ----------------------------------------------------------------------
def init_driver():
    global driver
    
    try:
        # Close existing driver if any
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        logging.info("🔄 Initializing browser driver...")
        
        # Try different approaches
        driver_options = [
            {
                "uc": True,
                "headless": False,
                "undetectable": True,
                "incognito": True,
            },
            {
                "uc": True,
                "headless": False,
                "undetectable": True,
            },
            {
                "browser": "chrome",
                "headless": False,
                "undetectable": True,
            }
        ]
        
        for i, options in enumerate(driver_options):
            try:
                logging.info(f"🔄 Attempt {i+1} with options: {options}")
                driver = Driver(**options)
                
                # Set reasonable timeouts
                driver.set_page_load_timeout(30)
                driver.implicitly_wait(10)
                
                # Test the driver with a simple page
                logging.info("🧪 Testing driver with about:blank...")
                driver.get("about:blank")
                
                if driver.current_url == "about:blank":
                    logging.info("✅ Driver initialized successfully")
                    return driver
                else:
                    driver.quit()
                    
            except Exception as e:
                logging.warning(f"❌ Driver attempt {i+1} failed: {e}")
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                continue
        
        logging.error("❌ All driver initialization attempts failed")
        return None
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize driver: {e}")
        return None

# ----------------------------------------------------------------------
# Test Browser Functionality
# ----------------------------------------------------------------------
def test_browser_functionality():
    """Test if browser can actually load websites"""
    try:
        logging.info("🧪 Testing browser with google.com...")
        driver.get("https://www.google.com")
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        logging.info("✅ Browser test successful - can load external websites")
        return True
        
    except Exception as e:
        logging.error(f"❌ Browser test failed: {e}")
        return False

# ----------------------------------------------------------------------
# Enhanced Website Navigation
# ----------------------------------------------------------------------
def navigate_to_url(url, max_retries=3):
    """Navigate to URL with retry logic"""
    for attempt in range(max_retries):
        try:
            logging.info(f"🌐 Attempt {attempt + 1}/{max_retries} to navigate to: {url}")
            
            # Clear cookies and cache for fresh start
            if attempt > 0:
                driver.delete_all_cookies()
            
            driver.get(url)
            
            # Wait for page to load
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait a bit more for dynamic content
            time.sleep(3)
            
            logging.info("✅ Page loaded successfully")
            return True
            
        except TimeoutException:
            logging.warning(f"⏰ Page load timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                logging.info("🔄 Retrying...")
                time.sleep(5)
            else:
                logging.error("❌ All navigation attempts failed due to timeout")
                return False
        except Exception as e:
            logging.error(f"❌ Navigation error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return False
    return False

# ----------------------------------------------------------------------
# Check for Common Blocking Issues
# ----------------------------------------------------------------------
def check_for_blocks():
    """Check for common website blocking techniques"""
    try:
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        page_title = driver.title.lower()
        
        # Check for common blocking indicators
        blocks = [
            ("cloudflare", "cloudflare" in page_source or "cloudflare" in page_title),
            ("access denied", "access denied" in page_source),
            ("bot detected", "bot" in page_source and "detected" in page_source),
            ("security check", "security" in page_source and "check" in page_source),
            ("captcha", "captcha" in page_source),
            ("blocked", "blocked" in page_source),
            ("unusual traffic", "unusual" in page_source and "traffic" in page_source),
        ]
        
        found_blocks = [name for name, found in blocks if found]
        if found_blocks:
            logging.warning(f"🚫 Possible blocks detected: {', '.join(found_blocks)}")
            return True
            
        return False
        
    except Exception as e:
        logging.error(f"Error checking for blocks: {e}")
        return False

# ----------------------------------------------------------------------
# Enhanced CAPTCHA Handling
# ----------------------------------------------------------------------
def is_cloudflare_captcha_present():
    """Check if Cloudflare CAPTCHA is present"""
    try:
        indicators = ["cf-challenge", "challenge-form", "cloudflare", "cf_captcha", "turnstile"]
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()
        
        for indicator in indicators:
            if indicator in page_source or indicator in current_url:
                return True
        
        # Check for common CAPTCHA selectors
        captcha_selectors = [
            "div[class*='cf-challenge']",
            "div[class*='challenge']", 
            "iframe[src*='challenges.cloudflare.com']",
            "div[id*='cf-challenge']",
            ".cf-turnstile",
            "#cf-challenge"
        ]
        
        for selector in captcha_selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except:
                continue
                
        return False
    except:
        return False

def wait_for_captcha_completion(timeout=300):
    """Wait for manual CAPTCHA completion"""
    logging.info("🔍 CAPTCHA detected! Please complete it manually in the browser.")
    logging.info("💡 Tips: If CAPTCHA doesn't appear, try refreshing the page (F5)")
    
    start_time = time.time()
    last_status = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Check if CAPTCHA is gone
            if not is_cloudflare_captcha_present():
                logging.info("✅ CAPTCHA completed!")
                return True
                
            # Check if we're logged in
            if is_logged_in():
                logging.info("✅ Successfully logged in!")
                return True
            
            # Show status every 30 seconds
            if time.time() - last_status > 30:
                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                logging.info(f"⏳ Waiting for CAPTCHA... {int(remaining)}s remaining")
                logging.info("💡 Still seeing CAPTCHA? Try:")
                logging.info("   • Refreshing the page (F5)")
                logging.info("   • Checking if the website is accessible")
                logging.info("   • Waiting a few minutes and trying again")
                last_status = time.time()
                
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"Error during CAPTCHA wait: {e}")
            time.sleep(10)
    
    logging.error("❌ CAPTCHA timeout!")
    return False

# ----------------------------------------------------------------------
# Check if logged in
# ----------------------------------------------------------------------
def is_logged_in():
    """Check if we're logged in"""
    try:
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        if PORTAL_URL in current_url or "portal" in current_url.lower():
            return True
            
        logged_in_indicators = ["logout", "log out", "sign out", "dashboard", "welcome"]
        for indicator in logged_in_indicators:
            if indicator in page_source:
                return True
                
        return False
    except:
        return False

# ----------------------------------------------------------------------
# Extract ranges from page
# ----------------------------------------------------------------------
def extract_new_ranges(html_content: str):
    """Extract range information from HTML"""
    new_entries = []
    
    try:
        pattern = r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>'
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            if len(match) >= 5:
                range_name = re.sub(r'<[^>]+>', '', match[0]).strip()
                test_number = re.sub(r'<[^>]+>', '', match[1]).strip()
                sid = re.sub(r'<[^>]+>', '', match[2]).strip()
                message_content = re.sub(r'<[^>]+>', '', match[3]).strip()
                receive_time = re.sub(r'<[^>]+>', '', match[4]).strip()
                
                if not range_name or not test_number:
                    continue
                
                if test_number and not test_number.startswith('+'):
                    test_number = '+' + test_number
                
                if not receive_time:
                    receive_time = time.strftime("%Y-%m-%d %H:%M:%S")
                
                key = f"{range_name}-{test_number}-{receive_time}"
                
                if key not in posted_keys:
                    posted_keys.add(key)
                    new_entries.append({
                        'range_name': range_name,
                        'test_number': test_number,
                        'receive_time': receive_time
                    })
                    logging.info(f"New range found: {range_name} - {test_number}")
    
    except Exception as e:
        logging.error(f"Error extracting ranges: {e}")
    
    return new_entries

# ----------------------------------------------------------------------
# Send messages to groups
# ----------------------------------------------------------------------
async def send_to_all_groups(message: str, keyboard: InlineKeyboardMarkup):
    """Send message to all groups"""
    groups = await get_all_groups()
    success_count = 0
    
    if not groups:
        logging.warning("No groups found in database")
        return 0
    
    for group_id, group_name in groups:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            success_count += 1
            logging.info(f"✓ Message sent to: {group_name or group_id}")
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"✗ Failed to send to {group_name or group_id}: {e}")
            if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                await remove_group(group_id)
    
    return success_count

# ----------------------------------------------------------------------
# Bot Handlers
# ----------------------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 IVASMS Range Monitor Bot is running!\n\n"
                        "Add me to your groups and I'll automatically share new range information.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    groups = await get_all_groups()
    await message.answer(f"📊 Bot Statistics:\n"
                        f"• Active Groups: {len(groups)}\n"
                        f"• Refresh Interval: {REFRESH_INTERVAL} seconds\n"
                        f"• Last Refresh: {time.strftime('%Y-%m-%d %H:%M:%S')}")

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    """Debug command to check browser status"""
    global driver
    
    status = []
    status.append("🔧 Debug Information:")
    status.append(f"• Driver initialized: {driver is not None}")
    
    if driver:
        try:
            current_url = driver.current_url
            status.append(f"• Current URL: {current_url}")
            status.append(f"• Page title: {driver.title}")
        except Exception as e:
            status.append(f"• Driver error: {e}")
    else:
        status.append("• Driver: NOT INITIALIZED")
    
    status.append(f"• Website accessible: {check_website_available()}")
    status.append(f"• Posted keys count: {len(posted_keys)}")
    
    await message.answer("\n".join(status))

@dp.my_chat_member()
async def handle_chat_member_update(chat_member: types.ChatMemberUpdated):
    try:
        chat = chat_member.chat
        old_status = chat_member.old_chat_member.status
        new_status = chat_member.new_chat_member.status
        
        if (old_status in ["left", "kicked"] and 
            new_status in ["member", "administrator"]):
            
            if chat.type in ["group", "supergroup"]:
                await add_group(str(chat.id), chat.title)
                logging.info(f"Bot added to group: {chat.title} ({chat.id})")
                
                welcome_msg = (
                    "🤖 IVASMS Range Monitor Bot Activated!\n\n"
                    "I will automatically share new range information every 2 minutes.\n"
                    "Make sure I have permission to send messages in this group."
                )
                await bot.send_message(chat.id, welcome_msg)
        
        elif (old_status in ["member", "administrator"] and 
              new_status in ["left", "kicked"]):
            
            if chat.type in ["group", "supergroup"]:
                await remove_group(str(chat.id))
                logging.info(f"Bot removed from group: {chat.title} ({chat.id})")
                
    except Exception as e:
        logging.error(f"Error handling chat member update: {e}")

# ----------------------------------------------------------------------
# Main Monitoring Function with Better Error Handling
# ----------------------------------------------------------------------
async def monitor_ranges():
    global driver, bot
    
    bot = Bot(token=BOT_TOKEN)
    
    # Initialize driver with retry
    max_driver_attempts = 3
    for attempt in range(max_driver_attempts):
        driver = init_driver()
        if driver:
            break
        logging.warning(f"🚨 Driver initialization failed, attempt {attempt + 1}/{max_driver_attempts}")
        if attempt < max_driver_attempts - 1:
            await asyncio.sleep(10)
    
    if not driver:
        logging.error("❌ Could not initialize browser driver after all attempts")
        await send_admin_alert("❌ Browser driver initialization failed completely")
        return
    
    try:
        # Step 1: Test browser functionality
        logging.info("🧪 Testing browser functionality...")
        if not test_browser_functionality():
            logging.error("❌ Browser functionality test failed")
            await send_admin_alert("❌ Browser cannot load websites")
            return
        
        # Step 2: Check if website is accessible
        logging.info("🔍 Checking website availability...")
        if not check_website_available():
            logging.warning("⚠️ Website might be down or inaccessible")
            # Continue anyway as it might be blocking HTTP requests but allowing browsers
        
        # Step 3: Navigate to login page
        logging.info("🌐 Navigating to login page...")
        if not navigate_to_url(LOGIN_URL):
            logging.error("❌ Failed to navigate to login page")
            
            # Check for blocking
            if check_for_blocks():
                logging.error("🚫 Website is blocking the browser")
                await send_admin_alert("🚫 Website is blocking the browser access")
            return
        
        # Step 4: Check for CAPTCHA or blocks
        if check_for_blocks() or is_cloudflare_captcha_present():
            logging.info("🛡️ Cloudflare protection detected")
            if not wait_for_captcha_completion():
                logging.error("❌ CAPTCHA not completed in time")
                await send_admin_alert("❌ CAPTCHA not completed in time")
                return
        else:
            logging.info("✅ No CAPTCHA detected, waiting for manual login...")
        
        # Step 5: Wait for manual login
        logging.info("🔑 Please log in manually in the browser window...")
        logging.info("💡 After logging in, the bot will automatically start monitoring")
        
        login_start = time.time()
        while time.time() - login_start < LOGIN_TIMEOUT:
            if is_logged_in():
                logging.info("✅ Login successful!")
                break
            
            # Show progress every 30 seconds
            if int(time.time() - login_start) % 30 == 0:
                elapsed = time.time() - login_start
                remaining = LOGIN_TIMEOUT - elapsed
                logging.info(f"⏳ Waiting for login... {int(remaining)}s remaining")
                
            await asyncio.sleep(5)
        else:
            logging.error("❌ Login timeout! Please check credentials and try again.")
            await send_admin_alert("❌ Login timeout! Please check the browser.")
            return
        
        # Step 6: Navigate to monitor page
        logging.info("📊 Navigating to monitor page...")
        if not navigate_to_url(MONITOR_URL):
            logging.error("❌ Failed to navigate to monitor page")
            return
        
        # Step 7: Start monitoring loop
        logging.info("🚀 Starting monitoring loop...")
        refresh_count = 0
        
        while True:
            try:
                refresh_count += 1
                logging.info(f"🔄 Refresh #{refresh_count}")
                
                # Refresh page
                driver.refresh()
                await asyncio.sleep(5)
                
                # Check if still logged in
                if not is_logged_in():
                    logging.error("❌ Logged out! Please restart the bot.")
                    await send_admin_alert("❌ Bot got logged out, needs restart")
                    break
                
                # Extract and send ranges
                html_content = driver.page_source
                new_ranges = extract_new_ranges(html_content)
                
                if new_ranges:
                    for range_data in new_ranges:
                        message = build_message(
                            range_data['range_name'],
                            range_data['test_number'], 
                            range_data['receive_time']
                        )
                        
                        keyboard = create_keyboard()
                        success_count = await send_to_all_groups(message, keyboard)
                        logging.info(f"✅ Sent to {success_count} groups: {range_data['range_name']}")
                        await asyncio.sleep(2)
                else:
                    logging.info("ℹ️ No new ranges found")
                
                # Wait for next refresh
                next_time = time.strftime("%H:%M:%S", time.localtime(time.time() + REFRESH_INTERVAL))
                logging.info(f"⏰ Next refresh at: {next_time}")
                await asyncio.sleep(REFRESH_INTERVAL)
                
            except Exception as e:
                logging.error(f"❌ Monitoring error: {e}")
                await asyncio.sleep(30)
                
    except Exception as e:
        logging.error(f"💥 Fatal error in monitor: {e}")
        await send_admin_alert(f"💥 Monitor crashed: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("🔚 Browser closed")
            except:
                pass

async def send_admin_alert(message: str):
    """Send alert to first group in database"""
    try:
        groups = await get_all_groups()
        if groups:
            await bot.send_message(chat_id=groups[0][0], text=f"🚨 {message}")
    except Exception as e:
        logging.error(f"Failed to send admin alert: {e}")

# ----------------------------------------------------------------------
# Health Monitor
# ----------------------------------------------------------------------
async def health_monitor():
    max_restarts = 3
    restarts = 0
    
    while restarts < max_restarts:
        try:
            logging.info(f"🚀 Starting monitor (attempt {restarts + 1}/{max_restarts})")
            await monitor_ranges()
        except Exception as e:
            restarts += 1
            logging.error(f"💥 Monitor crashed: {e}")
            
            if restarts < max_restarts:
                wait_time = 60 * restarts
                logging.info(f"🕒 Waiting {wait_time} seconds before restart...")
                await asyncio.sleep(wait_time)
            else:
                logging.error("❌ Max restarts reached")
                break

# ----------------------------------------------------------------------
# Main Function
# ----------------------------------------------------------------------
async def main():
    await init_database()
    logging.info("✅ Database initialized")
    
    bot = Bot(token=BOT_TOKEN)
    
    groups = await get_all_groups()
    logging.info(f"📊 Bot is in {len(groups)} groups")
    
    # Start tasks
    monitor_task = asyncio.create_task(health_monitor())
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    await asyncio.gather(monitor_task, bot_task, return_exceptions=True)

# ----------------------------------------------------------------------
# Entry Point with Better Diagnostics
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting IVASMS Range Monitor Bot")
    print("=" * 60)
    print("Troubleshooting Guide:")
    print("• Make sure Chrome browser is installed")
    print("• Check your internet connection")
    print("• If browser doesn't open, try running as administrator")
    print("• Make sure the website is accessible in your browser")
    print("• If blocked by Cloudflare, complete CAPTCHA manually")
    print("=" * 60)
    
    # Check dependencies
    try:
        from seleniumbase import Driver
        import phonenumbers
        import pycountry
        import aiosqlite
        import requests
        logging.info("✅ All packages installed")
    except ImportError as e:
        logging.error(f"❌ Missing package: {e}")
        logging.info("💡 Run: pip install seleniumbase phonenumbers pycountry aiosqlite requests")
        exit(1)
    
    # Additional system checks
    try:
        import selenium
        logging.info(f"✅ Selenium version: {selenium.__version__}")
    except:
        logging.warning("⚠️ Selenium version check failed")
    
    try:
        # Test basic web request
        response = requests.get("https://www.google.com", timeout=10)
        logging.info("✅ Internet connection: OK")
    except:
        logging.error("❌ No internet connection or network issues")
    
    asyncio.run(main())
