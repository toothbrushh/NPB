"""解析器單元測試（使用手寫的模擬 HTML，結構依 npb.jp 頁面格式）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import npb_scraper as s  # noqa: E402

CALENDAR = """
<table>
<tr>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20250328.html">28</a></div>
<div><a href="/bis/eng/2025/games/s2025032801085.html">T 1 - 3 G</a></div>
<div><a href="/bis/eng/2025/games/s2025032802085.html">DB * - * C</a></div>
</td>
<td><div class="teschedate"><span>29</span></div><div>S - D 14:00</div><div>CL - PL 18:30</div></td>
</tr>
<tr>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20251011.html">11</a></div>
<div class="tescheaten">CS First Stage</div>
<div><a href="/bis/eng/2025/games/s2025101101234.html">DB 6 - 2 G</a></div>
<div><a href="/bis/eng/2025/games/s2025101101235.html">F 3 - 3 B</a></div>
</td>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20251025.html">25</a></div>
<div><a href="/bis/eng/2025/games/s2025102501300.html">T 2 - 1 H</a></div>
</td>
</tr>
</table>
"""

BOX = """
<html><body>
<div>阪神甲子園球場　開始 18:00　終了 21:05　試合時間 3時間05分　入場者 42,600人</div>
<table class="line">
<tr><th>チーム</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th><th>計</th><th>H</th><th>E</th></tr>
<tr><td>巨人</td><td>0</td><td>0</td><td>2</td><td>0</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0</td><td>3</td><td>8</td><td>0</td></tr>
<tr><td>阪神</td><td>0</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>1</td><td>5</td><td>1</td></tr>
</table>
<p>勝投手 戸郷　敗投手 村上　セーブ 大勢</p>
<p>本塁打：岡本 1号(2ラン 村上)</p>
<h3>巨人</h3>
<table><tr><th>打順</th><th>位置</th><th>選手</th><th>打数</th><th>得点</th><th>安打</th><th>打点</th></tr>
<tr><td>1</td><td>(中)</td><td>丸</td><td>4</td><td>1</td><td>2</td><td>0</td></tr>
<tr><td>4</td><td>(三)</td><td><a href="/bis/players/11615137.html">岡本</a></td><td>4</td><td>1</td><td>1</td><td>2</td></tr>
<tr><td></td><td></td><td>計</td><td>8</td><td>2</td><td>3</td><td>2</td></tr>
</table>
<h3>阪神</h3>
<table><tr><th>打順</th><th>位置</th><th>選手</th><th>打数</th><th>得点</th><th>安打</th><th>打点</th></tr>
<tr><td>1</td><td>(中)</td><td>近本</td><td>4</td><td>0</td><td>1</td><td>0</td></tr>
</table>
<h3>巨人</h3>
<table><tr><th></th><th>投手</th><th>投球回</th><th>投球数</th><th>打者</th><th>被安打</th><th>三振</th><th>四球</th><th>失点</th><th>自責点</th></tr>
<tr><td>○</td><td>戸郷</td><td>7 2/3</td><td>110</td><td>28</td><td>4</td><td>8</td><td>1</td><td>1</td><td>1</td></tr>
<tr><td>S</td><td>大勢</td><td>1 1/3</td><td>20</td><td>5</td><td>1</td><td>2</td><td>0</td><td>0</td><td>0</td></tr>
</table>
<h3>阪神</h3>
<table><tr><th></th><th>投手</th><th>投球回</th><th>投球数</th><th>打者</th><th>被安打</th><th>三振</th><th>四球</th><th>失点</th><th>自責点</th></tr>
<tr><td>●</td><td>村上</td><td>8</td><td>100</td><td>30</td><td>8</td><td>6</td><td>1</td><td>3</td><td>3</td></tr>
</table>
</body></html>
"""


PROFILE = """
<html><head><title>岡本 和真（読売ジャイアンツ） | 個人年度別成績 | NPB.jp 日本野球機構</title></head>
<body><img src="/img/common/logo.png"><h1>岡本 和真</h1><p>おかもと・かずま</p>
<img src="/img/player/no/11615137.jpg">
<table><tr><th>ポジション</th><td>内野手</td></tr><tr><th>背番号</th><td>25</td></tr>
<tr><th>投打</th><td>右投右打</td></tr><tr><th>生年月日</th><td>1996年6月30日</td></tr></table>
</body></html>
"""


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.games = s.fix_stages(s.parse_calendar(CALENDAR, 2025, "04"))
        self.by_id = {g["id"]: g for g in self.games}

    def test_final(self):
        g = self.by_id["2025032801085"]
        self.assertEqual((g["away"], g["home"], g["awayScore"], g["homeScore"]), ("T", "G", 1, 3))
        self.assertEqual((g["status"], g["stage"], g["date"]), ("final", "regular", "2025-03-28"))

    def test_postponed(self):
        self.assertEqual(self.by_id["2025032802085"]["status"], "postponed")

    def test_scheduled_and_allstar(self):
        sched = [g for g in self.games if g["status"] == "scheduled"]
        self.assertEqual(len(sched), 2)
        self.assertEqual((sched[0]["away"], sched[0]["time"], sched[0]["date"]), ("S", "14:00", "2025-04-29"))
        self.assertEqual(sched[1]["stage"], "allstar")

    def test_postseason(self):
        self.assertEqual(self.by_id["2025101101234"]["stage"], "cs1")
        self.assertEqual(self.by_id["2025101101235"]["stage"], "cs1")  # 同格沿用標記
        self.assertEqual(self.by_id["2025102501300"]["stage"], "js")   # 無標記的跨聯盟秋季賽


class BoxTest(unittest.TestCase):
    def setUp(self):
        game = {"id": "1", "date": "2025-03-28", "away": "G", "home": "T",
                "awayScore": 3, "homeScore": 1, "stage": "regular"}
        self.box = s.parse_box(BOX, game)

    def test_meta(self):
        info = self.box["info"]
        self.assertEqual(info["venue"], "阪神甲子園球場")
        self.assertEqual(info["start"], "18:00")
        self.assertEqual(info["attendance"], 42600)
        self.assertEqual(info["duration"], "3:05")
        self.assertEqual((info["winP"], info["loseP"], info["saveP"]), ("戸郷", "村上", "大勢"))

    def test_tables(self):
        self.assertTrue(self.box["ok"])
        self.assertEqual(len(self.box["linescore"]["rows"]), 2)
        g = self.box["teams"]["G"]
        self.assertEqual(g["batting"]["rows"][1][2], "岡本")
        self.assertEqual(self.box["teams"]["T"]["batting"]["rows"][0][2], "近本")
        self.assertEqual(self.box["teams"]["T"]["pitching"]["rows"][0][1], "村上")

    def test_player_ids(self):
        self.assertEqual(self.box["teams"]["G"]["batting"]["pids"], [None, "11615137", None])

    def test_profile(self):
        p = s.parse_profile(PROFILE, "11615137")
        self.assertEqual(p["fullName"], "岡本 和真")
        self.assertEqual(p["kana"], "おかもと・かずま")
        self.assertEqual((p["number"], p["position"]), ("25", "内野手"))
        self.assertEqual(p["photo"], "https://npb.jp/img/player/no/11615137.jpg")
        self.assertEqual(p["fields"]["投打"], "右投右打")

    def test_innings(self):
        self.assertEqual(s.innings_to_outs("7 2/3"), 23)
        self.assertEqual(s.innings_to_outs("5.1"), 16)
        self.assertEqual(s.innings_to_outs("8"), 24)
        self.assertEqual(s.innings_to_outs("0/3"), 0)


if __name__ == "__main__":
    unittest.main()
