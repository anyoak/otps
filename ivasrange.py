import asyncio
import time
import re
import logging
import random
import aiosqlite
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"  # Replace with your bot token

LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal/"
MONITOR_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
LOGIN_TIMEOUT = 600  # 10 minutes for manual login and CAPTCHA
REFRESH_INTERVAL = 120  # 2 minutes refresh

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
    """Initialize SQLite database to store group IDs"""
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
    """Add a group to the database"""
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
    """Remove a group from the database"""
    try:
        async with aiosqlite.connect("groups.db") as db:
            await db.execute("DELETE FROM groups WHERE group_id = ?", (str(group_id),))
            await db.commit()
            logging.info(f"Group removed from database: {group_id}")
    except Exception as e:
        logging.error(f"Error removing group from database: {e}")

async def get_all_groups():
    """Get all group IDs from database"""
    try:
        async with aiosqlite.connect("groups.db") as db:
            cursor = await db.execute("SELECT group_id, group_name FROM groups")
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        logging.error(f"Error getting groups from database: {e}")
        return []

# ----------------------------------------------------------------------
# Automatic Country Flag Detection
# ----------------------------------------------------------------------
def get_country_flag(phone_number: str) -> str:
    """Automatically detect country flag from phone number using phonenumbers and pycountry"""
    try:
        # Parse the phone number
        parsed_number = phonenumbers.parse(phone_number, None)
        
        # Get country code
        country_code = phonenumbers.region_code_for_number(parsed_number)
        
        if country_code:
            # Get country object from pycountry
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                # Convert country code to flag emoji
                return country_code_to_flag(country.alpha_2)
        
        # Fallback: try to get country name from geocoder
        country_name = geocoder.description_for_number(parsed_number, "en")
        if country_name:
            country = pycountry.countries.get(name=country_name)
            if country:
                return country_code_to_flag(country.alpha_2)
                
    except Exception as e:
        logging.warning(f"Could not detect country for {phone_number}: {e}")
    
    return "🌍"  # Default globe emoji

def country_code_to_flag(country_code: str) -> str:
    """Convert country code (ISO 3166-1 alpha-2) to flag emoji"""
    if len(country_code) != 2:
        return "🌍"
    
    # Convert country code to regional indicator symbols
    base = 0x1F1E6
    flag_emoji = chr(base + ord(country_code[0]) - ord('A')) + chr(base + ord(country_code[1]) - ord('A'))
    return flag_emoji

# ----------------------------------------------------------------------
# Message builder (Markdown)
# ----------------------------------------------------------------------
def build_message(range_name: str, test_number: str, receive_time: str) -> str:
    """Build the message using website receive time and fixed SID"""
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

# ----------------------------------------------------------------------
# Create inline keyboard
# ----------------------------------------------------------------------
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
# Human-like behavior simulation
# ----------------------------------------------------------------------
def human_like_behavior():
    """Simulate human-like behavior to avoid detection"""
    try:
        # Random mouse movements and scrolling
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * Math.random());")
        
        # Random delays between actions
        time.sleep(random.uniform(1, 3))
        
        # Random tab switching simulation
        if random.random() > 0.7:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[0])
            
    except Exception as e:
        logging.debug(f"Human behavior simulation minor issue: {e}")

# ----------------------------------------------------------------------
# Initialize Chrome driver with enhanced anti-detection
# ----------------------------------------------------------------------
def init_driver():
    global driver
    
    # Enhanced SeleniumBase Driver configuration
    driver = Driver(
        uc=True,                    # Undetectable Chrome mode
        headless=False,             # Keep visible for manual CAPTCHA
        undetectable=True,          # Anti-detection
        incognito=True,             # Use incognito mode
        block_images=False,         # Allow images for human-like behavior
        do_not_track=True,          # Enable Do Not Track
        disable_gpu=False,          # Keep GPU enabled
        no_sandbox=True,            # Bypass OS security model
        disable_dev_shm_usage=True, # Overcome limited resource problems
        agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),  # Real user agent
        extension_zip=None,         # No extensions that could be detected
        extension_dir=None
    )
    
    # Additional anti-detection measures
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    # Remove webdriver properties
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    logging.info("✅ Enhanced SeleniumBase Driver initialized with anti-detection measures")
    return driver

