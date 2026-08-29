import asyncio
import json
import re
from playwright.async_api import async_playwright

TARGET_URL = "https://stream4liv.netlify.app/"

async def run():
    print(f"Opening {TARGET_URL} in headless browser...")
    
    captured_streams = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Intercept background network responses for JSON data or stream URLs
        async def handle_response(response):
            try:
                url = response.url
                # Capture backend JSON API payloads
                if ".json" in url or "api" in url:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        data = await response.json()
                        print(f"Captured API data from: {url}")
                        # Process list if formatted as channel array
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and ("url" in item or "stream" in item or "link" in item):
                                    captured_streams.append({
                                        "name": item.get("name") or item.get("title", "Unknown Channel"),
                                        "group": item.get("category") or item.get("group", "Live TV"),
                                        "logo": item.get("logo") or item.get("image", ""),
                                        "url": item.get("url") or item.get("stream") or item.get("link")
                                    })
            except Exception:
                pass

        page.on("response", handle_response)

        # Navigate to target
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # If data was not in an API response, parse DOM elements directly
        if not captured_streams:
            print("Extracting channels directly from page DOM...")
            channel_elements = await page.query_selector_all("a, div[onclick], button, .channel-item, .card")
            
            for elem in channel_elements:
                try:
                    name = (await elem.inner_text()).strip()
                    href = await elem.get_attribute("href") or await elem.get_attribute("data-url") or await elem.get_attribute("data-stream")
                    
                    # Extract logo if present
                    img_elem = await elem.query_selector("img")
                    logo = await img_elem.get_attribute("src") if img_elem else ""

                    # Find parent category / group
                    parent_category = "General"
                    try:
                        parent_group = await elem.evaluate("el => el.closest('[data-category]')?.getAttribute('data-category') || 'General'")
                        if parent_group:
                            parent_category = parent_group
                    except Exception:
                        pass

                    if href and any(ext in href for ext in [".m3u8", ".mpd", "token=", "live"]):
                        captured_streams.append({
                            "name": name.split("\n")[0] if name else "Live Channel",
                            "group": parent_category,
                            "logo": logo or "",
                            "url": href
                        })
                except Exception:
                    continue

        await browser.close()

    # Generate M3U Content
    m3u_lines = ['#EXTM3U x-tvg-url="https://raw.githubusercontent.com/epg.xml"']
    
    unique_channels = {}
    for ch in captured_streams:
        if ch["url"] and ch["url"] not in unique_channels:
            unique_channels[ch["url"]] = ch

    for ch in unique_channels.values():
        logo_attr = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        m3u_lines.append(f'#EXTINF:-1 group-title="{ch["group"]}"{logo_attr},{ch["name"]}')
        m3u_lines.append(ch["url"])

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")

    print(f"Generated playlist.m3u with {len(unique_channels)} channels.")

if __name__ == "__main__":
    asyncio.run(run())
