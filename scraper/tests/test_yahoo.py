"""Yahoo 比分備援的單元測試。

範例 HTML 依 baseball.yahoo.co.jp「日程・結果」頁的結構手寫精簡而成（不收錄原始頁面）。
"""
import datetime as dt
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import npb_scraper as s  # noqa: E402
import yahoo_scores as y  # noqa: E402


def card(home, away, label, left=None, right=None, venue="甲子園", time=None):
    if time:
        status = f'<time class="bb-score__status">{time}</time>'
    else:
        scores = ""
        if left is not None:
            scores += f'<span class="bb-score__score bb-score__score--left">{left}</span>'
        scores += '<span class="bb-score__score bb-score__score--center">-</span>'
        if right is not None:
            scores += f'<span class="bb-score__score bb-score__score--right">{right}</span>'
        status = f'<p class="bb-score__status">{scores}</p>'
    return f"""
<li class="bb-score__item"><a class="bb-score__content" href="/npb/game/1/index">
<p class="bb-score__description"><span class="bb-score__venue">{venue}</span></p>
<div class="bb-score__team">
<p class="bb-score__homeLogo bb-score__homeLogo--npbTeam5">{home}</p>
<p class="bb-score__awayLogo bb-score__awayLogo--npbTeam3">{away}</p></div>
<div class="bb-score__info"><div class="bb-score__wrap"><div class="bb-score__detail">
{status}<p class="bb-score__link">{label}</p></div></div></div></a></li>"""


def page(title, *cards):
    return f"""<html><body>
<header class="bb-head01"><h2 class="bb-head01__title">{title}</h2></header>
<div id="gm_card"><section class="bb-score"><ul class="bb-score__card">{''.join(cards)}</ul></section></div>
</body></html>"""


DAY = page("9月21日（月）",
           card("阪神", "DeNA", "試合終了", 3, 2),
           card("楽天", "ソフトバンク", "試合中止", venue="楽天モバイル"),
           card("日本ハム", "オリックス", "7回裏", 1, 4),
           card("ロッテ", "西武", "試合前", time="18:00"))


def game(date, away, home, status="scheduled"):
    return {"id": f"{date.replace('-', '')}{away}{home}", "date": date, "away": away, "home": home,
            "awayScore": None, "homeScore": None, "status": status, "hasBox": False}


class ParseTest(unittest.TestCase):
    def test_rows(self):
        rows = {(r["home"], r["away"]): r for r in y.parse_yahoo_day(DAY, "2026-09-21")}
        self.assertEqual(rows[("T", "DB")]["status"], "final")
        self.assertEqual((rows[("T", "DB")]["homeScore"], rows[("T", "DB")]["awayScore"]), (3, 2))
        self.assertEqual(rows[("E", "H")]["status"], "postponed")
        self.assertEqual(rows[("F", "B")]["status"], "live")
        self.assertEqual(rows[("M", "L")]["status"], "scheduled")

    def test_wrong_date_is_ignored(self):
        self.assertEqual(y.parse_yahoo_day(DAY, "2026-09-22"), [])
        self.assertEqual(y.parse_yahoo_day(None, "2026-09-21"), [])


class ApplyTest(unittest.TestCase):
    def test_only_final_and_postponed_are_written(self):
        games = [game("2026-09-21", "DB", "T"), game("2026-09-21", "H", "E"),
                 game("2026-09-21", "B", "F"), game("2026-09-21", "L", "M")]
        n = y.apply_rows(games, y.parse_yahoo_day(DAY, "2026-09-21"))
        self.assertEqual(n, 2)
        self.assertEqual((games[0]["status"], games[0]["awayScore"], games[0]["homeScore"]), ("final", 2, 3))
        self.assertEqual(games[0]["scoreSource"], "yahoo")
        self.assertFalse(games[0]["hasBox"])
        self.assertEqual(games[1]["status"], "postponed")
        self.assertEqual(games[2]["status"], "scheduled")
        self.assertIsNone(games[2]["homeScore"])
        self.assertEqual(games[3]["status"], "scheduled")

    def test_already_final_not_touched(self):
        g = game("2026-09-21", "DB", "T", status="final")
        g["awayScore"], g["homeScore"] = 9, 9
        self.assertEqual(y.apply_rows([g], y.parse_yahoo_day(DAY, "2026-09-21")), 0)
        self.assertEqual(g["awayScore"], 9)

    def test_dates_to_check(self):
        boxed = {**game("2026-09-21", "DB", "T", status="final"), "hasBox": True}
        games = [game("2026-09-01", "DB", "T"), game("2026-09-20", "DB", "T"),
                 boxed, game("2026-09-25", "DB", "T")]
        self.assertEqual(y.dates_to_check(games, dt.date(2026, 9, 22)), ["2026-09-20"])
        # 已賽但還沒有單場成績的日子也要再看一次（補單場成績）
        games.append(game("2026-09-19", "G", "S", status="final"))
        self.assertEqual(y.dates_to_check(games, dt.date(2026, 9, 22)), ["2026-09-19", "2026-09-20"])


