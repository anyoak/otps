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
from aiogram.filters import Command, CommandObject
import phonenumbers
from phonenumbers import geocoder, timezone
import pycountry

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"
ADMIN_ID = 6577308099

LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal/"
MONITOR_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
LOGIN_TIMEOUT = 600
REFRESH_INTERVAL = 120

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
        group_id = str(group_id)
        async with aiosqlite.connect("groups.db") as db:
            await db.execute(
                "INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)",
                (group_id, group_name)
            )
            await db.commit()
            logging.info(f"✅ Group added to database: {group_name} ({group_id})")
            return True
    except Exception as e:
        logging.error(f"❌ Error adding group to database: {e}")
        return False

async def remove_group(group_id: str):
    try:
        async with aiosqlite.connect("groups.db") as db:
            await db.execute("DELETE FROM groups WHERE group_id = ?", (str(group_id),))
            await db.commit()
            logging.info(f"✅ Group removed from database: {group_id}")
            return True
    except Exception as e:
        logging.error(f"❌ Error removing group from database: {e}")
        return False

async def get_all_groups():
    try:
        async with aiosqlite.connect("groups.db") as db:
            cursor = await db.execute("SELECT group_id, group_name FROM groups")
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logging.error(f"❌ Error getting groups from database: {e}")
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
# Admin Check Function
# ----------------------------------------------------------------------
def is_admin(user_id: int):
    return user_id == ADMIN_ID

# ----------------------------------------------------------------------
# Enhanced Driver Initialization with Better Navigation
# ----------------------------------------------------------------------
def init_driver():
    global driver
    try:
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        logging.info("🔄 Initializing browser driver...")
        
        driver = Driver(
            uc=True,
            headless=False,
            undetectable=True,
            incognito=True,
        )
        
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(15)
        
        logging.info("✅ Driver initialized successfully")
        return driver
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize driver: {e}")
        return None

