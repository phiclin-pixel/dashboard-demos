#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def screenshot(url, path, width=1440, height=900, wait=3000):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(wait / 1000)  # wait for charts animation
        await page.screenshot(path=path, full_page=True)
        await browser.close()
        print(f"Saved: {path}")

async def main():
    base = "http://localhost:8080"
    shots = [
        (f"{base}/index.html", "/home/phiclin/dashboard-demos/preview-index.png"),
        (f"{base}/dashboard-1-overview.html", "/home/phiclin/dashboard-demos/preview-overview.png"),
        (f"{base}/dashboard-2-quarterly.html", "/home/phiclin/dashboard-demos/preview-quarterly.png"),
        (f"{base}/dashboard-3-projects.html", "/home/phiclin/dashboard-demos/preview-projects.png"),
        (f"{base}/dashboard-4-financial.html", "/home/phiclin/dashboard-demos/preview-financial.png"),
    ]
    for url, path in shots:
        await screenshot(url, path)

asyncio.run(main())
