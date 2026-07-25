from auth.playwright_manager import Browser
from finviz.downloader import download
from finviz.screener import FinvizScreener


def main():
    browser = Browser()

    context = browser.start()

    page = context.new_page()

    screener = FinvizScreener(page)

    screener.open()

    csv_file = download(page)

    print(f"\nCSV downloaded successfully:\n{csv_file}")

    context.close()
    browser.stop()


if __name__ == "__main__":
    main()