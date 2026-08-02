from pathlib import Path

from playwright.sync_api import sync_playwright


page_path = Path(__file__).resolve().parents[1] / "web" / "index.html"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(page_path.as_uri())
    page.wait_for_load_state("networkidle")

    assert page.title() == "工程协同 Agent Relay"
    assert page.get_by_role("heading", name="工程协同 Agent Relay").is_visible()
    assert page.get_by_text("SC 管壁厚专项核查").is_visible()
    assert page.get_by_text("Mock nodes / anonymized demo data").is_visible()
    page.screenshot(path="/tmp/agent-relay-start-page.png", full_page=True)
    browser.close()
