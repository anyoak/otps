# forwarder.py
import asyncio
import time
import html
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from aiogram import Bot
from aiogram.enums import ParseMode

# ----------------------------------------------------------------------
# Load config
# ----------------------------------------------------------------------
from config import (
    BOT_TOKEN, GROUP_ID, LOGIN_URL, PORTAL_URL,
    MONITOR_URL, LOGIN_TIMEOUT
)

# ----------------------------------------------------------------------
# Global state
# ----------------------------------------------------------------------
posted_keys = set()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ----------------------------------------------------------------------
# Helper: country flag emoji
# ----------------------------------------------------------------------
def flag_emoji(country_code: str) -> str:
    if len(country_code) != 2:
        return "Globe"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in country_code.upper())
    except Exception:
        return "Globe"

# ----------------------------------------------------------------------
# Message builder (HTML)
# ----------------------------------------------------------------------
def build_message(flag: str, range_name: str, test_number: str) -> str:
    recv_time = time.strftime("%Y-%m-%d %H:%M:%S")
    return (
        "<b>╔═━IVASMS NEW RANGE━━═╗</b>\n"
        f"<pre>{flag} RANE: {html.escape(range_name)}</pre>\n"
        f"<pre>Time     ➜ {recv_time}</pre>\n"
        "<pre>Source      ➜ TELEGRAM</pre>\n"
        f"<pre>Test NO. ➜ {html.escape(test_number)}</pre>\n"
        "<pre>DEV.     ➜ @professor_cry</pre>\n"
        "<b>╚═━━━━ ◢◤◆◥◣ ━━━━═╝</b>"
    )

# ----------------------------------------------------------------------
# Manual login (once) → keep driver alive
# ----------------------------------------------------------------------
def init_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # keep headless **OFF** – you need to see the page for login
    # opts.add_argument("--headless=new")

    service = Service(executable_path="chromedriver")   # same folder or in PATH
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

# ----------------------------------------------------------------------
# Extract rows from current page source
# ----------------------------------------------------------------------
def extract_new_ranges(html_content: str):
    """
    Example row in the page:
        <td>US - New York</td> ... <td>+1234567890</td>
    The regex is tolerant to extra spaces / HTML tags.
    """
    pattern = r'>([A-Z]{2})\s*-\s*([^<]+?)\s*<[^>]*>\s*(\+\d{6,15})'
    matches = re.findall(pattern, html_content, re.DOTALL)

    new_entries = []
    for cc, rng, test in matches:
        rng = rng.strip()
        test = test.strip()
        key = f"{cc}-{rng}-{test}"
        if key not in posted_keys:
            posted_keys.add(key)
            new_entries.append((cc, rng, test))
    return new_entries

# ----------------------------------------------------------------------
# Main loop – refresh every 10 seconds
# ----------------------------------------------------------------------
async def monitor_with_refresh():
    bot = Bot(token=BOT_TOKEN)
    driver = init_driver()

    # ---------- 1. Manual login ----------
    driver.get(LOGIN_URL)
    logging.info("Browser opened – please log in manually.")
    logging.info(f"Waiting up to {LOGIN_TIMEOUT}s for portal redirect…")

    start = time.time()
    while time.time() - start < LOGIN_TIMEOUT:
        if driver.current_url.startswith(PORTAL_URL):
            logging.info("Login successful!")
            break
        await asyncio.sleep(2)
    else:
        logging.error("Login timeout – exiting.")
        driver.quit()
        return

    # ---------- 2. Open monitor page ----------
    driver.get(MONITOR_URL)
    logging.info("Monitor page loaded – starting 10-second refresh loop…")

    # ---------- 3. Infinite refresh + parse ----------
    while True:
        try:
            # Refresh page
            driver.refresh()
            await asyncio.sleep(1)          # give JS a moment to render

            html_content = driver.page_source
            new_ranges = extract_new_ranges(html_content)

            for cc, rng, test in new_ranges:
                flag = flag_emoji(cc)
                msg = build_message(flag, rng, test)
                await bot.send_message(
                    chat_id=GROUP_ID,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                logging.info(f"Posted: {cc} – {rng} – {test}")

        except Exception as e:
            logging.error(f"Error in loop: {e}")

        # Exact 10-second cycle
        await asyncio.sleep(10)

    # (never reached)
    driver.quit()
    await bot.session.close()

# ----------------------------------------------------------------------
# Entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(monitor_with_refresh())
