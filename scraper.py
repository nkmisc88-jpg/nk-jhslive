import asyncio
import datetime
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"
REFERER_HEADER = "https://stream4liv.netlify.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    print("Starting comprehensive scraper...")
    unique_channels = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT)

        # Block heavy resources for speed, allowing JS/XHR through
        async def route_intercept(route):
            if route.request.resource_type in ["image", "media", "font"]:
                await route.abort()
            else:
                await route.continue_()
        
        await page.route("**/*", route_intercept)

        print(f"Loading {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Find all category tabs/buttons
        tabs = await page.query_selector_all("button, .nav-link, .tab, .category-btn, ul li, .cursor-pointer")
        
        for tab in tabs:
            try:
                cat_name = (await tab.inner_text()).strip()
                # Filter out useless or non-category buttons
                if not cat_name or len(cat_name) > 30 or "Telegram" in cat_name or "Join" in cat_name:
                    continue
                
                print(f"Scraping category: {cat_name}")
                await tab.click(force=True, timeout=2000)
                await page.wait_for_timeout(1500) # Wait for JS to render the channels

                # Extract channels using robust selectors that catch hidden attributes
                cards = await page.query_selector_all("a, div[onclick], .channel-card, .card, div.cursor-pointer")
                for card in cards:
                    # Fallback through all possible URL attributes the site might use
                    href = (
                        await card.get_attribute("href") or 
                        await card.get_attribute("data-url") or 
                        await card.get_attribute("data-stream") or
                        await card.get_attribute("data-link")
                    )
                    
                    if href and any(ext in href for ext in [".m3u8", ".mpd", "token=", "live", "jio", "ts"]):
                        name = (await card.inner_text()).strip().split("\n")[0]
                        if not name:
                            name = "Live Channel"
                            
                        img = await card.query_selector("img")
                        logo = await img.get_attribute("src") if img else ""

                        if href not in unique_channels:
                            unique_channels[href] = {
                                "name": name,
                                "group": cat_name,
                                "logo": logo,
                                "url": href
                            }
            except Exception:
                continue

        # Safety Fallback: If tab clicking failed, scrape the main view
        if not unique_channels:
            print("Tab routing failed. Scraping main view fallback...")
            cards = await page.query_selector_all("a, div[onclick], .channel-card, .card")
            for card in cards:
                href = (
                    await card.get_attribute("href") or 
                    await card.get_attribute("data-url") or 
                    await card.get_attribute("data-stream")
                )
                if href and any(ext in href for ext in [".m3u8", ".mpd", "token=", "live", "jio"]):
                    name = (await card.inner_text()).strip().split("\n")[0] or "Live Channel"
                    if href not in unique_channels:
                        unique_channels[href] = {
                            "name": name,
                            "group": "Live TV",
                            "logo": "",
                            "url": href
                        }

        await browser.close()

    print(f"Extraction complete. Total unique channels found: {len(unique_channels)}")

    # Generate M3U
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    m3u_lines = [
        '#EXTM3U x-tvg-url="https://raw.githubusercontent.com/epg.xml"',
        f'# Playlist Last Updated: {current_time}'
    ]
    
    for ch in unique_channels.values():
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        m3u_lines.append(f'#EXTINF:-1 group-title="{ch["group"]}"{logo_attr},{ch["name"]}')
        m3u_lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        m3u_lines.append(f'#EXTVLCOPT:http-referrer={REFERER_HEADER}')
        m3u_lines.append(ch["url"])

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")

if __name__ == "__main__":
    asyncio.run(run())