# 單場頁（結構同 baseball.yahoo.co.jp/npb/game/{ID}/stats）：DeNA（客）@ 阪神（主），3-2
def bat_row(pos, name, nums, plays):
    tds = "".join(f'<td class="bb-statsTable__data">{n}</td>' for n in nums)
    inn = "".join('<td class="bb-statsTable__data bb-statsTable__data--inning">'
                  + "".join(f'<div class="bb-statsTable__dataDetail">{p}</div>' for p in ps) + "</td>"
                  for ps in plays)
    return (f'<tr class="bb-statsTable__row"><td class="bb-statsTable__data bb-statsTable__data--bat">{pos}</td>'
            f'<td class="bb-statsTable__data bb-statsTable__data--player"><a href="/npb/player/1/top">{name}</a></td>'
            f'{tds}{inn}</tr>')


BAT_HEAD = ('<tr class="bb-statsTable__row"><th>位置</th><th>選手名</th>'
            + "".join(f"<th><p>{h}</p></th>" for h in
                      ["打率", "打数", "得点", "安打", "打点", "三振", "四球", "死球", "犠打", "盗塁", "失策", "本塁打"])
            + "<th>1回</th><th>2回</th></tr>")


def bat_total(nums):
    return ('<tr class="bb-statsTable__row--total"><th colspan="2">合計</th><td></td>'
            + "".join(f"<td>{n}</td>" for n in nums) + '<td colspan="2"></td></tr>')


PIT_HEAD = ("<tr><th></th><th>選手名</th>" + "".join(f"<th>{h}</th>" for h in
            ["防御率", "投球回", "投球数", "打者", "被安打", "被本塁打", "奪三振", "与四球", "与死球", "ボーク", "失点", "自責点"])
            + "</tr>")


def pit_row(mark, name, nums):
    return (f'<tr class="bb-scoreTable__row"><td class="bb-scoreTable__data--state">{mark}</td>'
            f'<td><a href="/npb/player/1/top">{name}</a></td>'
            + "".join(f'<td><p class="bb-scoreTable__dataLabel">{n}</p></td>' for n in nums) + "</tr>")


STATS = f"""<html><body>
<table id="ing_brd" class="bb-gameScoreTable"><thead><tr><th></th><th>1</th><th>2</th>
<th>計</th><th>安</th><th>失</th></tr></thead><tbody>
<tr><td><a href="/npb/teams/3/index">DeNA</a></td><td><a>2</a></td><td><a>0</a></td><td>2</td><td>3</td><td>1</td></tr>
<tr><td><a href="/npb/teams/5/index">阪神</a></td><td><a>1</a></td><td><a>2x</a></td><td>3</td><td>4</td><td>0</td></tr>
</tbody></table>
<div id="async-gameBatterStats">
<table class="bb-statsTable bb-statsTable--npbTeam3">{BAT_HEAD}
{bat_row("(左)", "度会 隆輝", [".250", 1, 1, 1, 2, 0, 0, 0, 0, 0, 0, 1], [["左中本"], []])}
{bat_row("打", "宮﨑 敏郎", ["-", 1, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0], [["右安", "三振"], []])}
{bat_total([2, 2, 3, 2, 0, 0, 0, 0, 0, 1, 1])}</table>
<table class="bb-teamScoreTable"><tr><th>DeNA</th></tr></table>
<table class="bb-statsTable bb-statsTable--npbTeam5">{BAT_HEAD}
{bat_row("(中)", "近本 光司", [".300", 2, 1, 2, 3, 0, 0, 0, 0, 1, 0, 0], [["中安"], ["右２"]])}
{bat_total([2, 1, 2, 3, 0, 0, 0, 0, 1, 0, 0])}</table>
</div>
<div id="async-gamePitcherStats">
<table class="bb-scoreTable bb-scoreTable--npbTeam3">{PIT_HEAD}
{pit_row("", "東 克樹", ["2.00", "1.1", 30, 8, 3, 0, 2, 1, 0, 0, 2, 2])}
{pit_row("敗", "伊勢 大夢", ["4.50", "0.1", 10, 3, 1, 0, 0, 0, 0, 0, 1, 1])}</table>
<table class="bb-scoreTable bb-scoreTable--npbTeam5">{PIT_HEAD}
{pit_row("勝", "才木 浩人", ["1.00", "2", 25, 9, 3, 1, 4, 0, 0, 0, 2, 2])}</table>
</div></body></html>"""

