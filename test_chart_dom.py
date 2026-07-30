"""检查 chart tab 各元素的实际高度和 overflow 设置。"""
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

    debug_info = page.evaluate("""() => {
        const result = {};
        const elements = [
            {sel: '.h-full.flex-col-stretch', name: 'outer'},
            {sel: '.flex.flex-col.flex-1', name: 'rightContainer'},
            {sel: '.result-card', name: 'resultCard'},
            {sel: '.result-card .n-card__content', name: 'cardContent'},
            {sel: '.result-area', name: 'resultArea'},
            {sel: '.result-area .n-tabs', name: 'nTabs'},
            {sel: '.n-tabs-pane-wrapper', name: 'paneWrapper'},
            {sel: '.n-tab-pane', name: 'tabPane'},
            {sel: '.n-tab-pane .flex.flex-col', name: 'flexContainer'},
            {sel: '.chart-container', name: 'chartContainer'}
        ];
        
        for (const {sel, name} of elements) {
            const el = document.querySelector(sel);
            if (el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                result[name] = {
                    offsetHeight: el.offsetHeight,
                    offsetWidth: el.offsetWidth,
                    rect_y: Math.round(rect.y),
                    rect_bottom: Math.round(rect.bottom),
                    overflow: style.overflow,
                    overflowY: style.overflowY,
                    display: style.display,
                    flex: style.flex,
                    minHeight: style.minHeight,
                    height: style.height
                };
            } else {
                result[name] = {exists: false};
            }
        }
        
        result.viewport_height = window.innerHeight;
        return result;
    }""")
    
    print(json.dumps(debug_info, indent=2, ensure_ascii=False))

    browser.close()
