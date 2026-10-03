"""Fetch sample npb.jp pages so parsers can be written against real HTML (debug only)."""
import os, re, sys, time, urllib.request

OUT = "debug/samples"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (NPB schedule site; +https://github.com/toothbrushh/npb)"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception as e:
        print("FAIL", url, e)
        return None

def save(name, url):
    data = get(url)
    time.sleep(1)
    if data is None:
        return ""
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(data)
    print("OK", url, len(data))
    return data.decode("utf-8", "replace")

pages = {
    "bis_eng_cal_2025_04.html": "https://npb.jp/bis/eng/2025/calendar/index_04.html",
    "bis_eng_cal_2025_10.html": "https://npb.jp/bis/eng/2025/calendar/index_10.html",
    "bis_jp_cal_2025_04.html": "https://npb.jp/bis/2025/calendar/index_04.html",
    "bis_jp_cal_2025_10.html": "https://npb.jp/bis/2025/calendar/index_10.html",
    "bis_jp_cal_2026_10.html": "https://npb.jp/bis/2026/calendar/index_10.html",
    "bis_jp_cal_2026_09.html": "https://npb.jp/bis/2026/calendar/index_09.html",
    "games_sched_2025_04.html": "https://npb.jp/games/2025/schedule_04_detail.html",
    "games_sched_2025_10.html": "https://npb.jp/games/2025/schedule_10_detail.html",
    "games_sched_2026_10.html": "https://npb.jp/games/2026/schedule_10_detail.html",
    "cs_2025.html": "https://npb.jp/cs/2025/",
    "nippons_2025.html": "https://npb.jp/nippons/2025/",
    "bis_jp_std_2025.html": "https://npb.jp/bis/2025/stats/",
    "bis_teams.html": "https://npb.jp/bis/teams/",
}
texts = {k: save(k, u) for k, u in pages.items()}

# follow a few game links of each kind
seen = set()
for key, txt in texts.items():
    for m in re.findall(r'href="([^"]*/games/s\d+\.html)"', txt)[:2] + re.findall(r'href="([^"]*/scores/\d{4}/\d{4}/[^"]+/)"', txt)[:2]:
        url = m if m.startswith("http") else "https://npb.jp" + m
        if url in seen:
            continue
        seen.add(url)
        name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("npb.jp/")[1]).strip("_")
        body = save(name + ".html", url)
        if "/scores/" in url:
            for sub in ("box.html", "playbyplay.html", "roster.html"):
                save(name + "_" + sub.replace(".", "_") + ".html", url + sub)
