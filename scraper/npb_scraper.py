#!/usr/bin/env python3
"""
NPB 賽程 / 比分 / 個人成績爬蟲。

資料來源：日本野球機構官方網站 npb.jp
  * 月曆（賽程與比分）：https://npb.jp/bis/eng/{年}/calendar/index_{月}.html
  * 單場成績：          https://npb.jp/bis/{年}/games/s{比賽ID}.html
  * 場地補充（未賽）：  https://npb.jp/games/{年}/schedule_{月}_detail.html

輸出（皆為靜態 JSON，供網頁直接讀取）：
  data/seasons.json                 各年度清單
  data/{年}/schedule.json           該年度全部比賽（季賽、明星賽、季後賽）
  data/{年}/games/{比賽ID}.json      單場詳細（比分、上場名單、個人當場數據）
  data/{年}/players.json            依單場成績累計的年度個人成績

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
BOX_SCHEMA = 1  # 解析器版本；調高可讓舊的單場資料在下次執行時重抓

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


# ---------------------------------------------------------------- 賽程（月曆）

STAGE_PATTERNS = [
    (r"all.?star|オールスター", "allstar", "明星賽"),
    (r"first", "cs1", "高潮系列賽 第一階段"),
    (r"final", "cs2", "高潮系列賽 最終階段"),
    (r"climax|\bcs\b|クライマックス", "cs", "高潮系列賽"),
    (r"japan series|nippon series|日本シリーズ|smbc", "js", "日本一系列賽"),
]

STAGE_LABELS = {"regular": "例行賽", "allstar": "明星賽", "cs1": "高潮系列賽 第一階段",
                "cs2": "高潮系列賽 最終階段", "cs": "高潮系列賽", "js": "日本一系列賽"}


def classify_stage(marker):
    m = (marker or "").lower()
    for pat, code, _ in STAGE_PATTERNS:
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

    已賽：<a href=".../games/s2025032801085.html">G 3 - 1 T</a>（左客右主）
    延賽：<a ...>G * - * T</a>
    未賽：<div>C - DB 18:00</div>
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
                gid, away, a_s, h_s, home = m.groups()
                g = new_game(gid, date, away, home, marker)
                if "*" in (a_s + h_s):
                    g["status"] = "postponed"
                else:
                    g["status"] = "final"
                    g["awayScore"], g["homeScore"] = int(a_s), int(h_s)
            else:
                away, home, t = m.groups()
                g = new_game(None, date, away, home, marker)
                g["time"] = t.zfill(5)
            if g:
                games.append(g)
    return games


def new_game(gid, date, away, home, marker):
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
    """沒有標記時用規則推論季後賽：例行賽最後一天之後的比賽。"""
    reg = [g for g in games if g["stage"] == "regular"]
    league = lambda c: TEAMS.get(c, {}).get("league")
    for g in reg:
        if g["date"][5:7] not in ("10", "11"):
            continue
        la, lh = league(g["away"]), league(g["home"])
        if la and lh and la != lh:
            g["stage"] = "js"  # 10–11 月的跨聯盟比賽只可能是日本一系列賽
    for g in games:
        g["stageName"] = STAGE_LABELS.get(g["stage"], g["stage"])
    return games


def scrape_schedule(year, old_games):
    """抓整季月曆；過去已抓過的資訊（場地、成績有無）會保留。"""
    games = []
    for mm in MONTHS:
        url = f"{BASE}/bis/eng/{year}/calendar/index_{mm}.html"
        html = fetch(url)
        if html is None:
            continue
        got = parse_calendar(html, year, mm)
        print(f"  calendar {year}-{mm}: {len(got)} games")
        games.extend(got)

    # 去重（3 月與 4 月可能在同一頁）
    uniq = {}
    for g in games:
        key = g["id"]
        if g["status"] == "scheduled":
            # 已賽版本優先，避免同場既是未賽又是已賽
            key = (g["date"], g["away"], g["home"])
        uniq.setdefault(key, g)
    played = {(g["date"], g["away"], g["home"]) for g in uniq.values() if g["status"] != "scheduled"}
    games = [g for k, g in uniq.items()
             if not (g["status"] == "scheduled" and (g["date"], g["away"], g["home"]) in played)]

    old = {g["id"]: g for g in old_games}
    for g in games:
        o = old.get(g["id"])
        if o:
            for k in ("venue", "venueSource", "time", "hasBox", "attendance", "duration",
                      "winP", "loseP", "saveP"):
                if g.get(k) in (None, False) and o.get(k) not in (None, False):
                    g[k] = o[k]
    games.sort(key=lambda g: (g["date"], g.get("time") or "99", g["id"]))
    return fix_stages(games)


# ---------------------------------------------------------------- 場地補充（日文賽程頁）

def enrich_venues(year, games, months):
    """未賽比賽在月曆上沒有球場，從日文賽程頁盡力補上；失敗不影響其他流程。"""
    need = {}
    for g in games:
        if not g.get("venue"):
            need.setdefault(g["date"], []).append(g)
    if not need:
        return
    for mm in months:
        try:
            html = fetch(f"{BASE}/games/{year}/schedule_{mm}_detail.html")
        except Exception as e:  # noqa: BLE001
            print(f"  schedule detail {mm} failed: {e}")
            continue
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        cur_date = None
        hit = 0
        for tr in soup.find_all("tr"):
            text = clean(tr.get_text(" "))
            dm = re.search(r"(\d{1,2})\s*[/月]\s*(\d{1,2})", text)
            if dm and 1 <= int(dm.group(1)) <= 12:
                cur_date = f"{year}-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
            if not cur_date or cur_date not in need:
                continue
            codes = teams_in_text(text)
            if len(codes) < 2:
                continue
            venue = find_venue(text)
            tm = re.search(r"(\d{1,2}):(\d{2})", text)
            for g in need[cur_date]:
                if {g["away"], g["home"]} == set(codes[:2]):
                    if venue and not g.get("venue"):
                        g["venue"], g["venueSource"] = venue, "schedule"
                        hit += 1
                    if tm and not g.get("time"):
                        g["time"] = f"{int(tm.group(1)):02d}:{tm.group(2)}"
        print(f"  schedule detail {year}-{mm}: venues filled {hit}")


def teams_in_text(text):
    from teams import JA_NAMES
    found = []
    for name, code in sorted(JA_NAMES.items(), key=lambda kv: -len(kv[0])):
        idx = text.find(name)
        if idx >= 0 and code not in [c for _, c in found]:
            found.append((idx, code))
            text = text.replace(name, "　" * len(name))
    return [c for _, c in sorted(found)]


def find_venue(text):
    for v in VENUES:
        if v in text:
            return v
    m = re.search(r"([^\s\d:()（）]{2,20}(?:球場|ドーム|スタジアム|フィールド|パーク[^\s]*))", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 單場成績

BAT_KEYS = ["打数", "AB"]
PIT_KEYS = ["投球回", "IP", "回数", "投球数", "NP"]
TOTAL_NAMES = {"計", "合計", "チーム計", "Totals", "Total", "TOTAL", "TOTALS"}
PLAYER_LINK_RE = re.compile(r"/bis/(?:eng/)?players/(\d+)\.html")


def table_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        row = [clean(c.get_text(" ")) for c in cells]
        # 展開 colspan，讓欄位對齊表頭
        out = []
        for c, txt in zip(cells, row):
            try:
                span = int(c.get("colspan", 1))
            except ValueError:
                span = 1
            out.append(txt)
            out.extend([""] * (min(span, 30) - 1))
        # 選手連結 → npb.jp 選手 ID（用於選手頁、照片、個人資料）
        pid = None
        for a in tr.find_all("a", href=True):
            m = PLAYER_LINK_RE.search(a["href"])
            if m:
                pid = m.group(1)
                break
        rows.append((out, all(c.name == "th" for c in cells), pid))
    return rows


def is_header(row, keys):
    return any(cell in keys for cell in row)


def split_table(rows, keys):
    """回傳 (表頭, 資料列, 各列選手 ID)。"""
    for i, (row, _, _) in enumerate(rows):
        if is_header(row, keys):
            body = [(r, pid) for r, _, pid in rows[i + 1:] if any(r) and not is_header(r, keys)]
            return row, [r for r, _ in body], [pid for _, pid in body]
    return None, [], []


def team_near(table):
    """往表格前面找最近出現的隊名。"""
    n = 0
    for s in table.find_all_previous(string=True):
        t = clean(s)
        if not t:
            continue
        code = resolve_ja(t)
        if code:
            return code
        for c, info in TEAMS.items():
            if info["ja"] in t:
                return c
        n += 1
        if n > 8:
            break
    return None


def parse_linescore(table):
    rows = table_rows(table)
    for i, (row, _, _) in enumerate(rows):
        nums = [c for c in row if re.fullmatch(r"\d{1,2}", c)]
        if nums[:3] == ["1", "2", "3"] and any(c in ("計", "R", "得点") for c in row):
            data = [r for r, _, _ in rows[i + 1:i + 3] if any(r)]
            return {"headers": row, "rows": data}
    return None


def parse_box(html, game):
    soup = BeautifulSoup(html, "html.parser")
    text = clean(soup.get_text(" "))
    box = {"id": game["id"], "schema": BOX_SCHEMA, "date": game["date"],
           "away": game["away"], "home": game["home"],
           "awayScore": game.get("awayScore"), "homeScore": game.get("homeScore"),
           "stage": game.get("stage"), "linescore": None,
           "teams": {game["away"]: {"batting": None, "pitching": None},
                     game["home"]: {"batting": None, "pitching": None}},
           "info": {}}

    leaves = [t for t in soup.find_all("table") if not t.find("table")]
    bat_tables, pit_tables = [], []
    for t in leaves:
        rows = table_rows(t)
        flat = [c for r, _, _ in rows for c in r]
        if box["linescore"] is None:
            ls = parse_linescore(t)
            if ls:
                box["linescore"] = ls
                continue
        if any(k in flat for k in BAT_KEYS):
            h, d, ids = split_table(rows, BAT_KEYS)
            if h and d:
                bat_tables.append((t, h, d, ids))
        elif any(k in flat for k in PIT_KEYS):
            h, d, ids = split_table(rows, PIT_KEYS)
            if h and d:
                pit_tables.append((t, h, d, ids))

    order = [game["away"], game["home"]]  # 慣例：先攻（客隊）在前
    for kind, tables in (("batting", bat_tables), ("pitching", pit_tables)):
        used = set()
        for idx, (t, h, d, ids) in enumerate(tables):
            code = team_near(t)
            if code not in order or code in used:
                code = next((c for c in order if c not in used), None) if idx < 2 else None
            if code is None:
                continue
            used.add(code)
            box["teams"][code][kind] = {"headers": h, "rows": d}
            if any(ids):
                box["teams"][code][kind]["pids"] = ids

    info = box["info"]
    m = re.search(r"([\d,]{3,})\s*人", text) or re.search(r"(?:入場者数?|Att(?:endance)?\.?)\s*[:：]?\s*([\d,]+)", text)
    if m:
        info["attendance"] = int(m.group(1).replace(",", ""))
    m = re.search(r"(?:開始|Start)\s*[:：]?\s*(\d{1,2})\s*[:：時]\s*(\d{2})", text)
    if m:
        info["start"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"(?:試合時間|Time of Game|Time)\s*[:：]?\s*(\d{1,2})\s*(?:[:：]|時間)\s*(\d{1,2})", text)
    if m:
        info["duration"] = f"{int(m.group(1))}:{int(m.group(2)):02d}"
    venue = find_venue(text)
    if venue:
        info["venue"] = venue
    for key, pats in (("winP", [r"勝(?:利)?投手", r"\bWP\b", r"Winning Pitcher"]),
                      ("loseP", [r"敗(?:戦)?投手", r"\bLP\b", r"Losing Pitcher"]),
                      ("saveP", [r"セーブ", r"\bSV\b", r"Save"])):
        for p in pats:
            m = re.search(p + r"\s*[:：]?\s*[［\[(（]?\s*([^\s\]］)）0-9]{1,12})", text)
            if m:
                info[key] = m.group(1)
                break
    m = re.search(r"(?:本塁打|HR)\s*[:：]\s*(.{1,200}?)(?:二塁打|三塁打|盗塁|審判|$)", text)
    if m:
        info["homeRuns"] = clean(m.group(1))
    m = re.search(r"(?:審判|Umpires?)\s*[:：]?\s*(.{1,80}?)(?:試合時間|入場者|$)", text)
    if m:
        info["umpires"] = clean(m.group(1))

    box["ok"] = bool(bat_tables) or box["linescore"] is not None
    return box


def scrape_box(year, game):
    for url in (f"{BASE}/bis/{year}/games/s{game['id']}.html",
                f"{BASE}/bis/eng/{year}/games/s{game['id']}.html"):
        try:
            html = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"  box {game['id']} {url} failed: {e}")
            continue
        if html:
            box = parse_box(html, game)
            box["source"] = url
            if box["ok"]:
                return box
    return None


# ---------------------------------------------------------------- 年度個人成績

def col(headers, *names):
    for n in names:
        for i, h in enumerate(headers):
            if h == n:
                return i
    for n in names:
        for i, h in enumerate(headers):
            if n in h and len(h) <= len(n) + 2:
                return i
    return None


def name_col(headers, rows, pitching=False):
    if pitching:
        i = col(headers, "投手", "投手名", "選手", "選手名", "Player", "Name", "PITCHERS", "Pitcher")
    else:
        i = col(headers, "選手", "選手名", "打者", "Player", "Name", "BATTERS", "Batter")
    if i is not None:
        return i
    # 退而求其次：第一個「看起來像人名」的欄位
    for i in range(len(headers)):
        vals = [r[i] for r in rows if i < len(r)]
        if vals and sum(bool(re.search(r"[^\d\s.\-/()（）]", v)) and len(v) >= 2 for v in vals) > len(vals) * 0.6:
            return i
    return 0


def num(v):
    v = (v or "").replace(",", "").strip()
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return 0


def innings_to_outs(v):
    v = clean(v).replace("⅓", " 1/3").replace("⅔", " 2/3")
    m = re.fullmatch(r"(\d+)?\s*(?:\+?\s*([12])\s*/\s*3)?", v)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 3 + int(m.group(2) or 0)
    m = re.fullmatch(r"(\d+)\.([012])", v)
    if m:
        return int(m.group(1)) * 3 + int(m.group(2))
    return 0


BAT_STATS = {"G": None, "AB": ("打数", "AB"), "R": ("得点", "R"), "H": ("安打", "H"),
             "RBI": ("打点", "RBI"), "HR": ("本塁打", "HR"), "BB": ("四球", "四死球", "BB"),
             "SO": ("三振", "SO"), "SB": ("盗塁", "SB")}
PIT_STATS = {"G": None, "OUTS": None, "H": ("被安打", "安打", "H"), "R": ("失点", "R"),
             "ER": ("自責点", "自責", "ER"), "BB": ("四球", "与四球", "四死球", "BB"),
             "SO": ("三振", "奪三振", "SO"), "NP": ("投球数", "球数", "NP"),
             "W": None, "L": None, "SV": None}


BAT_LOG = ["AB", "R", "H", "RBI", "HR", "BB", "SO", "SB"]
PIT_LOG = ["OUTS", "H", "R", "ER", "BB", "SO", "NP"]


def player_key(pid, team, name):
    """有 npb.jp 選手 ID 就用 ID，否則用「隊伍_姓名」。"""
    return pid if pid else f"{team}_{re.sub(r'[^0-9A-Za-z一-鿿ぁ-んァ-ヿ々ー]', '', name)}"


def build_players(year, games):
    """累計年度個人成績，並輸出每位選手的逐場紀錄 data/{年}/players/{key}.json。"""
    bat, pit, logs = {}, {}, {}
    gdir = os.path.join(DATA, str(year), "games")
    for g in games:
        if g["stage"] != "regular" or not g.get("hasBox"):
            continue
        box = read_json(os.path.join(gdir, f"{g['id']}.json"))
        if not box:
            continue
        info = box.get("info", {})
        for team, t in box.get("teams", {}).items():
            opp = g["home"] if team == g["away"] else g["away"]
            ha = "A" if team == g["away"] else "H"
            b = t.get("batting")
            if b and b.get("headers"):
                h, rows, pids = b["headers"], b["rows"], b.get("pids") or []
                ni = name_col(h, rows)
                idx = {k: (col(h, *v) if v else None) for k, v in BAT_STATS.items()}
                for ri, r in enumerate(rows):
                    nm = clean(r[ni] if ni < len(r) else "").lstrip("()（）")
                    if not nm or nm in TOTAL_NAMES or re.fullmatch(r"[\d\s]+", nm):
                        continue
                    pid = pids[ri] if ri < len(pids) else None
                    key = player_key(pid, team, nm)
                    p = bat.setdefault(key, {"key": key, "id": pid, "team": team, "name": nm,
                                             **{k: 0 for k in BAT_STATS}})
                    p["team"] = team
                    p["G"] += 1
                    line = {k: 0 for k in BAT_LOG}
                    for k, i in idx.items():
                        if i is not None and i < len(r):
                            p[k] += num(r[i])
                            if k in line:
                                line[k] = num(r[i])
                    lg = logs.setdefault(key, {"key": key, "id": pid, "name": nm, "team": team, "bat": [], "pit": []})
                    lg["bat"].append([g["id"], g["date"], opp, ha] + [line[k] for k in BAT_LOG])
            for pt in [t["pitching"]] if t.get("pitching") else []:
                h, rows, pids = pt["headers"], pt["rows"], pt.get("pids") or []
                ni = name_col(h, rows, pitching=True)
                ip_i = col(h, "投球回", "IP", "回数")
                idx = {k: (col(h, *v) if v else None) for k, v in PIT_STATS.items()}
                for ri, r in enumerate(rows):
                    nm = clean(r[ni] if ni < len(r) else "")
                    if not nm or nm in TOTAL_NAMES:
                        continue
                    nm_plain = re.sub(r"^(?:[○●◯△]\s*|[勝敗SHＳＨ]\s+)|\s*[(（].*$", "", nm).strip()
                    pid = pids[ri] if ri < len(pids) else None
                    key = player_key(pid, team, nm_plain)
                    p = pit.setdefault(key, {"key": key, "id": pid, "team": team, "name": nm_plain,
                                             **{k: 0 for k in PIT_STATS}})
                    p["team"] = team
                    p["G"] += 1
                    line = {k: 0 for k in PIT_LOG}
                    if ip_i is not None and ip_i < len(r):
                        outs = innings_to_outs(r[ip_i])
                        # 部分頁面把 1/3 局拆成下一欄
                        if ip_i + 1 < len(r) and re.fullmatch(r"[12]\s*/\s*3", r[ip_i + 1] or ""):
                            outs += int(r[ip_i + 1].strip()[0])
                        p["OUTS"] += outs
                        line["OUTS"] = outs
                    for k, i in idx.items():
                        if i is not None and i < len(r):
                            p[k] += num(r[i])
                            if k in line:
                                line[k] = num(r[i])
                    dec = ""
                    for key_, stat in (("winP", "W"), ("loseP", "L"), ("saveP", "SV")):
                        if info.get(key_) and info[key_] in nm_plain:
                            p[stat] += 1
                            dec = stat
                    lg = logs.setdefault(key, {"key": key, "id": pid, "name": nm_plain, "team": team, "bat": [], "pit": []})
                    lg["pit"].append([g["id"], g["date"], opp, ha] + [line[k] for k in PIT_LOG] + [dec])
    for p in bat.values():
        p["AVG"] = round(p["H"] / p["AB"], 3) if p["AB"] else None
    for p in pit.values():
        ip = p["OUTS"] / 3
        p["IP"] = f"{p['OUTS'] // 3}" + ("" if p["OUTS"] % 3 == 0 else f" {p['OUTS'] % 3}/3")
        p["ERA"] = round(p["ER"] * 9 / ip, 2) if ip else None

    # 合併選手個人資料（照片、全名、背號、守備位置）
    for p in list(bat.values()) + list(pit.values()):
        prof = read_json(os.path.join(DATA, "players", f"{p['id']}.json")) if p.get("id") else None
        if prof:
            for k in ("fullName", "kana", "photo", "number", "position"):
                if prof.get(k):
                    p[k] = prof[k]

    pdir = os.path.join(DATA, str(year), "players")
    for key, lg in logs.items():
        lg["batCols"], lg["pitCols"] = BAT_LOG, PIT_LOG + ["DEC"]
        write_json(os.path.join(pdir, f"{key}.json"), lg)
    return {"year": year, "batting": sorted(bat.values(), key=lambda p: (-p["AB"], p["name"])),
            "pitching": sorted(pit.values(), key=lambda p: (-p["OUTS"], p["name"]))}


# ---------------------------------------------------------------- 選手個人資料

PROFILE_KEYS = ["ポジション", "投打", "身長／体重", "身長/体重", "生年月日", "経歴", "ドラフト",
                "出身地", "背番号", "Position", "Bats / Throws", "Height / Weight", "Born", "Draft"]
KANA_RE = re.compile(r"^[ぁ-んァ-ヶー・\s　]{3,}$")


def parse_profile(html, pid):
    soup = BeautifulSoup(html, "html.parser")
    prof = {"id": pid, "url": f"{BASE}/bis/players/{pid}.html"}
    title = clean(soup.title.get_text()) if soup.title else ""
    name = re.split(r"[（(|｜]", title)[0].strip() if title else ""
    h1 = soup.find(["h1", "h2"])
    if not name and h1:
        name = clean(h1.get_text())
    if name:
        prof["fullName"] = name
    for st in soup.find_all(string=True):
        t = clean(st)
        if KANA_RE.match(t) and len(t) <= 20:
            prof["kana"] = t
            break
    fields = {}
    for tr in soup.find_all("tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            k, v = clean(th.get_text()), clean(td.get_text(" "))
            if k and v and len(k) <= 12 and len(v) <= 160:
                fields.setdefault(k, v)
    for dt_ in soup.find_all("dt"):
        dd = dt_.find_next_sibling("dd")
        if dd:
            k, v = clean(dt_.get_text()), clean(dd.get_text(" "))
            if k and v and len(k) <= 12 and len(v) <= 160:
                fields.setdefault(k, v)
    prof["fields"] = {k: v for k, v in fields.items() if any(pk in k for pk in PROFILE_KEYS)}
    for k, v in fields.items():
        if "ポジション" in k or k == "Position":
            prof["position"] = v
        if "背番号" in k:
            prof["number"] = re.sub(r"\D", "", v) or v
    if "number" not in prof:
        m = re.search(r"背番号\s*[:：]?\s*(\d{1,3})", clean(soup.get_text(" ")))
        if m:
            prof["number"] = m.group(1)
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if re.search(r"logo|icon|banner|btn|arrow|common/|sns", src, re.I):
            continue
        if re.search(r"player|photo|/\d{6,}", src, re.I):
            prof["photo"] = requests.compat.urljoin(prof["url"], src)
            break
    prof["fetched"] = now_jst().date().isoformat()
    return prof


def update_profiles(games, year, limit=None):
    """抓取本季新出現的選手個人資料（每位選手只抓一次，存在 data/players/{id}.json）。"""
    pids = set()
    gdir = os.path.join(DATA, str(year), "games")
    for g in games:
        if not g.get("hasBox"):
            continue
        box = read_json(os.path.join(gdir, f"{g['id']}.json")) or {}
        for t in box.get("teams", {}).values():
            for kind in ("batting", "pitching"):
                pids.update(x for x in ((t.get(kind) or {}).get("pids") or []) if x)
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
        print(f"{year}: fetched {n} player profiles")
    return n


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

    # 未賽的比賽補場地（只看還有未賽比賽的月份）
    pending_months = sorted({g["date"][5:7] for g in games if g["status"] == "scheduled"})
    if pending_months:
        enrich_venues(year, games, pending_months)

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

    today = now_jst().date().isoformat()
    complete = (year < now_jst().year
                and all(g["status"] != "scheduled" for g in games)
                and all(g["hasBox"] for g in games if g["status"] == "final" and g["id"].isdigit()))
    out = {"year": year, "updated": now_jst().isoformat(timespec="minutes"),
           "complete": complete, "games": games}
    changed = write_json(sched_path, out, pretty=False)
    profiles = update_profiles(games, year, limit=max_boxes) if boxes else 0
    if changed or profiles or not os.path.exists(os.path.join(ydir, "players.json")):
        out_players = build_players(year, games)
        write_json(os.path.join(ydir, "players.json"), out_players)
    else:
        # 沒變化時保留原 updated 時間
        out = read_json(sched_path, out)
    nf = sum(g["status"] == "final" for g in games)
    print(f"{year}: {len(games)} games, {nf} final, complete={complete}, boxes fetched={fetched}, today={today}")
    return out


def update_index(years_touched):
    path = os.path.join(DATA, "seasons.json")
    idx = {s["year"]: s for s in (read_json(path, {}) or {}).get("seasons", [])}
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
            years.update(range(int(a), int(b) + 1))
        else:
            years.add(int(part))
    return sorted(years, reverse=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NPB data scraper")
    ap.add_argument("--seasons", default="current",
                    help="例：current、2025、2018-2024、2023,current")
    ap.add_argument("--force", action="store_true", help="忽略快取全部重抓")
    ap.add_argument("--max-boxes", type=int, default=None, help="本次最多抓幾場單場成績")
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
