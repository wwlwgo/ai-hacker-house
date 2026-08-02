from playwright.sync_api import expect, sync_playwright


URL = "http://127.0.0.1:8501/"


def wait_for_status(page, status):
    expect(page.get_by_text(status, exact=True)).to_be_visible(timeout=15_000)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="工程协同 Agent Relay")).to_be_visible()
    expect(page.get_by_text("sc-pipe-001", exact=True)).to_be_visible()
    wait_for_status(page, "NEW")
    expect(page.get_by_text("Mock nodes / anonymized demo data", exact=False)).to_be_visible()
    page.screenshot(path="/tmp/agent-relay-initial.png", full_page=True)

    page.get_by_role("button", name="运行 Round 1", exact=True).click()
    wait_for_status(page, "AWAITING_HUMAN_CORRECTION")
    expect(page.get_by_text("初步证据已提交", exact=False).first).to_be_visible()

    page.get_by_role("button", name="人工纠偏", exact=True).click()
    wait_for_status(page, "CLARIFICATION_REQUIRED")
    expect(page.get_by_text("人工介入", exact=False)).to_be_visible()
    page.screenshot(path="/tmp/agent-relay-correction.png", full_page=True)

    page.get_by_role("button", name="运行 Round 2", exact=True).click()
    wait_for_status(page, "HUMAN_CONFIRMATION")
    expect(page.get_by_text("拟定结论", exact=True)).to_be_visible()
    expect(page.get_by_text("待人工确认", exact=False).first).to_be_visible()

    page.get_by_role("button", name="总监批准并生成报告", exact=True).click()
    wait_for_status(page, "REPORT_DRAFTED")
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).to_be_visible()
    expect(page.get_by_text("报告来源：", exact=False)).to_be_visible()
    expect(page.get_by_text("sc-pipe-001", exact=False).last).to_be_visible()
    page.screenshot(path="/tmp/agent-relay-approved.png", full_page=True)

    page.get_by_role("button", name="重置案例", exact=True).click()
    wait_for_status(page, "NEW")
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).not_to_be_visible()

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="工程协同 Agent Relay")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.screenshot(path="/tmp/agent-relay-dashboard-mobile.png", full_page=True)
    browser.close()
