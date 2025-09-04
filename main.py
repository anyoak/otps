import time
import json
import os
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from forwarder import extract_sms
import config

COOKIES_FILE = "cookies.json"

def wait_for_login(driver, timeout=180):
    print("[*] Waiting for manual login...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            # Check for "Logout" or a specific element (e.g., user profile)
            if "Logout" in driver.page_source or "logout" in driver.page_source:
                print("[✅] Login successful (detected 'Logout')!")
                return True
            # Alternative: Check for a specific element (adjust selector as needed)
            WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            if driver.current_url != config.LOGIN_URL:
                print("[✅] Login successful (URL changed)!")
                return True
        except:
            continue
    print("[❌] Login timeout!")
    return False

def launch_browser(headless=False):
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")

    # Unique user-data-dir
    user_data_dir = f"/tmp/selenium_{uuid.uuid4().hex}"
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    try:
        os.makedirs(user_data_dir, exist_ok=True)
        print(f"[*] Created user-data-dir: {user_data_dir}")
    except Exception as e:
        print(f"[⚠️] Failed to create user-data-dir: {e}")
        raise

    if headless:
        chrome_options.add_argument("--headless=new")

    service = Service()  # Replace with Service(executable_path="/path/to/chromedriver") if needed
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"[⚠️] Failed to initialize WebDriver: {e}")
        raise

    # Retry loading login page
    for attempt in range(3):
        try:
            driver.get(config.LOGIN_URL)
            print(f"[*] Navigated to login page: {config.LOGIN_URL}")
            break
        except Exception as e:
            print(f"[⚠️] Failed to load login page (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                raise Exception("Failed to load login page after 3 attempts")

    # Load cookies if available
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                driver.add_cookie(cookie)
            driver.refresh()
            print("[✅] Cookies loaded, auto-login attempt done!")
        except Exception as e:
            print(f"[⚠️] Failed to load cookies: {e}")

    return driver

def main():
    headless_mode = False  # Set to True for headless mode
    driver = None
    try:
        driver = launch_browser(headless=headless_mode)

        # Check login if cookies not valid
        if "Logout" not in driver.page_source and "logout" not in driver.page_source:
            if not wait_for_login(driver):
                return
            # Save cookies after manual login
            try:
                with open(COOKIES_FILE, "w") as f:
                    json.dump(driver.get_cookies(), f)
                print("[✅] Cookies saved for future auto-login.")
            except Exception as e:
                print(f"[⚠️] Failed to save cookies: {e}")
        else:
            print("[*] Logged in via cookies.")

        print("[*] Starting OTP monitoring...")
        while True:
            try:
                extract_sms(driver)
                time.sleep(5)
            except Exception as e:
                print(f"[ERR] Failed to extract SMS: {e}")
                time.sleep(5)
    except Exception as e:
        print(f"[⚠️] Fatal error in main: {e}")
    finally:
        if driver:
            driver.quit()
            print("[*] Browser closed.")

if __name__ == "__main__":
    main()
