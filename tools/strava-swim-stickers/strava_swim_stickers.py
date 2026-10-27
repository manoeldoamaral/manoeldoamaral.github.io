#!/usr/bin/env python3
"""Export transparent PNG stat stickers for every Strava swim in the last N days.

Strava's API does not expose the in-app "Share Activity" images, so this script
pulls the swims through the API and renders an equivalent transparent sticker
(distance / time / pace per 100m) for each one.

Usage:
  # one-time: get a refresh token with activity:read_all scope
  python strava_swim_stickers.py auth --client-id ID --client-secret SECRET

  # export (reads STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET / STRAVA_REFRESH_TOKEN)
  python strava_swim_stickers.py export --days 99 --out swims
"""

import argparse
import glob
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

API = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
SWIM_TYPES = {"Swim"}

WIDTH, HEIGHT = 1080, 1920
FONT_CANDIDATES = [
    "/usr/share/fonts/**/Montserrat-Bold.*",
    "/usr/share/fonts/**/Montserrat-SemiBold.*",
    "/Library/Fonts/Montserrat-Bold.*",
    os.path.expanduser("~/Library/Fonts/Montserrat-Bold.*"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/**/LiberationSans-Bold.ttf",
]


# --- Strava API -------------------------------------------------------------

def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def _get(path, token, params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def access_token(client_id, client_secret, refresh_token):
    data = _post(TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    if data.get("refresh_token") and data["refresh_token"] != refresh_token:
        print("Note: Strava issued a new refresh token; update your secret to:",
              data["refresh_token"], file=sys.stderr)
    return data["access_token"]


def swims_since(token, after_epoch):
    page = 1
    while True:
        batch = _get("/athlete/activities", token,
                     {"after": after_epoch, "per_page": 200, "page": page})
        if not batch:
            return
        for act in batch:
            if act.get("sport_type", act.get("type")) in SWIM_TYPES:
                yield act
        page += 1


# --- Formatting -------------------------------------------------------------

def fmt_distance(meters):
    return f"{round(meters):,} m"


def fmt_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def fmt_pace(seconds, meters):
    if not meters:
        return "--"
    per100 = int(seconds / (meters / 100))  # Strava truncates, it doesn't round
    return f"{per100 // 60}:{per100 % 60:02d} /100m"


# --- Rendering --------------------------------------------------------------

def find_font(explicit=None):
    if explicit:
        return explicit
    for pattern in FONT_CANDIDATES:
        hits = sorted(glob.glob(pattern, recursive=True))
        if hits:
            return hits[0]
    return None


def load_font(path, size):
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def draw_waves(draw, x, y, width, color, stroke):
    """Three stacked wavy lines, like the swim icon."""
    amp, gap = stroke * 0.9, stroke * 3.2
    for row in range(3):
        cy = y + amp + row * gap
        pts = [(x + i, cy + amp * math.sin(i / width * 2 * math.pi * 2))
               for i in range(int(width) + 1)]
        draw.line(pts, fill=color, width=stroke, joint="curve")
    return y + 2 * amp + 2 * gap


def render_sticker(activity, path, font_path=None, color=(255, 255, 255, 255)):
    distance = activity.get("distance") or 0
    moving = activity.get("moving_time") or activity.get("elapsed_time") or 0
    stats = [
        ("Distance", fmt_distance(distance)),
        ("Time", fmt_duration(moving)),
        ("Pace", fmt_pace(moving, distance)),
    ]

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    label_font = load_font(font_path, 30)
    value_font = load_font(font_path, 58)

    col_gap = 56
    widths = [max(draw.textlength(lbl, font=label_font),
                  draw.textlength(val, font=value_font)) for lbl, val in stats]
    total = sum(widths) + col_gap * (len(stats) - 1)
    # Shrink the value font if the block would not fit with a side margin.
    while total > WIDTH - 120 and value_font.size > 30:
        value_font = load_font(font_path, value_font.size - 2)
        widths = [max(draw.textlength(lbl, font=label_font),
                      draw.textlength(val, font=value_font)) for lbl, val in stats]
        total = sum(widths) + col_gap * (len(stats) - 1)

    left = (WIDTH - total) / 2
    top = HEIGHT / 2 - 110
    stats_top = draw_waves(draw, left, top, 100, color, 7) + 70

    x = left
    for (lbl, val), w in zip(stats, widths):
        draw.text((x, stats_top), lbl, font=label_font, fill=color)
        draw.text((x, stats_top + 44), val, font=value_font, fill=color)
        x += w + col_gap

    img.save(path)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "swim"


# --- Commands ---------------------------------------------------------------

def cmd_auth(args):
    params = urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": "http://localhost/exchange_token",
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "activity:read_all",
    })
    print("1. Open this URL, log in and click Authorize:\n")
    print(f"   https://www.strava.com/oauth/authorize?{params}\n")
    print("2. The browser lands on a localhost page that fails to load; that's expected.")
    print("   Copy the `code=` value from its address bar.\n")
    code = input("Paste the code: ").strip()
    data = _post(TOKEN_URL, {
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    if "refresh_token" not in data:
        sys.exit(f"Token exchange failed: {data}")
    print("\nSTRAVA_REFRESH_TOKEN =", data["refresh_token"])


def cmd_export(args):
    env = {k: os.environ.get(k) for k in
           ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN")}
    missing = [k for k, v in env.items() if not v]
    if missing:
        sys.exit("Missing environment variables: " + ", ".join(missing))

    token = access_token(*env.values())
    after = int(time.time()) - args.days * 86400
    font_path = find_font(args.font)
    os.makedirs(args.out, exist_ok=True)

    count = 0
    for act in swims_since(token, after):
        day = datetime.fromisoformat(act["start_date_local"].rstrip("Z")).date()
        name = f"{day}_{act['id']}_{slug(act.get('name', ''))}.png"
        render_sticker(act, os.path.join(args.out, name), font_path)
        print("saved", name)
        count += 1
    print(f"{count} swim sticker(s) written to {args.out}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    auth = sub.add_parser("auth", help="get a refresh token (one-time)")
    auth.add_argument("--client-id", required=True)
    auth.add_argument("--client-secret", required=True)
    auth.set_defaults(func=cmd_auth)

    export = sub.add_parser("export", help="render PNGs for recent swims")
    export.add_argument("--days", type=int, default=99)
    export.add_argument("--out", default="swims")
    export.add_argument("--font", help="path to a .ttf/.otf font (default: auto)")
    export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
