#!/usr/bin/env python3
"""
NPB 賽程 / 比分 / 個人成績爬蟲。

資料來源：日本野球機構官方網站 npb.jp
  * 月曆（賽程與比分）：https://npb.jp/bis/eng/{年}/calendar/index_{月}.html
  * 單場成績：          https://npb.jp/scores/{年}/{月日}/{主}-{客}-{NN}/box.html
                        （備援：/bis/{年}/games/s{比賽ID}.html 與英文版）
  * 未賽場地與預告先發：https://npb.jp/games/{年}/schedule_{月}_detail.html
  * 年度個人成績：      https://npb.jp/bis/{年}/stats/idb1_{隊}.html、idp1_{隊}.html
  * 選手個人頁：        https://npb.jp/bis/players/{選手ID}.html

輸出（皆為靜態 JSON，供網頁直接讀取）：
  data/seasons.json                 各年度清單
  data/{年}/schedule.json           該年度全部比賽（季賽、明星賽、季後賽）
  data/{年}/games/{比賽ID}.json      單場詳細（比分、上場名單、個人當場數據）
  data/{年}/players.json            官方年度個人成績
  data/{年}/players/{key}.json      選手逐場紀錄
  data/{年}/names.json              單場成績表上的簡稱 → 選手 key
  data/players/{選手ID}.json        選手個人資料（照片、全名、背號…）

快取規則：
  * 已結束的比賽，單場 JSON 寫入後永不重抓。
  * 過去年度一旦所有比賽都已完賽並抓到成績，標記 complete，之後整季跳過。
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from teams import TEAMS, VENUES, resolve, resolve_ja  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BASE = "https://npb.jp"
JST = dt.timezone(dt.timedelta(hours=9))
MONTHS = ["03", "04", "05", "06", "07", "08", "09", "10", "11"]
DELAY = float(os.environ.get("NPB_DELAY", "1.0"))
BOX_SCHEMA = 2  # 解析器版本；調高可讓舊的單場資料在下次執行時重抓

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; NPB-schedule-site; +https://github.com/toothbrushh/npb)",
    "Accept-Language": "ja,en;q=0.8",
})


# ---------------------------------------------------------------- 共用工具

def now_jst():
    return dt.datetime.now(JST)


def fetch(url):
    """抓網頁；404 回傳 None，其他錯誤拋出。"""
    time.sleep(DELAY)
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            if attempt == 2:
                raise
            print(f"  retry {url}: {e}")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 404:
            return None
        if r.status_code >= 500 and attempt < 2:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    return None


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj, pretty=False):
    """只在內容改變時寫檔，避免無意義的 git diff。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if pretty:
        text = json.dumps(obj, ensure_ascii=False, indent=1)
    else:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True




def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("　", " ")).strip()


def nospace(s):
    return re.sub(r"[\s　]+", "", s or "")


def text_of(cell):
    return clean(cell.get_text(" "))


# ---------------------------------------------------------------- 賽程（月曆）

STAGE_PATTERNS = [
    (r"all.?star|オールスター", "allstar"),
    (r"first", "cs1"),
    (r"final", "cs2"),
    (r"climax|\bcs\b|クライマックス", "cs"),
    (r"japan series|nippon series|日本シリーズ|smbc", "js"),
]

STAGE_LABELS = {"regular": "例行賽", "allstar": "明星賽", "cs1": "高潮系列賽 第一階段",
                "cs2": "高潮系列賽 最終階段", "cs": "高潮系列賽", "js": "日本一系列賽"}


def classify_stage(marker):
    m = (marker or "").lower()
    for pat, code in STAGE_PATTERNS:
        if re.search(pat, m):
            return code
    return "cs" if m else "regular"


CELL_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.I)
DATE_LINK_RE = re.compile(r"gm(\d{8})\.html", re.I)
DAY_RE = re.compile(r"<span[^>]*>\s*(\d{1,2})\s*</span>", re.I)
MARKER_RE = re.compile(r"<div[^>]*class=[\"']tescheaten[\"'][^>]*>([\s\S]*?)</div>", re.I)
FINAL_RE = re.compile(
    r"<a[^>]*href=[\"'][^\"']*/games/s(\d+)\.html[\"'][^>]*>\s*([A-Za-z]+)\s+([\d*]+)\s*-\s*([\d*]+)\s+([A-Za-z]+)\s*</a>",
    re.I)
SCHED_RE = re.compile(r"<div[^>]*>\s*([A-Za-z]+)\s*-\s*([A-Za-z]+)\s+(\d{1,2}:\d{2})\s*</div>", re.I)


def parse_calendar(html, year, month):
    """解析英文版 BIS 月曆。回傳比賽 dict 的 list。

    npb.jp 月曆一律「主隊在左」：
    已賽：<a href=".../games/s2025032800105.html">G 6 - 5 S</a>（巨人主場 6:5 勝養樂多）
    延賽：<a ...>G * - * S</a>
    未賽：<div>S - C 18:00</div>
    季後賽 / 明星賽前方會有 <div class="tescheaten">CS First Stage</div>
    """
    games = []
    for cm in CELL_RE.finditer(html or ""):
        cell = cm.group(1)
        dm = DATE_LINK_RE.search(cell)
        if dm:
            d = dm.group(1)
            date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        else:
            sm = DAY_RE.search(cell)
            if not sm:
                continue
            date = f"{year}-{month}-{int(sm.group(1)):02d}"

        # 依出現位置排序所有事件（標記 / 已賽 / 未賽），標記套用到其後同格比賽
        events = []
        for m in MARKER_RE.finditer(cell):
            events.append((m.start(), "marker", m))
        for m in FINAL_RE.finditer(cell):
            events.append((m.start(), "final", m))
        for m in SCHED_RE.finditer(cell):
            events.append((m.start(), "sched", m))
        events.sort(key=lambda e: e[0])

        marker = ""
        for _, kind, m in events:
            if kind == "marker":
                marker = clean(re.sub(r"<[^>]+>", "", m.group(1)))
                continue
            if kind == "final":
                gid, home, h_s, a_s, away = m.groups()
                g = new_game(gid, date, home, away, marker)
                if "*" in (a_s + h_s):
                    g["status"] = "postponed"
                else:
                    g["status"] = "final"
                    g["homeScore"], g["awayScore"] = int(h_s), int(a_s)
            else:
                home, away, t = m.groups()
                g = new_game(None, date, home, away, marker)
                g["time"] = t.zfill(5)
            games.append(g)
    return games


