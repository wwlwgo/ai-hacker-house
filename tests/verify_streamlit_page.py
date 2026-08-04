from playwright.sync_api import expect, sync_playwright

URL = "http://127.0.0.1:8501/"
STEPS = ["发布总监指令", "接收双专业初判", "记录专业质疑", "总监人工纠偏", "执行跨专业核对", "接收核对回复", "补充证据", "记录总监裁决", "总监批准并生成报告"]


STATUS = {"NEW": "新建事项", "HUMAN_CONFIRMATION": "等待总监裁决或批准", "REPORT_DRAFTED": "报告草稿已生成"}


def status(page, value):
    expect(page.get_by_text(STATUS[value], exact=True)).to_be_visible(timeout=40_000)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(URL); page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="工程协同 Agent Relay")).to_be_visible()
    status(page, "NEW")
    for name in STEPS[1:]: assert not page.get_by_role("button", name=name).is_enabled()
    page.screenshot(path="/tmp/agent-relay-initial.png", full_page=True)
    for name in STEPS[:-1]:
        page.get_by_role("button", name=name).click()
    status(page, "HUMAN_CONFIRMATION")
    expect(page.get_by_role("button", name="总监批准并生成报告")).to_be_enabled(timeout=15_000)
    expect(page.get_by_text("结论裁决台账", exact=True)).to_be_visible(timeout=15_000)
    expect(page.get_by_text("待总监批准结论包", exact=True)).to_be_visible()
    expect(page.get_by_text("已批准结论包 · Report Agent 的唯一输入", exact=True)).not_to_be_visible()
    page.screenshot(path="/tmp/agent-relay-decision.png", full_page=True)
    page.get_by_role("button", name="总监批准并生成报告").click()
    status(page, "REPORT_DRAFTED")
    expect(page.get_by_text("已批准结论包 · Report Agent 的唯一输入", exact=True)).to_be_visible()
    expect(page.get_by_text("报告来源：", exact=False).first).to_be_visible()
    expect(page.get_by_text("DeltaGenerator", exact=False)).not_to_be_visible()
    expect(page.get_by_text('st.success("报告来源：', exact=False)).not_to_be_visible()
    page.screenshot(path="/tmp/agent-relay-approved.png", full_page=True)
    page.get_by_role("button", name="重置案例", exact=True).first.click()
    status(page, "NEW")
    expect(page.get_by_text("结论裁决台账", exact=True)).not_to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844}); page.reload(); page.wait_for_load_state("networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    page.screenshot(path="/tmp/agent-relay-dashboard-mobile.png", full_page=True)
    browser.close()
