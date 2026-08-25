import json
import os
import sys
import urllib.parse
import urllib.request

# The .strip() here removes any accidental spaces or newlines from your secret token
USER_TOKEN = os.getenv("HOTSTAR_USER_TOKEN", "").strip()
USER_AGENT = "Hotstar;in.startv.hotstar.dplus.tv/26.05.10.2 (Android/14; tv)"

# Base API endpoint with standard Android TV client capabilities
API_URL = (
    "https://www.hotstar.com/api/internal/bff/v2/slugs/in/browse/editorial/best-in-sports/6517?"
    "client_capabilities="
    + urllib.parse.quote(
        json.dumps(
            {
                "ads": ["non_ssai"],
                "audio_channel": ["stereo"],
                "container": ["fmp4", "fmp4br", "ts"],
                "dvr": ["short"],
                "dynamic_range": ["sdr"],
                "encryption": ["plain"],
                "ladder": ["phone", "web"],
                "package": ["hls", "dash"],
                "resolution": ["sd", "hd", "fhd"],
                "video_codec": ["h264"],
                "video_codec_non_secure": ["h265", "h264"],
            }
        )
    )
    + "&drm_parameters="
    + urllib.parse.quote(
        json.dumps(
            {
                "hdcp_version": ["HDCP_V2_2"],
                "widevine_security_level": [
                    "SW_SECURE_DECODE",
                    "SW_SECURE_CRYPTO",
                ],
            }
        )
    )
    + "&request_features=consent_supported&lang=eng"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "X-HS-Platform": "androidtv",
    "X-Country-Code": "in",
    "x-hs-app": "260510002",
    "X-HS-Client": "platform:androidtv;app_id:in.startv.hotstar.dplus.tv;app_version:26.05.10.2;os:Android;os_version:14;schema_version:0.0.1690",
    "Referer": "https://www.hotstar.com/in/browse/editorial/best-in-sports/6517",
    "Origin": "https://www.hotstar.com",
    "x-hs-usertoken": USER_TOKEN,
}


def fetch_hotstar_data():
    req = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_items(obj, seen):
    entries = []

    def extract_from_card(item):
        if not isinstance(item, dict):
            return None

        card = (
            item.get("horizontal_content_card")
            or item.get("vertical_content_card")
            or {}
        )
        d = card.get("data", {}) or item

        title = (
            d.get("footer", {}).get("title")
            or d.get("header", {}).get("title")
            or d.get("title")
            or "Live Sports"
        )

        slug = ""
        actions = d.get("actions", {})
        for action in actions.get("on_click", []):
            nav = action.get("page_navigation", {})
            slug = nav.get("page_slug", "")
            if slug:
                break

        if not slug or "/live/" not in slug or slug in seen:
            return None

        seen.add(slug)

        if slug.startswith("/"):
            url = f"https://www.hotstar.com{slug}"
        else:
            url = f"https://www.hotstar.com/in/{slug}"

        # Extract thumbnail image if available
        image_url = ""
        images = d.get("images", {})
        if isinstance(images, dict):
            for k in ["h", "v", "tile"]:
                if k in images:
                    img_data = images[k]
                    if isinstance(img_data, dict):
                        image_url = img_data.get("url", "")
                        if image_url:
                            break

        return {"title": title.strip(), "url": url, "logo": image_url}

    def walk(curr):
        if isinstance(curr, dict):
            if "items" in curr and isinstance(curr["items"], list):
                for sub_item in curr["items"]:
                    res = extract_from_card(sub_item)
                    if res:
                        entries.append(res)
            res = extract_from_card(curr)
            if res:
                entries.append(res)
            for v in curr.values():
                walk(v)
        elif isinstance(curr, list):
            for sub in curr:
                walk(sub)

    walk(obj)
    return entries


def main():
    print("Fetching live sports from Hotstar...")
    try:
        data = fetch_hotstar_data()
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)

    seen_urls = set()
    items = extract_items(data, seen_urls)
    print(f"Found {len(items)} live events.")

    # Write M3U Playlist
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for item in items:
            logo_tag = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
            f.write(
                f'#EXTINF:-1 group-title="Hotstar Live"{logo_tag},{item["title"]}\n'
            )
            # Pass custom headers for player clients that support inline headers
            f.write(
                '#EXTVLCOPT:http-user-agent=Hotstar;in.startv.hotstar.dplus.tv/26.05.10.2 (Android/14; tv)\n'
            )
            f.write(f"{item['url']}\n\n")

    print("Successfully generated playlist.m3u")


if __name__ == "__main__":
    main()
