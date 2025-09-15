import time
import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from forwarder import extract_sms

def wait_for_login(driver, timeout=180):
    print("[*] Waiting for manual login...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            if "Logout" in driver.page_source or "logout" in driver.page_source:
                print("[✅] Login successful!")
                return True
        except Exception as e:
            print(f"[⚠️] Page check failed: {e}")
    print("[❌] Login timeout!")
    return False

def launch_browser():
    print("[*] Launching headless Chrome browser...")

    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Uncomment below line to run in headless mode
    # chrome_options.add_argument("--headless=new")

    service = Service()  # You can specify executable_path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def main():
    driver = launch_browser()
    driver.get(config2.LOGIN_URL)

    if not wait_for_login(driver):
        driver.quit()
        return

    print("[*] Login done. Starting OTP monitoring...")
    try:
        while True:
            try:
                extract_sms(driver)
                time.sleep(2)
            except Exception as e:
                print(f"[ERR] Failed to extract SMS: {e}")
                time.sleep(5)
    finally:
        print("[*] Closing browser.")
        driver.quit()

if __name__ == "__main__":
    main()
