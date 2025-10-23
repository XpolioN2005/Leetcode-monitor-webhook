import json
import os
import sys
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# ------------------ CONFIG ------------------
USERS = ["xpolion", "Sandipan-developer", "anirbansarkarsk", "rishabhchatterjee"]
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
IMAGE_FILE = "leetcode_table.png"
CACHE_DIR = os.getenv("GITHUB_WORKSPACE", ".") + "/cache"
os.makedirs(CACHE_DIR, exist_ok=True)
STATS_CACHE_FILE = os.path.join(CACHE_DIR, "leetcode_stats_cache.json")
GRAPHQL_URL = "https://leetcode.com/graphql"

# ------------------ OS-AWARE FONT ------------------
def get_system_font(font_size=14):
    try:
        if sys.platform.startswith("win"):
            font_path = "C:/Windows/Fonts/arial.ttf"
        elif sys.platform.startswith("linux"):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        elif sys.platform.startswith("darwin"):
            font_path = "/System/Library/Fonts/Helvetica.ttc"
        else:
            font_path = None

        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

FONT_SIZE = 14
font = get_system_font(FONT_SIZE)

# ------------------ FETCH STATS ------------------
GRAPHQL_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    profile {
      ranking
    }
    submitStats {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }
}
"""

def fetch_leetcode_stats(username: str):
    payload = {"query": GRAPHQL_QUERY, "variables": {"username": username}}
    headers = {
        "User-Agent": "python-requests/leetcode-stats",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    matched = data.get("data", {}).get("matchedUser")
    if not matched:
        raise ValueError(f"User '{username}' not found or profile is private.")

    stats_raw = matched["submitStats"]["acSubmissionNum"]
    result = {"easy": 0, "medium": 0, "hard": 0, "total": 0, "ranking": None}

    for item in stats_raw:
        diff = item["difficulty"].lower()
        if diff in result:
            result[diff] = item["count"]
        elif diff == "all":
            result["total"] = item["count"]

    result["ranking"] = matched["profile"].get("ranking")
    return result

# ------------------ HASH CHECK ------------------
def stats_changed(new_stats, cache_file=STATS_CACHE_FILE):
    new_stats_str = json.dumps(new_stats, sort_keys=True)
    new_hash = hashlib.md5(new_stats_str.encode()).hexdigest()

    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
        if cache.get("hash") == new_hash:
            return False  # No changes

    # Save new hash
    with open(cache_file, "w") as f:
        json.dump({"hash": new_hash, "stats": new_stats}, f, indent=2)
    return True

def generate_table_image(users_stats, filename=IMAGE_FILE):
    headers = ["#", "NAME", "RANK", "EASY", "MEDIUM", "HARD", "TOTAL"]
    rows = []
    for i, u in enumerate(users_stats):
        pos = i + 1
        if pos == 1:
            rank_color = (255, 215, 0)      # gold
        elif pos == 2:
            rank_color = (192, 192, 192)    # silver
        elif pos == 3:
            rank_color = (205, 127, 50)     # bronze
        else:
            rank_color = (255, 255, 255)    # white for others

        rows.append([
            str(pos),
            u["username"],
            str(u.get("ranking") or "—"),
            str(u.get("easy", 0)),
            str(u.get("medium", 0)),
            str(u.get("hard", 0)),
            str(u.get("total", 0))
        ])
        u["_rank_color"] = rank_color  # store for later drawing color

    # ---------- COLORS ----------
    bg_color = (30, 30, 30)
    header_bg_color = (66, 250, 250)
    alt_row_color = (45, 45, 45)
    header_color = (25, 25, 25)
    easy_color = (66, 245, 125)
    medium_color = (245, 125, 66)
    hard_color = (245, 80, 66)
    total_color = (255, 255, 255)
    line_color = (100, 100, 100)

    padding_x = 20
    padding_y = 10

    # ---------- MEASURE COLUMN WIDTHS ----------
    temp_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(temp_img)
    col_widths = []
    for i, h in enumerate(headers):
        max_width = draw.textbbox((0, 0), h, font=font)[2]
        for row in rows:
            w = draw.textbbox((0, 0), row[i], font=font)[2]
            if w > max_width:
                max_width = w
        col_widths.append(max_width + padding_x * 2)

    row_height = draw.textbbox((0, 0), "Hg", font=font)[3] + padding_y * 2
    img_width = sum(col_widths)
    img_height = row_height * (len(rows) + 1) + padding_y * 2

    # ---------- CREATE IMAGE ----------
    img = Image.new("RGB", (img_width, img_height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # ---------- HEADER ----------
    x_offset = 0
    y_offset = padding_y
    for i, h in enumerate(headers):
        draw.rectangle(
            [x_offset, y_offset, x_offset + col_widths[i], y_offset + row_height],
            fill=header_bg_color,
        )
        w = draw.textbbox((0, 0), h, font=font)[2]
        h_text = draw.textbbox((0, 0), h, font=font)[3]
        text_x = x_offset + (col_widths[i] - w) // 2
        text_y = y_offset + (row_height - h_text) // 2
        draw.text((text_x, text_y), h, fill=header_color, font=font)
        x_offset += col_widths[i]

    # ---------- ROWS ----------
    y_offset += row_height
    for idx, row in enumerate(rows):
        row_bg = alt_row_color if idx % 2 else bg_color
        draw.rectangle([0, y_offset, img_width, y_offset + row_height], fill=row_bg)

        x_offset = 0
        for i, cell in enumerate(row):
            if i == 0:
                color = users_stats[idx]["_rank_color"]
            elif i == 3:
                color = easy_color
            elif i == 4:
                color = medium_color
            elif i == 5:
                color = hard_color
            else:
                color = total_color  # name, rank, total

            w = draw.textbbox((0, 0), cell, font=font)[2]
            h_text = draw.textbbox((0, 0), cell, font=font)[3]
            text_x = x_offset + (col_widths[i] - w) // 2 if i != 1 else x_offset + padding_x // 2
            text_y = y_offset + (row_height - h_text) // 2
            draw.text((text_x, text_y), cell, fill=color, font=font)
            x_offset += col_widths[i]

        y_offset += row_height

    img.save(filename)
    print(f"Leaderboard image saved: {filename}")

# ------------------ SEND IMAGE IN EMBED ------------------
def send_image_embed_discord(filename=IMAGE_FILE, webhook_url=WEBHOOK_URL):
    # IST timestamp (timezone-aware)
    now_utc = datetime.now(timezone.utc)
    IST = timezone(timedelta(hours=5, minutes=30))
    now_ist = now_utc.astimezone(IST)
    timestamp = now_ist.strftime("%Y-%m-%d %H:%M:%S")

    with open(filename, "rb") as f:
        multipart_data = {
            "payload_json": (
                None,
                json.dumps({
                    "username": "LeetCode Monitor",
                    "embeds": [
                        {
                            "title": "LeetCode Stats - ByteBuilders",
                            "color": 0xFF6600,
                            "image": {"url": f"attachment://{filename}"},
                            "footer": {"text": f"Updated: {timestamp} IST"}
                        }
                    ]
                }),
                "application/json"
            ),
            "file": (filename, f)
        }

        response = requests.post(webhook_url, files=multipart_data)

    if response.status_code in [200, 204]:
        print("Embed with image sent successfully!")
    else:
        print("Failed to send embed:", response.status_code, response.text)

# ------------------ MAIN ------------------
def rank_key(u):
    """Return integer rank for sorting; missing or non-int ranks go to the end."""
    r = u.get("ranking")
    if r is None or r == "":
        return 10**12
    try:
        return int(r)
    except Exception:
        try:
            return int(float(r))
        except Exception:
            return 10**12

if __name__ == "__main__":
    users_stats = []
    for username in USERS:
        try:
            stats = fetch_leetcode_stats(username)
            stats["username"] = username
            users_stats.append(stats)
        except Exception as e:
            print(f"Error fetching {username}: {e}")

    if not users_stats:
        print("No stats fetched; exiting.")
        sys.exit(0)

    # ---- Sort by rank (ascending). Users with no rank go last. ----
    users_stats.sort(key=rank_key)

    if users_stats and stats_changed(users_stats):
        print("Stats changed! Generating image and sending to Discord...")
        generate_table_image(users_stats)
        send_image_embed_discord()
    else:
        print("No changes in stats. Skipping image generation and Discord message.")
