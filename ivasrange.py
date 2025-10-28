import asyncio
import time
import html
import pycountry
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# --- CONFIG ---
BOT_TOKEN = "8335302596:AAFDsN1hRYLvFVawMIrZiJU8o1wpaTBaZIU"
GROUP_ID = -1002631004312
LOGIN_URL = "https://www.ivasms.com/login"
PORTAL_URL = "https://www.ivasms.com/portal"
TARGET_URL = "https://www.ivasms.com/portal/sms/test/sms?app=Telegram"
CHECK_INTERVAL = 10  # seconds
RUN_DURATION = 300   # seconds (5 minutes)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


def country_to_flag(country_name):
    """Convert country name to emoji flag."""
    try:
        country = pycountry.countries.lookup(country_name.strip())
        code = country.alpha_2.upper()
        return ''.join(chr(127397 + ord(c)) for c in code)
    except:
        return "🏳️‍🌈"


async def wait_for_login(driver):
    """Wait until user successfully logs in (portal URL visible)."""
    print("🕓 Waiting for successful login...")
    start_time = time.time()
    while time.time() - start_time < 180:  # wait up to 3 minutes
        current_url = driver.current_url
        if current_url.startswith(PORTAL_URL):
            print("✅ Login successful! Starting monitor...")
            return True
        await asyncio.sleep(2)
    print("❌ Login timeout (3 minutes). Exiting.")
    return False


async def monitor(driver):
    """Monitor IVASMS page every 10 seconds and send updates to Telegram."""
    print("🔁 Monitoring started for 300 seconds...")
    start_time = time.time()

    while (time.time() - start_time) < RUN_DURATION:
        try:
            driver.get(TARGET_URL)
            await asyncio.sleep(3)
            html_source = driver.page_source
            soup = BeautifulSoup(html_source, "html.parser")
            table = soup.find("table")
            if not table:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = [c.text.strip() for c in row.find_all("td")]
                if len(cols) < 5:
                    continue
                range_name = cols[0]
                test_number = cols[1]
                sid = cols[2]
                recv_time = cols[4]
                flag = country_to_flag(range_name.split()[0])

                # Message format with your original emojis & Markdown copy text
                text = (
                    f"╔═━IVASMS NEW RANGE  ◥◣◆◢◤ ━━━━━━━━━═╗\n"
                    f"┣{flag} RANE: `{html.escape(range_name)}`\n"
                    f"┣🕓 TIMR     ➜ {recv_time}\n"
                    f"┣🌐 SID      ➜ TELEGRAM\n"
                    f"┣☎️ TEST NO. ➜ `{html.escape(test_number)}`\n"
                    f"┣💬 DEV.     ➜ @professor_cry\n"
                    f"╚═━━━━━━━━━ ◢◤◆◥◣ ━━━━━━━━━═╝"
                )

                try:
                    await bot.send_message(GROUP_ID, text, parse_mode="Markdown")
                except Exception as e:
                    print("⚠️ Telegram send error:", e)

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("⚠️ Monitor error:", e)
            await asyncio.sleep(CHECK_INTERVAL)

    print("🕒 Monitoring stopped after 300 seconds.")


async def main():
    print("🌐 Opening browser for manual login...")
    chrome_options = Options()
    # Comment out this line if you want GUI visible
    # chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(LOGIN_URL)

    print("\n🔑 Please login manually in the browser window.")
    print("When the URL becomes 'https://www.ivasms.com/portal', monitoring will start automatically.\n")

    login_success = await wait_for_login(driver)
    if login_success:
        await monitor(driver)
    driver.quit()


if __name__ == "__main__":
    asyncio.run(main())