def new_game(gid, date, home, away, marker):
    away_c, home_c = resolve(away), resolve(home)
    if {away.upper(), home.upper()} == {"CL", "PL"}:
        stage = "allstar"
    else:
        stage = classify_stage(marker)
    return {
        "id": gid or f"{date.replace('-', '')}{away_c}{home_c}",
        "date": date,
        "time": None,
        "away": away_c,
        "home": home_c,
        "awayScore": None,
        "homeScore": None,
        "status": "scheduled",
        "stage": stage,
        "stageLabel": marker or None,
        "venue": None,
        "hasBox": False,
    }


def fix_stages(games):
    """沒有標記時用規則推論季後賽：10–11 月的跨聯盟比賽只可能是日本一系列賽。"""
    league = lambda c: TEAMS.get(c, {}).get("league")
    for g in games:
        if g["stage"] == "regular" and g["date"][5:7] in ("10", "11"):
            la, lh = league(g["away"]), league(g["home"])
            if la and lh and la != lh:
                g["stage"] = "js"
    for g in games:
        g["stageName"] = STAGE_LABELS.get(g["stage"], g["stage"])
    return games


KEEP_FIELDS = ("venue", "venueSource", "time", "hasBox", "attendance", "duration",
               "winP", "loseP", "saveP", "scores")


def scrape_schedule(year, old_games):
    """抓整季月曆；過去已抓過的資訊（場地、成績有無）會保留。"""
    games = []
    for mm in MONTHS:
        html = fetch(f"{BASE}/bis/eng/{year}/calendar/index_{mm}.html")
        if html is None:
            continue
        got = parse_calendar(html, year, mm)
        print(f"  calendar {year}-{mm}: {len(got)} games")
        games.extend(got)

    # 去重（3 月與 4 月可能在同一頁）；同一場既有已賽又有未賽版本時保留已賽
    uniq = {}
    for g in games:
        key = (g["date"], g["away"], g["home"]) if g["status"] == "scheduled" else g["id"]
        uniq.setdefault(key, g)
    played = {(g["date"], g["away"], g["home"]) for g in uniq.values() if g["status"] != "scheduled"}
    games = [g for g in uniq.values()
             if not (g["status"] == "scheduled" and (g["date"], g["away"], g["home"]) in played)]

    old = {g["id"]: g for g in old_games}
    for g in games:
        o = old.get(g["id"])
        if o:
            for k in KEEP_FIELDS:
                if g.get(k) in (None, False) and o.get(k) not in (None, False):
                    g[k] = o[k]
    games.sort(key=lambda g: (g["date"], g.get("time") or "99", g["id"]))
    return fix_stages(games)


# ---------------------------------------------------------------- 未賽：場地、開賽時間、預告先發

def parse_schedule_detail(html, year):
    """解析日文賽程頁。每列：日期 | 主隊 - 客隊 | 球場|時間 | … | 先發：甲|先發：乙"""
    soup = BeautifulSoup(html or "", "html.parser")
    out, cur = [], None
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        m = re.match(r"(\d{1,2})/(\d{1,2})", text_of(cells[0]))
        if m:
            cur = f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            cells = cells[1:]
        if not cur or len(cells) < 2:
            continue
        parts = [p for p in cells[0].get_text("|", strip=True).split("|") if p]
        if len(parts) < 3:
            continue
        home, away = resolve_ja(parts[0]), resolve_ja(parts[-1])
        if not home or not away:
            continue
        vt = [p for p in cells[1].get_text("|", strip=True).split("|") if p]
        link = tr.find("a", href=re.compile(r"/scores/\d{4}/\d{4}/[^/]+/"))
        row = {"date": cur, "home": home, "away": away,
               "reserve": "予備日" in parts[1],
               "scores": re.search(r"/scores/\d{4}/\d{4}/[^/]+/", link["href"]).group(0) if link else None,
               "venue": nospace(vt[0]) if vt and not re.match(r"\d", vt[0]) else None,
               "time": next((t for t in vt if re.fullmatch(r"\d{1,2}:\d{2}", t)), None)}
        if len(cells) >= 4:
            st = [re.sub(r"^先発\s*[:：]\s*", "", p) for p in cells[3].get_text("|", strip=True).split("|")
                  if p.startswith("先発")]
            if len(st) == 2:
                row["probables"] = {"home": st[0], "away": st[1]}
        out.append(row)
    return out


