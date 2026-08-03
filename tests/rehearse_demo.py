from playwright.sync_api import expect, sync_playwright

URL = "http://127.0.0.1:8501/"
STEPS = ["发布总监指令", "接收双专业初判", "记录专业质疑", "总监人工纠偏", "执行跨专业核对", "接收核对回复", "补充证据", "记录总监裁决", "总监批准并生成报告"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for rehearsal in range(1, 4):
        context = browser.new_context(viewport={"width": 1440, "height": 900}); page = context.new_page()
        page.goto(URL); page.wait_for_load_state("networkidle")
        for name in STEPS[:-1]: page.get_by_role("button", name=name).click()
        expect(page.get_by_role("button", name="总监批准并生成报告")).to_be_enabled(timeout=15_000)
        page.get_by_role("button", name=STEPS[-1]).click()
        expect(page.get_by_text("报告草稿已生成", exact=True)).to_be_visible(timeout=40_000)
        expect(page.get_by_text("报告来源：", exact=False).first).to_be_visible()
        page.get_by_role("button", name="重新演示").click()
        expect(page.get_by_text("新建事项", exact=True)).to_be_visible(timeout=15_000)
        print("Rehearsal {0}: passed".format(rehearsal)); context.close()
    browser.close()
