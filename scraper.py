import asyncio
import datetime
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"
REFERER_HEADER = "https://stream4liv.netlify.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    print("Starting reliable scraper without resource blocking...")
    unique_channels = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Create a proper browser context to mimic a real session
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        print(f"Loading {TARGET_URL}...")
        # Let the page load completely naturally without intercepting/blocking resources
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(5000) # Give extra time for the JS framework to mount

        # Find all potential category tabs
        tabs = await page.query_selector_all("button, .category-btn, .nav-item, li.nav-item, a.nav-link, div.cursor-pointer")
        
        valid_tabs = []
        for tab in tabs:
            try:
                text = (await tab.inner_text()).strip()
                if text and len(text) < 30 and "Telegram" not in text and "Join" not in text:
                    valid_tabs.append((tab, text))
            except Exception:
                continue

        if not valid_tabs:
            print("No category tabs found. Scraping main page as fallback.")
            valid_tabs.append((None, "Live TV"))

        for tab, cat_name in valid_tabs:
            print(f"Scraping category: {cat_name}")
            if tab:
                try:
                    await tab.click(force=True)
                    # Wait 3 seconds for the site to fetch and render the new category's channels
                    await page.wait_for_timeout(3000) 
                except Exception as e:
                    print(f"Could not click tab {cat_name}: {e}")
                    continue

            # Scrape whatever channels are currently visible in the DOM
            elements = await page.query_selector_all("a, div[onclick], div[data-url], div[data-stream], button[data-link]")
            
            for el in elements:
                try:
                    # Check all possible attribute variations the site might use
                    href = (
                        await el.get_attribute("href") or
                        await el.get_attribute("data-url") or
                        await el.get_attribute("data-stream") or
                        await el.get_attribute("data-link")
                    )
                    
                    if href and any(ext in href.lower() for ext in [".m3u8", ".mpd", "token=", "live", "jio"]):
                        name = (await el.inner_text()).strip().split("\n")[0]
                        if not name:
                            name = "Live Channel"
                            
                        img = await el.query_selector("img")
                        logo = await img.get_attribute("src") if img else ""
                        
                        # Save the channel to the exact category tab we just clicked
                        if href not in unique_channels:
                            unique_channels[href] = {
                                "name": name,
                                "group": cat_name,
                                "logo": logo,
                                "url": href
                            }
                except Exception:
                    continue

        await browser.close()

    print(f"Total unique channels found: {len(unique_channels)}")

    # Generate M3U formatting
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