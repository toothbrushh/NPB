"""比分備援：npb.jp 連不上時，改從 Yahoo! スポーツナビ 的「日程・結果」頁更新比分。

只更新既有賽程中各場的狀態與比分（已賽／中止），不新增比賽，也不抓單場成績、
個人成績或選手資料；npb.jp 恢復後，下一次正常執行會以官方資料整份重建賽程，
並自動補抓這段期間缺少的單場成績。

頁面：https://baseball.yahoo.co.jp/npb/schedule/?date=YYYY-MM-DD
  每場一個 li.bb-score__item：主隊（homeLogo）在左、客隊（awayLogo）在右，
  比分 span.bb-score__score--left 為主隊、--right 為客隊，
  p.bb-score__link 為狀態（試合終了／試合中止／試合前／進行中的局數…）。
"""

import datetime as dt
import re

from bs4 import BeautifulSoup

from teams import resolve_ja

YAHOO_DAY = "https://baseball.yahoo.co.jp/npb/schedule/?date={date}"
LOOKBACK_DAYS = 14  # 最多往回補幾天（一般只需補 npb.jp 斷線的那幾天）

FINAL_WORDS = ("試合終了",)
POSTPONED_WORDS = ("中止", "ノーゲーム")
PREGAME_WORDS = ("試合前", "見どころ", "予告先発")


def _text(el):
    return el.get_text(strip=True) if el else ""


def parse_yahoo_day(html, date):
    """解析單日頁面，回傳 [{date, home, away, status, homeScore, awayScore, venue}]。

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
        row = {"date": date, "home": home, "away": away,
               "homeScore": None, "awayScore": None,
               "venue": _text(item.select_one(".bb-score__venue")) or None}
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


def dates_to_check(games, today):
    """需要補的日期：今天以前（含今天）仍是「未賽」的比賽所在日，限最近 LOOKBACK_DAYS 天。"""
    first = (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    last = today.isoformat()
    return sorted({g["date"] for g in games
                   if g["status"] == "scheduled" and first <= g["date"] <= last})


def apply_rows(games, rows):
    """把 Yahoo 結果套到既有賽程上；回傳實際更新的場數。

    同一天同一組對戰有兩場（雙重賽）時無法可靠對應，略過不改。
    """
    by_key = {}
    for g in games:
        by_key.setdefault((g["date"], g["home"], g["away"]), []).append(g)
    changed = 0
    for r in rows:
        if r["status"] not in ("final", "postponed"):
            continue
        cands = [g for g in by_key.get((r["date"], r["home"], r["away"]), [])
                 if g["status"] == "scheduled"]
        if len(cands) != 1:
            continue
        g = cands[0]
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
