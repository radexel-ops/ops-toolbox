"""
WEHAGO Service

Selenium-based automation service for Douzone WEHAGO platform.
Handles login, navigation, and data extraction.
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WehagoConfig:
    """WEHAGO configuration."""
    username: str
    password: str
    company_code: str = ""
    download_dir: str = "./downloads"
    headless: bool = True
    timeout: int = 30


@dataclass
class VacationRecord:
    """Vacation record data."""
    employee_name: str
    employee_id: str
    vacation_type: str
    start_date: datetime
    end_date: datetime
    days: float
    status: str
    note: str = ""


class WehagoService:
    """
    Service for interacting with WEHAGO platform.

    Features:
    - Automated login
    - Vacation data export
    - Document scraping
    - Transaction history export
    """

    # CSS Selectors (WEHAGO specific)
    CSS_LOGIN_BTN = '#contnt > div.content_box.login_process > div > button'
    CSS_ID_INPUT = '#inputId'
    CSS_PW_INPUT = '#inputPw'
    CSS_SUBMIT_BTN = '#lgnBtn'
    CSS_TAB_DAYOFF = (
        "#BODY_CLASS > div > div.container > div > div > div > div.content_bx > "
        "div > div > div > div > div > div.am_admin_content > div > div.right_section > "
        "div > div > div.LUX_basic_tabs.table_tabs > div > ul > li:nth-child(2) > a > span"
    )

    # URLs
    LOGIN_URL = "https://www.wehago.com/#/login"
    VACATION_URL = "https://hr.wehago.com/#/attendance"
    SERVICE_URL = "https://www.wehago.com/#/eapprovals/menu/servicemanagement"

    def __init__(self, config: Optional[WehagoConfig] = None):
        """
        Initialize WEHAGO service.

        Args:
            config: Configuration object. If None, loads from environment.
        """
        self.config = config or self._load_config_from_env()
        self.driver = None
        self._logged_in = False

    def _load_config_from_env(self) -> WehagoConfig:
        """Load configuration from environment variables."""
        return WehagoConfig(
            username=os.environ.get("WEHAGO_ID", ""),
            password=os.environ.get("WEHAGO_PW", ""),
            company_code=os.environ.get("WEHAGO_COMPANY_CODE", ""),
            download_dir=os.environ.get("WEHAGO_DOWNLOAD_DIR", "./downloads"),
            headless=os.environ.get("WEHAGO_HEADLESS", "true").lower() == "true",
            timeout=int(os.environ.get("WEHAGO_TIMEOUT", "30"))
        )

    def _setup_driver(self):
        """Setup Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()

            if self.config.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

            # Download settings
            download_path = Path(self.config.download_dir).absolute()
            download_path.mkdir(parents=True, exist_ok=True)

            prefs = {
                "download.default_directory": str(download_path),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(self.config.timeout)

            logger.info("WebDriver initialized successfully")

        except ImportError as e:
            logger.error(f"Selenium not installed: {e}")
            raise RuntimeError("Selenium is required. Install with: pip install selenium webdriver-manager")
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {e}")
            raise

    def _ensure_driver(self):
        """Ensure WebDriver is initialized."""
        if self.driver is None:
            self._setup_driver()

    async def login(self) -> bool:
        """
        Login to WEHAGO.

        Returns:
            True if login successful
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        self._ensure_driver()

        try:
            logger.info("Navigating to WEHAGO login page...")
            self.driver.get(self.LOGIN_URL)

            # Wait for login button and click
            wait = WebDriverWait(self.driver, self.config.timeout)
            login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, self.CSS_LOGIN_BTN)))
            login_btn.click()

            # Enter credentials
            id_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.CSS_ID_INPUT)))
            id_input.clear()
            id_input.send_keys(self.config.username)

            pw_input = self.driver.find_element(By.CSS_SELECTOR, self.CSS_PW_INPUT)
            pw_input.clear()
            pw_input.send_keys(self.config.password)

            # Submit
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, self.CSS_SUBMIT_BTN)
            submit_btn.click()

            # Wait for login to complete (check for profile element or URL change)
            time.sleep(3)

            # Verify login
            if "login" not in self.driver.current_url.lower():
                self._logged_in = True
                logger.info("WEHAGO login successful")
                return True
            else:
                logger.error("WEHAGO login failed - still on login page")
                return False

        except Exception as e:
            logger.error(f"WEHAGO login error: {e}")
            return False

    async def export_vacation_data(
        self,
        months: int = 1,
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Export vacation data to Excel files.

        Args:
            months: Number of months to export (default: 1)
            output_dir: Output directory for Excel files

        Returns:
            List of downloaded file paths
        """
        if not self._logged_in:
            if not await self.login():
                raise RuntimeError("Failed to login to WEHAGO")

        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        output_path = Path(output_dir or self.config.download_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        downloaded_files = []

        try:
            # Navigate to vacation page
            self.driver.get(self.VACATION_URL)
            time.sleep(3)

            wait = WebDriverWait(self.driver, self.config.timeout)

            # Click dayoff tab
            dayoff_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, self.CSS_TAB_DAYOFF)))
            dayoff_tab.click()
            time.sleep(2)

            # Export for each month
            for i in range(months):
                # Navigate to target month (implementation depends on UI)
                # This is a simplified version
                logger.info(f"Exporting vacation data for month -{i}")

                # Click export button (CSS selector varies)
                # export_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_BTN_EXCEL)))
                # export_btn.click()

                # Wait for download
                time.sleep(5)

                # Check for downloaded files
                # (Implementation depends on specific file naming)

            logger.info(f"Downloaded {len(downloaded_files)} vacation files")
            return downloaded_files

        except Exception as e:
            logger.error(f"Error exporting vacation data: {e}")
            raise

    async def get_vacation_summary(self) -> Dict[str, Any]:
        """
        Get vacation summary for current period.

        Returns:
            Summary dict with counts and statistics
        """
        # This would parse the vacation data and return summary
        return {
            "period": datetime.now().strftime("%Y-%m"),
            "total_employees": 0,
            "on_vacation_today": [],
            "upcoming_vacations": [],
            "statistics": {}
        }

    def close(self):
        """Close WebDriver and cleanup."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
                self._logged_in = False

    def __del__(self):
        """Cleanup on destruction."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.close()


# Utility functions
def wait_for_download(
    download_dir: str,
    timeout: int = 60,
    check_interval: float = 0.5
) -> Optional[str]:
    """
    Wait for a file download to complete.

    Args:
        download_dir: Directory to watch
        timeout: Maximum wait time in seconds
        check_interval: Check interval in seconds

    Returns:
        Path to downloaded file, or None if timeout
    """
    download_path = Path(download_dir)
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check for .crdownload files (Chrome temp files)
        temp_files = list(download_path.glob("*.crdownload"))
        if not temp_files:
            # No temp files, check for new files
            files = sorted(download_path.glob("*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                return str(files[0])

        time.sleep(check_interval)

    return None