INDEX = """<html><body>
<section id="pit_rec"><table>
<tr><th>勝利投手</th><td><span>阪神</span><a class="bb-gameTable__player">才木</a> (1勝0敗0S)</td></tr>
<tr><th>敗戦投手</th><td><span>DeNA</span><a class="bb-gameTable__player">伊勢</a> (0勝1敗0S)</td></tr>
</table></section>
<section id="homerun"><table>
<tr><th>DeNA</th><td><a>度会</a> 1号(1回表2ラン)</td></tr><tr><th>阪神</th><td></td></tr>
</table></section>
<div id="async-attendanceAndGameTime"><table><tr><th>観客数</th><td>42,600人</td>
<th>試合時間</th><td>3時間05分</td></tr></table></div>
</body></html>"""

JS_GAME = {**game("2026-09-21", "DB", "T", status="final"), "awayScore": 2, "homeScore": 3,
           "stage": "regular", "venue": "甲子園", "time": "18:00"}


def no_ids(team, full):
    return full.replace(" ", ""), None


class BoxParseTest(unittest.TestCase):
    def setUp(self):
        self.box = y.parse_yahoo_box(STATS, INDEX, JS_GAME, no_ids)

    def test_ok_and_provisional(self):
        self.assertTrue(self.box["ok"])
        self.assertTrue(self.box["provisional"])

    def test_linescore(self):
        ls = self.box["linescore"]
        self.assertEqual(ls["headers"], ["", "1", "2", "R", "H", "E"])
        self.assertEqual(ls["teams"], ["DB", "T"])
        self.assertEqual(ls["rows"][1], ["", "1", "2x", "3", "4", "0"])

    def test_batting(self):
        b = self.box["teams"]["DB"]["batting"]
        self.assertEqual(b["headers"][:4], ["", "守備", "選手", "打数"])
        self.assertEqual(b["headers"][-2:], ["1", "2"])
        self.assertEqual(b["rows"][0][:6], ["1", "(左)", "度会隆輝", "1", "1", "1"])
        self.assertEqual(b["rows"][0][-2:], ["左中本", "-"])
        self.assertEqual(b["rows"][1][:3], ["", "打", "宮﨑敏郎"])
        self.assertEqual(b["rows"][1][-2], "右安/三振")  # 同一局兩個打席
        total = b["rows"][-1]
        self.assertEqual(total[:7], ["", "", "チーム計", "2", "2", "3", "2"])
        self.assertEqual(total[b["headers"].index("本塁打")], "1")
        self.assertEqual(len(b["pids"]), len(b["rows"]))

    def test_pitching(self):
        p = self.box["teams"]["DB"]["pitching"]
        h = p["headers"]
        self.assertEqual(h[:5], ["", "投手", "投球数", "打者", "投球回"])
        self.assertEqual(p["rows"][0][h.index("投球回")], "1 .1")
        self.assertEqual(p["rows"][0][h.index("三振")], "2")
        self.assertEqual(p["rows"][0][h.index("四球")], "1")
        self.assertEqual(p["rows"][1][0], "●")
        total = p["rows"][-1]
        self.assertEqual(total[1], "チーム計")
        self.assertEqual(total[h.index("投球回")], "1 .2")
        self.assertEqual(total[h.index("投球数")], "40")
        self.assertEqual(self.box["teams"]["T"]["pitching"]["rows"][0][0], "○")
        # 局數與選手頁的出局數換算相容
        self.assertEqual(s.innings_to_outs("1 .1"), 4)

    def test_info(self):
        info = self.box["info"]
        self.assertEqual((info["winP"], info["loseP"]), ("才木", "伊勢"))
        self.assertNotIn("saveP", info)
        self.assertEqual(info["attendance"], 42600)
        self.assertEqual(info["duration"], "3:05")
        self.assertEqual(info["homeRuns"], "［DeNA］度会 1号(1回表2ラン)")
        self.assertEqual((info["venue"], info["start"]), ("甲子園", "18:00"))

    def test_incomplete_page(self):
        self.assertFalse(y.parse_yahoo_box("<html></html>", "", JS_GAME, no_ids)["ok"])


def fake_fetch(url):
    if "/schedule/" in url:
        return DAY
    if url.endswith("/stats"):
        return STATS
    if url.endswith("/index"):
        return INDEX
    raise AssertionError(url)


