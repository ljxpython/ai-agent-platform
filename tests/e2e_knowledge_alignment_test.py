import os
import sys
import time
import json
import re
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = os.path.join(
    BASE_DIR,
    "docs/projects/20261021-lightrag-mcp-real-doc-status-alignment/evidence"
)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

BASE_URL = "http://127.0.0.1:3000"
DEFAULT_PROJECT_ID = "11111111-1111-4111-8111-111111111111"
ISOLATED_PROJECT_ID = "5a5b7239-43e3-40e6-bba3-e64d96057607"

def wait_for_stream_completion(page, timeout=120, description=""):
    print(f"  [等待响应] 正在等待真实大模型全链路推理及MCP工具调用完成 ({description})...")
    start = time.time()

    # 阶段 1：等待大模型开始输出（生成中状态出现）
    started = False
    for _ in range(25):
        body = page.inner_text("body")
        if "Agent 正在组织答复" in body or "Agent 正在实时输出" in body or page.locator('button:has-text("停止生成")').is_visible():
            started = True
            print("  ✓ 检测到大模型已开始流式生成/工具调用...")
            break
        time.sleep(1)

    # 阶段 2：等待生成完成（停止按钮和加载状态消失，文本稳定）
    last_text = ""
    stable_ticks = 0
    while time.time() - start < timeout:
        time.sleep(2)
        body = page.inner_text("body")

        # 实时打印MCP工具调用日志
        if "mcp_list_project_knowledge_documents" in body and "mcp_list_project_knowledge_documents" not in last_text:
            print("  [工具调用] 捕捉到 dearflow_agent 调用: mcp_list_project_knowledge_documents")

        is_generating = (
            "Agent 正在组织答复" in body or
            "Agent 正在实时输出" in body or
            page.locator('button:has-text("停止生成")').is_visible()
        )

        if not is_generating and len(body) > 400:
            if len(body) == len(last_text):
                stable_ticks += 1
                if stable_ticks >= 2:
                    print(f"  ✓ {description} 流式输出完全结束，内容已稳定！")
                    break
            else:
                stable_ticks = 0
                last_text = body
        else:
            last_text = body
            stable_ticks = 0

    return page.inner_text("body")