def enrich_schedule(year, games, months):
    """從日文賽程頁補上：所有比賽的 /scores/ 頁面路徑；未賽比賽的場地、時間、預告先發。"""
    by_key = {(g["date"], g["home"], g["away"]): g for g in games}
    for g in games:
        if g["status"] == "scheduled":
            g.pop("probables", None)
    for mm in months:
        try:
            html = fetch(f"{BASE}/games/{year}/schedule_{mm}_detail.html")
        except Exception as e:  # noqa: BLE001
            print(f"  schedule detail {mm} failed: {e}")
            continue
        if not html:
            continue
        hit = 0
        for row in parse_schedule_detail(html, year):
            g = by_key.get((row["date"], row["home"], row["away"]))
            if not g:
                continue
            hit += 1
            if row.get("scores") and g["status"] != "scheduled":
                g["scores"] = row["scores"]
            if g["status"] != "scheduled":
                continue
            if row["venue"]:
                g["venue"], g["venueSource"] = row["venue"], "schedule"
            if row["time"]:
                g["time"] = row["time"].zfill(5)
            if row.get("probables"):
                g["probables"] = row["probables"]
        print(f"  schedule detail {year}-{mm}: matched {hit}")
    # 季後賽不在公式戰賽程頁：/scores/{年}/{月日}/{主}-{客}-{該系列第幾戰}/
    n = {}
    for g in games:
        if g["stage"] in ("cs1", "cs2", "cs", "js") and g["status"] == "final":
            k = (g["stage"], frozenset((g["home"], g["away"])))
            n[k] = n.get(k, 0) + 1
            g.setdefault("scores", f"/scores/{year}/{g['date'][5:7]}{g['date'][8:]}/"
                                   f"{g['home'].lower()}-{g['away'].lower()}-{n[k]:02d}/")


