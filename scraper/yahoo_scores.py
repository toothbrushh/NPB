"""備援：npb.jp 連不上時，改從 Yahoo! スポーツナビ 補比分與單場成績。

* 比分：「日程・結果」單日頁 https://baseball.yahoo.co.jp/npb/schedule/?date=YYYY-MM-DD
    每場一個 li.bb-score__item：主隊（homeLogo）在左、客隊（awayLogo）在右，
    比分 span.bb-score__score--left 為主隊、--right 為客隊，
    p.bb-score__link 為狀態（試合終了／試合中止／試合前／進行中的局數…），
    a.bb-score__content 連到 /npb/game/{Yahoo 比賽 ID}/index。
* 單場成績：/npb/game/{ID}/stats（逐局比分、打擊成績、投手成績）
            /npb/game/{ID}/index（責任投手、全壘打、觀眾數、比賽時間）

只更新既有賽程，不新增比賽。單場成績轉成與 npb.jp 單場 JSON 相同的格式，並標記
provisional：npb.jp 恢復後，正常流程會以官方資料取代。
"""

import datetime as dt
import re

from bs4 import BeautifulSoup

from teams import resolve_ja

YAHOO = "https://baseball.yahoo.co.jp"
YAHOO_DAY = YAHOO + "/npb/schedule/?date={date}"
YAHOO_GAME = YAHOO + "/npb/game/{yid}/{page}"
LOOKBACK_DAYS = 14  # 最多往回補幾天（一般只需補 npb.jp 斷線的那幾天）

FINAL_WORDS = ("試合終了",)
POSTPONED_WORDS = ("中止", "ノーゲーム")
PREGAME_WORDS = ("試合前", "見どころ", "予告先発")

# Yahoo 打擊表欄位（打率為當季累計，不收）→ 輸出欄位（沿用 npb.jp 表頭）
BAT_COLS = ["打数", "得点", "安打", "打点", "三振", "四球", "死球", "犠打", "盗塁", "失策", "本塁打"]
# Yahoo 投手表欄位 → npb.jp 表頭；輸出依 npb.jp 欄位順序
PIT_MAP = {"投球数": "投球数", "打者": "打者", "投球回": "投球回", "被安打": "安打", "被本塁打": "本塁打",
           "与四球": "四球", "与死球": "死球", "奪三振": "三振", "ボーク": "ボーク", "失点": "失点", "自責点": "自責点"}
PIT_COLS = ["投球数", "打者", "投球回", "安打", "本塁打", "四球", "死球", "三振", "ボーク", "失点", "自責点"]
MARKS = {"勝": "○", "敗": "●", "S": "S", "Ｓ": "S", "セ": "S", "H": "H", "Ｈ": "H"}


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def _int(v):
    v = (v or "").replace(",", "").strip()
    return int(v) if v.isdigit() else None


# ---------------------------------------------------------------- 比分

def parse_yahoo_day(html, date):
    """解析單日頁面，回傳 [{date, home, away, status, homeScore, awayScore, venue, yahooId}]。

    頁面標題的日期與 date 不符時（例如該日無比賽而被導到別天）回傳空清單。
    進行中的比賽回傳 status="live"，呼叫端不應寫入其比分。
    """
    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.select_one(".bb-head01__title")
    m = re.search(r"(\d{1,2})月(\d{1,2})日", _text(title))
    if not m or (int(m.group(1)), int(m.group(2))) != (int(date[5:7]), int(date[8:10])):
        return []

    rows = []
    for item in soup.select("#gm_card li.bb-score__item"):
        home = resolve_ja(_text(item.select_one("[class*=bb-score__homeLogo]")))
        away = resolve_ja(_text(item.select_one("[class*=bb-score__awayLogo]")))
        if not home or not away:
            continue
        label = _text(item.select_one(".bb-score__link"))
        left = _text(item.select_one(".bb-score__score--left"))
        right = _text(item.select_one(".bb-score__score--right"))
        link = item.select_one("a[href*='/npb/game/']")
        ym = re.search(r"/npb/game/(\d+)/", link["href"]) if link else None
        row = {"date": date, "home": home, "away": away,
               "homeScore": None, "awayScore": None,
               "venue": _text(item.select_one(".bb-score__venue")) or None,
               "yahooId": ym.group(1) if ym else None}
        if any(w in label for w in FINAL_WORDS) and left.isdigit() and right.isdigit():
            row["status"] = "final"
            row["homeScore"], row["awayScore"] = int(left), int(right)
        elif any(w in label for w in POSTPONED_WORDS):
            row["status"] = "postponed"
        elif any(w in label for w in PREGAME_WORDS) or not label:
            row["status"] = "scheduled"
        else:
            row["status"] = "live"
        rows.append(row)
    return rows


def needs_box(g):
    return g["status"] == "final" and not g.get("hasBox") and g.get("stage") != "allstar"


