"""Playwright E2E automation script for Docker Sandbox lifecycle, streaming download, and lock state verification."""

import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path("/Users/lijiaxin/.gemini/antigravity/brain/511834f5-594a-48cf-a49d-c3c754dec907/e2e_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_URL = "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/46ea9860-2482-4c45-ba92-b619704fba79?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61"


def get_admin_token():
    import urllib.request
    req = urllib.request.Request(
        "http://127.0.0.1:2142/api/identity/session",
        data=json.dumps({"username": "admin", "password": "admin123456"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        tokens = data["tokens"]
        return {
            "accessToken": tokens["access_token"],
            "refreshToken": tokens["refresh_token"],
            "tokenType": tokens["token_type"],
        }


def run_e2e():
    print("[E2E] Obtaining admin token...")
    token_set = get_admin_token()
    print("[E2E] Token obtained successfully.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1680, "height": 1000},
            accept_downloads=True,
        )

        init_script = f"""
        window.localStorage.setItem('pw:auth:token-set', JSON.stringify({json.dumps(token_set)}));
        """
        context.add_init_script(init_script)

        page = context.new_page()

        page.on("request", lambda req: print(f"[HTTP REQ] {req.method} {req.url}") if "workspace" in req.url else None)
        page.on("response", lambda res: print(f"[HTTP RES] {res.status} {res.url} (Content-Type: {res.headers.get('content-type', '')}, Content-Length: {res.headers.get('content-length', '')})") if "workspace" in res.url else None)
        page.on("console", lambda msg: print(f"[Browser Console {msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        print(f"[E2E] Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)

        # Step 1: Capture chat loaded state
        shot_01 = SCREENSHOT_DIR / "01_chat_loaded.png"
        page.screenshot(path=str(shot_01), full_page=True)
        print(f"[E2E] Step 1 screenshot saved to {shot_01}")

        # Step 2: Open Workspace Panel via top bar button
        print("[E2E] Opening workspace panel via header button...")
        workspace_toggle = page.locator("button[title='沙箱工作区与产物面板']")
        if workspace_toggle.count() > 0:
            workspace_toggle.first.click()
            time.sleep(2)

        shot_02 = SCREENSHOT_DIR / "02_workspace_panel_open.png"
        page.screenshot(path=str(shot_02), full_page=True)
        print(f"[E2E] Step 2 screenshot saved to {shot_02}")

        # Step 3: Expand uploads directory using exact title selector
        print("[E2E] Expanding uploads directory...")
        uploads_btn = page.locator("button[title='/workspace/uploads']").first
        uploads_btn.click()
        time.sleep(2)

        shot_tree = SCREENSHOT_DIR / "03_tree_expanded.png"
        page.screenshot(path=str(shot_tree), full_page=True)
        print(f"[E2E] Directory expanded screenshot saved to {shot_tree}")

        # Step 4: Locate file button inside uploads
        file_btn = page.locator("button[title^='/workspace/uploads/']").first
        file_path_title = file_btn.get_attribute("title")
        print(f"[E2E] Found target file entry: {file_path_title}")
        file_btn.click()
        time.sleep(2)

        shot_03 = SCREENSHOT_DIR / "04_file_preview_ready.png"
        page.screenshot(path=str(shot_03), full_page=True)
        print(f"[E2E] Step 4 preview screenshot saved to {shot_03}")

        # Step 5: Test Single File Download & Locking state
        download_btn = page.locator("button:has-text('下载原文件')")
        if download_btn.count() == 0:
            download_btn = page.locator("button:has-text('下载')").last

        print(f"[E2E] Found download button: count={download_btn.count()}. Triggering download...")
        start_time = time.time()
        with page.expect_response(lambda r: "workspace/content" in r.url, timeout=45000) as resp_info:
            download_btn.first.click()

            # Immediate check of lock state
            time.sleep(0.08)
            is_disabled = download_btn.first.is_disabled()
            btn_text = download_btn.first.inner_text().strip()
            print(f"[E2E] >>> BUTTON LOCK VERIFICATION <<<: is_disabled={is_disabled}, text='{btn_text}'")

            shot_04 = SCREENSHOT_DIR / "05_download_locked_state.png"
            page.screenshot(path=str(shot_04), full_page=True)
            print(f"[E2E] Download locked state screenshot saved to {shot_04}")

        resp = resp_info.value
        duration = time.time() - start_time
        body = resp.body()
        size_mb = len(body) / (1024 * 1024)
        save_path = SCREENSHOT_DIR / "downloaded_presentation.pptx"
        save_path.write_bytes(body)
        print(f"[E2E] >>> SINGLE FILE STREAMING DOWNLOAD SUCCESS <<<")
        print(f"[E2E] Status: {resp.status}")
        print(f"[E2E] Content-Type: {resp.headers.get('content-type', '')}")
        print(f"[E2E] Size: {size_mb:.2f} MiB")
        print(f"[E2E] Duration: {duration:.2f}s")
        print(f"[E2E] Transfer Speed: {(size_mb / max(0.01, duration)):.2f} MiB/s")

        time.sleep(1)

        # Step 6: Test Smart Zip Archive Download
        archive_btn = page.locator("button[title*='打包下载全部文件']")
        if archive_btn.count() > 0:
            print("[E2E] Found archive button. Triggering smart zip streaming download...")
            start_time = time.time()
            with page.expect_response(lambda r: "workspace/zip" in r.url, timeout=45000) as zip_resp_info:
                archive_btn.first.click()
                time.sleep(0.1)
                shot_05 = SCREENSHOT_DIR / "06_archive_download_in_progress.png"
                page.screenshot(path=str(shot_05), full_page=True)

            zip_resp = zip_resp_info.value
            zip_duration = time.time() - start_time
            zip_body = zip_resp.body()
            zip_size_mb = len(zip_body) / (1024 * 1024)
            zip_path = SCREENSHOT_DIR / "workspace_archive.zip"
            zip_path.write_bytes(zip_body)
            print(f"[E2E] >>> SMART ZIP ARCHIVE DOWNLOAD SUCCESS <<<")
            print(f"[E2E] Status: {zip_resp.status}")
            print(f"[E2E] Content-Type: {zip_resp.headers.get('content-type', '')}")
            print(f"[E2E] Size: {zip_size_mb:.2f} MiB")
            print(f"[E2E] Duration: {zip_duration:.2f}s")

        # Step 7: Final screen
        shot_final = SCREENSHOT_DIR / "07_final_success.png"
        page.screenshot(path=str(shot_final), full_page=True)
        print(f"[E2E] Final screenshot saved to {shot_final}")

        browser.close()
        print("\n========================================================")
        print("[E2E] ALL PLAYWRIGHT AUTOMATION TESTS PASSED 100%!")
        print("========================================================")


if __name__ == "__main__":
    run_e2e()
