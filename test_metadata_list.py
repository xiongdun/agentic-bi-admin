"""验证元数据管理页面的数据源列表"""
from playwright.sync_api import sync_playwright
import json

CHROME_PATH = "/Users/Summer/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROME_PATH)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: print(f"[console.{msg.type}] {msg.text}"))

        page.goto("http://localhost:9527/login")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        page.locator('button:has-text("超级管理员")').first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # 进入元数据管理
        page.goto("http://localhost:9527/bi/metadata")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # 检查页面元素
        info = page.evaluate("""() => {
            const cards = document.querySelectorAll('.n-card');
            const dataTable = document.querySelector('.n-data-table');
            const tableRows = document.querySelectorAll('.n-data-table-tbody tr');
            const firstRowCells = [];
            if (tableRows.length > 0) {
                tableRows[0].querySelectorAll('td').forEach(td => {
                    firstRowCells.push(td.innerText.trim());
                });
            }
            // 表头
            const headers = [];
            document.querySelectorAll('.n-data-table-thead th').forEach(th => {
                headers.push(th.innerText.trim());
            });
            return {
                cardsCount: cards.length,
                hasDataTable: !!dataTable,
                rowCount: tableRows.length,
                headers,
                firstRowCells,
            };
        }""")
        print("\n=== 元数据管理页面 ===")
        print(json.dumps(info, indent=2, ensure_ascii=False))

        page.screenshot(path="/tmp/metadata_list.png", full_page=True)
        print("截图: /tmp/metadata_list.png")

        # 点击第一行的"查看"按钮
        first_view_btn = page.locator('.n-data-table-tbody tr:first-child button:has-text("查看")').first
        if first_view_btn.count() > 0:
            first_view_btn.click()
            page.wait_for_timeout(3000)
            # 检查选中状态
            selected_info = page.evaluate("""() => {
                const selectedRow = document.querySelector('.n-data-table-tbody tr.row-selected');
                const allCards = document.querySelectorAll('.n-card');
                const allStatistics = document.querySelectorAll('.n-statistic');
                const tabs = document.querySelectorAll('.n-tabs-tab');
                const tabNames = [];
                tabs.forEach(t => tabNames.push(t.innerText.trim()));
                // 列出所有 NCard 的 header 文本
                const cardHeaders = [];
                allCards.forEach(c => {
                    const header = c.querySelector('.n-card-header__main');
                    cardHeaders.push(header ? header.innerText.trim() : '(no header)');
                });
                // 检查 NGrid
                const grids = document.querySelectorAll('.n-grid');
                const gridInfo = [];
                grids.forEach(g => {
                    gridInfo.push({
                        childCount: g.children.length,
                        html: g.outerHTML.substring(0, 300),
                    });
                });
                return {
                    hasSelectedRow: !!selectedRow,
                    cardCount: allCards.length,
                    cardHeaders,
                    statisticCount: allStatistics.length,
                    gridInfo,
                    tabNames,
                };
            }""")
            print("\n=== 点击查看后 ===")
            print(json.dumps(selected_info, indent=2, ensure_ascii=False))

        browser.close()


if __name__ == "__main__":
    main()
