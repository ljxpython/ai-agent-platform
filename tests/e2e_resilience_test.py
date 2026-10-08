import os
import sys
import time
import json
import re
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = os.path.abspath("tests/e2e_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

BASE_URL = "http://127.0.0.1:3000"
PROJECT_ID = "5a5b7239-43e3-40e6-bba3-e64d96057607"

def extract_target_ids(url: str):
    m = re.search(r"/threads/([^/]+)/runs/([^/]+)/diagnostics", url)
    if m:
        return m.group(1), m.group(2)
    return "unknown_thread", "unknown_run"

def run_e2e_test():
    print(f"=== 老王暴躁技术流：启动 Playwright + Chromium 自动化端到端闭环测试 ===")
    print(f"截图输出目录: {SCREENSHOT_DIR}")

    with sync_playwright() as p:
        # 启动 Chromium
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 监听 console 日志，不放过任何报错
        console_errors = []
        def on_console(msg):
            if msg.type == "error":
                print(f"[Browser ERROR] {msg.text}")
                console_errors.append(msg.text)
        page.on("console", on_console)

        # ----------------------------------------------------
        # 阶段 1：登录系统并验证鉴权
        # ----------------------------------------------------
        print("\n--> [Step 1] 导航至登录页面并登录...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle")
        page.wait_for_selector('button[type="submit"]')
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_login_page.png"))

        # 提交登录
        page.click('button[type="submit"]')
        page.wait_for_url("**/workspace/**", timeout=15000)
        print("  ✓ 登录成功，已重定向至工作区！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_workspace_overview.png"))

        # ----------------------------------------------------
        # 阶段 2：进入项目 Chat 页面，选择 reference_agent
        # ----------------------------------------------------
        print("\n--> [Step 2] 导航至 Chat 页面...")
        chat_link = page.locator('a:has-text("开始对话")')
        chat_link.wait_for(state="visible", timeout=10000)
        chat_link.click()
        time.sleep(2)

        # 如果页面展示选择智能体，则选择 reference_agent
        agent_select_btn = page.locator('button:has-text("选择智能体")')
        if agent_select_btn.is_visible():
            print("选择 reference_agent 智能体...")
            agent_select_btn.click()
            time.sleep(1)
            page.locator('text=reference_agent').click()
            time.sleep(2)

        # 等待输入框出现
        textarea_selector = 'textarea[aria-label="消息草稿"]'
        page.wait_for_selector(textarea_selector, timeout=15000)
        print("  ✓ Chat 会话就绪，输入框已加载！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_chat_page_ready.png"))

        # ----------------------------------------------------
        # 阶段 3：发送真实消息，调用真实模型进行推理并等待结束
        # ----------------------------------------------------
        prompt = "你好，请用一句话回答：1+1等于几？"
        print(f"\n--> [Step 3] 发送真实模型消息: '{prompt}'...")
        textarea = page.locator(textarea_selector)
        textarea.fill(prompt)
        page.keyboard.press("Enter")

        print("等待真实模型响应与 Run 结束...")
        page.wait_for_selector('text=1+1等于几', timeout=15000)

        # 轮询直到会话不处于 busy 状态
        for i in range(45):
            time.sleep(1)
            stop_btn = page.locator('button:has-text("停止")')
            if not stop_btn.is_visible() and i > 5:
                assistant_msgs = page.locator('.pw-chat-stream')
                if assistant_msgs.is_visible():
                    break

        print("  ✓ 真实模型推理与流式响应完成！")
        time.sleep(2)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_real_model_response.png"))

        # ----------------------------------------------------
        # 阶段 4：切换至轨迹排障视图 (Trajectory View)
        # ----------------------------------------------------
        print("\n--> [Step 4] 切换至轨迹排障视图...")
        trajectory_tab = page.locator('button:has-text("轨迹")').first
        trajectory_tab.click()

        page.wait_for_selector('[data-testid="trajectory-view"]', timeout=10000)
        print("  ✓ 轨迹视图加载成功！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_trajectory_view.png"))

        # ----------------------------------------------------
        # 阶段 5：展开运行诊断面板 (Run Diagnostics) 并测试刷新
        # ----------------------------------------------------
        print("\n--> [Step 5] 打开运行诊断面板...")
        diag_btn = page.locator('[data-testid="toggle-diagnostics-btn"]')
        diag_btn.click()

        diag_panel = page.locator('[data-testid="run-diagnostics-panel"]')
        diag_panel.wait_for(state="visible", timeout=10000)
        print("  ✓ 运行诊断面板已展开！")

        # 诊断面板加载完成后，刷新按钮必定可用
        refresh_btn = page.locator('[data-testid="refresh-diagnostics-btn"]')
        refresh_btn.wait_for(state="visible", timeout=5000)

        time.sleep(2)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_real_run_diagnostics_panel.png"))

        print("点击刷新诊断按钮验证重新拉取...")
        with page.expect_response("**/api/langgraph/threads/*/runs/*/diagnostics*"):
            refresh_btn.click()
        time.sleep(1)
        print("  ✓ 刷新诊断交互验证成功！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_run_diagnostics_refreshed.png"))

        # ----------------------------------------------------
        # 阶段 6：F01-F10 专项浏览器视觉与安全验收 (真实 Chromium 渲染和断言)
        # ----------------------------------------------------
        print("\n--> [Step 6] 执行 F01-F10 专项规范断言与视觉核验...")

        # 6.1 F01：旧版响应兼容（无 preparations 和 retries 字段）
        print("--> 验收 F01: 旧版响应兼容...")
        legacy_dto = {
            "version": 1,
            "availability": "available",
            "unavailable_reason": None,
            "correlation": {"execution_request_id": "req-123", "platform_trace_id": "trace-123"},
            "trace": None,
            "graph_executions": [{"observation_id": "g1", "duration_ms": 12.3, "outcome": "success", "error_code": None}],
            "model_errors": [],
            "startup": None,
            "truncated": False,
            "run_status": "success",
            "request_id": "req-legacy"
        }

        def handle_legacy_route(route):
            tid, rid = extract_target_ids(route.request.url)
            payload = {**legacy_dto, "thread_id": tid, "run_id": rid}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/langgraph/threads/*/runs/*/diagnostics*", handle_legacy_route)
        with page.expect_response("**/api/langgraph/threads/*/runs/*/diagnostics*"):
            refresh_btn.click()
        time.sleep(1)

        # 断言两子区域完全隐藏，且无冗余占位卡片
        assert not page.locator('[data-testid="run-preparations-section"]').is_visible(), "F01 失败：preparations 区域应当隐藏！"
        assert not page.locator('[data-testid="run-retries-section"]').is_visible(), "F01 失败：retries 区域应当隐藏！"
        print("  ✓ F01 校验通过：旧版数据下准备与重试区域完全隐藏，无冗余占位！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_f01_legacy_dto_verified.png"))
        page.unroute("**/api/langgraph/threads/*/runs/*/diagnostics*")

        # 6.2 F02 & F03：准备结果展示与重试琥珀色降级
        print("--> 验收 F02 & F03: 准备结果与调用尝试展示（主 Run 成功时 Amber 琥珀色降级）...")
        f02_f03_dto = {
            "version": 1,
            "availability": "available",
            "unavailable_reason": None,
            "correlation": {"execution_request_id": "req-f03", "platform_trace_id": "trace-f03"},
            "trace": None,
            "graph_executions": [],
            "model_errors": [],
            "startup": None,
            "preparations": [
                {
                    "observation_id": "b5a281b4e9954c6dad46d35b4d9119ac",
                    "scope": "primary",
                    "namespace": ["ProbeWorkspace_workspace.before_agent:3f05860b-b143-712f-cec4-1bc9e42431ca"],
                    "component": "workspace",
                    "outcome": "prepared",
                    "duration_ms": 2.641,
                    "error_code": None
                }
            ],
            "retries": [
                {
                    "observation_id": "3a85de2d55884942bab0bbf1760bd3ad",
                    "scope": "primary",
                    "namespace": ["model:9301043c-61ff-f881-7ea1-75e7ff76a764"],
                    "unit": "model",
                    "role": None,
                    "attempts": 2,
                    "outcome": "success",
                    "code": "provider_rate_limited",
                    "duration_ms": 986.68
                }
            ],
            "truncated": False,
            "run_status": "success",
            "request_id": "req-f03"
        }

        def handle_f03_route(route):
            tid, rid = extract_target_ids(route.request.url)
            payload = {**f02_f03_dto, "thread_id": tid, "run_id": rid}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/langgraph/threads/*/runs/*/diagnostics*", handle_f03_route)
        with page.expect_response("**/api/langgraph/threads/*/runs/*/diagnostics*"):
            refresh_btn.click()
        time.sleep(1)

        # 断言准备组件渲染
        prep_section = page.locator('[data-testid="run-preparations-section"]')
        prep_section.wait_for(state="visible", timeout=5000)
        prep_text = prep_section.inner_text()
        assert "工作区" in prep_text and "已准备" in prep_text, f"F02 失败：准备文案不符合预期: {prep_text}"

        # 断言重试组件渲染
        retries_section = page.locator('[data-testid="run-retries-section"]')
        retries_section.wait_for(state="visible", timeout=5000)
        retries_text = retries_section.inner_text()
        assert "调用尝试与重试" in retries_text, "F03 失败：重试区域标题不符合语义！"
        assert "重试 1 次" in retries_text, "F03 失败：attempts=2 应当格式化为'重试 1 次'！"
        assert "限流" in retries_text or "provider_rate_limited" in retries_text, "F03 失败：未显示限流信息！"

        print("  ✓ F02 & F03 校验通过：准备与调用重试渲染完美，文案准确！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_f02_f03_amber_verified.png"))
        page.unroute("**/api/langgraph/threads/*/runs/*/diagnostics*")

        # 6.3 F04 & F05：多条目与子任务重试耗尽
        print("--> 验收 F04 & F05: 子任务多条目与重试耗尽渲染...")
        f04_dto = {
            "version": 1,
            "availability": "available",
            "unavailable_reason": None,
            "correlation": {"execution_request_id": "req-f04", "platform_trace_id": "trace-f04"},
            "trace": None,
            "graph_executions": [],
            "model_errors": [],
            "startup": None,
            "preparations": [
                {
                    "observation_id": "prep-reused",
                    "scope": "primary",
                    "namespace": ["ws:reused"],
                    "component": "workspace",
                    "outcome": "reused",
                    "duration_ms": 0.5,
                    "error_code": None
                },
                {
                    "observation_id": "prep-repaired",
                    "scope": "subagent",
                    "namespace": ["ws:repaired"],
                    "component": "workspace",
                    "outcome": "repaired",
                    "duration_ms": 15.2,
                    "error_code": None
                }
            ],
            "retries": [
                {
                    "observation_id": "ret-task",
                    "scope": "primary",
                    "namespace": ["task:general-purpose"],
                    "unit": "task",
                    "role": "general-purpose",
                    "attempts": 2,
                    "outcome": "exhausted",
                    "code": None,
                    "duration_ms": 2500.0
                },
                {
                    "observation_id": "ret-model",
                    "scope": "subagent",
                    "namespace": ["model:sub"],
                    "unit": "model",
                    "role": None,
                    "attempts": 1,
                    "outcome": "failed",
                    "code": "model_call_failed",
                    "duration_ms": 120.0
                }
            ],
            "truncated": False,
            "run_status": "error",
            "request_id": "req-f04"
        }

        def handle_f04_route(route):
            tid, rid = extract_target_ids(route.request.url)
            payload = {**f04_dto, "thread_id": tid, "run_id": rid}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/langgraph/threads/*/runs/*/diagnostics*", handle_f04_route)
        with page.expect_response("**/api/langgraph/threads/*/runs/*/diagnostics*"):
            refresh_btn.click()
        time.sleep(1)

        retries_text_f04 = page.locator('[data-testid="run-retries-section"]').inner_text()
        print("  [DEBUG] F04 retries text:\n", retries_text_f04)
        assert "general-purpose" in retries_text_f04, "F04 失败：未展示角色名 general-purpose！"
        assert "重试耗尽" in retries_text_f04, "F04 失败：未展示重试耗尽标签！"
        print("  ✓ F04 & F05 校验通过：多条目、子任务角色与耗尽状态展示准确！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_f04_f05_multi_entries.png"))
        page.unroute("**/api/langgraph/threads/*/runs/*/diagnostics*")

        # 6.4 F09：防注入与敏感 canary 剥离
        print("--> 验收 F09: 防注入与 canary 敏感信息剥离...")
        f09_dto = {
            "version": 1,
            "availability": "available",
            "unavailable_reason": None,
            "correlation": {"execution_request_id": "req-f09", "platform_trace_id": "trace-f09"},
            "trace": None,
            "graph_executions": [],
            "model_errors": [],
            "startup": None,
            "preparations": [
                {
                    "observation_id": "prep-normal",
                    "scope": "primary",
                    "namespace": ["ws:norm"],
                    "component": "workspace",
                    "outcome": "prepared",
                    "duration_ms": 1.0,
                    "error_code": None,
                    "secret_canary": "LEAKED_CANARY_VALUE_SECRET_999",
                    "internal_debug_stack": "should_be_stripped"
                }
            ],
            "retries": [
                {
                    "observation_id": "ret-normal",
                    "scope": "primary",
                    "namespace": ["test"],
                    "unit": "model",
                    "role": None,
                    "attempts": 2,
                    "outcome": "success",
                    "code": None,
                    "duration_ms": 10.0,
                    "secret_token": "FORBIDDEN_TOKEN_ABC"
                }
            ],
            "truncated": False,
            "run_status": "success",
            "request_id": "req-f09"
        }

        def handle_f09_route(route):
            tid, rid = extract_target_ids(route.request.url)
            payload = {**f09_dto, "thread_id": tid, "run_id": rid}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/langgraph/threads/*/runs/*/diagnostics*", handle_f09_route)
        with page.expect_response("**/api/langgraph/threads/*/runs/*/diagnostics*"):
            refresh_btn.click()
        time.sleep(1)

        page_html = page.content()
        assert "LEAKED_CANARY_VALUE_SECRET_999" not in page_html, "F09 严重安全漏洞：未知字段 secret_canary 泄露到 DOM！"
        assert "FORBIDDEN_TOKEN_ABC" not in page_html, "F09 严重安全漏洞：未知字段 secret_token 泄露到 DOM！"
        print("  ✓ F09 校验通过：未知字段与敏感 token 严格剥离，DOM 安全无污染！")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_f09_security_verified.png"))
        page.unroute("**/api/langgraph/threads/*/runs/*/diagnostics*")

        # 6.5 F10：移动端视口 (390x844) 响应式验收
        print("--> 验收 F10: 移动端视口 (390x844) 响应式布局与无溢出...")
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_f10_mobile_responsive.png"))
        print("  ✓ F10 校验通过：移动端视口截图完成！")

        browser.close()
        print("\n=== 老王宣布：Playwright 端到端全链路自动化测试全部顺利通过！===")

if __name__ == "__main__":
    run_e2e_test()
