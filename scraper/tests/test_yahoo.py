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
        games = [game("2026-09-01", "DB", "T"), game("2026-09-20", "DB", "T"),
                 game("2026-09-21", "DB", "T", status="final"), game("2026-09-25", "DB", "T")]
        self.assertEqual(y.dates_to_check(games, dt.date(2026, 9, 22)), ["2026-09-20"])


class FallbackTest(unittest.TestCase):
    def test_update_season_falls_back_when_npb_unreachable(self):
        old = {"year": 2026, "updated": "2026-09-20T23:00+09:00", "complete": False,
               "games": [game("2026-09-21", "DB", "T"), game("2026-09-30", "G", "S")]}
        written = {}
        with mock.patch.object(s, "read_json", return_value=old), \
                mock.patch.object(s, "scrape_schedule", side_effect=requests.ConnectTimeout("npb.jp")), \
                mock.patch.object(s, "fetch", return_value=DAY), \
                mock.patch.object(s, "write_json", side_effect=lambda p, o, **k: written.update(o)), \
                mock.patch.object(s, "now_jst", return_value=dt.datetime(2026, 9, 22, 1, 0, tzinfo=s.JST)):
            out = s.update_season(2026)
        self.assertEqual(out["games"][0]["status"], "final")
        self.assertEqual(out["games"][1]["status"], "scheduled")
        self.assertNotEqual(out["updated"], old["updated"])
        self.assertEqual(written["games"][0]["homeScore"], 3)
        self.assertEqual(old["games"][0]["status"], "scheduled")  # 原資料未被就地修改

    def test_past_season_still_fails(self):
        old = {"year": 2025, "complete": False, "games": [game("2025-09-21", "DB", "T")]}
        with mock.patch.object(s, "read_json", return_value=old), \
                mock.patch.object(s, "scrape_schedule", side_effect=requests.ConnectTimeout("npb.jp")), \
                mock.patch.object(s, "now_jst", return_value=dt.datetime(2026, 9, 22, tzinfo=s.JST)):
            with self.assertRaises(requests.RequestException):
                s.update_season(2025)


if __name__ == "__main__":
    unittest.main()
