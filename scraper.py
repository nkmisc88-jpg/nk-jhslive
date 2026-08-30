import asyncio
import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"
REFERER_HEADER = "https://stream4liv.netlify.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    print("Starting Playwright + BeautifulSoup Hybrid Scraper...")
    unique_channels = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT)

        print(f"Loading {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Locate all category tabs
        tabs = await page.query_selector_all("button, li.nav-item, div.cursor-pointer, .category-btn, .tab")
        valid_tabs = []
        for tab in tabs:
            try:
                text = (await tab.inner_text()).strip()
                if text and len(text) < 25 and "Telegram" not in text:
                    valid_tabs.append((tab, text))
            except Exception:
                continue

        if not valid_tabs:
            valid_tabs.append((None, "Live TV"))

        for tab, cat_name in valid_tabs:
            print(f"Scraping category: {cat_name}")
            if tab:
                try:
                    await tab.click(force=True, timeout=3000)
                    await page.wait_for_timeout(3000) # Wait for UI to stabilize
                except Exception:
                    pass
            
            # Extract raw HTML string and parse offline to avoid DOM detachment
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Search for any element containing stream links
            elements = soup.find_all(lambda tag: tag.has_attr('href') or tag.has_attr('data-url') or tag.has_attr('data-stream') or tag.has_attr('data-link'))

            for el in elements:
                href = el.get('href') or el.get('data-url') or el.get('data-stream') or el.get('data-link')
                
                if href and any(ext in href for ext in [".m3u8", ".mpd", "token=", "live", "jio"]):
                    # Extract the first visible string as the channel name
                    name_strings = list(el.stripped_strings)
                    name = name_strings[0] if name_strings else "Live Channel"
                    
                    img = el.find('img')
                    logo = img['src'] if img and img.has_attr('src') else ""

                    # Map channel to the current category tab
                    if href not in unique_channels:
                        unique_channels[href] = {
                            "name": name,
                            "group": cat_name,
                            "logo": logo,
                            "url": href
                        }

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
