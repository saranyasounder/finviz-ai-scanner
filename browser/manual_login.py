"""One-time interactive helper: log into Finviz Elite so the persistent browser profile is authenticated.

Run directly: python -m browser.manual_login
"""

from __future__ import annotations

from browser.browser import Browser
from config.settings import load_settings


def main() -> None:
    settings = load_settings()
    browser = Browser(
        profile_dir=settings.browser.profile_dir,
        headless=False,
    )

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
