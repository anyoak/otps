import asyncio
import time
import html
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import Message
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import re

# ==== CONFIGURATION ====
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"      # Replace with your bot token
GROUP_ID = -1001234567890              # Replace with your Telegram group/channel ID
LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal"
MONITOR_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
LOGIN_TIMEOUT = 300                     # seconds

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot)

# Cache to prevent reposting the same entries
posted_ranges = set()

# ==== COUNTRY FLAG FUNCTION ====
def get_flag_emoji(country_code):
    try:
        return chr(127397 + ord(country_code[0])) + chr(127397 + ord(country_code[1]))
    except:
        return "🌍"  # fallback globe emoji

# ==== TELEGRAM MESSAGE STYLE ====
def format_message(flag, range_name, test_number):
    recv_time = time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"╔═━IVASMS NEW RANGE━━═╗\n"
        f"┣{flag} RANE: `{html.escape(range_name)}`\n"
        f"┣🕓 TIMR     ➜ {recv_time}\n"
        f"┣🌐 SID      ➜ TELEGRAM\n"
        f"┣☎️ TEST NO. ➜ `{html.escape(test_number)}`\n"
        f"┣💬 DEV.     ➜ @professor_cry\n"
        "╚═━━━━ ◢◤◆◥◣ ━━━━═╝"
    )

# ==== COMMANDS ====
@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("🧭 Monitoring will begin once you log in manually...")

# ==== MAIN MONITORING LOGIC ====
async def monitor_ranges():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless=new")  # ❌ comment out for manual login

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(LOGIN_URL)
    print("🔑 Please log in manually... Waiting up to 300 seconds.")

    # Wait for login success
    start_time = time.time()
    while time.time() - start_time < LOGIN_TIMEOUT:
        current_url = driver.current_url
        if current_url.startswith(PORTAL_URL):
            print("✅ Login successful!")
            break
        await asyncio.sleep(3)
    else:
        print("❌ Login timeout. Please try again.")
        driver.quit()
        return

    driver.get(MONITOR_URL)
    print("📡 Monitoring started...")

    while True:
        try:
            await asyncio.sleep(5)
            driver.refresh()
            html_content = driver.page_source

            # Regex to match country code, range name, test number
            matches = re.findall(r'>([A-Z]{2})\s*-\s*([A-Za-z0-9\s]+).*?(\+\d{6,15})', html_content)
            for country_code, range_name, test_no in matches:
                key = f"{country_code}-{range_name}-{test_no}"
                if key not in posted_ranges:
                    posted_ranges.add(key)
                    flag = get_flag_emoji(country_code)
                    msg = format_message(flag, range_name.strip(), test_no.strip())
                    await bot.send_message(GROUP_ID, msg, parse_mode=ParseMode.MARKDOWN_V2)
                    print(f"✅ Posted new range: {key}")

        except Exception as e:
            print("⚠️ Error during monitoring:", e)
            await asyncio.sleep(10)

# ==== MAIN ====
async def main():
    asyncio.create_task(monitor_ranges())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
