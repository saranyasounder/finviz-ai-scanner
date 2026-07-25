from playwright.sync_api import sync_playwright

print("Starting")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.google.com")
    print(page.title())
    input("Press Enter...")
    browser.close()

print("Done")