class FallbackTest(unittest.TestCase):
    def run_fallback(self, old):
        written = {}
        with mock.patch.object(s, "read_json", return_value=old), \
                mock.patch.object(s, "scrape_schedule", side_effect=requests.ConnectTimeout("npb.jp")), \
                mock.patch.object(s, "fetch", side_effect=fake_fetch), \
                mock.patch.object(s, "yahoo_name_resolver", return_value=no_ids), \
                mock.patch.object(s, "write_json", side_effect=lambda p, o, **k: written.__setitem__(p, o)), \
                mock.patch.object(s, "now_jst", return_value=dt.datetime(2026, 9, 22, 1, 0, tzinfo=s.JST)):
            out = s.update_season(2026)
        return out, written

    def test_update_season_falls_back_when_npb_unreachable(self):
        old = {"year": 2026, "updated": "2026-09-20T23:00+09:00", "complete": False,
               "games": [game("2026-09-21", "DB", "T"), game("2026-09-30", "G", "S")]}
        out, written = self.run_fallback(old)
        g = out["games"][0]
        self.assertEqual((g["status"], g["homeScore"], g["yahooId"]), ("final", 3, "1"))
        self.assertEqual(out["games"][1]["status"], "scheduled")
        self.assertNotEqual(out["updated"], old["updated"])
        self.assertEqual(old["games"][0]["status"], "scheduled")  # 原資料未被就地修改
        # 單場成績也一併從 Yahoo 補上
        self.assertTrue(g["hasBox"])
        self.assertEqual((g["winP"], g["attendance"]), ("才木", 42600))
        box = next(o for p, o in written.items() if p.endswith(f"{g['id']}.json"))
        self.assertTrue(box["provisional"])
        self.assertEqual(box["schema"], s.BOX_SCHEMA)
        self.assertIn("/npb/game/1/stats", box["source"])

    def test_box_backfilled_for_game_already_final(self):
        g = {**game("2026-09-21", "DB", "T", status="final"), "awayScore": 2, "homeScore": 3, "scoreSource": "yahoo"}
        out, written = self.run_fallback({"year": 2026, "updated": "x", "complete": False, "games": [g]})
        self.assertTrue(out["games"][0]["hasBox"])
        self.assertTrue(any(p.endswith(f"{g['id']}.json") for p in written))


class ProvisionalReplaceTest(unittest.TestCase):
    """npb.jp 恢復後：有官方單場成績就取代 Yahoo 暫時資料，沒有就先保留。"""

    def run_update(self, official):
        g = {**game("2026-09-21", "DB", "T", status="final"), "id": "2026092101234", "stage": "regular",
             "hasBox": True}
        prov = {"schema": s.BOX_SCHEMA, "provisional": True, "info": {}, "teams": {}}
        written = {}

        def read(path, default=None):
            if path.endswith("schedule.json"):
                return {"year": 2026, "games": [dict(g)]}
            if path.endswith(f"{g['id']}.json"):
                return prov
            return default

        with mock.patch.object(s, "read_json", side_effect=read), \
                mock.patch.object(s, "scrape_schedule", return_value=[dict(g)]), \
                mock.patch.object(s, "enrich_schedule"), \
                mock.patch.object(s, "scrape_box", return_value=official), \
                mock.patch.object(s, "fetch_official_stats", return_value=None), \
                mock.patch.object(s, "update_profiles"), \
                mock.patch.object(s, "build_players", return_value={}), \
                mock.patch.object(s, "write_json", side_effect=lambda p, o, **k: written.__setitem__(p, o)):
            out = s.update_season(2026)
        return out, {p: o for p, o in written.items() if p.endswith(f"{g['id']}.json")}

    def test_official_box_replaces_provisional(self):
        official = {"schema": s.BOX_SCHEMA, "ok": True, "info": {"venue": "甲子園"}, "teams": {}}
        out, boxes = self.run_update(official)
        self.assertEqual(list(boxes.values()), [official])
        self.assertTrue(out["games"][0]["hasBox"])

    def test_provisional_kept_when_official_missing(self):
        out, boxes = self.run_update(None)
        self.assertEqual(boxes, {})
        self.assertTrue(out["games"][0]["hasBox"])

    def test_past_season_still_fails(self):
        old = {"year": 2025, "complete": False, "games": [game("2025-09-21", "DB", "T")]}
        with mock.patch.object(s, "read_json", return_value=old), \
                mock.patch.object(s, "scrape_schedule", side_effect=requests.ConnectTimeout("npb.jp")), \
                mock.patch.object(s, "now_jst", return_value=dt.datetime(2026, 9, 22, tzinfo=s.JST)):
            with self.assertRaises(requests.RequestException):
                s.update_season(2025)


if __name__ == "__main__":
    unittest.main()
