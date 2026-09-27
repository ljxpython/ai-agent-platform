#!/usr/bin/env python3
"""AI Agent Platform 流式响应速度对比与诊断工具
支持三档测试：
  --target platform : 走平台层 API（前端同款完整链路：鉴权 + 代理 + 运行时）
  --target runtime  : 走底层 Runtime Service（8123端口，跳过平台层用户鉴权与网关）
  --target upstream : 直连上游大模型 API（彻底跳过本项目代码，测试模型原生首字延迟）
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

PLATFORM_URL = "http://127.0.0.1:2142"
RUNTIME_URL = "http://127.0.0.1:8123"
PROJECT_ID = "5a5b7239-43e3-40e6-bba3-e64d96057607"  # 默认 test 项目
DEFAULT_ASSISTANT_ID = "reference_agent"  # 默认使用极简的轻量级 Agent（仅1个工具）

# 终端高亮色彩
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"
RED = "\033[31m"


def log_phase(name: str, detail: str = ""):
    print(f"\n{CYAN}[阶段: {name}]{RESET} {detail}")


def bench_platform(prompt: str, assistant_id: str = DEFAULT_ASSISTANT_ID):
    print(f"{BOLD}=== 🚀 测试1: 平台层 API 全链路 (Platform API -> Runtime) ==={RESET}")
    print(f"目标接口: {PLATFORM_URL}/api/langgraph/threads/.../runs/stream")
    print(f"当前智能体: {YELLOW}{assistant_id}{RESET}")
    print(f"提示词: \"{prompt}\"")

    t_all_start = time.perf_counter()

    # 1. 登录拿平台 Token
    log_phase("1. 平台认证", "获取 access_token")
    t0 = time.perf_counter()
    login_req = urllib.request.Request(
        f"{PLATFORM_URL}/api/identity/session",
        data=json.dumps({"username": "admin", "password": "admin123456"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(login_req, timeout=10) as resp:
        token = json.loads(resp.read())["tokens"]["access_token"]
    print(f"  └─ 认证耗时: {GREEN}{(time.perf_counter() - t0)*1000:.2f} ms{RESET}")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Project-Id": PROJECT_ID,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    # 2. 创建 Thread
    log_phase("2. 会话初始化", "创建 Thread")
    t0 = time.perf_counter()
    thread_req = urllib.request.Request(
        f"{PLATFORM_URL}/api/langgraph/threads",
        data=b"{}",
        headers=headers,
    )
    with urllib.request.urlopen(thread_req, timeout=10) as resp:
        thread_id = json.loads(resp.read())["thread_id"]
    print(f"  └─ Thread 创建成功: {thread_id} ({GREEN}{(time.perf_counter() - t0)*1000:.2f} ms{RESET})")

    # 3. 发起流式 Run
    log_phase("3. 发起流式 Run", f"以 [{assistant_id}] 身份等待首包与流式输出...")
    payload = {
        "assistant_id": assistant_id,
        "input": {"messages": [{"type": "human", "content": prompt}]},
        "stream_mode": ["messages"],
        "stream_resumable": True,
    }
    t_req = time.perf_counter()
    stream_req = urllib.request.Request(
        f"{PLATFORM_URL}/api/langgraph/threads/{thread_id}/runs/stream",
        data=json.dumps(payload).encode(),
        headers=headers,
    )

    t_first_packet = None
    t_first_token = None
    t_first_content_token = None
    reasoning_chars = 0
    text_chars = 0
    in_reasoning = False

    with urllib.request.urlopen(stream_req, timeout=90) as resp:
        t_connected = time.perf_counter()
        print(f"  └─ HTTP 连接建立耗时: {GREEN}{(t_connected - t_req)*1000:.2f} ms{RESET}")
        print(f"\n{BOLD}--- 实时输出开始 ---{RESET}")

        for line in resp:
            line_str = line.decode("utf-8", errors="ignore").strip()
            if not line_str.startswith("data: "):
                continue

            now = time.perf_counter()
            if t_first_packet is None:
                t_first_packet = now
                print(f"{YELLOW}[首个数据包到达 (TTFE): {(t_first_packet - t_req):.2f}s]{RESET}")

            raw = line_str[6:].strip()
            try:
                events = json.loads(raw)
                if not isinstance(events, list):
                    continue
                for item in events:
                    if not isinstance(item, dict):
                        continue
                    event_type = item.get("event")
                    delta = item.get("delta") or {}

                    # 思考内容
                    if event_type == "content-block-start" and item.get("content", {}).get("type") == "reasoning":
                        if not in_reasoning:
                            in_reasoning = True
                            sys.stdout.write(f"{GRAY}[思考中] ")
                            sys.stdout.flush()

                    reasoning_text = delta.get("reasoning")
                    if reasoning_text:
                        if t_first_token is None:
                            t_first_token = now
                        reasoning_chars += len(reasoning_text)
                        sys.stdout.write(f"{GRAY}{reasoning_text}{RESET}")
                        sys.stdout.flush()

                    # 正文内容
                    content_text = delta.get("text")
                    if content_text:
                        if in_reasoning:
                            in_reasoning = False
                            sys.stdout.write(f"\n{BOLD}[正式回复]{RESET} ")
                        if t_first_token is None:
                            t_first_token = now
                        if t_first_content_token is None:
                            t_first_content_token = now
                        text_chars += len(content_text)
                        sys.stdout.write(f"{GREEN}{content_text}{RESET}")
                        sys.stdout.flush()
            except Exception:
                pass

    t_end = time.perf_counter()
    print(f"\n{BOLD}--- 实时输出结束 ---{RESET}\n")
    print(f"{BOLD}=== 📊 链路性能统计 ==={RESET}")
    print(f"  - 智能体: {YELLOW}{assistant_id}{RESET}")
    print(f"  - 总请求耗时: {CYAN}{(t_end - t_all_start):.2f} s{RESET}")
    print(f"  - 网络握手建立: {GREEN}{(t_connected - t_req)*1000:.2f} ms{RESET}")
    print(f"  - 服务端首包延迟 (TTFE): {GREEN}{(t_first_packet - t_req):.2f} s{RESET}" if t_first_packet else "  - 未收到首包")
    print(f"  - 首Token延迟 (TTFT-首字): {YELLOW}{(t_first_token - t_req):.2f} s{RESET}" if t_first_token else "  - 无有效Token")
    if t_first_content_token:
        print(f"  - 正文开始延迟 (思考完成): {CYAN}{(t_first_content_token - t_req):.2f} s{RESET}")
    print(f"  - 思考字数: {reasoning_chars} 字符")
    print(f"  - 正文字数: {text_chars} 字符")
    if t_first_token and (t_end - t_first_token) > 0:
        print(f"  - 生成速率: {CYAN}{text_chars / (t_end - t_first_token):.1f} chars/sec{RESET}")


def bench_runtime(prompt: str, assistant_id: str = DEFAULT_ASSISTANT_ID):
    print(f"{BOLD}=== ⚡ 测试2: 直打底层 Runtime 接口 (跳过平台层网关) ==={RESET}")
    print(f"目标接口: {RUNTIME_URL}/threads/.../runs/stream")
    print(f"当前智能体: {YELLOW}{assistant_id}{RESET}")
    print(f"提示词: \"{prompt}\"")

    # 本地直接生成 Delegation Token 绕过 Platform-API 登录和校验
    try:
        import jwt
    except ImportError:
        print(f"{RED}缺少 pyjwt 库，请使用 uv run python scripts/stream_bench.py --target runtime 运行{RESET}")
        return

    import uuid

    def make_token(operation: str, asst_id: str | None = None, th_id: str | None = None) -> str:
        secret = "ebae5abf4f2440be0cb8f1784e7064bd8463c7e85aeb167ff8c0a80d1f2b13ac"
        now_ts = int(time.time())
        scope = {
            "tenant_id": "__default",
            "project_id": PROJECT_ID,
            "operation": operation,
        }
        if asst_id:
            scope["assistant_id"] = asst_id
        if th_id:
            scope["thread_id"] = th_id
        claims = {
            "iss": "platform-api",
            "aud": "runtime-service",
            "type": "runtime_delegation",
            "sub": "c277dbea-63c4-4289-816a-3b6b83839ea5",
            "tenant_id": "__default",
            "project_id": PROJECT_ID,
            "role": "admin",
            "permissions": ["project.runtime.execute", "project.runtime.read", "project.runtime.write"],
            "policy_version": "v1",
            "allowed_model_ids": ["4a20b48d-7db9-4655-b9bf-f1fd71e5f604"],
            "delegation_version": 2,
            "tool_overrides": {},
            "tool_policy_version": "unscoped-thread-operation" if operation == "thread-create" else "v1",
            "iat": now_ts,
            "nbf": now_ts,
            "exp": now_ts + 300,
            "scope": scope,
            "context_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
        return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": "runtime-delegation-v1", "typ": "JWT"})

    t_all_start = time.perf_counter()

    # 1. 直接调 Runtime 创建 Thread (必须携带 UUID 且与 scope.thread_id 严格一致)
    thread_id = str(uuid.uuid4())
    log_phase("1. Runtime 直连", f"预分配并创建 Thread: {thread_id}")
    t0 = time.perf_counter()
    thread_token = make_token("thread-create", th_id=thread_id)
    thread_req = urllib.request.Request(
        f"{RUNTIME_URL}/threads",
        data=json.dumps({"thread_id": thread_id, "metadata": {}}).encode(),
        headers={
            "Authorization": f"Bearer {thread_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(thread_req, timeout=10) as resp:
        res_data = json.loads(resp.read())
        thread_id = res_data.get("thread_id", thread_id)
    print(f"  └─ Runtime Thread 创建: {thread_id} ({GREEN}{(time.perf_counter() - t0)*1000:.2f} ms{RESET})")

    # 2. 直打 runs/stream
    log_phase("2. Runtime 流式 Run", f"以 [{assistant_id}] 身份直接执行图工作流...")
    run_token = make_token("run-create", asst_id=assistant_id, th_id=thread_id)
    payload = {
        "assistant_id": assistant_id,
        "input": {"messages": [{"type": "human", "content": prompt}]},
        "stream_mode": ["messages"],
    }
    t_req = time.perf_counter()
    stream_req = urllib.request.Request(
        f"{RUNTIME_URL}/threads/{thread_id}/runs/stream",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {run_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    t_first_packet = None
    t_first_token = None
    t_first_content_token = None
    reasoning_chars = 0
    text_chars = 0
    in_reasoning = False

    with urllib.request.urlopen(stream_req, timeout=90) as resp:
        t_connected = time.perf_counter()
        print(f"  └─ HTTP 连接建立耗时: {GREEN}{(t_connected - t_req)*1000:.2f} ms{RESET}")
        print(f"\n{BOLD}--- 实时输出开始 ---{RESET}")

        for line in resp:
            line_str = line.decode("utf-8", errors="ignore").strip()
            if not line_str.startswith("data: "):
                continue

            now = time.perf_counter()
            if t_first_packet is None:
                t_first_packet = now
                print(f"{YELLOW}[首个数据包到达 (TTFE): {(t_first_packet - t_req):.2f}s]{RESET}")

            raw = line_str[6:].strip()
            try:
                events = json.loads(raw)
                if not isinstance(events, list):
                    continue
                for item in events:
                    if not isinstance(item, dict):
                        continue
                    event_type = item.get("event")
                    delta = item.get("delta") or {}

                    reasoning_text = delta.get("reasoning")
                    if reasoning_text:
                        if not in_reasoning:
                            in_reasoning = True
                            sys.stdout.write(f"{GRAY}[思考中] ")
                        if t_first_token is None:
                            t_first_token = now
                        reasoning_chars += len(reasoning_text)
                        sys.stdout.write(f"{GRAY}{reasoning_text}{RESET}")
                        sys.stdout.flush()

                    content_text = delta.get("text")
                    if content_text:
                        if in_reasoning:
                            in_reasoning = False
                            sys.stdout.write(f"\n{BOLD}[正式回复]{RESET} ")
                        if t_first_token is None:
                            t_first_token = now
                        if t_first_content_token is None:
                            t_first_content_token = now
                        text_chars += len(content_text)
                        sys.stdout.write(f"{GREEN}{content_text}{RESET}")
                        sys.stdout.flush()
            except Exception:
                pass

    t_end = time.perf_counter()
    print(f"\n{BOLD}--- 实时输出结束 ---{RESET}\n")
    print(f"{BOLD}=== 📊 Runtime 性能统计 ==={RESET}")
    print(f"  - 智能体: {YELLOW}{assistant_id}{RESET}")
    print(f"  - 总请求耗时: {CYAN}{(t_end - t_all_start):.2f} s{RESET}")
    print(f"  - 网络握手建立: {GREEN}{(t_connected - t_req)*1000:.2f} ms{RESET}")
    print(f"  - 服务端首包延迟 (TTFE): {GREEN}{(t_first_packet - t_req):.2f} s{RESET}" if t_first_packet else "  - 未收到首包")
    print(f"  - 首Token延迟 (TTFT-首字): {YELLOW}{(t_first_token - t_req):.2f} s{RESET}" if t_first_token else "  - 无有效Token")
    if t_first_content_token:
        print(f"  - 正文开始延迟 (思考完成): {CYAN}{(t_first_content_token - t_req):.2f} s{RESET}")
    print(f"  - 思考字数: {reasoning_chars} 字符")
    print(f"  - 正文字数: {text_chars} 字符")


def bench_upstream(prompt: str):
    print(f"{BOLD}=== ⚡ 测试3: 彻底跳过平台全部代码与鉴权，直连底层大模型 API ==={RESET}")
    print(f"提示词: \"{prompt}\"")

    try:
        sys.path.insert(0, os.path.abspath("apps/platform-api/src"))
        import psycopg
        from platform_api.config import Settings
        from platform_api.modules.runtime_catalog.application.credentials import decrypt_api_key

        settings = Settings(_env_file="apps/platform-api/.env")
        with psycopg.connect("postgresql://platform_api:pUsYDD3ZQXesxLUAr5x9Qo7p901ubyOkZIkC9NFJZMxJHneO@127.0.0.1:5432/platform_api") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT api_key_ciphertext, base_url, model_name FROM runtime_catalog_models WHERE id = '4a20b48d-7db9-4655-b9bf-f1fd71e5f604'")
                ciphertext, base_url, model_name = cur.fetchone()
                api_key = decrypt_api_key(ciphertext, master_key=settings.model_config_master_key)
    except Exception as exc:
        print(f"{RED}获取上游模型配置失败: {exc}，请使用 uv run --project apps/runtime-service python scripts/stream_bench.py --target upstream{RESET}")
        return

    clean_base = base_url.rstrip("/")
    url = f"{clean_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    print(f"上游提供商: {CYAN}{clean_base}{RESET}")
    print(f"模型标识: {CYAN}{model_name}{RESET}")

    t0 = time.perf_counter()
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)

    t_first_packet = None
    t_first_token = None
    reasoning_chars = 0
    text_chars = 0
    in_reasoning = False

    with urllib.request.urlopen(req, timeout=60) as resp:
        t_connected = time.perf_counter()
        print(f"  └─ HTTP 连接建立耗时: {GREEN}{(t_connected - t0)*1000:.2f} ms{RESET}")
        print(f"\n{BOLD}--- 实时输出开始 ---{RESET}")

        for line in resp:
            line_str = line.decode("utf-8", errors="ignore").strip()
            if not line_str.startswith("data: "):
                continue

            raw = line_str[6:].strip()
            if raw == "[DONE]":
                break

            now = time.perf_counter()
            if t_first_packet is None:
                t_first_packet = now
                print(f"{YELLOW}[首包到达 (TTFT): {(t_first_packet - t0):.2f}s]{RESET}")

            try:
                data = json.loads(raw)
                delta = data["choices"][0].get("delta", {})
                r = delta.get("reasoning_content") or delta.get("reasoning")
                c = delta.get("content")

                if r:
                    if not in_reasoning:
                        in_reasoning = True
                        sys.stdout.write(f"{GRAY}[思考中] ")
                    if t_first_token is None:
                        t_first_token = now
                    reasoning_chars += len(r)
                    sys.stdout.write(f"{GRAY}{r}{RESET}")
                    sys.stdout.flush()

                if c:
                    if in_reasoning:
                        in_reasoning = False
                        sys.stdout.write(f"\n{BOLD}[正式回复]{RESET} ")
                    if t_first_token is None:
                        t_first_token = now
                    text_chars += len(c)
                    sys.stdout.write(f"{GREEN}{c}{RESET}")
                    sys.stdout.flush()
            except Exception:
                pass

    t_end = time.perf_counter()
    print(f"\n{BOLD}--- 实时输出结束 ---{RESET}\n")
    print(f"{BOLD}=== 📊 上游大模型性能统计 ==={RESET}")
    print(f"  - 总请求耗时: {CYAN}{(t_end - t0):.2f} s{RESET}")
    print(f"  - 握手建连耗时: {GREEN}{(t_connected - t0)*1000:.2f} ms{RESET}")
    print(f"  - 原生首字延迟 (TTFT): {YELLOW}{(t_first_token - t0):.2f} s{RESET}" if t_first_token else "  - 无有效Token")
    print(f"  - 思考字数: {reasoning_chars} 字符")
    print(f"  - 正文字数: {text_chars} 字符")


def _auto_load_venvs():
    """自动将 monorepo 各子服务的虚拟环境 site-packages 加入 sys.path，
    避免用户在根目录下执行 python3 scripts/stream_bench.py 时缺少第三方依赖。
    """
    import glob
    for p in glob.glob("apps/*/.venv/lib/python*/site-packages"):
        abs_p = os.path.abspath(p)
        if abs_p not in sys.path:
            sys.path.insert(0, abs_p)

_auto_load_venvs()


HELP_DOC = f"""
{BOLD}AI Agent Platform 流式响应速度对比与诊断工具{RESET}