def find_venue(text):
    for v in VENUES:
        if v in text:
            return v
    m = re.search(r"([^\s\d:()（）]{2,20}(?:球場|ドーム|スタジアム|フィールド|パーク[^\s]*))", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 單場成績

BAT_KEYS = ("打数", "AB")
PIT_KEYS = ("投回", "投球回", "IP")
DECISION_MARKS = {"○": "W", "●": "L", "S": "SV", "H": "HLD", "Ｓ": "SV", "Ｈ": "HLD"}


def table_rows(table):
    """表格 → [(cells, is_header_row)]；表頭文字去空白（npb.jp 用直排「打|数」）。"""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        is_th = all(c.name == "th" for c in cells)
        out = []
        for c in cells:
            out.append(nospace(c.get_text("")) if is_th else text_of(c))
            try:
                span = int(c.get("colspan", 1))
            except ValueError:
                span = 1
            out.extend([""] * (min(span, 30) - 1))
        rows.append((out, is_th))
    return rows


def leaf_tables(soup):
    return [t for t in soup.find_all("table") if not t.find("table")]


def split_table(rows, keys):
    for i, (row, _) in enumerate(rows):
        if any(c in keys for c in row):
            return row, [r for r, _ in rows[i + 1:] if any(r) and not any(c in keys for c in r)]
    return None, []


def label_headers(h, rows, pitching):
    """補上空白表頭（npb.jp 的守備位置、選手名欄沒有標題）。"""
    h = list(h)
    vals = lambda i: [r[i] for r in rows if i < len(r) and r[i]]
    name_label = "投手" if pitching else "選手"
    if name_label in h:
        return h
    for i, x in enumerate(h):
        if x:
            if x in PIT_KEYS:
                h[i] = "投球回"
            continue
        v = vals(i)
        if not v:
            continue
        if not pitching and sum(bool(re.match(r"[(（]", s)) for s in v) >= len(v) / 2:
            h[i] = "守備"
        elif pitching and all(s in DECISION_MARKS or s in ("+",) or re.fullmatch(r"\.\d", s) for s in v):
            continue
        elif name_label not in h and sum(not re.fullmatch(r"[\d.+\-/ ]+", s) for s in v) >= len(v) * 0.8:
            h[i] = name_label
    return h


def parse_linescore(table):
    """逐局比分。npb.jp：td.gmscoreteam | 每局… | - | R | H | E（每三局有空白分隔欄）。"""
    if not table.select("td.gmscoreteam") and not any(
            {"R", "H", "E"} <= {nospace(c.get_text("")).translate(FW) for c in tr.find_all(["td", "th"])}
            for tr in table.find_all("tr")):
        return None
    lines = []
    for tr in table.find_all("tr"):
        cells = [text_of(c) for c in tr.find_all(["td", "th"])]
        if len(cells) < 5 or not cells[0] or re.fullmatch(r"[\dＲＨＥRHE]", cells[0]):
            continue
        vals = [v for v in cells[1:] if v != ""]
        if len(vals) >= 4 and vals[-4] == "-":
            inn, rhe = vals[:-4], vals[-3:]
        elif len(vals) >= 4:
            inn, rhe = vals[:-3], vals[-3:]
        else:
            continue
        if not all(re.fullmatch(r"\d+", x) for x in rhe):
            continue
        lines.append((cells[0], inn, rhe))
    if len(lines) < 2:
        return None
    n = max(len(x[1]) for x in lines[:2])
    return {"headers": [""] + [str(i + 1) for i in range(n)] + ["R", "H", "E"],
            "rows": [[nm] + inn + [""] * (n - len(inn)) + rhe for nm, inn, rhe in lines[:2]]}


FW = str.maketrans("ＲＨＥ０１２３４５６７８９", "RHE0123456789")


def parse_labels(soup):
    """「勝投手 ： 某某 ( 1勝0敗 )」這類兩欄的列；空白標籤的列延續上一個標籤。"""
    out, cur = {}, None
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td", recursive=False) or tr.find_all("td")
        if len(cells) != 2:
            cur = None
            continue
        lab, val = text_of(cells[0]), text_of(cells[1])
        m = re.fullmatch(r"(.{1,8}?)\s*[:：]", lab)
        if m:
            cur = nospace(m.group(1))
            out.setdefault(cur, []).append(val)
        elif not lab and cur and val:
            out[cur].append(val)
        else:
            cur = None
    return out


def parse_box(html, game):
    soup = BeautifulSoup(html, "html.parser")
    full = clean(soup.get_text(" "))
    y, mo, d = game["date"].split("-")
    i = full.find(f"{int(y)}年{int(mo)}月{int(d)}日")
    text = full[i:] if i >= 0 else full  # 略過頁首「今日賽程」跑馬燈
    box = {"id": game["id"], "schema": BOX_SCHEMA, "date": game["date"],
           "away": game["away"], "home": game["home"],
           "awayScore": game.get("awayScore"), "homeScore": game.get("homeScore"),
           "stage": game.get("stage"), "linescore": None,
           "teams": {game["away"]: {"batting": None, "pitching": None},
                     game["home"]: {"batting": None, "pitching": None}},
           "info": {}}

    bat_tables, pit_tables = [], []
    for t in leaf_tables(soup):
        if box["linescore"] is None:
            ls = parse_linescore(t)
            if ls:
                ls["teams"] = [game["away"], game["home"]]  # 先攻（客隊）在上
                box["linescore"] = ls
                continue
        rows = table_rows(t)
        flat = {c for r, _ in rows for c in r}
        if flat & set(BAT_KEYS):
            h, d_ = split_table(rows, BAT_KEYS)
            if h and d_:
                bat_tables.append((t, label_headers(h, d_, False), d_))
        elif flat & set(PIT_KEYS):
            h, d_ = split_table(rows, PIT_KEYS)
            if h and d_:
                pit_tables.append((t, label_headers(h, d_, True), d_))

    # npb.jp 單場頁的打擊、投手表都是先攻（客隊）在前、後攻（主隊）在後
    order = [game["away"], game["home"]]
    for kind, tables in (("batting", bat_tables), ("pitching", pit_tables)):
        for code, (t, h, d_) in zip(order, tables[:2]):
            box["teams"][code][kind] = {"headers": h, "rows": d_}

    info = box["info"]
    m = re.search(r"入場者\s*[-－:：]?\s*([\d,]+)", text) or re.search(r"([\d,]{3,})\s*人", text)
    if m:
        info["attendance"] = int(m.group(1).replace(",", ""))
    m = re.search(r"開始\s*[:：]?\s*(\d{1,2})\s*[:：時]\s*(\d{2})", text)
    if m:
        info["start"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"試合時間\s*[-－:：]?\s*(\d{1,2})\s*(?:[:：]|時間)\s*(\d{1,2})", text)
    if m:
        info["duration"] = f"{int(m.group(1))}:{int(m.group(2)):02d}"
    m = re.search(r"(\d+)回戦\s*\(\s*(.+?)\s*\)", text)
    if m:
        info["series"] = f"第{m.group(1)}戰（{m.group(2)}）"
    m = re.search(r"\(\s*(延長\d+回[^)]*|\d+回[^)]*(?:コールド|降雨)[^)]*)\s*\)", text)
    if m:
        info["note"] = m.group(1).strip()
    # 球場：「試合時間」所在儲存格的前一格
    venue = None
    node = soup.find(string=re.compile("試合時間"))
    if node and node.find_parent("td"):
        prev = node.find_parent("td").find_previous_sibling("td")
        if prev and text_of(prev) and not re.search(r"\d", text_of(prev)):
            venue = nospace(text_of(prev))
    venue = venue or find_venue(text)
    if venue:
        info["venue"] = venue
    labels = parse_labels(soup)
    for lab, key in (("勝投手", "winP"), ("敗投手", "loseP"), ("セーブ", "saveP")):
        if labels.get(lab):
            info[key] = re.sub(r"\s*[(（].*$", "", labels[lab][0]).strip()
    if labels.get("本塁打"):
        info["homeRuns"] = " / ".join(labels["本塁打"])
    for lab, vals in labels.items():
        if lab not in ("勝投手", "敗投手", "セーブ", "本塁打"):
            info.setdefault("extra", {})[lab] = " / ".join(vals)

    box["ok"] = bool(bat_tables) or box["linescore"] is not None
    return box


def own_rows(table):
    """只取表格自己的列（略過儲存格內巢狀表格的列）。"""
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def own_cells(tr):
    cells = []
    for c in tr.find_all(["td", "th"], recursive=False):
        inner = c.find("table")
        if inner:  # 投球回：<th>6</th><td>1/3</td>
            cells.append(clean(" ".join(x.get_text(" ", strip=True) for x in inner.find_all(["th", "td"]))))
        else:
            cells.append(text_of(c))
    return cells


def parse_scores_table(table):
    rows = own_rows(table)
    if not rows:
        return None
    headers = [nospace(c.get_text("")) for c in rows[0].find_all(["td", "th"], recursive=False)]
    out, pids = [], []
    for tr in rows[1:]:
        cells = own_cells(tr)
        if not any(cells):
            continue
        a = tr.find("a", href=re.compile(r"/bis/players/\d+\.html"))
        out.append(cells)
        pids.append(re.search(r"/players/(\d+)\.html", a["href"]).group(1) if a else None)
    return {"headers": headers, "rows": out, "pids": pids}


def parse_scores_box(html, game):
    """解析 npb.jp/scores/{年}/{月日}/{主}-{客}-{NN}/box.html（含選手 ID、每打席結果、用球數）。"""
    soup = BeautifulSoup(html, "html.parser")
    box = {"id": game["id"], "schema": BOX_SCHEMA, "date": game["date"],
           "away": game["away"], "home": game["home"],
           "awayScore": game.get("awayScore"), "homeScore": game.get("homeScore"),
           "stage": game.get("stage"), "linescore": None,
           "teams": {game["away"]: {"batting": None, "pitching": None},
                     game["home"]: {"batting": None, "pitching": None}},
           "info": {}}
    ls = soup.find(id="tablefix_ls")
    if ls:
        rows = own_rows(ls)
        head = [text_of(c) for c in rows[0].find_all(["td", "th"], recursive=False)]
        body = []
        for tr in rows[1:3]:
            cells = tr.find_all(["td", "th"], recursive=False)
            body.append([""] + [text_of(c) for c in cells[1:]])
        if len(body) == 2:
            head = [""] + ["R" if h == "計" else h for h in head[1:]]
            box["linescore"] = {"headers": head, "rows": body, "teams": [game["away"], game["home"]]}
    # t = 表（先攻＝客隊）、b = 裏（後攻＝主隊）
    for side, code in (("t", game["away"]), ("b", game["home"])):
        for kind, suffix in (("batting", "b"), ("pitching", "p")):
            t = soup.find(id=f"tablefix_{side}_{suffix}")
            if t:
                tb = parse_scores_table(t)
                if tb:
                    box["teams"][code][kind] = tb

    info = box["info"]
    place = soup.select_one("span.place")
    if place and text_of(place):
        info["venue"] = nospace(text_of(place))
    gi = text_of(soup.select_one("p.game_info")) if soup.select_one("p.game_info") else ""
    m = re.search(r"開始\s*(\d{1,2}):(\d{2})", gi)
    if m:
        info["start"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"試合時間\s*(\d{1,2})時間(\d{1,2})分", gi)
    if m:
        info["duration"] = f"{int(m.group(1))}:{int(m.group(2)):02d}"
    m = re.search(r"入場者\s*([\d,]+)", gi)
    if m:
        info["attendance"] = int(m.group(1).replace(",", ""))
    h3 = soup.find("h3")
    if h3:
        m = re.search(r"(\d+)回戦", text_of(h3))
        if m:
            info["series"] = f"第{m.group(1)}戰"
    # 勝敗投手：投手表第一欄的 ○ ● S
    for t in box["teams"].values():
        p = t.get("pitching")
        if not p:
            continue
        for r in p["rows"]:
            mark = DECISION_MARKS.get(r[0]) if r else None
            key = {"W": "winP", "L": "loseP", "SV": "saveP"}.get(mark)
            if key and len(r) > 1:
                info[key] = r[1]
    # 全壘打：打擊表每打席結果中含「本」
    hrs = []
    for code in (game["away"], game["home"]):
        b = box["teams"][code].get("batting")
        if not b:
            continue
        h = b["headers"]
        ni = h.index("選手") if "選手" in h else 2
        for r in b["rows"]:
            for i, c in enumerate(r):
                if i < len(h) and re.fullmatch(r"\d+", h[i] or "") and "本" in c:
                    hrs.append(f"［{TEAMS.get(code, {}).get('ja', code)}］{r[ni]}（{h[i]}局 {c}）")
    if hrs:
        info["homeRuns"] = " / ".join(hrs)
    m = re.search(r"\(\s*(延長\d+回[^)]*)\)", gi)
    if m:
        info["note"] = m.group(1).strip()
    if box["linescore"] and len(box["linescore"]["headers"]) > 13:
        info.setdefault("note", f"延長{len(box['linescore']['headers']) - 4}回")

    box["ok"] = any(t.get("batting") for t in box["teams"].values())
    return box


def scrape_box(year, game):
    cands = []
    if game.get("scores"):
        cands.append((f"{BASE}{game['scores']}box.html", parse_scores_box))
    cands += [(f"{BASE}/bis/{year}/games/s{game['id']}.html", parse_box),
              (f"{BASE}/bis/eng/{year}/games/s{game['id']}.html", parse_box)]
    for url, parser in cands:
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"  box {game['id']} {url} failed: {e}")
            continue
        if html:
            box = parser(html, game)
            box["source"] = url
            if box["ok"]:
                return box
    return None


