import asyncio
import datetime
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"
REFERER_HEADER = "https://stream4liv.netlify.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    print("Starting optimized fast scraper...")
    unique_channels = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT)

        # SPEED FIX: Block resource downloads (images, fonts, css) to reduce run time to < 2 mins
        async def route_intercept(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        
        await page.route("**/*", route_intercept)

        print(f"Loading {TARGET_URL}...")
        # wait_until="domcontentloaded" is significantly faster than "networkidle"
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        # Locate all potential navigation tabs/buttons
        category_buttons = await page.query_selector_all("button, .btn, .nav-item, li, .category-btn")
        
        for btn in category_buttons:
            try:
                cat_text = (await btn.inner_text()).strip()
                # Skip empty text or navigation buttons unrelated to categories
                if not cat_text or len(cat_text) > 25 or "Telegram" in cat_text:
                    continue
                
                print(f"Extracting category: {cat_text}")
                
                # Click the tab to trigger dynamic channel loading
                await btn.click(timeout=2000)
                await page.wait_for_timeout(800) # Give the DOM 0.8s to swap the channel list

                # Scrape all valid stream links currently rendered on screen
                channel_elements = await page.query_selector_all("a[href]")
                for elem in channel_elements:
                    href = await elem.get_attribute("href")
                    
                    # Filter for typical stream URL footprints
                    if href and any(ext in href for ext in [".m3u8", ".mpd", "token=", "live", "jio"]):
                        # Extract Name
                        name = (await elem.inner_text()).strip().split("\n")[0]
                        if not name:
                            name = "Live Channel"
                        
                        # Extract Logo URL string (even though the image download was blocked)
                        img_elem = await elem.query_selector("img")
                        logo = await img_elem.get_attribute("src") if img_elem else ""

                        # CATEGORY FIX: Assign the exact clicked button's text to the group
                        if href not in unique_channels:
                            unique_channels[href] = {
                                "name": name,
                                "group": cat_text, 
                                "logo": logo or "",
                                "url": href
                            }
            except Exception:
                continue

        await browser.close()

    print(f"Extraction complete. Total unique channels found: {len(unique_channels)}")

    # UPDATE FIX: Inject a dynamic timestamp so GitHub always detects a file change
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
