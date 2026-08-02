"""Black-box acceptance checks for the live Streamlit demo."""

from playwright.sync_api import expect, sync_playwright


URL = "http://127.0.0.1:8501/"


def expect_status(page, value):
    expect(page.get_by_text(value, exact=True)).to_be_visible(timeout=15_000)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("sc-pipe-001", exact=True)).to_be_visible()
    expect(page.get_by_text("Mock nodes / anonymized demo data", exact=False)).to_be_visible()
    expect_status(page, "NEW")
    assert page.get_by_role("button", name="运行 Round 1").is_enabled()
    assert not page.get_by_role("button", name="人工纠偏").is_enabled()
    assert not page.get_by_role("button", name="运行 Round 2").is_enabled()
    assert not page.get_by_role("button", name="总监批准并生成报告").is_enabled()
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).not_to_be_visible()

    page.get_by_role("button", name="运行 Round 1").click()
    expect_status(page, "AWAITING_HUMAN_CORRECTION")
    assert page.get_by_role("button", name="人工纠偏").is_enabled()
    assert not page.get_by_role("button", name="运行 Round 2").is_enabled()

    page.get_by_role("button", name="人工纠偏").click()
    expect_status(page, "CLARIFICATION_REQUIRED")
    expect(page.get_by_text("人工介入", exact=False)).to_be_visible()
    assert page.get_by_role("button", name="运行 Round 2").is_enabled()

    page.get_by_role("button", name="运行 Round 2").click()
    expect_status(page, "HUMAN_CONFIRMATION")
    expect(page.get_by_text("拟定结论", exact=True)).to_be_visible()
    expect(page.get_by_text("结论仍待总监 Human Adapter 批准", exact=False)).to_be_visible()
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).not_to_be_visible()
    assert page.get_by_role("button", name="总监批准并生成报告").is_enabled()

    page.get_by_role("button", name="总监批准并生成报告").click()
    expect_status(page, "REPORT_DRAFTED")
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).to_be_visible()
    expect(page.get_by_text("报告来源：", exact=False)).to_be_visible()
    expect(page.get_by_text("sc-pipe-001", exact=False).last).to_be_visible()
    page.screenshot(path="/tmp/agent-relay-acceptance.png", full_page=True)

    page.get_by_role("button", name="重置案例").click()
    expect_status(page, "NEW")
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).not_to_be_visible()
    browser.close()