# ---------------------------------------------------------------- 年度個人成績（官方）

BAT_COLS = {"試合": "G", "打席": "PA", "打数": "AB", "得点": "R", "安打": "H", "二塁打": "2B",
            "三塁打": "3B", "本塁打": "HR", "塁打": "TB", "打点": "RBI", "盗塁": "SB", "盗塁刺": "CS",
            "犠打": "SH", "犠飛": "SF", "四球": "BB", "故意四": "IBB", "死球": "HBP", "三振": "SO",
            "併殺打": "GDP", "打率": "AVG", "長打率": "SLG", "出塁率": "OBP"}
PIT_COLS = {"登板": "G", "勝利": "W", "敗北": "L", "セーブ": "SV", "ホールド": "HLD", "HP": "HP",
            "ＨＰ": "HP", "完投": "CG", "完封勝": "SHO", "無四球": "NBB", "勝率": "PCT", "打者": "BF",
            "投球回": "IP", "安打": "H", "本塁打": "HR", "四球": "BB", "故意四": "IBB", "死球": "HBP",
            "三振": "SO", "暴投": "WP", "ボーク": "BK", "失点": "R", "自責点": "ER", "防御率": "ERA"}
TEAM_URL_CODES = {"DB": ["db", "yb"], "B": ["b", "bs"]}


def num(v):
    v = (v or "").replace(",", "").strip()
    if v in ("", "-", "----"):
        return None
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return None


def innings_to_outs(v):
    """'7 2/3'、'5.1'（=5又1/3）、'12 .1'、'8' → 出局數。"""
    v = clean(v).replace("⅓", " 1/3").replace("⅔", " 2/3")
    m = re.fullmatch(r"(\d+)?\s*(?:\+?\s*([12])\s*/\s*3)?", v)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 3 + int(m.group(2) or 0)
    m = re.fullmatch(r"(\d*)\s*\.([012])", v)
    if m:
        return int(m.group(1) or 0) * 3 + int(m.group(2))
    return 0


