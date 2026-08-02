"""Run the five-step Streamlit demo three times in isolated browser sessions."""

from playwright.sync_api import expect, sync_playwright


URL = "http://127.0.0.1:8501/"


def expect_status(page, status):
    expect(page.get_by_text(status, exact=True)).to_be_visible(timeout=15_000)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for rehearsal in range(1, 4):
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")

        expect_status(page, "NEW")
        page.get_by_role("button", name="运行 Round 1").click()
        expect_status(page, "AWAITING_HUMAN_CORRECTION")
        page.get_by_role("button", name="人工纠偏").click()
        expect_status(page, "CLARIFICATION_REQUIRED")
        page.get_by_role("button", name="运行 Round 2").click()
        expect_status(page, "HUMAN_CONFIRMATION")
        page.get_by_role("button", name="总监批准并生成报告").click()
        expect_status(page, "REPORT_DRAFTED")
        expect(page.get_by_text("已确认事实", exact=True)).to_be_visible()
        expect(page.get_by_text("证据引用", exact=True)).to_be_visible()
        page.get_by_role("button", name="重新演示").click()
        expect_status(page, "NEW")
        print("Rehearsal {0}: passed".format(rehearsal))
        context.close()
    browser.close()
