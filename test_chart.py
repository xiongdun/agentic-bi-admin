"""调试图表 tab 高度问题。"""
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
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
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

    # 设置 SQL 并执行
    page.evaluate("""() => {
        const editors = window.monaco?.editor?.getEditors?.();
        if (editors && editors.length > 0) {
            editors[0].setValue('SELECT * FROM users LIMIT 10;');
        }
    }""")
    page.wait_for_timeout(800)
    page.locator('button:has-text("执行")').first.click()
    page.wait_for_timeout(3000)

    # 切换到图表 tab
    page.locator('.n-tabs-tab:has-text("图表")').first.click()
    page.wait_for_timeout(2000)

    page.screenshot(path='/tmp/chart_tab.png', full_page=True)

    # 检查图表相关 DOM 高度
    debug_info = page.evaluate("""() => {
        const result = {};
        
        const chartContainer = document.querySelector('.chart-container');
        if (chartContainer) {
            const rect = chartContainer.getBoundingClientRect();
            const style = window.getComputedStyle(chartContainer);
            result.chartContainer = {
                offsetHeight: chartContainer.offsetHeight,
                offsetWidth: chartContainer.offsetWidth,
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                flex: style.flex,
                minHeight: style.minHeight,
                overflow: style.overflow,
                position: style.position
            };
            // 检查 echarts canvas
            const canvas = chartContainer.querySelector('canvas');
            if (canvas) {
                result.canvas = {
                    offsetHeight: canvas.offsetHeight,
                    offsetWidth: canvas.offsetWidth,
                    rect: canvas.getBoundingClientRect()
                };
            }
            // 检查 echarts div
            const echartsDiv = chartContainer.querySelector('div[_echarts_instance_]');
            if (echartsDiv) {
                result.echartsDiv = {
                    offsetHeight: echartsDiv.offsetHeight,
                    offsetWidth: echartsDiv.offsetWidth
                };
            }
        }
        
        // 检查 chart tab pane
        const chartPane = document.querySelector('.n-tab-pane[name="chart"]');
        if (!chartPane) {
            // 可能用其他选择器
            const panes = document.querySelectorAll('.n-tab-pane');
            result.allPanes = Array.from(panes).map((p, i) => ({
                index: i,
                offsetHeight: p.offsetHeight,
                offsetWidth: p.offsetWidth,
                display: window.getComputedStyle(p).display,
                attrs: p.getAttribute('name') || p.getAttribute('id') || ''
            }));
        } else {
            result.chartPane = {
                offsetHeight: chartPane.offsetHeight,
                offsetWidth: chartPane.offsetWidth,
                display: window.getComputedStyle(chartPane).display
            };
        }
        
        // 检查 result-area
        const resultArea = document.querySelector('.result-area');
        if (resultArea) {
            result.resultArea = {
                offsetHeight: resultArea.offsetHeight,
                offsetWidth: resultArea.offsetWidth,
                overflow: window.getComputedStyle(resultArea).overflow
            };
        }
        
        // 检查 n-tabs-pane-wrapper
        const paneWrapper = document.querySelector('.n-tabs-pane-wrapper');
        if (paneWrapper) {
            result.paneWrapper = {
                offsetHeight: paneWrapper.offsetHeight,
                offsetWidth: paneWrapper.offsetWidth,
                overflow: window.getComputedStyle(paneWrapper).overflow,
                display: window.getComputedStyle(paneWrapper).display
            };
        }
        
        // 检查 n-card-content
        const cardContent = document.querySelector('.result-card .n-card__content');
        if (cardContent) {
            result.cardContent = {
                offsetHeight: cardContent.offsetHeight,
                offsetWidth: cardContent.offsetWidth,
                overflow: window.getComputedStyle(cardContent).overflow
            };
        }
        
        // 检查 chart tab 内的 flex 容器
        const flexContainer = document.querySelector('.n-tab-pane .flex.flex-col');
        if (flexContainer) {
            result.flexContainer = {
                offsetHeight: flexContainer.offsetHeight,
                offsetWidth: flexContainer.offsetWidth,
                display: window.getComputedStyle(flexContainer).display
            };
        }
        
        // 检查 NSpace 的高度
        const nSpace = document.querySelector('.n-tab-pane .n-space');
        if (nSpace) {
            result.nSpace = {
                offsetHeight: nSpace.offsetHeight,
                offsetWidth: nSpace.offsetWidth
            };
        }
        
        return result;
    }""")
    
    print(json.dumps(debug_info, indent=2, ensure_ascii=False))

    browser.close()