def outs_to_ip(o):
    return f"{o // 3}" + ("" if o % 3 == 0 else f" {o % 3}/3")


def parse_stats_page(html, pitching):
    soup = BeautifulSoup(html or "", "html.parser")
    t = soup.find("table", class_="tablefix2")
    if t is None:
        cands = [x for x in leaf_tables(soup) if "選手" in {nospace(c.get_text("")) for c in x.find_all("th")}]
        t = cands[0] if cands else None
    if t is None:
        return []
    cols = PIT_COLS if pitching else BAT_COLS
    header, out = None, []
    for tr in t.find_all("tr"):
        ths = tr.find_all("th")
        if ths and not tr.find("td"):
            header = [nospace(c.get_text("")) for c in ths]
            continue
        tds = tr.find_all("td")
        if not header or len(tds) < len(header) // 2:
            continue
        name = re.sub(r"^[*+＊＋\s]+", "", text_of(tds[0]))
        if not name or name in ("合計", "計"):
            continue
        p = {"name": name}
        for h, td in zip(header[1:], tds[1:]):
            k = cols.get(h)
            if not k:
                continue
            raw = nospace(td.get_text(""))
            if k == "IP":
                p["OUTS"] = innings_to_outs(raw)
                p["IP"] = outs_to_ip(p["OUTS"])
            else:
                p[k] = num(raw)
        out.append(p)
    return out


def fetch_official_stats(year):
    """回傳 {'batting': [...], 'pitching': [...]}，每筆含 team；抓不到時回傳 None。"""
    res = {"batting": [], "pitching": []}
    ok = 0
    for code in [c for c in TEAMS]:
        for kind, prefix in (("batting", "idb1"), ("pitching", "idp1")):
            for uc in TEAM_URL_CODES.get(code, [code.lower()]):
                try:
                    html = fetch(f"{BASE}/bis/{year}/stats/{prefix}_{uc}.html")
                except Exception as e:  # noqa: BLE001
                    print(f"  stats {prefix}_{uc} failed: {e}")
                    html = None
                if html:
                    rows = parse_stats_page(html, kind == "pitching")
                    if rows:
                        for r in rows:
                            r["team"] = code
                        res[kind].extend(rows)
                        ok += 1
                        break
    print(f"{year}: official stats pages {ok}/24")
    return res if ok else None


# ---------------------------------------------------------------- 現役名單與選手個人資料

PROFILE_KEYS = ["ポジション", "投打", "身長／体重", "身長/体重", "生年月日", "経歴", "ドラフト", "出身地"]


