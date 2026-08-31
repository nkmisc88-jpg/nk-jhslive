import asyncio
import datetime
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app"

async def run():
    print("Starting Data-Matching Scraper with Vercel Proxy Routing...")
    
    channel_database = {}
    final_playlist = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        async def handle_response(response):
            try:
                if "application/json" in response.headers.get("content-type", ""):
                    data = await response.json()
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                name = item.get("name") or item.get("title")
                                url = item.get("url") or item.get("link") or item.get("stream")
                                logo = item.get("logo") or item.get("image", "")
                                if name and url:
                                    clean_name = name.strip().lower()
                                    channel_database[clean_name] = {
                                        "url": url,
                                        "logo": logo,
                                        "original_name": name.strip()
                                    }
            except Exception:
                pass

        page.on("response", handle_response)
        
        print("Intercepting API data...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        tabs = await page.query_selector_all("button, .nav-item, li, .category-btn, div.cursor-pointer")
        for tab in tabs:
            try:
                cat_name = (await tab.inner_text()).strip()
                if not cat_name or len(cat_name) > 30 or "Telegram" in cat_name or "Join" in cat_name:
                    continue
                    
                await tab.click(force=True, timeout=2000)
                await page.wait_for_timeout(1000)
                
                cards = await page.query_selector_all("a, div[onclick], .card, .channel-item, div.cursor-pointer")
                for card in cards:
                    visible_text = (await card.inner_text()).strip()
                    if visible_text:
                        primary_name = visible_text.split("\n")[0].strip().lower()
                        
                        if primary_name in channel_database:
                            db_data = channel_database[primary_name]
                            url = db_data["url"]
                            
                            if url not in final_playlist:
                                final_playlist[url] = {
                                    "name": db_data["original_name"],
                                    "group": cat_name,
                                    "logo": db_data["logo"],
                                    "url": url
                                }
            except Exception:
                continue
                
        await browser.close()

    VERCEL_URL = "https://nk-jhslive.vercel.app" 
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    m3u_lines = [
        '#EXTM3U x-tvg-url="https://raw.githubusercontent.com/epg.xml"',
        f'# Playlist Last Updated: {current_time}'
    ]
    
    for ch in final_playlist.values():
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        m3u_lines.append(f'#EXTINF:-1 group-title="{ch["group"]}"{logo_attr},{ch["name"]}')
        
        proxied_url = f"{VERCEL_URL}/play?url={ch['url']}"
        m3u_lines.append(proxied_url)

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")
        
    print(f"Playlist generated successfully with {len(final_playlist)} channels.")

if __name__ == "__main__":
    asyncio.run(run())
