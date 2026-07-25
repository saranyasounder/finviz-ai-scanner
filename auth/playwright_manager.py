from pathlib import Path

from playwright.sync_api import sync_playwright


PROFILE_DIR = Path("chrome_profile")


class Browser:
    def __init__(self):
        self.playwright = sync_playwright().start()

    def start(self):
        return self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            accept_downloads=True,
        )

    def stop(self):
        self.playwright.stop()