"""用不同视口大小调试图表显示问题。"""
import requests
import json
from playwright.sync_api import sync_playwright

login_resp = requests.post(
    'http://localhost:9999/api/v1/auth/login',
    json={'user_name': 'Soybean', 'password': '123456'}
)
token = login_resp.json()['data']['token']
refresh_token = login_resp.json()['data']['refreshToken']


def test_viewport(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path='/Users/Summer/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')
        context = browser.new_context(viewport={'width': width, 'height': height})
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

        page.screenshot(path=f'/tmp/chart_{width}x{height}.png', full_page=True)

        debug_info = page.evaluate("""() => {
            const result = {};
            const chartContainer = document.querySelector('.chart-container');
            if (chartContainer) {
                const rect = chartContainer.getBoundingClientRect();
                result.chartContainer = {
                    offsetHeight: chartContainer.offsetHeight,
                    rect_y: rect.y,
                    rect_bottom: rect.bottom,
                    viewport_height: window.innerHeight
                };
                const canvas = chartContainer.querySelector('canvas');
                if (canvas) {
                    const cRect = canvas.getBoundingClientRect();
                    result.canvas = {
                        offsetHeight: canvas.offsetHeight,
                        rect_y: cRect.y,
                        rect_bottom: cRect.bottom,
                        visible: cRect.bottom > 0 && cRect.y < window.innerHeight
                    };
                }
            }
            const outer = document.querySelector('.h-full.flex-col-stretch');
            if (outer) {
                const rect = outer.getBoundingClientRect();
                result.outer = {
                    offsetHeight: outer.offsetHeight,
                    rect_y: rect.y,
                    rect_bottom: rect.bottom
                };
            }
            return result;
        }""")

        print(f'\n=== 视口 {width}x{height} ===')
        print(json.dumps(debug_info, indent=2, ensure_ascii=False))

        browser.close()


# 测试不同视口
test_viewport(1440, 900)
test_viewport(1440, 800)
test_viewport(1440, 700)
