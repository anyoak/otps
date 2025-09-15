import time
import config  # Make sure config.LOGIN_URL exists
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from forwarder import extract_sms  # Your custom module

def wait_for_login(driver, timeout=300):
    """
    Wait for manual login. Checks every 2 seconds.
    """
    print("[*] Waiting for manual login...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        try:
            # Check for logout button or unique SMS page element
            if "Logout" in driver.page_source or "logout" in driver.page_source:
                print("[✅] Login detected!")
                return True
        except Exception as e:
            print(f"[⚠️] Page check failed: {e}")
    print("[❌] Login timeout!")
    return False

def launch_browser():
    """
    Launch Chrome with options to reduce logging noise.
    """
    print("[*] Launching Chrome browser...")

    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # Uncomment to run headless
    # chrome_options.add_argument("--headless=new")

    service = Service()  # Add executable_path="path/to/chromedriver" if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def main():
    driver = launch_browser()
    driver.get(config.LOGIN_URL)  # Open login page

    # Wait for manual login
    if not wait_for_login(driver):
        driver.quit()
        return

    # Go to SMS stats page
    driver.get("https://beta.full-sms.com/stats")
    print("[*] Navigated to SMS stats page. Starting monitoring...")

    try:
        while True:
            try:
                # Your custom function to extract SMS
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