# ----------------------------------------------------------------------
# SMART NAVIGATION SYSTEM - FIXED
# ----------------------------------------------------------------------
def smart_navigate_to_url(target_url, max_retries=5):
    """Smart navigation with multiple fallback methods"""
    for attempt in range(max_retries):
        try:
            logging.info(f"🧭 Navigation attempt {attempt + 1}/{max_retries} to: {target_url}")
            
            # Clear cookies and cache for fresh start
            if attempt > 0:
                try:
                    driver.delete_all_cookies()
                    logging.info("🧹 Cookies cleared")
                except:
                    pass
            
            # Method 1: Direct navigation
            driver.get(target_url)
            
            # Wait for page to load completely
            WebDriverWait(driver, 25).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Wait additional time for dynamic content
            time.sleep(5)
            
            current_url = driver.current_url
            logging.info(f"📍 Current URL: {current_url}")
            
            # Check if we reached the target URL
            if target_url in current_url or "sms/test/sms" in current_url:
                logging.info("🎯 Successfully navigated to target URL")
                return True
            else:
                logging.warning(f"⚠️ Not on target URL. Current: {current_url}")
                
                # If we're on portal page but not the specific monitor page
                if "portal" in current_url and "sms/test/sms" not in current_url:
                    logging.info("🔍 On portal page, trying to navigate directly to monitor URL")
                    # Try Method 2: JavaScript navigation
                    try:
                        driver.execute_script(f"window.location.href = '{MONITOR_URL}';")
                        time.sleep(5)
                        
                        current_url = driver.current_url
                        if "sms/test/sms" in current_url:
                            logging.info("✅ JavaScript navigation successful")
                            return True
                    except Exception as js_e:
                        logging.warning(f"JavaScript navigation failed: {js_e}")
                
                # Method 3: Try finding and clicking the SMS test link
                if attempt >= 2:  # Try this method after 2 failed attempts
                    if click_sms_test_link():
                        logging.info("✅ Clicked SMS test link successfully")
                        return True
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logging.info(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
        except TimeoutException:
            logging.warning(f"⏰ Page load timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                continue
            else:
                logging.error("❌ All navigation attempts timed out")
                return False
        except Exception as e:
            logging.error(f"❌ Navigation error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return False
    
    return False

def click_sms_test_link():
    """Try to find and click the SMS test link in the portal"""
    try:
        logging.info("🔍 Looking for SMS test link in portal...")
        
        # Common selectors for SMS test links
        link_selectors = [
            "a[href*='sms/test']",
            "a[href*='sms?app=Telegram']",
            "a:contains('SMS')",
            "a:contains('Test')",
            "a:contains('sms')",
            "//a[contains(text(), 'SMS')]",
            "//a[contains(text(), 'Test')]",
            "//a[contains(@href, 'sms/test')]"
        ]
        
        for selector in link_selectors:
            try:
                if selector.startswith("//"):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        href = element.get_attribute("href")
                        if href and "sms" in href.lower():
                            logging.info(f"🔗 Found SMS link: {href}")
                            element.click()
                            time.sleep(5)
                            
                            # Check if navigation was successful
                            if "sms/test/sms" in driver.current_url:
                                logging.info("✅ Successfully clicked SMS test link")
                                return True
                    except:
                        continue
            except:
                continue
        
        logging.warning("❌ Could not find SMS test link")
        return False
        
    except Exception as e:
        logging.error(f"Error clicking SMS test link: {e}")
        return False

def wait_for_monitor_page(timeout=30):
    """Wait for monitor page to load completely"""
    try:
        logging.info("🕒 Waiting for monitor page to load...")
        
        # Wait for page to be ready
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Wait for table to be present (indicating monitor page is loaded)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Additional wait for any dynamic content
        time.sleep(3)
        
        logging.info("✅ Monitor page loaded successfully")
        return True
        
    except TimeoutException:
        logging.error("❌ Timeout waiting for monitor page")
        return False
    except Exception as e:
        logging.error(f"❌ Error waiting for monitor page: {e}")
        return False

# ----------------------------------------------------------------------
# Login Management
# ----------------------------------------------------------------------
def wait_for_manual_login(timeout=LOGIN_TIMEOUT):
    """Wait for user to manually complete login"""
    logging.info("🔑 Please complete login manually in the browser...")
    logging.info("💡 After login, you should be redirected to the portal page")
    
    start_time = time.time()
    last_status = time.time()
    
    while time.time() - start_time < timeout:
        try:
            current_url = driver.current_url
            
            # Check if we're logged in (on portal page or dashboard)
            if is_logged_in():
                logging.info("✅ Login successful! Detected portal/dashboard page")
                return True
            
            # Show status every 30 seconds
            if time.time() - last_status > 30:
                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                logging.info(f"⏳ Waiting for login... {int(remaining)}s remaining")
                logging.info(f"📍 Current URL: {current_url}")
                last_status = time.time()
            
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"Error during login wait: {e}")
            time.sleep(10)
    
    logging.error("❌ Login timeout reached!")
    return False

def is_logged_in():
    """Check if we're properly logged in"""
    try:
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        # Check if we're on portal page or dashboard
        if "portal" in current_url.lower():
            return True
            
        # Check for logged-in indicators
        logged_in_indicators = [
            "logout", "log out", "sign out", "dashboard", 
            "welcome", "portal", "sms", "test"
        ]
        
        for indicator in logged_in_indicators:
            if indicator in page_source:
                return True
        
        # Check for navigation menu or user profile
        user_indicators = [
            "nav", "menu", "profile", "user", "account"
        ]
        for indicator in user_indicators:
            if f'"{indicator}"' in page_source or f"'{indicator}'" in page_source:
                return True
                
        return False
        
    except Exception as e:
        logging.error(f"Error checking login status: {e}")
        return False

# ----------------------------------------------------------------------
# Enhanced Range Extraction
# ----------------------------------------------------------------------
def extract_new_ranges(html_content: str):
    """Extract range information from HTML"""
    new_entries = []
    
    try:
        # Multiple patterns to handle different HTML structures
        patterns = [
            r'<tr[^>]*>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>',
            r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if matches:
                logging.info(f"🔍 Found {len(matches)} potential ranges")
                break
        else:
            matches = []
            logging.warning("❌ No range patterns matched")
        
        for match in matches:
            if len(match) >= 5:
                range_name = re.sub(r'<[^>]+>', '', match[0]).strip()
                test_number = re.sub(r'<[^>]+>', '', match[1]).strip()
                sid = re.sub(r'<[^>]+>', '', match[2]).strip()
                message_content = re.sub(r'<[^>]+>', '', match[3]).strip()
                receive_time = re.sub(r'<[^>]+>', '', match[4]).strip()
                
                # Validate data
                if not range_name or not test_number:
                    continue
                    
                # Format phone number
                if test_number and not test_number.startswith('+'):
                    test_number = '+' + test_number.lstrip()
                
                # Format time
                if not receive_time:
                    receive_time = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Create unique key
                key = f"{range_name}-{test_number}-{receive_time}"
                
                if key not in posted_keys:
                    posted_keys.add(key)
                    new_entries.append({
                        'range_name': range_name,
                        'test_number': test_number,
                        'receive_time': receive_time
                    })
                    logging.info(f"✅ NEW RANGE: {range_name} - {test_number}")
    
    except Exception as e:
        logging.error(f"❌ Error extracting ranges: {e}")
    
    return new_entries

# ----------------------------------------------------------------------
# Send messages to groups
# ----------------------------------------------------------------------
async def send_to_all_groups(message: str, keyboard: InlineKeyboardMarkup):
    groups = await get_all_groups()
    success_count = 0
    
    if not groups:
        logging.warning("No groups found in database")
        return 0
    
    logging.info(f"📤 Sending to {len(groups)} groups...")
    
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
            logging.info(f"✓ Sent to: {group_name or group_id}")
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
    await message.answer(
        "🤖 IVASMS Range Monitor Bot\n\n"
        "Add me to groups and I'll share range information automatically."
    )

@dp.message(Command("addthisgroup"))
async def cmd_add_this_group(message: types.Message):
    """Manually add current group to database"""
    try:
        if message.chat.type not in ["group", "supergroup"]:
            await message.answer("❌ This command only works in groups!")
            return
        
        group_id = str(message.chat.id)
        group_name = message.chat.title
        
        success = await add_group(group_id, group_name)
        
        if success:
            await message.answer(
                f"✅ Group added!\n"
                f"• {group_name}\n"
                f"• ID: `{group_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer("❌ Failed to add group.")
        
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

@dp.message(Command("nav"))
async def cmd_navigate_manual(message: types.Message):
    """Manual navigation command for admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Admin only!")
        return
    
    try:
        await message.answer("🔄 Attempting manual navigation to monitor page...")
        
        if smart_navigate_to_url(MONITOR_URL):
            await message.answer("✅ Navigation successful!")
        else:
            await message.answer("❌ Navigation failed!")
            
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

# ----------------------------------------------------------------------
# MAIN MONITORING FUNCTION - COMPLETELY FIXED
# ----------------------------------------------------------------------
async def monitor_ranges():
    global driver, bot
    
    bot = Bot(token=BOT_TOKEN)
    
    # Initialize driver
    driver = init_driver()
    if not driver:
        logging.error("❌ Could not initialize browser driver")
        return
    
    try:
        # Step 1: Navigate to login page
        logging.info("🌐 STEP 1: Navigating to login page...")
        if not smart_navigate_to_url(LOGIN_URL):
            logging.error("❌ Failed to navigate to login page")
            return
        
        # Step 2: Wait for manual login
        logging.info("🔑 STEP 2: Waiting for manual login...")
        if not wait_for_manual_login():
            logging.error("❌ Manual login failed or timeout")
            return
        
        # Step 3: Navigate to monitor page - THIS IS THE FIX
        logging.info("📊 STEP 3: Navigating to monitor page...")
        logging.info("💡 Using smart navigation to target URL...")
        
        if not smart_navigate_to_url(MONITOR_URL):
            logging.error("❌ CRITICAL: Failed to navigate to monitor page")
            logging.info("💡 Tips: Check if the URL is correct and accessible after login")
            return
        
        # Step 4: Verify we're on monitor page
        logging.info("✅ STEP 4: Verifying monitor page...")
        if not wait_for_monitor_page():
            logging.error("❌ Failed to load monitor page properly")
            return
        
        # Step 5: Start monitoring loop
        logging.info("🚀 STEP 5: Starting monitoring loop...")
        refresh_count = 0
        
        while True:
            try:
                refresh_count += 1
                logging.info(f"🔄 Refresh #{refresh_count} - Checking for new ranges...")
                
                # Refresh the page
                driver.refresh()
                time.sleep(5)
                
                # Verify we're still on monitor page
                current_url = driver.current_url
                if "sms/test/sms" not in current_url:
                    logging.warning("⚠️ Not on monitor page, attempting to navigate back...")
                    if not smart_navigate_to_url(MONITOR_URL):
                        logging.error("❌ Could not return to monitor page")
                        break
                
                # Extract and process ranges
                html_content = driver.page_source
                new_ranges = extract_new_ranges(html_content)
                
                if new_ranges:
                    logging.info(f"🎉 Found {len(new_ranges)} new ranges!")
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
        logging.error(f"💥 Fatal error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("🔚 Browser closed")
            except:
                pass

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
    
    # Add target group
    await add_group("-1002631004312", "Main Monitoring Group")
    
    bot = Bot(token=BOT_TOKEN)
    
    groups = await get_all_groups()
    logging.info(f"📊 Bot is in {len(groups)} groups")
    
    # Start tasks
    monitor_task = asyncio.create_task(health_monitor())
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    await asyncio.gather(monitor_task, bot_task, return_exceptions=True)

# ----------------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting IVASMS Range Monitor Bot")
    print("=" * 60)
    print("NAVIGATION FIXES APPLIED:")
    print("• Smart navigation with multiple methods")
    print("• Automatic link clicking if navigation fails") 
    print("• JavaScript navigation fallback")
    print("• Manual navigation command (/nav)")
    print("=" * 60)
    
    asyncio.run(main())