def parse_profile(html, pid):
    soup = BeautifulSoup(html or "", "html.parser")
    prof = {"id": pid, "url": f"{BASE}/bis/players/{pid}.html"}
    sel = lambda css: soup.select_one(css)
    # 頁面上有兩個 id="pc_v_name"（外層容器與姓名本身），取文字最短的那個
    names = sorted((text_of(x) for x in soup.select("#pc_v_name") if text_of(x)), key=len)
    if names:
        prof["fullName"] = names[0]
    elif soup.title:
        prof["fullName"] = clean(re.split(r"[（(|｜]", soup.title.get_text())[0])
    for css, key in (("#pc_v_kana", "kana"), ("#pc_v_no", "number"), ("#pc_v_team", "teamName")):
        el = sel(css)
        if el and text_of(el):
            prof[key] = text_of(el)
    img = sel("#pc_v_photo img")
    if img and img.get("src"):
        prof["photo"] = requests.compat.urljoin(prof["url"], img["src"])
    fields = {}
    for tr in soup.find_all("tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            k, v = text_of(th), text_of(td)
            if k in PROFILE_KEYS and v:
                fields.setdefault(k, v)
    prof["fields"] = fields
    if fields.get("ポジション"):
        prof["position"] = fields["ポジション"]
    prof["fetched"] = now_jst().date().isoformat()
    return prof


def update_profiles(pids, limit=None):
    """抓取尚未存檔的選手個人資料（每位選手只抓一次）。"""
    n = 0
    for pid in sorted(pids):
        path = os.path.join(DATA, "players", f"{pid}.json")
        if os.path.exists(path):
            continue
        if limit is not None and n >= limit:
            break
        n += 1
        try:
            html = fetch(f"{BASE}/bis/players/{pid}.html")
        except Exception as e:  # noqa: BLE001
            print(f"  profile {pid} failed: {e}")
            continue
        if html:
            write_json(path, parse_profile(html, pid), pretty=True)
    if n:
        print(f"profiles: fetched {n}")
    return n


def name_index():
    """全名（去空白）→ 選手 ID，來源：已存的選手個人資料。"""
    idx = {}
    pdir = os.path.join(DATA, "players")
    if os.path.isdir(pdir):
        for f in os.listdir(pdir):
            p = read_json(os.path.join(pdir, f)) or {}
            if p.get("fullName"):
                idx.setdefault(nospace(p["fullName"]), p["id"])
    return idx


# ---------------------------------------------------------------- 選手頁資料：年度成績、逐場紀錄

# 逐場紀錄欄位：代碼 → 單場表頭（可多個寫法）
BAT_LOG = {"AB": ("打数",), "R": ("得点",), "H": ("安打",), "RBI": ("打点",), "HR": ("本塁打",),
           "BB": ("四球",), "HBP": ("死球",), "SO": ("三振",), "SB": ("盗塁",)}
PIT_LOG = {"NP": ("投球数",), "BF": ("打者",), "H": ("安打",), "HR": ("本塁打",), "BB": ("四球",),
           "HBP": ("死球",), "SO": ("三振",), "R": ("失点",), "ER": ("自責点", "自責")}
TOTAL_ROWS = {"チーム計", "計", "合計"}


def player_key(pid, team, name):
    """有 npb.jp 選手 ID 就用 ID；否則用「隊伍_全名」。"""
    return pid if pid else f"{team}_{nospace(name)}"


def match_name(short, fulls):
    """單場成績表的簡稱（例：岡本、中村悠）對應年度成績的全名（岡本 和真、中村 悠平）。"""
    s = nospace(short)
    exact = [f for f in fulls if nospace(f) == s]
    if exact:
        return exact[0]
    hits = []
    for f in fulls:
        parts = clean(f).split(" ")
        sur, given = parts[0], "".join(parts[1:])
        if s == sur or (s.startswith(sur) and len(s) > len(sur) and given.startswith(s[len(sur):])):
            hits.append(f)
    return hits[0] if len(hits) == 1 else None


def box_pids(year, games):
    pids = set()
    gdir = os.path.join(DATA, str(year), "games")
    for g in games:
        if g.get("hasBox"):
            box = read_json(os.path.join(gdir, f"{g['id']}.json")) or {}
            for t in box.get("teams", {}).values():
                for kind in ("batting", "pitching"):
                    pids.update(x for x in ((t.get(kind) or {}).get("pids") or []) if x)
    return pids


def pick(h, r, names):
    for n in names:
        if n in h and h.index(n) < len(r):
            return num(r[h.index(n)])
    return None


def bat_line(h, r):
    vals = {k: pick(h, r, v) for k, v in BAT_LOG.items()}
    # /scores/ 頁面沒有四球、三振欄，改由每打席結果推算
    inn = [r[i] for i in range(len(h)) if i < len(r) and re.fullmatch(r"\d+", h[i] or "")]
    if inn:
        for k, word in (("BB", "四球"), ("HBP", "死球"), ("SO", "三振"), ("HR", "本")):
            if vals[k] is None:
                vals[k] = sum(nospace(c).count(word) if word != "本" else ("本" in c) for c in inn)
    return [vals[k] for k in BAT_LOG]


def build_players(year, games, stats):
    idx = name_index()
    stats = stats or {"batting": [], "pitching": []}
    fulls = {}
    for kind in ("batting", "pitching"):
        for p in stats[kind]:
            pid = idx.get(nospace(p["name"]))
            p["key"] = player_key(pid, p["team"], p["name"])
            if pid:
                p["id"] = pid
            fulls.setdefault(p["team"], set()).add(p["name"])

    names, logs, short_ids = {}, {}, {}
    gdir = os.path.join(DATA, str(year), "games")
    for g in games:
        if not g.get("hasBox") or g["stage"] == "allstar":
            continue
        box = read_json(os.path.join(gdir, f"{g['id']}.json"))
        if not box:
            continue
        for team, t in box.get("teams", {}).items():
            opp = g["home"] if team == g["away"] else g["away"]
            ha = "A" if team == g["away"] else "H"
            for kind in ("batting", "pitching"):
                tb = t.get(kind)
                if not tb or not tb.get("headers"):
                    continue
                h = tb["headers"]
                nm_col = "投手" if kind == "pitching" else "選手"
                if nm_col not in h:
                    continue
                ni = h.index(nm_col)
                pids = tb.get("pids") or []
                for ri, r in enumerate(tb["rows"]):
                    short = r[ni] if ni < len(r) else ""
                    if not short or short in TOTAL_ROWS:
                        continue
                    pid = pids[ri] if ri < len(pids) else None
                    full = None
                    if pid:
                        prof = read_json(os.path.join(DATA, "players", f"{pid}.json")) or {}
                        full = prof.get("fullName")
                    full = full or match_name(short, fulls.get(team, ()))
                    if not pid and full:
                        pid = idx.get(nospace(full))
                    if pid:
                        short_ids[(team, nospace(short))] = pid
                    key = player_key(pid, team, full or short)
                    names.setdefault(team, {})[short] = key
                    lg = logs.setdefault(key, {"key": key, "id": pid, "name": full or short, "team": team,
                                               "bat": [], "pit": []})
                    base = [g["id"], g["date"], opp, ha, g["stage"]]
                    if kind == "batting":
                        pos = r[h.index("守備")] if "守備" in h and h.index("守備") < len(r) else ""
                        lg["bat"].append(base + [pos] + bat_line(h, r))
                    else:
                        ip_i = h.index("投球回") if "投球回" in h else None
                        outs = 0
                        if ip_i is not None and ip_i < len(r):
                            outs = innings_to_outs(r[ip_i])
                            nxt = r[ip_i + 1] if ip_i + 1 < len(r) and h[ip_i + 1] == "" else ""
                            if re.fullmatch(r"\.\d", nxt):
                                outs += int(nxt[1])
                        dec = next((DECISION_MARKS[c] for c in r[:ni] if c in DECISION_MARKS), "")
                        lg["pit"].append(base + [outs] + [pick(h, r, v) for v in PIT_LOG.values()] + [dec])

    # 官方成績表沒有 ID → 以「隊伍＋全名」或「隊伍＋單場表上的名字」（外籍、登錄名選手）對應逐場紀錄的 ID
    by_name = {(lg["team"], nospace(lg["name"])): lg["id"] for lg in logs.values() if lg.get("id")}
    for kind in ("batting", "pitching"):
        for p in stats[kind]:
            if not p.get("id"):
                k = (p["team"], nospace(p["name"]))
                pid = by_name.get(k) or short_ids.get(k)
                if pid:
                    p["id"] = p["key"] = pid
            if p.get("id"):
                prof = read_json(os.path.join(DATA, "players", f"{p['id']}.json")) or {}
                for k in ("photo", "kana", "number", "position"):
                    if prof.get(k):
                        p[k] = prof[k]
                if logs.get(p["id"]):
                    logs[p["id"]]["name"] = p["name"]

    pdir = os.path.join(DATA, str(year), "players")
    for key, lg in logs.items():
        lg["batCols"] = ["POS"] + list(BAT_LOG)
        lg["pitCols"] = ["OUTS"] + list(PIT_LOG) + ["DEC"]
        write_json(os.path.join(pdir, f"{key}.json"), lg)
    write_json(os.path.join(DATA, str(year), "names.json"), names)
    return {"year": year, "official": bool(stats["batting"] or stats["pitching"]),
            "batting": stats["batting"], "pitching": stats["pitching"]}


# ---------------------------------------------------------------- 主流程

def update_season(year, force=False, max_boxes=None, boxes=True):
    ydir = os.path.join(DATA, str(year))
    sched_path = os.path.join(ydir, "schedule.json")
    old = read_json(sched_path, {}) or {}
    if old.get("complete") and not force:
        print(f"{year}: complete, skipped (use --force to refresh)")
        return old

    print(f"{year}: fetching schedule")
    games = scrape_schedule(year, old.get("games", []))
    if not games:
        print(f"{year}: no games found")
        return old

    # 日文賽程頁：各場 /scores/ 路徑（單場成績來源）、未賽的場地與預告先發
    months = sorted({g["date"][5:7] for g in games
                     if g["status"] == "scheduled" or (g["status"] == "final" and not g.get("hasBox"))})
    if months:
        enrich_schedule(year, games, months)

    fetched = 0
    gdir = os.path.join(ydir, "games")
    for g in games:
        if g["status"] != "final" or not g["id"].isdigit() or not boxes:
            continue
        path = os.path.join(gdir, f"{g['id']}.json")
        box = read_json(path)
        if box and box.get("schema") == BOX_SCHEMA and not force:
            g["hasBox"] = True
        else:
            if max_boxes is not None and fetched >= max_boxes:
                continue
            fetched += 1
            box = scrape_box(year, g)
            if not box:
                print(f"  box {g['id']}: not available")
                continue
            write_json(path, box)
            g["hasBox"] = True
            print(f"  box {g['id']} {g['away']}@{g['home']} saved")
        info = box.get("info", {})
        if info.get("venue"):
            g["venue"], g["venueSource"] = info["venue"], "box"
        for k in ("start", "attendance", "duration", "winP", "loseP", "saveP"):
            if info.get(k) is not None:
                g["time" if k == "start" else k] = info[k]

    for g in games:
        if not g.get("venue") and g["home"] in TEAMS and g["stage"] != "allstar":
            g["venue"], g["venueSource"] = TEAMS[g["home"]]["home"], "home"

    # 年度個人成績（官方）與選手個人資料（照片、全名…，每位選手只抓一次）
    stats = fetch_official_stats(year)
    if boxes:
        update_profiles(box_pids(year, games), limit=max_boxes)
    players = build_players(year, games, stats)
    write_json(os.path.join(ydir, "players.json"), players)

    complete = (year < now_jst().year and stats is not None
                and all(g["status"] != "scheduled" for g in games)
                and all(g["hasBox"] for g in games if g["status"] == "final" and g["id"].isdigit()))
    prev_games = old.get("games")
    out = {"year": year, "updated": old.get("updated"), "complete": complete, "games": games}
    if prev_games != games or old.get("complete") != complete or not old.get("updated"):
        out["updated"] = now_jst().isoformat(timespec="minutes")
    write_json(sched_path, out)
    nf = sum(g["status"] == "final" for g in games)
    print(f"{year}: {len(games)} games, {nf} final, complete={complete}, boxes fetched={fetched}")
    return out


def update_index(years_touched):
    path = os.path.join(DATA, "seasons.json")
    idx = {}
    for y in os.listdir(DATA) if os.path.isdir(DATA) else []:
        if not y.isdigit():
            continue
        s = read_json(os.path.join(DATA, y, "schedule.json"))
        if not s or not s.get("games"):
            continue
        idx[int(y)] = {"year": int(y), "complete": s.get("complete", False),
                       "updated": s.get("updated"), "games": len(s["games"])}
    seasons = sorted(idx.values(), key=lambda s: -s["year"])
    write_json(path, {"seasons": seasons}, pretty=True)


def parse_years(spec):
    years = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "current":
            years.add(now_jst().year)
        elif "-" in part:
            a, b = part.split("-", 1)
            b = now_jst().year if b.strip() == "current" else int(b)
            years.update(range(int(a), b + 1))
        else:
            years.add(int(part))
    return sorted(years, reverse=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NPB data scraper")
    ap.add_argument("--seasons", default="current",
                    help="例：current、2025、2018-2024、2015-current、2023,current")
    ap.add_argument("--force", action="store_true", help="忽略快取全部重抓")
    ap.add_argument("--max-boxes", type=int, default=None, help="本次最多抓幾場單場成績（與選手資料）")
    ap.add_argument("--no-boxes", action="store_true", help="只抓賽程")
    args = ap.parse_args(argv)

    years = parse_years(args.seasons)
    failed = []
    for y in years:
        try:
            update_season(y, force=args.force, max_boxes=args.max_boxes, boxes=not args.no_boxes)
        except Exception as e:  # noqa: BLE001
            print(f"{y}: FAILED {e!r}")
            failed.append(y)
    update_index(years)
    if failed and len(failed) == len(years):
        sys.exit(1)


if __name__ == "__main__":
    main()