# ----------------------------------------------------------------------
# Cloudflare CAPTCHA Detection and Handling
# ----------------------------------------------------------------------
def is_cloudflare_captcha_present():
    """Check if Cloudflare CAPTCHA is present on the page"""
    try:
        # Common Cloudflare CAPTCHA indicators
        cloudflare_indicators = [
            "cf-challenge", 
            "challenge-form",
            "cloudflare",
            "cf_captcha",
            "turnstile"
        ]
        
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()
        
        # Check for Cloudflare in page source or URL
        for indicator in cloudflare_indicators:
            if indicator in page_source or indicator in current_url:
                return True
        
        # Check for specific CAPTCHA elements
        captcha_selectors = [
            "div[class*='cf-challenge']",
            "div[class*='challenge']",
            "iframe[src*='challenges.cloudflare.com']",
            "div[id*='cf-challenge']"
        ]
        
        for selector in captcha_selectors:
            if driver.find_elements(By.CSS_SELECTOR, selector):
                return True
                
        return False
    except Exception as e:
        logging.error(f"Error checking for Cloudflare CAPTCHA: {e}")
        return False

def wait_for_captcha_completion(timeout=600):
    """
    Wait for manual CAPTCHA completion with enhanced detection
    Returns True if CAPTCHA is solved, False if timeout
    """
    logging.info("🔍 Cloudflare CAPTCHA detected! Please complete it manually in the browser window.")
    logging.info("⏰ Waiting up to 10 minutes for manual CAPTCHA completion...")
    
    start_time = time.time()
    last_notification = start_time
    
    while time.time() - start_time < timeout:
        try:
            # Check if we're past the CAPTCHA
            if not is_cloudflare_captcha_present():
                logging.info("✅ CAPTCHA appears to be completed! Continuing...")
                return True
            
            # Check if we're on a logged-in page
            if is_logged_in():
                logging.info("✅ Successfully logged in! CAPTCHA bypassed.")
                return True
                
            # Periodic notifications
            if time.time() - last_notification > 30:  # Every 30 seconds
                remaining = timeout - (time.time() - start_time)
                logging.info(f"⏳ Still waiting for CAPTCHA completion... {int(remaining)} seconds remaining")
                last_notification = time.time()
                
            # Simulate human behavior while waiting
            human_like_behavior()
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"Error during CAPTCHA wait: {e}")
            time.sleep(10)
    
    logging.error("❌ CAPTCHA completion timeout! Please try again.")
    return False

# ----------------------------------------------------------------------
# Extract ranges from DataTable
# ----------------------------------------------------------------------
def extract_new_ranges(html_content: str):
    """Extract range information from the DataTable HTML with improved parsing"""
    new_entries = []
    
    try:
        # Pattern to match table rows with range data
        pattern = r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>'
        
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            if len(match) >= 5:
                # Clean HTML tags and extra spaces
                range_name = re.sub(r'<[^>]+>', '', match[0]).strip()
                test_number = re.sub(r'<[^>]+>', '', match[1]).strip()
                sid = re.sub(r'<[^>]+>', '', match[2]).strip()
                message_content = re.sub(r'<[^>]+>', '', match[3]).strip()
                receive_time = re.sub(r'<[^>]+>', '', match[4]).strip()
                
                # Skip empty or invalid entries
                if not range_name or not test_number:
                    continue
                
                # Ensure phone number has + prefix for proper parsing
                if test_number and not test_number.startswith('+'):
                    test_number = '+' + test_number
                
                # Use website receive time, not current time
                if not receive_time:
                    receive_time = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Create unique key for this range
                key = f"{range_name}-{test_number}-{receive_time}"
                
                if key not in posted_keys:
                    posted_keys.add(key)
                    new_entries.append({
                        'range_name': range_name,
                        'test_number': test_number,
                        'receive_time': receive_time
                    })
                    logging.info(f"New range found: {range_name} - {test_number} - {receive_time}")
    
    except Exception as e:
        logging.error(f"Error extracting ranges: {e}")
    
    return new_entries

