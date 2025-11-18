import asyncio
import time
import re
import logging
import aiosqlite
import requests
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
import phonenumbers
from phonenumbers import geocoder
import pycountry

# Configuration
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"
ADMIN_ID = 6577308099

LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal/"
MONITOR_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
LOGIN_TIMEOUT = 600
REFRESH_INTERVAL = 60

# Global state
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

# Database Functions
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

# Country Flag Detection
def get_country_flag(phone_number: str) -> str:
    try:
        parsed_number = phonenumbers.parse(phone_number, None)
        country_code = phonenumbers.region_code_for_number(parsed_number)
        if country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                return country_code_to_flag(country.alpha_2)
        return "🌍"
    except:
        return "🌍"

def country_code_to_flag(country_code: str) -> str:
    if len(country_code) != 2:
        return "🌍"
    base = 0x1F1E6
    flag_emoji = chr(base + ord(country_code[0]) - ord('A')) + chr(base + ord(country_code[1]) - ord('A'))
    return flag_emoji

# Message Builder
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

# Admin Check Function
def is_admin(user_id: int):
    return user_id == ADMIN_ID

# Website Availability Check
def check_website_available():
    try:
        response = requests.get(LOGIN_URL, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Website check failed: {e}")
        return False

# =============================================================================
# COMPLETE BOT COMMANDS
# =============================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start command with all available commands"""
    commands_text = """
🤖 IVASMS Range Monitor Bot

📋 Available Commands:

👥 Group Management:
/addthisgroup - Add current group to monitoring
/grouplist - List all monitored groups (Admin only)
/addgroup <id> - Add group by ID (Admin only) 
/removegroup <id> - Remove group by ID (Admin only)

📊 Bot Information:
/stats - Show bot statistics
/debug - Show system status (Admin only)
/help - Show this help message

🔧 Controls:
/nav - Force navigate to monitor page (Admin only)
/gotomonitor - Alternative navigation (Admin only)

💡 Simply add me to any group and I'll auto-detect, or use /addthisgroup in existing groups.
    """
    await message.answer(commands_text)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command with detailed instructions"""
    help_text = """
🆘 Bot Help Guide

🔹 How to Setup:
1. Add bot to your group
2. Make bot admin (required)
3. Bot will auto-start monitoring

🔹 Manual Setup:
Use /addthisgroup in any group to manually add it

🔹 Admin Commands:
• /grouplist - View all groups
• /addgroup <ID> - Add specific group
• /removegroup <ID> - Remove group
• /stats - Bot statistics
• /debug - System status

🔹 Monitoring:
• Checks for new ranges every 2 minutes
• Sends to all added groups automatically
• Different times = treated as new ranges

Need help? Contact @professor_cry
    """
    await message.answer(help_text)

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
                f"✅ Group added successfully!\n\n"
                f"📝 Group: {group_name}\n"
                f"🆔 ID: `{group_id}`\n\n"
                f"🤖 Bot will now send range updates every 2 minutes.\n"
                f"Make sure I have permission to send messages!",
                parse_mode=ParseMode.MARKDOWN
            )
            logging.info(f"Manual group add: {group_name} ({group_id})")
        else:
            await message.answer("❌ Failed to add group. Please try again or contact admin.")
        
    except Exception as e:
        await message.answer(f"❌ Error adding group: {str(e)}")
        logging.error(f"Manual group add error: {e}")

@dp.message(Command("grouplist"))
async def cmd_group_list(message: types.Message):
    """Show all groups in database"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("❌ Admin access required!")
            return
            
        groups = await get_all_groups()
        
        if not groups:
            await message.answer("📋 No groups in database yet.")
            return
        
        group_list = []
        total_groups = len(groups)
        
        for i, (group_id, group_name) in enumerate(groups, 1):
            group_list.append(f"{i}. {group_name or 'Unknown Group'}\n   ID: `{group_id}`")
        
        response = (
            f"📋 Monitored Groups ({total_groups}):\n\n" +
            "\n\n".join(group_list) +
            f"\n\n💡 Use /addgroup <id> to add more groups."
        )
        
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await message.answer(f"❌ Error getting group list: {str(e)}")
        logging.error(f"Group list error: {e}")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show bot statistics"""
    try:
        groups = await get_all_groups()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        stats_text = (
            f"📊 Bot Statistics\n\n"
            f"👥 Active Groups: {len(groups)}\n"
            f"📨 Posted Ranges: {len(posted_keys)}\n"
            f"🔄 Refresh Interval: {REFRESH_INTERVAL} seconds\n"
            f"⏰ Last Refresh: {current_time}\n"
            f"🔧 Status: {'🟢 Running' if driver else '🔴 Stopped'}\n\n"
            f"💡 Bot is monitoring for new ranges every 2 minutes."
        )
        
        await message.answer(stats_text)
        
    except Exception as e:
        await message.answer(f"❌ Error getting stats: {str(e)}")

@dp.message(Command("debug"))
async def cmd_debug(message: types.Message):
    """Debug command to check system status"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Admin access required!")
        return
    
    try:
        status = []
        status.append("🔧 System Debug Information\n")
        
        # Driver status
        status.append(f"🚗 Driver: {'🟢 INITIALIZED' if driver else '🔴 NOT INITIALIZED'}")
        
        if driver:
            try:
                current_url = driver.current_url
                page_title = driver.title[:50] + "..." if len(driver.title) > 50 else driver.title
                status.append(f"🌐 Current URL: {current_url}")
                status.append(f"📄 Page Title: {page_title}")
                status.append(f"🔐 Logged In: {'🟢 YES' if is_logged_in() else '🔴 NO'}")
            except Exception as e:
                status.append(f"❌ Driver Error: {str(e)}")
        
        # System status - FIXED LINE BELOW
        status.append(f"📊 Groups in DB: {len(await get_all_groups())}")
        status.append(f"📨 Posted Keys: {len(posted_keys)}")
        status.append(f"🌐 Website Access: {'🟢 OK' if check_website_available() else '🔴 DOWN'}")
        status.append(f"🤖 Bot: {'🟢 RUNNING' if bot else '🔴 STOPPED'}")
        
        # Add timestamp
        status.append(f"\n🕒 Last Update: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        await message.answer("\n".join(status))
        
    except Exception as e:
        await message.answer(f"❌ Debug error: {str(e)}")

@dp.message(Command("addgroup"))
async def cmd_addgroup_manual(message: types.Message, command: CommandObject):
    """Manually add group by ID (Admin only)"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("❌ Admin access required!")
            return

        group_id = command.args
        if not group_id:
            await message.answer("❌ Please provide a Group ID\nUsage: /addgroup <group_id>")
            return

        # Validate group ID format
        if not (group_id.startswith('-100') and group_id[1:].isdigit()):
            await message.answer("❌ Invalid Group ID format. Should start with -100 and be numeric.")
            return

        success = await add_group(group_id, "Manually Added Group")
        if success:
            await message.answer(
                f"✅ Group added successfully!\n"
                f"🆔 ID: `{group_id}`\n\n"
                f"Bot will now send range updates to this group.",
                parse_mode=ParseMode.MARKDOWN
            )
            logging.info(f"Group manually added via command: {group_id}")
        else:
            await message.answer("❌ Failed to add group. It might already exist.")
        
    except Exception as e:
        await message.answer(f"❌ Failed to add group: {str(e)}")
        logging.error(f"Error in manual group add: {e}")

@dp.message(Command("removegroup"))
async def cmd_remove_group(message: types.Message, command: CommandObject):
    """Remove group by ID (Admin only)"""
    try:
        if not is_admin(message.from_user.id):
            await message.answer("❌ Admin access required!")
            return

        group_id = command.args
        if not group_id:
            await message.answer("❌ Please provide a Group ID\nUsage: /removegroup <group_id>")
            return

        success = await remove_group(group_id)
        if success:
            await message.answer(f"✅ Group `{group_id}` has been removed from database.", parse_mode=ParseMode.MARKDOWN)
            logging.info(f"Group manually removed via command: {group_id}")
        else:
            await message.answer("❌ Failed to remove group. It might not exist in database.")
        
    except Exception as e:
        await message.answer(f"❌ Failed to remove group: {str(e)}")
        logging.error(f"Error in manual group remove: {e}")

@dp.message(Command("nav"))
async def cmd_navigate_manual(message: types.Message):
    """Manual navigation command for admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Admin only!")
        return
    
    try:
        await message.answer("🔄 Attempting manual navigation to monitor page...")
        
        if navigate_to_monitor_page():
            await message.answer("✅ Navigation successful! Monitor page loaded.")
        else:
            await message.answer("❌ Navigation failed! Check browser window.")
            
    except Exception as e:
        await message.answer(f"❌ Navigation error: {str(e)}")

@dp.message(Command("gotomonitor"))
async def cmd_go_to_monitor(message: types.Message):
    """Alternative manual navigation command"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Admin only!")
        return
    
    try:
        await message.answer("🔄 Navigating to monitor page...")
        
        if smart_navigate_to_url(MONITOR_URL):
            await message.answer("✅ Successfully reached monitor page!")
        else:
            await message.answer("❌ Failed to reach monitor page!")
            
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# Auto Group Detection Handler
@dp.my_chat_member()
async def handle_chat_member_update(chat_member: types.ChatMemberUpdated):
    try:
        chat = chat_member.chat
        old_status = chat_member.old_chat_member.status
        new_status = chat_member.new_chat_member.status
        
        logging.info(f"🔄 Chat member update: {chat.title} ({chat.id}) - {old_status} -> {new_status}")
        
        # Bot added to group
        if (old_status in ["left", "kicked", "restricted"] and 
            new_status in ["member", "administrator"]):
            
            if chat.type in ["group", "supergroup"]:
                group_id = str(chat.id)
                success = await add_group(group_id, chat.title)
                
                if success:
                    logging.info(f"✅ Bot auto-added to group: {chat.title} ({group_id})")
                    
                    welcome_msg = (
                        "🤖 IVASMS Range Monitor Bot Activated!\n\n"
                        "I will automatically share new range information every 2 minutes.\n"
                        "Make sure I have permission to send messages in this group.\n\n"
                        "Type /addthisgroup if you don't see updates within 5 minutes."
                    )
                    await bot.send_message(chat.id, welcome_msg)
        
        # Bot removed from group
        elif (old_status in ["member", "administrator"] and 
              new_status in ["left", "kicked", "restricted"]):
            
            if chat.type in ["group", "supergroup"]:
                group_id = str(chat.id)
                success = await remove_group(group_id)
                if success:
                    logging.info(f"❌ Bot auto-removed from group: {chat.title} ({group_id})")
                
    except Exception as e:
        logging.error(f"Error handling chat member update: {e}")

# =============================================================================
# NAVIGATION AND MONITORING FUNCTIONS
# =============================================================================

def init_driver():
    global driver
    try:
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        logging.info("🔄 Initializing browser driver...")
        driver = Driver(uc=True, headless=False, undetectable=True, incognito=True)
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(15)
        logging.info("✅ Driver initialized successfully")
        return driver
    except Exception as e:
        logging.error(f"❌ Failed to initialize driver: {e}")
        return None

def smart_navigate_to_url(target_url, max_retries=3):
    for attempt in range(max_retries):
        try:
            logging.info(f"🌐 Navigation attempt {attempt+1} to: {target_url}")
            driver.get(target_url)
            WebDriverWait(driver, 25).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(3)
            logging.info("✅ Page loaded successfully")
            return True
        except Exception as e:
            logging.error(f"❌ Navigation error: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return False

def is_logged_in():
    try:
        current_url = driver.current_url
        if PORTAL_URL in current_url or "portal" in current_url.lower():
            return True
        page_source = driver.page_source.lower()
        logged_in_indicators = ["logout", "log out", "sign out", "dashboard", "welcome"]
        for indicator in logged_in_indicators:
            if indicator in page_source:
                return True
        return False
    except:
        return False

def navigate_to_monitor_page():
    logging.info("📊 Navigating to monitor page...")
    if smart_navigate_to_url(MONITOR_URL):
        current_url = driver.current_url
        if "sms/test/sms" in current_url:
            logging.info("🎯 Successfully reached monitor page!")
            return True
    return False

def wait_for_login_completion():
    logging.info("🔑 Please complete login manually in browser...")
    start_time = time.time()
    while time.time() - start_time < LOGIN_TIMEOUT:
        if is_logged_in():
            logging.info("✅ Login detected! Navigating to monitor page...")
            return navigate_to_monitor_page()
        time.sleep(5)
    return False

def extract_new_ranges(html_content: str):
    new_entries = []
    try:
        pattern = r'<tr[^>]*>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>[\s\S]*?<td[^>]*>([^<]*)</td>'
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            if len(match) >= 5:
                range_name = re.sub(r'<[^>]+>', '', match[0]).strip()
                test_number = re.sub(r'<[^>]+>', '', match[1]).strip()
                receive_time = re.sub(r'<[^>]+>', '', match[4]).strip()
                
                if range_name and test_number:
                    if not test_number.startswith('+'):
                        test_number = '+' + test_number.lstrip()
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
                        logging.info(f"✅ NEW RANGE: {range_name} - {test_number}")
    except Exception as e:
        logging.error(f"❌ Error extracting ranges: {e}")
    return new_entries

async def send_to_all_groups(message: str, keyboard: InlineKeyboardMarkup):
    groups = await get_all_groups()
    success_count = 0
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
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"✗ Failed to send to {group_name or group_id}: {e}")
    return success_count

async def monitor_ranges():
    global driver, bot
    bot = Bot(token=BOT_TOKEN)
    driver = init_driver()
    if not driver:
        return
    
    try:
        if not smart_navigate_to_url(LOGIN_URL):
            return
        
        if not wait_for_login_completion():
            return
        
        refresh_count = 0
        while True:
            refresh_count += 1
            logging.info(f"🔄 Refresh #{refresh_count}")
            driver.refresh()
            time.sleep(5)
            
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
                    await send_to_all_groups(message, keyboard)
                    await asyncio.sleep(2)
            
            await asyncio.sleep(REFRESH_INTERVAL)
                
    except Exception as e:
        logging.error(f"💥 Fatal error: {e}")
    finally:
        if driver:
            driver.quit()

async def health_monitor():
    max_restarts = 3
    restarts = 0
    while restarts < max_restarts:
        try:
            await monitor_ranges()
        except Exception as e:
            restarts += 1
            if restarts < max_restarts:
                await asyncio.sleep(60 * restarts)

async def main():
    await init_database()
    await add_group("-1002631004312", "Main Monitoring Group")
    bot = Bot(token=BOT_TOKEN)
    
    monitor_task = asyncio.create_task(health_monitor())
    bot_task = asyncio.create_task(dp.start_polling(bot))
    await asyncio.gather(monitor_task, bot_task, return_exceptions=True)

if __name__ == "__main__":
    print("🚀 Starting IVASMS Range Monitor Bot - Complete Command Set")
    asyncio.run(main())