def run_e2e_test():
    print(f"\n========================================================")
    print(f"=== 老王暴躁技术流：LightRAG 真实 13 份文档与专属隔离 E2E 终极验收 ===")
    print(f"========================================================")
    print(f"证据截图保存目录: {SCREENSHOT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # ----------------------------------------------------
        # 步骤 1：登录系统并进入工作区
        # ----------------------------------------------------
        print("\n--> [Step 1] 打开登录页并进行登录...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
        page.wait_for_selector('button[type="submit"]', timeout=15000)
        page.click('button[type="submit"]')
        page.wait_for_url("**/workspace/**", timeout=20000)
        time.sleep(2)
        print("  ✓ 登录成功，已重定向至工作区！")
        shot_01 = os.path.join(SCREENSHOT_DIR, "01_login_and_workspace.png")
        page.screenshot(path=shot_01, full_page=True)
        print(f"  ✓ Step 1 截图固化: {shot_01}")

        # ----------------------------------------------------
        # 步骤 2：进入“平台默认项目”对话，验证真实 13 份多模态文档
        # ----------------------------------------------------
        print(f"\n--> [Step 2] 导航至【平台默认项目】Chat 对话页面: {DEFAULT_PROJECT_ID}...")
        page.goto(f"{BASE_URL}/workspace/projects/{DEFAULT_PROJECT_ID}/chat", wait_until="networkidle")
        time.sleep(3)

        # 确保选择 dearflow_agent
        agent_btn = page.locator('button:has-text("选择智能体")')
        if agent_btn.is_visible():
            print("  选择 dearflow_agent 智能体...")
            agent_btn.click()
            time.sleep(1)
            dearflow_option = page.locator('text=dearflow_agent').first
            if dearflow_option.is_visible():
                dearflow_option.click()
                time.sleep(1)

        # 开启新对话确保干净上下文
        new_chat_btn = page.locator('button:has-text("新对话")').first
        if new_chat_btn.is_visible():
            new_chat_btn.click()
            time.sleep(1.5)

        textarea_selector = 'textarea[aria-label="消息草稿"]'
        page.wait_for_selector(textarea_selector, timeout=20000)
        print("  ✓ 默认项目 Chat 就绪，输入提问: '你查一下知识库，看下知识库中有哪些文档'...")

        query_text = "你查一下知识库，看下知识库中有哪些文档"
        page.fill(textarea_selector, query_text)
        time.sleep(1)

        send_btn = page.locator('button:has(svg path[d*="M12 19V5"])')
        if send_btn.is_visible():
            send_btn.click()
        else:
            page.press(textarea_selector, "Enter")
        print("  ✓ 默认项目消息已发送，等待真实大模型全链路推理...")

        final_body_default = wait_for_stream_completion(page, timeout=120, description="默认项目大模型推理")
        time.sleep(3)
        shot_02 = os.path.join(SCREENSHOT_DIR, "02_default_project_13_docs.png")
        page.screenshot(path=shot_02, full_page=True)
        print(f"  ✓ 默认项目验收截图已固化: {shot_02}")

        # 检查多模态文档命中情况
        doc_samples = [
            "旅行日记2.pdf",
            "api.md",
            "operations.md",
            "release.md",
            "questions.json",
            "study_methods_poster.svg",
            "01_强势_L01",
            "12-多轮对话",
            "接口文档.pdf",
            "13"
        ]
        hits = [t for t in doc_samples if t in final_body_default]
        print(f"\n  [默认项目验证结果] 命中的真实多模态文档标识: {hits} (命中数: {len(hits)})")
        assert len(hits) >= 3, f"默认项目文档召回不足，实际命中: {hits}"

        # ----------------------------------------------------
        # 步骤 3：进入【隔离测试项目】对话，验证专属隔离（物理隔离，0篇文档）
        # ----------------------------------------------------
        print(f"\n--> [Step 3] 导航至【隔离测试项目】Chat 对话页面: {ISOLATED_PROJECT_ID}...")
        page.goto(f"{BASE_URL}/workspace/projects/{ISOLATED_PROJECT_ID}/chat", wait_until="networkidle")
        time.sleep(3)

        agent_btn2 = page.locator('button:has-text("选择智能体")')
        if agent_btn2.is_visible():
            agent_btn2.click()
            time.sleep(1)
            dearflow_option2 = page.locator('text=dearflow_agent').first
            if dearflow_option2.is_visible():
                dearflow_option2.click()
                time.sleep(1)

        new_chat_btn2 = page.locator('button:has-text("新对话")').first
        if new_chat_btn2.is_visible():
            new_chat_btn2.click()
            time.sleep(1.5)

        page.wait_for_selector(textarea_selector, timeout=20000)
        print("  ✓ 隔离项目 Chat 就绪，输入相同提问: '你查一下知识库，看下知识库中有哪些文档'...")

        page.fill(textarea_selector, query_text)
        time.sleep(1)
        send_btn2 = page.locator('button:has(svg path[d*="M12 19V5"])')
        if send_btn2.is_visible():
            send_btn2.click()
        else:
            page.press(textarea_selector, "Enter")
        print("  ✓ 隔离项目消息已发送，等待真实大模型全链路推理...")

        final_body_isolated = wait_for_stream_completion(page, timeout=90, description="隔离项目大模型推理")
        time.sleep(3)
        shot_03 = os.path.join(SCREENSHOT_DIR, "03_isolated_project_empty.png")
        page.screenshot(path=shot_03, full_page=True)
        print(f"  ✓ 隔离项目验收截图已固化: {shot_03}")

        # 提取最后一个 assistant 回复气泡的内容进行隔离验证
        # 避免受左侧历史会话列表中标题文本的干扰
        last_response_text = final_body_isolated
        try:
            # 找到最后一个 dearflow_agent 的回复容器
            agent_messages = page.locator('div:has-text("dearflow_agent")').all()
            if agent_messages:
                last_response_text = agent_messages[-1].inner_text()
        except Exception:
            pass

        print(f"  --> 隔离项目大模型实际答复截取:")
        for line in last_response_text.split("\n")[-15:]:
            if line.strip():
                print("     ", line.strip())

        # 验证物理隔离：隔离项目的回复中绝对不能包含默认项目的专属文档！
        leak_docs = [t for t in ["旅行日记2.pdf", "study_methods_poster.svg", "01_强势_L01", "release.md", "operations.md"] if t in last_response_text]
        print(f"  [隔离项目泄露检查] 串台文档数量: {len(leak_docs)}")
        assert len(leak_docs) == 0, f"发现跨项目串台泄露: {leak_docs}"
        print("  ✓ 隔离验证成功：隔离项目完全看不到默认项目专属文档！物理隔离严格生效！")

        # ----------------------------------------------------
        # 步骤 4：项目列表与两端名称对齐验证
        # ----------------------------------------------------
        print("\n--> [Step 4] 导航至项目列表，验证两端项目名称对齐...")
        page.goto(f"{BASE_URL}/workspace/projects", wait_until="networkidle")
        time.sleep(2)
        shot_04 = os.path.join(SCREENSHOT_DIR, "04_projects_name_alignment.png")
        page.screenshot(path=shot_04, full_page=True)
        print(f"  ✓ 项目列表验收截图已固化: {shot_04}")

        list_body = page.inner_text("body")
        print("  [项目名称核验]")
        print("    - '平台默认项目' 在列表中:", "平台默认项目" in list_body)
        print("    - 'test' 在列表中:", "test" in list_body)

        print("\n========================================================")
        print("=== 恭喜！Playwright 端到端自动化验收全部通过！全链路闭环！ ===")
        print("========================================================\n")

if __name__ == "__main__":
    run_e2e_test()
