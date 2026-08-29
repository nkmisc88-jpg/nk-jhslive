import asyncio
import json
import re
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"
REFERER_HEADER = "https://stream4liv.netlify.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    print(f"Loading {TARGET_URL}...")
    captured_channels = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT)

        # Intercept any dynamic JSON responses triggered by tab switching
        async def handle_response(response):
            try:
                if ".json" in response.url or "api" in response.url:
                    if "application/json" in response.headers.get("content-type", ""):
                        data = await response.json()
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and any(k in item for k in ["url", "link", "stream"]):
                                    captured_channels.append({
                                        "name": item.get("name") or item.get("title", "Live TV"),
                                        "group": item.get("category") or item.get("group", "General"),
                                        "logo": item.get("logo") or item.get("image", ""),
                                        "url": item.get("url") or item.get("link") or item.get("stream")
                                    })
            except Exception:
                pass

        page.on("response", handle_response)
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        # Locate all category buttons / navigation tabs on the site
        category_buttons = await page.query_selector_all("nav button, .category-btn, .tab-btn, .categories a, button")
        
        for btn in category_buttons:
            try:
                cat_text = (await btn.inner_text()).strip()
                if cat_text and len(cat_text) < 30:
                    # Click each category tab to force dynamic content loading
                    await btn.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                continue

        # Extract all rendered channel elements from the DOM
        channel_cards = await page.query_selector_all("a, div[onclick], .channel-card, .card")
        for card in channel_cards:
            try:
                name = (await card.inner_text()).strip().split("\n")[0]
                href = (
                    await card.get_attribute("href")
                    or await card.get_attribute("data-url")
                    or await card.get_attribute("data-stream")
                )
                img = await card.query_selector("img")
                logo = await img.get_attribute("src") if img else ""

                # Determine active group/category
                group = "Live TV"
                parent = await card.evaluate("el => el.closest('[data-category]')?.getAttribute('data-category')")
                if parent:
                    group = parent

                if href and any(ext in href for ext in [".m3u8", ".mpd", "live", "stream"]):
                    captured_channels.append({
                        "name": name if name else "Live Channel",
                        "group": group,
                        "logo": logo or "",
                        "url": href
                    })
            except Exception:
                continue

        await browser.close()

    # Deduplicate entries
    unique_channels = {}
    for ch in captured_channels:
        if ch["url"] and ch["url"] not in unique_channels:
            unique_channels[ch["url"]] = ch

    # Generate M3U formatting with player headers
    m3u_lines = ['#EXTM3U x-tvg-url="https://raw.githubusercontent.com/epg.xml"']
    
    for ch in unique_channels.values():
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        m3u_lines.append(f'#EXTINF:-1 group-title="{ch["group"]}"{logo_attr},{ch["name"]}')
        # Append player headers to bypass standard 403 referrer blocks
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER_HEADER}')
        m3u_lines.append(ch["url"])

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")

    print(f"Playlist updated with {len(unique_channels)} channels.")

if __name__ == "__main__":
    asyncio.run(run())