{BOLD}一、--target 模式说明 (测试目标):{RESET}
  {CYAN}platform{RESET}  (默认模式) 平台 API 全链路测试 (端口: 2142)
            模拟前端用户的真实完整流程：
            1. 用户账号登录获取 JWT Access Token
            2. 会话初始化创建 Thread 并完成数据库零信任授权登记
            3. 发起 SSE 流式对话，经由平台网关 -> 运行时服务(8123) -> 大模型
            {YELLOW}适用场景：排查前端/客户端流式卡顿、首字延迟、全链路吞吐量。{RESET}

  {CYAN}upstream{RESET}  底层大模型直连测试 (彻底跳过本项目所有代码)
            直接从平台数据库取出当前大模型的提供商 BaseURL 与 API Key，
            通过裸 HTTP 连接直连大模型服务商接口 (https://hk-api.maomaoai.pro/v1)。
            {YELLOW}适用场景：测试大模型服务商裸速与跨境网络物理延迟，作为性能基线参考。{RESET}

  {CYAN}runtime{RESET}   底层运行时引擎直连 (端口: 8123)
            直接向 Runtime-Service 发起图工作流执行。
            {YELLOW}适用场景：测试底层 LangGraph 编排引擎本身的开销。{RESET}

{BOLD}二、--assistant / -a 智能体说明:{RESET}
  {CYAN}reference_agent{RESET} (默认推荐)
            极简智能体：仅挂载 1 个极轻量工具，系统提示词仅一句话。
            输入 Token 仅约 100 个，大模型 Prefill 预计算几乎零耗时，首字响应极快。

  {CYAN}dearflow_agent{RESET}
            全量重型智能体：默认挂载 57 个工具 (AntV图表/MCP/文件系统/Skills)，
            系统提示词包含海量规范，单次输入 Token 超过 22,000 个！
            大模型需要耗费大量时间进行 Attention 计算，首字延迟会显著增加。

{BOLD}三、常用执行示例:{RESET}
  1. 测极简 Agent 的平台流式表现 (最推荐，秒级响应):
     {GREEN}python3 scripts/stream_bench.py -a reference_agent "9.11和9.8哪个大？"{RESET}

  2. 测全量复杂 Agent (体会 57 个工具对时延的影响):
     {GREEN}python3 scripts/stream_bench.py -a dearflow_agent "9.11和9.8哪个大？"{RESET}

  3. 直连底层大模型测试物理裸速:
     {GREEN}python3 scripts/stream_bench.py --target upstream "9.11和9.8哪个大？"{RESET}

  4. 自定义测试问题:
     {GREEN}python3 scripts/stream_bench.py "用Python写一个快速排序"{RESET}
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Agent Platform 流式响应速度对比与诊断工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP_DOC,
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["platform", "upstream", "runtime"],
        default="platform",
        help="测试目标: platform(平台全链路), upstream(直连底层大模型裸速), runtime(底层运行时)",
    )
    parser.add_argument(
        "--assistant",
        "-a",
        default=DEFAULT_ASSISTANT_ID,
        help=f"指定测试的智能体标识 (默认: %(default)s，极简首选: reference_agent，全量复杂: dearflow_agent)",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="9.11和9.8哪个大？请简要回答",
        help="测试提示词 (默认: '9.11和9.8哪个大？请简要回答')",
    )
    args = parser.parse_args()

    if args.target == "platform":
        bench_platform(args.prompt, assistant_id=args.assistant)
    elif args.target == "runtime":
        bench_runtime(args.prompt, assistant_id=args.assistant)
    elif args.target == "upstream":
        bench_upstream(args.prompt)
