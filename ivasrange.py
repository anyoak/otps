import asyncio
import time
import re
import logging
import sqlite3
import aiosqlite
from seleniumbase import Driver  # Changed from selenium webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
LOGIN_TIMEOUT = 300  # 5 minutes for manual login
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
        f"SID: `Telegram`\n"
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
# Initialize Chrome driver WITH SeleniumBase UC Mode
# ----------------------------------------------------------------------
def init_driver():
    global driver
    
    # Use SeleniumBase Driver with UC Mode for CAPTCHA bypass
    driver = Driver(
        uc=True,                    # Undetectable Chrome mode
        headless=False,             # Keep visible for manual login
        undetectable=True,          # Anti-detection
        incognito=True,             # Use incognito mode
        agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )  # Real user agent
    )
    
    logging.info("✅ SeleniumBase Driver initialized with UC Mode")
    return driver

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
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
            
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
    current_url = driver.current_url
    return PORTAL_URL in current_url or "portal" in current_url.lower()

# ----------------------------------------------------------------------
# Wait for DataTable to load
# ----------------------------------------------------------------------
def wait_for_table_load(timeout=30):
    """Wait for the DataTable to load"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if "clientsmshistory-table" in driver.page_source:
            return True
        time.sleep(2)
    return False

# ----------------------------------------------------------------------
# Handle CAPTCHA with SeleniumBase
# ----------------------------------------------------------------------
def handle_captcha():
    """Attempt to handle CAPTCHA using SeleniumBase UC Mode"""
    try:
        logging.info("🛡️ Attempting CAPTCHA bypass...")
        # SeleniumBase UC Mode automatically handles many CAPTCHAs
        # For additional CAPTCHA clicking if needed:
        driver.uc_gui_click_captcha()
        logging.info("✅ CAPTCHA handling attempted")
        return True
    except Exception as e:
        logging.info(f"ℹ️ No CAPTCHA found or automatic handling not needed: {e}")
        return False

# ----------------------------------------------------------------------
# Main monitoring function
# ----------------------------------------------------------------------
async def monitor_ranges():
    global driver, bot
    
    # Initialize bot and driver
    bot = Bot(token=BOT_TOKEN)
    driver = init_driver()
    
    try:
        # Step 1: Manual login with CAPTCHA protection
        logging.info("Opening browser for manual login...")
        driver.get(LOGIN_URL)
        
        # Attempt CAPTCHA handling on login page
        handle_captcha()
        
        logging.info("Please log in manually within 5 minutes...")
        logging.info(f"Waiting for redirect to: {PORTAL_URL}")
        
        # Wait for manual login
        start_time = time.time()
        while time.time() - start_time < LOGIN_TIMEOUT:
            if is_logged_in():
                logging.info("✅ Login successful! Detected portal page.")
                break
            await asyncio.sleep(5)
        else:
            logging.error("❌ Login timeout! Please check your credentials.")
            return
        
        # Step 2: Navigate to monitor page
        logging.info(f"Navigating to monitor page: {MONITOR_URL}")
        driver.get(MONITOR_URL)
        
        # Attempt CAPTCHA handling on monitor page if needed
        handle_captcha()
        
        # Wait for table to load
        if not wait_for_table_load():
            logging.warning("Table might not have loaded properly, continuing anyway...")
        
        # Step 3: Start monitoring loop with 2-minute intervals
        logging.info("🚀 Starting monitoring loop with 2-minute refresh intervals...")
        
        refresh_count = 0
        while True:
            try:
                refresh_count += 1
                logging.info(f"🔄 Refresh #{refresh_count} - Checking for new ranges...")
                
                # Refresh the page
                driver.refresh()
                
                # Wait for page to load
                await asyncio.sleep(5)
                
                # Get page source and extract ranges
                html_content = driver.page_source
                new_ranges = extract_new_ranges(html_content)
                
                # Send new ranges to all groups
                if new_ranges:
                    for range_data in new_ranges:
                        message = build_message(
                            range_data['range_name'],
                            range_data['test_number'],
                            range_data['receive_time']  # Use website receive time
                        )
                        
                        keyboard = create_keyboard()
                        success_count = await send_to_all_groups(message, keyboard)
                        
                        logging.info(f"✅ Sent new range to {success_count} groups: {range_data['range_name']}")
                        
                        # Small delay between sending different ranges
                        await asyncio.sleep(2)
                else:
                    logging.info("ℹ️ No new ranges found in this refresh.")
                
                # Wait for 2 minutes before next refresh
                next_refresh = time.strftime("%H:%M:%S", time.localtime(time.time() + REFRESH_INTERVAL))
                logging.info(f"⏰ Next refresh at: {next_refresh}")
                await asyncio.sleep(REFRESH_INTERVAL)
                
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
                logging.info("🕒 Waiting 60 seconds before restart...")
                await asyncio.sleep(60)
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
    print("🚀 Starting IVASMS Range Monitor Bot with SeleniumBase CAPTCHA Bypass")
    print("=" * 60)
    print(f"📊 Configuration:")
    print(f"   - Refresh Interval: {REFRESH_INTERVAL} seconds")
    print(f"   - Login URL: {LOGIN_URL}")
    print(f"   - Monitor URL: {MONITOR_URL}")
    print(f"   - SeleniumBase UC Mode: Enabled")
    print(f"   - CAPTCHA Bypass: Active")
    print(f"   - Auto Group Detection: Enabled")
    print(f"   - Database: SQLite (groups.db)")
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
