"""验证图表 tab 是否可以滚动查看完整图表。"""
import requests
import json
from playwright.sync_api import sync_playwright

login_resp = requests.post(
    'http://localhost:9999/api/v1/auth/login',
    json={'user_name': 'Soybean', 'password': '123456'}
)
token = login_resp.json()['data']['token']
refresh_token = login_resp.json()['data']['refreshToken']

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/Users/Summer/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')
    context = browser.new_context(viewport={'width': 1440, 'height': 700})
    page = context.new_page()

    page.goto('http://localhost:9527/')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)

    page.evaluate(f"""() => {{
        localStorage.setItem('SOY_token', {json.dumps(json.dumps(token))});
        localStorage.setItem('SOY_refreshToken', {json.dumps(json.dumps(refresh_token))});
    }}""")

    page.goto('http://localhost:9527/bi/sql-workbench')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(4000)

    page.evaluate("""() => {
        const editors = window.monaco?.editor?.getEditors?.();
        if (editors && editors.length > 0) {
            editors[0].setValue('SELECT * FROM users LIMIT 10;');
        }
    }""")
    page.wait_for_timeout(800)
    page.locator('button:has-text("执行")').first.click()
    page.wait_for_timeout(3000)

    page.locator('.n-tabs-tab:has-text("图表")').first.click()
    page.wait_for_timeout(2000)

    # 检查滚动行为
    scroll_info = page.evaluate("""() => {
        const flexContainer = document.querySelector('.n-tab-pane .flex.flex-col');
        if (!flexContainer) return {error: 'flexContainer not found'};
        
        return {
            clientHeight: flexContainer.clientHeight,
            scrollHeight: flexContainer.scrollHeight,
            scrollTop: flexContainer.scrollTop,
            canScroll: flexContainer.scrollHeight > flexContainer.clientHeight,
            overflow: window.getComputedStyle(flexContainer).overflow
        };
    }""")
    print('滚动信息:', json.dumps(scroll_info, indent=2, ensure_ascii=False))

    # 截图（滚动前）
    page.screenshot(path='/tmp/chart_before_scroll.png', full_page=False)

    # 尝试滚动
    page.evaluate("""() => {
        const flexContainer = document.querySelector('.n-tab-pane .flex.flex-col');
        if (flexContainer) {
            flexContainer.scrollTop = flexContainer.scrollHeight;
        }
    }""")
    page.wait_for_timeout(1000)

    # 截图（滚动后）
    page.screenshot(path='/tmp/chart_after_scroll.png', full_page=False)

    scroll_info_after = page.evaluate("""() => {
        const flexContainer = document.querySelector('.n-tab-pane .flex.flex-col');
        if (!flexContainer) return {error: 'flexContainer not found'};
        return {
            scrollTop: flexContainer.scrollTop,
            scrollHeight: flexContainer.scrollHeight,
            clientHeight: flexContainer.clientHeight
        };
    }""")
    print('滚动后:', json.dumps(scroll_info_after, indent=2, ensure_ascii=False))

    browser.close()
