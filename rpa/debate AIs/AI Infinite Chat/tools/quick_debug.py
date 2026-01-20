"""Quick debug - 브라우저 콘솔 에러 확인"""
import asyncio
import sys
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 콘솔 로그 수집
        errors = []
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if 'error' in msg.type else None)
        page.on("pageerror", lambda err: errors.append(f"[PAGE ERROR] {err}"))

        print("Loading page...")
        await page.goto("http://localhost:5178", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        print("\n=== Console Errors ===")
        for e in errors:
            print(e)

        await page.screenshot(path="./test_results/debug.png")
        print("\nScreenshot saved to ./test_results/debug.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
