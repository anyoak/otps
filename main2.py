import time
import config  # Make sure config.LOGIN_URL exists
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from forwarder import extract_sms  # Your custom module

def wait_for_main_page(driver, timeout=300):
    """
    Wait until the current URL becomes https://beta.full-sms.com
    """
    print(f"[*] Waiting up to {timeout} seconds for main page...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            current_url = driver.current_url
            if current_url == "https://beta.full-sms.com" or current_url == "https://beta.full-sms.com/":
                print("[✅] Main page detected!")
                return True
        except Exception as e:
            print(f"[⚠️] URL check failed: {e}")
    print("[❌] Main page not detected within timeout!")
    return False

def launch_browser():
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # chrome_options.add_argument("--headless=new")  # Optional

    service = Service()  # Add executable_path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def main():
    driver = launch_browser()
    driver.get(config.LOGIN_URL)  # Open login page

    # Wait for main page after login
    if not wait_for_main_page(driver, timeout=300):
        driver.quit()
        return

    # Open SMS page
    driver.get("https://beta.full-sms.com/stats")
    print("[*] SMS page opened. Starting monitoring...")

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
