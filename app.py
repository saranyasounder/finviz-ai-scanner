from auth.playwright_manager import Browser

from finviz.downloader import download
from finviz.screener import FinvizScreener
from finviz.loader import FinvizLoader
from finviz.validator import FinvizValidator
from finviz.cleaner import FinvizCleaner


def main():

    browser = Browser()

    context = browser.start()

    page = context.new_page()

    screener = FinvizScreener(page)

    screener.open()

    csv_file = download(page)

    context.close()

    browser.stop()

    loader = FinvizLoader(csv_file)

    df = loader.load()

    FinvizValidator.validate(df)

    df = FinvizCleaner.clean(df)

    print(df.head())


if __name__ == "__main__":
    main()