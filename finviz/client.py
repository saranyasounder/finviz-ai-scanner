from loguru import logger

from config.settings import FINVIZ_URL
from finviz.downloader import download


class FinvizClient:

    def __init__(self, page):
        self.page = page

    def connect(self):
        """
        Open Finviz.
        If we're already on a screener page, simply refresh it.
        """

        logger.info("Connecting to Finviz...")

        if "finviz.com/screener" in self.page.url.lower():

            logger.info("Already on screener page.")

            self.page.reload(wait_until="domcontentloaded")

        else:

            self.page.goto(FINVIZ_URL)

            self.page.wait_for_load_state("domcontentloaded")

        self.page.get_by_text(
            "Export",
            exact=True
        ).wait_for()

        logger.success("Finviz ready.")

    def export_csv(self):

        logger.info("Exporting CSV...")

        return download(self.page)