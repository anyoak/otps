import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from forwarder import extract_sms
import config
import json

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

def launch_browser():
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument("--headless=new")  # Headless mode if you want

    service = Service()  # executable_path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Load cookies if exists
    try:
        driver.get(config.LOGIN_URL)
        with open("cookies.json", "r") as f:
            cookies = json.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.refresh()
        print("[✅] Cookies loaded, auto-login success!")
    except:
        print("[⚠️] No cookies found, manual login required.")

    return driver

def main():
    driver = launch_browser()
    driver.get(config.LOGIN_URL)

    if not wait_for_login(driver):
        driver.quit()
        return

    print("[*] Login done. Starting OTP monitoring...")
    try:
        while True:
            extract_sms(driver)
            time.sleep(5)
    finally:
        driver.quit()
        print("[*] Browser closed.")

if __name__ == "__main__":
    main()