def dates_to_check(games, today):
    """需要補的日期：最近 LOOKBACK_DAYS 天內，仍是「未賽」或已賽但還沒有單場成績的比賽所在日。"""
    first = (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    last = today.isoformat()
    return sorted({g["date"] for g in games
                   if (g["status"] == "scheduled" or needs_box(g)) and first <= g["date"] <= last})


def apply_rows(games, rows):
    """把 Yahoo 結果套到既有賽程上（就地修改）；回傳狀態或比分有更新的場數。

    也會記下 Yahoo 比賽 ID（yahooId），供之後抓單場成績。
    同一天同一組對戰有兩場（雙重賽）時無法可靠對應，略過不改。
    """
    by_key = {}
    for g in games:
        by_key.setdefault((g["date"], g["home"], g["away"]), []).append(g)
    changed = 0
    for r in rows:
        cands = by_key.get((r["date"], r["home"], r["away"]), [])
        if len(cands) != 1:
            continue
        g = cands[0]
        if r.get("yahooId"):
            g["yahooId"] = r["yahooId"]
        if r["status"] in ("final", "postponed") and g["status"] == "scheduled":
            g["status"] = r["status"]
            g["homeScore"], g["awayScore"] = r["homeScore"], r["awayScore"]
            g["scoreSource"] = "yahoo"
            changed += 1
    return changed


def update_scores_from_yahoo(games, fetch, today):
    """逐日抓 Yahoo 頁面並更新 games（就地修改）；回傳 (檢查天數, 更新場數)。"""
    days = dates_to_check(games, today)
    changed = 0
    for d in days:
        html = fetch(YAHOO_DAY.format(date=d))
        rows = parse_yahoo_day(html, d)
        n = apply_rows(games, rows)
        print(f"  yahoo {d}: {len(rows)} games on page, {n} updated")
        changed += n
    return len(days), changed


# ---------------------------------------------------------------- 單場成績

def _team_ids(soup):
    """逐局比分表的球隊連結 /npb/teams/{Yahoo 球隊 ID}/ → 球隊代碼；依表格順序（客隊在上）。"""
    out = []
    for a in soup.select("#ing_brd a[href*='/npb/teams/']"):
        m = re.search(r"/npb/teams/(\d+)/", a["href"])
        code = resolve_ja(_text(a))
        if m and code:
            out.append((m.group(1), code))
    return out


def _table_team(table, ids):
    m = re.search(r"--npbTeam(\d+)", " ".join(table.get("class", [])))
    return ids.get(m.group(1)) if m else None


def _ip(v):
    """'6.2' → '6 .2'（npb.jp 單場表寫法）；'7' → '7'。"""
    m = re.fullmatch(r"(\d+)\.([12])", (v or "").strip())
    return f"{m.group(1)} .{m.group(2)}" if m else (v or "").strip()


def _outs(v):
    m = re.fullmatch(r"(\d+)(?:\s*\.([012]))?", (v or "").strip())
    return int(m.group(1)) * 3 + int(m.group(2) or 0) if m else 0


def parse_linescore(soup):
    t = soup.select_one("#ing_brd")
    if not t:
        return None
    heads = [_text(th) for th in t.select("thead th")]
    if len(heads) < 4:
        return None
    headers = [""] + heads[1:-3] + ["R", "H", "E"]
    rows, teams = [], []
    for tr in t.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) != len(heads):
            continue
        teams.append(resolve_ja(_text(tds[0])))
        rows.append([""] + [_text(td) for td in tds[1:]])
    return {"headers": headers, "rows": rows, "teams": teams} if len(rows) == 2 else None


