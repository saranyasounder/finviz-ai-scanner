from loguru import logger
from dotenv import load_dotenv
import os

load_dotenv()


class FinvizScreener:
    def __init__(self, page):
        self.page = page
        self.screener_url = os.getenv("FINVIZ_SCREENER_URL")

        if not self.screener_url:
            raise ValueError(
                "FINVIZ_SCREENER_URL is not set in the .env file."
            )

    def open(self):
        logger.info("Opening Finviz Elite Screener...")
        logger.debug(f"Navigating to: {self.screener_url}")

        self.page.goto(self.screener_url)
        self.page.wait_for_load_state("networkidle")

        logger.success("Finviz Elite Screener loaded successfully.")