import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

USER_TOKEN = os.getenv("HOTSTAR_USER_TOKEN", "").strip()
USER_AGENT = "Hotstar;in.startv.hotstar.dplus.tv/26.05.10.2 (Android/14; tv)"

# Pool of candidate Indian proxies from your spys.one list
PROXY_POOL = [
    "http://219.65.73.80:80",
    "http://164.52.213.118:8080",
    "http://164.52.216.71:8080",
    "http://140.245.238.56:53",
    "http://103.246.194.251:3128",
    "http://103.171.12.2:8080",
    "http://216.48.180.178:8080",
]

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


def build_image_url(path):
    if not path:
        return ""
    if path.startswith("http"):
        return path
    clean_path = path.lstrip("/")
    return f"https://img.hotstar.com/image/upload/f_auto,q_90,w_720/{clean_path}"


def fetch_hotstar_data():
    req = urllib.request.Request(API_URL, headers=HEADERS)

    for proxy in PROXY_POOL:
        print(f"Trying Indian proxy: {proxy}...", flush=True)
        proxy_support = urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy}
        )
        opener = urllib.request.build_opener(proxy_support)

        try:
            with opener.open(req, timeout=10) as response:
                raw_bytes = response.read()
                raw_text = raw_bytes.decode("utf-8", errors="ignore")
                data = json.loads(raw_text)
                print(f"✅ Success with proxy: {proxy}", flush=True)
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"⚠️ Proxy failed ({proxy}): {e}", flush=True)
            continue

    print("❌ All proxies in the pool failed.", flush=True)
    sys.exit(1)


def parse_items(raw_json):
    seen_ids = set()
    matches = []

    def extract_from_card(item):
        if not isinstance(item, dict):
            return None

        card = (
            item.get("horizontal_content_card")
            or item.get("vertical_content_card")
            or {}
        )
        d = card.get("data", {}) or item

        slug = ""
        actions = d.get("actions", {})
        for action in actions.get("on_click", []):
            nav = action.get("page_navigation", {})
            slug = nav.get("page_slug", "")
            if slug:
                break

        if not slug or "/live/" not in slug:
            return None

        content_id = str(d.get("content_id") or d.get("id") or "")
        if not content_id or not content_id.isdigit():
            id_match = re.search(r"/(\d{8,12})(?:/|$)", slug)
            if id_match:
                content_id = id_match.group(1)

        if not content_id or content_id in seen_ids:
            return None

        seen_ids.add(content_id)

        title = (
            d.get("footer", {}).get("title")
            or d.get("header", {}).get("title")
            or d.get("title")
            or ""
        ).strip()

        description = (
            d.get("description")
            or d.get("synopsis")
            or d.get("short_synopsis")
            or d.get("footer", {}).get("description")
            or d.get("header", {}).get("description")
            or ""
        ).strip()

        images = d.get("images", {})
        image_h = ""
        image_v = ""

        if isinstance(images, dict):
            for key in ["h", "horizontal", "tile"]:
                img_val = images.get(key)
                if isinstance(img_val, dict):
                    image_h = img_val.get("url") or img_val.get("src") or ""
                elif isinstance(img_val, str):
                    image_h = img_val
                if image_h:
                    break

            for key in ["v", "vertical", "i", "poster"]:
                img_val = images.get(key)
                if isinstance(img_val, dict):
                    image_v = img_val.get("url") or img_val.get("src") or ""
                elif isinstance(img_val, str):
                    image_v = img_val
                if image_v:
                    break

        image_url = build_image_url(image_h)
        poster_url = build_image_url(image_v)

        tags = []
        raw_tags = d.get("tags") or d.get("badges") or []
        if isinstance(raw_tags, list):
            for t in raw_tags:
                if isinstance(t, str):
                    tags.append(t)
                elif isinstance(t, dict):
                    t_val = t.get("name") or t.get("label") or t.get("value")
                    if t_val:
                        tags.append(t_val)

        if not tags:
            tags = ["U", "Hindi", "Cricket", "Sports"]

        if slug.startswith("/"):
            watch_url = f"https://www.hotstar.com{slug}"
        else:
            watch_url = f"https://www.hotstar.com/in/{slug}"

        return {
            "contentId": content_id,
            "title": title,
            "description": description,
            "image": image_url,
            "poster": poster_url,
            "languages": {"Hindi": "hin"},
            "tags": tags,
            "watch_url": watch_url,
            "status": "LIVE",
            "isLive": True,
        }

    def walk(curr):
        if isinstance(curr, dict):
            if "items" in curr and isinstance(curr["items"], list):
                for sub_item in curr["items"]:
                    res = extract_from_card(sub_item)
                    if res:
                        matches.append(res)
            res = extract_from_card(curr)
            if res:
                matches.append(res)
            for val in curr.values():
                walk(val)
        elif isinstance(curr, list):
            for sub in curr:
                walk(sub)

    walk(raw_json)
    return matches


def main():
    print("Fetching live matches from Hotstar...", flush=True)
    raw_data = fetch_hotstar_data()

    items = parse_items(raw_data)

    now = datetime.now()
    hour = now.strftime("%I").lstrip("0") or "12"
    am_pm = now.strftime("%p").lower()
    formatted_time = (
        f"{now.day}/{now.month}/{now.year}, {hour}:{now.strftime('%M:%S')} {am_pm}"
    )

    output = {
        "success": True,
        "message": "Live matches fetched successfully",
        "total": len(items),
        "updatedAt": formatted_time,
        "data": items,
    }

    output_filename = "live_matches.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(items)} live events to {output_filename}", flush=True)


if __name__ == "__main__":
    main()