# ----------------------------------------------------------------------
# Send message to all groups
# ----------------------------------------------------------------------
async def send_to_all_groups(message: str, keyboard: InlineKeyboardMarkup):
    """Send message to all groups in database"""
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
            logging.info(f"✓ Message sent to group: {group_name or group_id}")
            
            # Random delay to avoid rate limiting and appear human-like
            await asyncio.sleep(random.uniform(1, 3))
            
        except Exception as e:
            logging.error(f"✗ Failed to send to group {group_name or group_id}: {e}")
            # If bot was removed from group, remove from database
            if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                await remove_group(group_id)
    
    return success_count

# ----------------------------------------------------------------------
# Bot Event Handlers
# ----------------------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command"""
    await message.answer("🤖 IVASMS Range Monitor Bot is running!\n\n"
                        "Add me to your groups and I'll automatically share new range information.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Handle /stats command"""
    groups = await get_all_groups()
    await message.answer(f"📊 Bot Statistics:\n"
                        f"• Active Groups: {len(groups)}\n"
                        f"• Refresh Interval: {REFRESH_INTERVAL} seconds\n"
                        f"• Last Refresh: {time.strftime('%Y-%m-%d %H:%M:%S')}")

@dp.my_chat_member()
async def handle_chat_member_update(chat_member: types.ChatMemberUpdated):
    """Handle bot being added to or removed from groups"""
    try:
        chat = chat_member.chat
        old_status = chat_member.old_chat_member.status
        new_status = chat_member.new_chat_member.status
        
        # Bot was added to group
        if (old_status in ["left", "kicked"] and 
            new_status in ["member", "administrator"]):
            
            if chat.type in ["group", "supergroup"]:
                await add_group(str(chat.id), chat.title)
                logging.info(f"Bot added to group: {chat.title} ({chat.id})")
                
                # Send welcome message
                welcome_msg = (
                    "🤖 IVASMS Range Monitor Bot Activated!\n\n"
                    "I will automatically share new range information every 2 minutes.\n"
                    "Make sure I have permission to send messages in this group."
                )
                await bot.send_message(chat.id, welcome_msg)
        
        # Bot was removed from group
        elif (old_status in ["member", "administrator"] and 
              new_status in ["left", "kicked"]):
            
            if chat.type in ["group", "supergroup"]:
                await remove_group(str(chat.id))
                logging.info(f"Bot removed from group: {chat.title} ({chat.id})")
                
    except Exception as e:
        logging.error(f"Error handling chat member update: {e}")

# ----------------------------------------------------------------------
# Check if logged in
# ----------------------------------------------------------------------
def is_logged_in():
    """Check if we're on a logged-in page"""
    try:
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        # Check for portal URL or logged-in indicators
        if PORTAL_URL in current_url or "portal" in current_url.lower():
            return True
            
        # Check for logout button or user menu (common logged-in indicators)
        logged_in_indicators = [
            "logout", "log out", "sign out", "user menu", "dashboard"
        ]
        
        for indicator in logged_in_indicators:
            if indicator in page_source:
                return True
                
        return False
    except Exception as e:
        logging.error(f"Error checking login status: {e}")
        return False

# ----------------------------------------------------------------------
# Wait for DataTable to load
# ----------------------------------------------------------------------
def wait_for_table_load(timeout=30):
    """Wait for the DataTable to load"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Check for the table or specific elements
            if "clientsmshistory-table" in driver.page_source:
                return True
            # Also check for any table with range data
            if driver.find_elements(By.TAG_NAME, "table"):
                return True
            time.sleep(2)
        except Exception as e:
            logging.debug(f"Waiting for table: {e}")
            time.sleep(2)
    return False

# ----------------------------------------------------------------------
# Enhanced CAPTCHA handling with manual completion support
# ----------------------------------------------------------------------
def handle_cloudflare_captcha():
    """Handle Cloudflare CAPTCHA with manual completion support"""
    try:
        logging.info("🛡️ Checking for Cloudflare protection...")
        
        # Check if Cloudflare CAPTCHA is present
        if is_cloudflare_captcha_present():
            logging.info("🔍 Cloudflare CAPTCHA detected!")
            return wait_for_captcha_completion()
        else:
            logging.info("✅ No Cloudflare CAPTCHA detected")
            return True
            
    except Exception as e:
        logging.error(f"Error handling Cloudflare CAPTCHA: {e}")
        return False

# ----------------------------------------------------------------------
# Main monitoring function with enhanced CAPTCHA handling
# ----------------------------------------------------------------------
async def monitor_ranges():
    global driver, bot
    
    # Initialize bot and driver
    bot = Bot(token=BOT_TOKEN)
    driver = init_driver()
    
    try:
        # Step 1: Navigate to login page with human-like behavior
        logging.info("Opening browser for login...")
        driver.get(LOGIN_URL)
        
        # Simulate human behavior
        human_like_behavior()
        
        # Step 2: Handle Cloudflare CAPTCHA before login
        logging.info("Checking for Cloudflare protection...")
        if not handle_cloudflare_captcha():
            logging.error("❌ Failed to bypass Cloudflare CAPTCHA")
            return
        
        logging.info("Please log in manually when the page loads...")
        logging.info(f"Waiting for redirect to: {PORTAL_URL}")
        
        # Step 3: Wait for manual login with CAPTCHA handling
        start_time = time.time()
        captcha_handled = False
        
        while time.time() - start_time < LOGIN_TIMEOUT:
            # Check if we need to handle CAPTCHA again
            if not captcha_handled and is_cloudflare_captcha_present():
                logging.info("🛡️ CAPTCHA detected during login process...")
                if handle_cloudflare_captcha():
                    captcha_handled = True
                else:
                    logging.error("❌ CAPTCHA handling failed during login")
                    return
            
            # Check if login was successful
            if is_logged_in():
                logging.info("✅ Login successful! Detected portal page.")
                break
                
            # Simulate human behavior while waiting
            human_like_behavior()
            await asyncio.sleep(5)
        else:
            logging.error("❌ Login timeout! Please check your credentials and complete CAPTCHA.")
            return
        
        # Step 4: Navigate to monitor page with CAPTCHA checks
        logging.info(f"Navigating to monitor page: {MONITOR_URL}")
        driver.get(MONITOR_URL)
        
        # Check for CAPTCHA on monitor page
        human_like_behavior()
        if is_cloudflare_captcha_present():
            logging.info("🛡️ CAPTCHA detected on monitor page...")
            if not handle_cloudflare_captcha():
                logging.error("❌ Failed to bypass CAPTCHA on monitor page")
                return
        
        # Wait for table to load
        if not wait_for_table_load():
            logging.warning("Table might not have loaded properly, continuing anyway...")
        
        # Step 5: Start monitoring loop with human-like intervals
        logging.info("🚀 Starting monitoring loop with human-like behavior...")
        
        refresh_count = 0
        while True:
            try:
                refresh_count += 1
                logging.info(f"🔄 Refresh #{refresh_count} - Checking for new ranges...")
                
                # Refresh the page with human-like behavior
                driver.refresh()
                human_like_behavior()
                
                # Check for CAPTCHA after refresh
                if is_cloudflare_captcha_present():
                    logging.warning("🛡️ CAPTCHA detected after refresh...")
                    if not handle_cloudflare_captcha():
                        logging.error("❌ Failed to bypass CAPTCHA after refresh")
                        # Continue monitoring anyway
                
                # Wait for page to load with random delay
                await asyncio.sleep(random.uniform(3, 7))
                
                # Get page source and extract ranges
                html_content = driver.page_source
                new_ranges = extract_new_ranges(html_content)
                
                # Send new ranges to all groups
                if new_ranges:
                    for range_data in new_ranges:
                        message = build_message(
                            range_data['range_name'],
                            range_data['test_number'],
                            range_data['receive_time']
                        )
                        
                        keyboard = create_keyboard()
                        success_count = await send_to_all_groups(message, keyboard)
                        
                        logging.info(f"✅ Sent new range to {success_count} groups: {range_data['range_name']}")
                        
                        # Random delay between sending different ranges
                        await asyncio.sleep(random.uniform(2, 5))
                else:
                    logging.info("ℹ️ No new ranges found in this refresh.")
                
                # Random wait before next refresh (human-like interval)
                next_wait = REFRESH_INTERVAL + random.randint(-30, 30)  # ±30 seconds variation
                next_refresh = time.strftime("%H:%M:%S", time.localtime(time.time() + next_wait))
                logging.info(f"⏰ Next refresh in {next_wait} seconds at: {next_refresh}")
                await asyncio.sleep(next_wait)
                
            except Exception as e:
                logging.error(f"❌ Error during monitoring cycle: {e}")
                logging.info("🕒 Waiting 30 seconds before retrying...")
                await asyncio.sleep(30)
                
    except Exception as e:
        logging.error(f"💥 Fatal error in monitor_ranges: {e}")
    finally:
        # Cleanup
        if driver:
            driver.quit()
            logging.info("🔚 Browser closed.")

# ----------------------------------------------------------------------
# Health check and restart mechanism
# ----------------------------------------------------------------------
async def health_monitor():
    """Monitor the main function and restart if needed"""
    max_restarts = 5
    restarts = 0
    
    while restarts < max_restarts:
        try:
            logging.info(f"🚀 Starting monitor (attempt {restarts + 1}/{max_restarts})")
            await monitor_ranges()
        except Exception as e:
            restarts += 1
            logging.error(f"💥 Monitor crashed (attempt {restarts}/{max_restarts}): {e}")
            
            if restarts < max_restarts:
                wait_time = 60 * restarts  # Increasing wait time
                logging.info(f"🕒 Waiting {wait_time} seconds before restart...")
                await asyncio.sleep(wait_time)
            else:
                logging.error("❌ Max restarts reached. Exiting.")
                break

# ----------------------------------------------------------------------
# Main function to run both bot and monitor
# ----------------------------------------------------------------------
async def main():
    """Main function to run both bot polling and monitoring"""
    global bot
    
    # Initialize database
    await init_database()
    logging.info("✅ Database initialized")
    
    # Initialize bot
    bot = Bot(token=BOT_TOKEN)
    
    # Get initial group count
    groups = await get_all_groups()
    logging.info(f"📊 Bot is in {len(groups)} groups")
    
    # Start both tasks
    monitor_task = asyncio.create_task(health_monitor())
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    # Wait for both tasks (they should run indefinitely)
    await asyncio.gather(monitor_task, bot_task, return_exceptions=True)

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting IVASMS Range Monitor Bot with Enhanced CAPTCHA Handling")
    print("=" * 60)
    print(f"📊 Enhanced Configuration:")
    print(f"   - Refresh Interval: {REFRESH_INTERVAL} seconds ±30s variation")
    print(f"   - Login Timeout: {LOGIN_TIMEOUT} seconds")
    print(f"   - Login URL: {LOGIN_URL}")
    print(f"   - Monitor URL: {MONITOR_URL}")
    print(f"   - SeleniumBase UC Mode: Enabled")
    print(f"   - Cloudflare CAPTCHA Detection: Enhanced")
    print(f"   - Manual CAPTCHA Completion: Supported")
    print(f"   - Human-like Behavior: Enabled")
    print(f"   - Auto Group Detection: Enabled")
    print("=" * 60)
    print("💡 IMPORTANT: When Cloudflare CAPTCHA appears, complete it manually in the browser window.")
    print("   The bot will wait up to 10 minutes for manual completion.")
    print("=" * 60)
    
    # Check required packages
    try:
        from seleniumbase import Driver
        import phonenumbers
        import pycountry
        import aiosqlite
        logging.info("✅ All required packages are installed")
    except ImportError as e:
        logging.error(f"❌ Missing required package: {e}")
        logging.info("💡 Install missing packages: pip install seleniumbase phonenumbers pycountry aiosqlite")
        exit(1)
    
    # Run main function
    asyncio.run(main())
