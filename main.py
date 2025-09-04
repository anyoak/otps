import time, json, os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from forwarder import extract_sms
import config

COOKIES_FILE = "cookies.json"

def wait_for_login(driver, timeout=180):
    print("[*] Waiting for manual login...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            if "Logout" in driver.page_source or "logout" in driver.page_source:
                print("[✅] Login successful!")
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

    # Unique user-data-dir to avoid SessionNotCreatedException
    user_data_dir = f"/tmp/selenium_{int(time.time())}"
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    if headless:
        chrome_options.add_argument("--headless=new")  # Headless mode

    service = Service()  # Specify executable_path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(config.LOGIN_URL)

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
    headless_mode = False  # True করলে GUI না খুলে headless run হবে
    driver = launch_browser(headless=headless_mode)

    # Check login if cookies not valid
    if "Logout" not in driver.page_source and "logout" not in driver.page_source:
        if not wait_for_login(driver):
            driver.quit()
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
    try:
        while True:
            try:
                extract_sms(driver)
                time.sleep(5)
            except Exception as e:
                print(f"[ERR] Failed to extract SMS: {e}")
                time.sleep(5)
    finally:
        driver.quit()
        print("[*] Browser closed.")

if __name__ == "__main__":
    main()
