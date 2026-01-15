import json
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

CHECKPOINT_FILE = "checkpoint.json"

class LeadAutomation:
    def __init__(self, url, logger_callback, headless=True):
        self.url = url
        self.log = logger_callback
        self.headless = headless
        self.driver = None
        self.wait = None
        self.max_retries = 10  # Hardened to 10 attempts

    def init_driver(self):
        options = Options()

        if self.headless:
            options.add_argument("--headless=new")  # ✅ cloud-safe

        # ✅ REQUIRED FOR STREAMLIT CLOUD / LINUX
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Reduce noise
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        self.wait = WebDriverWait(self.driver, 15)

    def save_checkpoint(self, index, success_count, fail_count):
        data = {
            "last_index": index,
            "success_count": success_count,
            "fail_count": fail_count
        }
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(data, f)

    def load_checkpoint(self):
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"last_index": 0, "success_count": 0, "fail_count": 0}

    def process_email(self, email):
        retry_count = 0

        while retry_count < self.max_retries:
            try:
                self.driver.get(self.url)

                # Email input
                email_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "Email"))
                )
                email_input.clear()
                email_input.send_keys(email)

                # Register
                self.driver.find_element(By.ID, "registerBtn").click()

                # Success verification (GIBS flow)
                click_here = self.wait.until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "Click here"))
                )
                click_here.click()

                self.wait.until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "//div[contains(@class,'modal-content')]")
                    )
                )

                return True

            except Exception:
                retry_count += 1
                self.log(
                    f"Connection hiccup for {email}. Attempt {retry_count}/10...",
                    "warning"
                )
                time.sleep(3)

        return False

    def quit(self):
        if self.driver:
            self.driver.quit()