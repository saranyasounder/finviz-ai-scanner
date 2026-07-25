from auth.playwright_manager import Browser

def main():
    browser = Browser()

    context = browser.start()

    page = context.new_page()

    page.goto("https://elite.finviz.com")

    input(
        "\nLog into Finviz Elite.\n"
        "Once you see your dashboard, press ENTER..."
    )

    context.close()
    browser.stop()


if __name__ == "__main__":
    main()