def parse_batting(table, resolve_name):
    """回傳 (npb.jp 格式的打擊表, 選手 ID 清單)。resolve_name(全名) → (顯示名, 選手 ID 或 None)。"""
    head = [_text(th) for th in table.select("tr")[0].find_all(["th", "td"])]
    try:
        ni = head.index("選手名")
    except ValueError:
        return None
    inn = [i for i, h in enumerate(head) if re.fullmatch(r"\d+回", h)]
    col = {h: i for i, h in enumerate(head)}
    headers = ["", "守備", "選手"] + BAT_COLS + [head[i][:-1] for i in inn]
    rows, pids, order = [], [], 0
    for tr in table.select("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if "total" in " ".join(tr.get("class", [])) or (cells and _text(cells[0]) == "合計"):
            # 合計列：第一格跨兩欄（守備＋選手），之後依序為 打率、打数…
            vals = [_text(c) for c in cells[1:]]
            stat = {h: vals[col[h] - ni - 1] if 0 <= col[h] - ni - 1 < len(vals) else ""
                    for h in BAT_COLS if h in col}
            rows.append(["", "", "チーム計"] + [stat.get(h, "") for h in BAT_COLS] + [""] * len(inn))
            pids.append(None)
            continue
        if len(cells) != len(head):
            continue
        pos = _text(cells[0])
        if pos.startswith("("):
            order += 1
        name, pid = resolve_name(_text(cells[ni]))
        plays = []
        for i in inn:
            ds = [d.get_text(strip=True) for d in cells[i].select("div")] or [_text(cells[i])]
            ds = [d for d in ds if d]
            plays.append("/".join(ds) if ds else "-")
        rows.append([str(order) if pos.startswith("(") else "", pos, name]
                    + [_text(cells[col[h]]) if h in col else "" for h in BAT_COLS] + plays)
        pids.append(pid)
    return {"headers": headers, "rows": rows, "pids": pids}


def parse_pitching(table, resolve_name):
    trs = table.select("tr")
    head = [_text(th) for th in trs[0].find_all(["th", "td"])]
    try:
        ni = head.index("選手名")
    except ValueError:
        return None
    col = {PIT_MAP[h]: i for i, h in enumerate(head) if h in PIT_MAP}
    headers = ["", "投手"] + PIT_COLS
    rows, pids = [], []
    tot = {h: 0 for h in PIT_COLS}
    for tr in trs[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) != len(head):
            continue
        name, pid = resolve_name(_text(cells[ni]))
        mark = MARKS.get(_text(cells[0]) if ni > 0 else "", "")
        vals = {h: _text(cells[i]) for h, i in col.items()}
        for h in PIT_COLS:
            if h == "投球回":
                tot[h] += _outs(vals.get(h))
            else:
                tot[h] += _int(vals.get(h)) or 0
        vals["投球回"] = _ip(vals.get("投球回"))
        rows.append([mark, name] + [vals.get(h, "") for h in PIT_COLS])
        pids.append(pid)
    if not rows:
        return None
    o = tot["投球回"]
    tot["投球回"] = f"{o // 3} .{o % 3}" if o % 3 else str(o // 3)
    rows.append(["", "チーム計"] + [str(tot[h]) for h in PIT_COLS])
    pids.append(None)
    return {"headers": headers, "rows": rows, "pids": pids}


def parse_game_info(index_html):
    """比賽首頁：責任投手、全壘打、觀眾數、比賽時間。"""
    soup = BeautifulSoup(index_html or "", "html.parser")
    info = {}
    keys = {"勝利投手": "winP", "敗戦投手": "loseP", "セーブ": "saveP"}
    for tr in soup.select("#pit_rec tr"):
        k = keys.get(_text(tr.find("th")))
        p = tr.select_one(".bb-gameTable__player")
        if k and p:
            info[k] = _text(p)
    hrs = []
    for tr in soup.select("#homerun tr"):
        td = tr.find("td")
        txt = re.sub(r"\s+", " ", td.get_text(" ", strip=True)) if td else ""
        if txt:
            hrs.append(f"［{_text(tr.find('th'))}］{txt}")
    if hrs:
        info["homeRuns"] = " / ".join(hrs)
    for th in soup.select("#async-attendanceAndGameTime th"):
        val = _text(th.find_next_sibling("td"))
        if _text(th) == "観客数" and _int(re.sub(r"[^\d]", "", val)) is not None:
            info["attendance"] = _int(re.sub(r"[^\d]", "", val))
        elif _text(th) == "試合時間":
            m = re.search(r"(\d+)時間(\d+)分", val)
            if m:
                info["duration"] = f"{int(m.group(1))}:{int(m.group(2)):02d}"
    return info


def parse_yahoo_box(stats_html, index_html, game, resolve_name):
    """把 Yahoo 單場頁轉成 npb.jp 單場 JSON 的格式。resolve_name(球隊代碼, 全名) → (顯示名, 選手 ID)。"""
    soup = BeautifulSoup(stats_html or "", "html.parser")
    ids = dict(_team_ids(soup))
    teams = {}
    for kind, sel, parser in (("batting", "#async-gameBatterStats table.bb-statsTable", parse_batting),
                              ("pitching", "#async-gamePitcherStats table.bb-scoreTable", parse_pitching)):
        for table in soup.select(sel):
            code = _table_team(table, ids)
            if code not in (game["away"], game["home"]):
                continue
            t = parser(table, lambda full, c=code: resolve_name(c, full))
            if t:
                teams.setdefault(code, {})[kind] = t
    info = {k: v for k, v in (("venue", game.get("venue")), ("start", game.get("time"))) if v}
    info.update(parse_game_info(index_html))
    ok = all(teams.get(c, {}).get("batting") and teams.get(c, {}).get("pitching")
             for c in (game["away"], game["home"]))
    return {"id": game["id"], "schema": None, "date": game["date"], "away": game["away"], "home": game["home"],
            "awayScore": game.get("awayScore"), "homeScore": game.get("homeScore"), "stage": game.get("stage"),
            "linescore": parse_linescore(soup), "teams": teams, "info": info, "ok": ok, "provisional": True}
