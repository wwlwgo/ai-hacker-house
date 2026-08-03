from playwright.sync_api import expect, sync_playwright

URL = "http://127.0.0.1:8501/"
STEPS = ["发布总监指令", "接收双专业初判", "记录专业质疑", "总监人工纠偏", "执行跨专业核对", "接收核对回复", "补充证据", "记录总监裁决"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True); page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL); page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Mock 专业节点", exact=False)).to_be_visible()
    expect(page.get_by_text("Markdown 报告草稿", exact=True)).not_to_be_visible()
    for name in STEPS: page.get_by_role("button", name=name).click()
    expect(page.get_by_role("button", name="总监批准并生成报告")).to_be_enabled(timeout=15_000)
    expect(page.get_by_text("待总监批准结论包", exact=True)).to_be_visible(timeout=15_000)
    expect(page.get_by_text("已批准结论包 · Report Agent 的唯一输入", exact=True)).not_to_be_visible()
    expect(page.get_by_text("结论裁决台账", exact=True)).to_be_visible()
    page.get_by_role("button", name="总监批准并生成报告").click()
    expect(page.get_by_text("已批准结论包 · Report Agent 的唯一输入", exact=True)).to_be_visible(timeout=40_000)
    expect(page.get_by_text("报告来源：", exact=False).first).to_be_visible()
    page.screenshot(path="/tmp/agent-relay-acceptance.png", full_page=True)
    browser.close()
