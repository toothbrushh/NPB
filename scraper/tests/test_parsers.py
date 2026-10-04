"""解析器單元測試。

範例 HTML 依 npb.jp 實際頁面結構手寫精簡而成（不收錄官方原始頁面）。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import npb_scraper as s  # noqa: E402

# 英文版月曆：主隊在左
CALENDAR = """
<table><tr>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20250328.html">28</a></div>
<div><a href="/bis/eng/2025/games/s2025032800105.html">G 6 - 5 S</a></div>
<div><a href="/bis/eng/2025/games/s2025032800106.html">DB * - * D</a></div></td>
<td><div class="teschedate"><span>29</span></div><div>S - C 14:00</div><div>CL - PL 18:30</div></td>
</tr><tr>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20251011.html">11</a></div>
<div class="tescheaten">CS First Stage</div>
<div><a href="/bis/eng/2025/games/s2025101101985.html">DB 6 - 2 G</a></div>
<div class="tescheaten">CS First Stage</div>
<div><a href="/bis/eng/2025/games/s2025101101988.html">F 2 - 0 B</a></div></td>
<td><div class="teschedate"><a href="/bis/eng/2025/games/gm20251025.html">25</a></div>
<div><a href="/bis/eng/2025/games/s2025102502002.html">H 1 - 2 T</a></div></td>
</tr></table>
"""

# 日文單場頁（結構同 npb.jp/bis/{年}/games/s{ID}.html）
BOX = """
<html><body>
<div id="header_score">2026 10/4 Sun. - （神　宮） 18:00</div>
<div>2025年3月28日 (金)</div>
<table><tr><td class="flagteam"></td><td class="contentshdname">読売ジャイアンツ</td><td class="gmboxrun">6</td></tr></table>
<table><tr><td class="flagteam"></td><td class="contentshdname">東京ヤクルトスワローズ</td><td class="gmboxrun">5</td></tr></table>
<table><tr><td>東京ドーム</td><td>試合時間 - 3：26　( 開始18:19　終了21:45 )　　入場者 - 42,270</td></tr></table>
<div>1回戦　( ［巨］1勝0敗0分 )</div>
<table>
<tr><td class="gmscorettl"></td><td class="gmscorettl">Ｒ</td><td class="gmscorettl">Ｈ</td><td class="gmscorettl">Ｅ</td></tr>
<tr><td class="gmscoreteam">東京ヤクルト</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscspan"></td>
<td class="gmscore">0</td><td class="gmscore">4</td><td class="gmscore">1</td><td class="gmscspan"></td>
<td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscspan"></td>
<td class="gmscore">0</td><td class="gmscore">-</td><td class="gmscore">5</td><td class="gmscore">8</td><td class="gmscore">0</td></tr>
<tr><td class="gmscoreteam">読　売</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscspan"></td>
<td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscore">0</td><td class="gmscspan"></td>
<td class="gmscore">0</td><td class="gmscore">2</td><td class="gmscore">3</td><td class="gmscspan"></td>
<td class="gmscore">1X</td><td class="gmscore">-</td><td class="gmscore">6</td><td class="gmscore">17</td><td class="gmscore">1</td></tr>
<tr><td class="gmresults">( 延長10回 )</td></tr>
</table>
<table><tr><td class="gmresunm">勝投手 ：</td><td class="gmresults">マルティネス ( 1勝0敗 )</td></tr>
<tr><td class="gmresunm">敗投手 ：</td><td class="gmresults">清水 ( 0勝1敗 )</td></tr></table>
<table><tr><td class="gmresunm">本塁打 ：</td><td class="gmresults">［ヤ］ サンタナ 1号 ( 6回1点 堀田 )</td></tr>
<tr><td class="gmresunm"></td><td class="gmresults">［巨］ キャベッジ 1号 ( 8回2点 山本 )</td></tr></table>
<table><tr><td class="flagteam2"></td><td class="gmtblteam">東京ヤクルト</td></tr></table>
<table><tr><td class="flagteam2"></td><td class="gmtblteam">読　売</td></tr></table>
<table class="gmtbltop">
<tr><th class="gmhdpos"></th><th></th><th>打<br>数</th><th>安<br>打</th><th>打<br>点</th><th>四<br>球</th><th>死<br>球</th><th>三<br>振</th></tr>
<tr><td>(右)左</td><td>西川</td><td>5</td><td>1</td><td>1</td><td>0</td><td>0</td><td>1</td></tr>
<tr><td>(捕)</td><td>中村悠</td><td>4</td><td>1</td><td>2</td><td>0</td><td>0</td><td>0</td></tr>
</table>
<table class="gmtbltop">
<tr><th class="gmhdpos"></th><th></th><th>打<br>数</th><th>安<br>打</th><th>打<br>点</th><th>四<br>球</th><th>死<br>球</th><th>三<br>振</th></tr>
<tr><td>(一)</td><td>岡本</td><td>5</td><td>1</td><td>0</td><td>0</td><td>0</td><td>1</td></tr>
</table>
<table class="gmtbltop">
<tr><th class="gmhdpos"></th><th></th><th>投<br>回</th><th class="gmhdip2"></th><th>打<br>者</th><th>安<br>打</th><th>四<br>球</th><th>死<br>球</th><th>三<br>振</th><th>自<br>責</th></tr>
<tr><td></td><td>奥川</td><td>6</td><td></td><td>24</td><td>7</td><td>0</td><td>0</td><td>2</td><td>0</td></tr>
<tr><td></td><td>山本</td><td></td><td>+</td><td>3</td><td>2</td><td>1</td><td>0</td><td>0</td><td>2</td></tr>
<tr><td>●</td><td>清水</td><td>0</td><td>.2</td><td>4</td><td>2</td><td>0</td><td>0</td><td>1</td><td>1</td></tr>
</table>
<table class="gmtbltop">
<tr><th class="gmhdpos"></th><th></th><th>投<br>回</th><th class="gmhdip2"></th><th>打<br>者</th><th>安<br>打</th><th>四<br>球</th><th>死<br>球</th><th>三<br>振</th><th>自<br>責</th></tr>
<tr><td></td><td>戸郷</td><td>5</td><td></td><td>21</td><td>4</td><td>1</td><td>0</td><td>2</td><td>2</td></tr>
<tr><td>○</td><td>マルティネス</td><td>1</td><td></td><td>3</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
</table>
</body></html>
"""

# 當季日文單場頁（結構同 npb.jp/scores/{年}/{月日}/{主}-{客}-{NN}/box.html）
SCORES_BOX = """
<html><body>
<div class="game_tit"><time>2026年3月27日（金）</time><span class="place">東京ドーム</span>
<h3>【JERA セ・リーグ公式戦】 読売ジャイアンツ vs 阪神タイガース 1回戦</h3></div>
<p class="game_info">【試合終了】 ◇開始 18:18 ◇終了 20:41 ◇試合時間 2時間23分 ◇入場者 42,111人</p>
<div id="table_linescore"><table id="tablefix_ls">
<tr><th></th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th><th class="total-1">計</th><th class="total-2">H</th><th class="total-2">E</th></tr>
<tr><td><span>阪神タイガース</span><span>阪神</span></td><td>0</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>1</td><td>4</td><td>0</td></tr>
<tr><td><span>読売ジャイアンツ</span><span>巨人</span></td><td>2</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>x</td><td>3</td><td>6</td><td>0</td></tr>
</table></div>
<div class="table_score" id="table_top_b"><table id="tablefix_t_b">
<tr><th></th><th>守備</th><th>選手</th><th>打数</th><th>得点</th><th>安打</th><th>打点</th><th>盗塁</th><th class="inn">1</th><th class="inn">2</th></tr>
<tr><td>1</td><td>(中)</td><td class="player"><a href="/bis/players/71075138.html">近本</a></td><td>4</td><td>0</td><td>0</td><td>0</td><td>0</td><td>中　飛</td><td>四　球</td></tr>
<tr><td></td><td></td><td>チーム計</td><td>27</td><td>1</td><td>4</td><td>1</td><td>0</td><td></td><td></td></tr>
</table></div>
<div class="table_score" id="table_bottom_b"><table id="tablefix_b_b">
<tr><th></th><th>守備</th><th>選手</th><th>打数</th><th>得点</th><th>安打</th><th>打点</th><th>盗塁</th><th class="inn">1</th><th class="inn">2</th></tr>
<tr><td>1</td><td>(左)</td><td class="player"><a href="/bis/players/73575150.html">キャベッジ</a></td><td>4</td><td>1</td><td>2</td><td>1</td><td>0</td><td class="hit">右越本①</td><td>三　振</td></tr>
</table></div>
<div class="table_score" id="table_top_p"><table id="tablefix_t_p">
<tr><th></th><th>投手</th><th>投球数</th><th>打者</th><th>投球回</th><th>安打</th><th>自責点</th></tr>
<tr><td>●</td><td class="player"><a href="/bis/players/13315153.html">村上</a></td><td>101</td><td>23</td>
<td><table class="table_inning"><tr><th>5</th><td>2/3</td></tr></table></td><td>5</td><td>3</td></tr>
</table></div>
<div class="table_score" id="table_bottom_p"><table id="tablefix_b_p">
<tr><th></th><th>投手</th><th>投球数</th><th>打者</th><th>投球回</th><th>安打</th><th>自責点</th></tr>
<tr><td>○</td><td class="player"><a href="/bis/players/71275152.html">竹丸</a></td><td>79</td><td>22</td>
<td><table class="table_inning"><tr><th>6</th><td></td></tr></table></td><td>3</td><td>1</td></tr>
<tr><td>S</td><td class="player"><a href="/bis/players/61065136.html">田中瑛</a></td><td>5</td><td>3</td>
<td><table class="table_inning"><tr><th>1</th><td></td></tr></table></td><td>1</td><td>0</td></tr>
</table></div>
</body></html>
"""

SCHEDULE_DETAIL = """
<table>
<tr><td class="holiday">10/4（日）</td><td><a href="/scores/2026/1004/s-c-25/"><div>ヤクルト</div><div>-</div><div>広島</div></a></td>
<td><div>神　宮</div><div>18:00</div></td><td></td><td><div>先発：吉村</div><div>先発：栗林</div></td></tr>
<tr><td><div>DeNA</div><div>-</div><div>阪神</div></td><td><div>横　浜</div><div>18:00</div></td><td></td><td></td></tr>
<tr><td>10/5（月）</td><td><div>楽天</div><div>-</div><div>ソフトバンク</div></td>
<td><div>楽天モバイル</div><div>18:00</div></td><td></td><td></td></tr>
</table>
"""

STATS_BAT = """
<table class="tablefix2">
<tr><th>選手</th><th>試合</th><th>打席</th><th>打数</th><th>安打</th><th>本塁打</th><th>打点</th><th>打率</th></tr>
<tr><td><span>*</span>秋広　優人</td><td>5</td><td>8</td><td>7</td><td>1</td><td>0</td><td>0</td><td>.143</td></tr>
<tr><td>岡本　和真</td><td>69</td><td>290</td><td>250</td><td>82</td><td>15</td><td>49</td><td>.328</td></tr>
</table>
"""

STATS_PIT = """
<table class="tablefix2">
<tr><th>選手</th><th>登板</th><th>勝利</th><th>敗北</th><th>投球回</th><th>自責点</th><th>防御率</th></tr>
<tr><td>泉　圭輔</td><td>10</td><td>0</td><td>0</td><td>12<span>.1</span></td><td>8</td><td>5.84</td></tr>
</table>
"""

PROFILE = """
<html><head><title>田中　将大（読売ジャイアンツ） | 個人年度別成績 | NPB.jp 日本野球機構</title></head>
<body><img src="//p.npb.jp/img/common/logo/2026/logo_g_m.gif">
<section id="pc_vitals"><div id="pc_v_wrap"><div id="pc_v_photo"><img src="https://p.npb.jp/players_photo/2026/180/g/011_11215114.jpg"></div>
<div id="pc_v_name"><ul><li id="pc_v_no">11</li><li id="pc_v_team">読売ジャイアンツ</li></ul>
<ul><li id="pc_v_name">田中　将大</li><li id="pc_v_kana">たなか・まさひろ</li></ul></div></div></section>
<table><tr><th>ポジション</th><td>投手</td></tr><tr><th>投打</th><td>右投右打</td></tr>
<tr><th>生年月日</th><td>1988年11月1日</td></tr></table>
</body></html>
"""


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.games = s.fix_stages(s.parse_calendar(CALENDAR, 2025, "04"))
        self.by_id = {g["id"]: g for g in self.games}

    def test_final_home_on_left(self):
        g = self.by_id["2025032800105"]
        self.assertEqual((g["home"], g["away"], g["homeScore"], g["awayScore"]), ("G", "S", 6, 5))
        self.assertEqual((g["status"], g["stage"], g["date"]), ("final", "regular", "2025-03-28"))

    def test_postponed(self):
        self.assertEqual(self.by_id["2025032800106"]["status"], "postponed")

    def test_scheduled_and_allstar(self):
        sched = [g for g in self.games if g["status"] == "scheduled"]
        self.assertEqual(len(sched), 2)
        self.assertEqual((sched[0]["home"], sched[0]["away"], sched[0]["time"]), ("S", "C", "14:00"))
        self.assertEqual(sched[1]["stage"], "allstar")

    def test_postseason(self):
        self.assertEqual(self.by_id["2025101101985"]["stage"], "cs1")
        self.assertEqual(self.by_id["2025101101988"]["stage"], "cs1")
        g = self.by_id["2025102502002"]
        self.assertEqual((g["stage"], g["home"], g["away"]), ("js", "H", "T"))


class BoxTest(unittest.TestCase):
    def setUp(self):
        game = {"id": "2025032800105", "date": "2025-03-28", "away": "S", "home": "G",
                "awayScore": 5, "homeScore": 6, "stage": "regular"}
        self.box = s.parse_box(BOX, game)

    def test_meta(self):
        info = self.box["info"]
        self.assertEqual(info["venue"], "東京ドーム")
        self.assertEqual((info["start"], info["duration"], info["attendance"]), ("18:19", "3:26", 42270))
        self.assertEqual((info["winP"], info["loseP"]), ("マルティネス", "清水"))
        self.assertIn("キャベッジ", info["homeRuns"])
        self.assertEqual(info["note"], "延長10回")

    def test_linescore(self):
        ls = self.box["linescore"]
        self.assertEqual(ls["headers"][-4:], ["10", "R", "H", "E"])
        self.assertEqual(ls["rows"][1][-4:], ["1X", "6", "17", "1"])
        self.assertEqual(ls["teams"], ["S", "G"])

    def test_tables(self):
        s_bat = self.box["teams"]["S"]["batting"]
        self.assertEqual(s_bat["headers"][:3], ["守備", "選手", "打数"])
        self.assertEqual(s_bat["rows"][0][1], "西川")
        self.assertEqual(self.box["teams"]["G"]["batting"]["rows"][0][1], "岡本")
        pit = self.box["teams"]["S"]["pitching"]
        self.assertEqual(pit["headers"][:3], ["", "投手", "投球回"])
        self.assertEqual(self.box["teams"]["G"]["pitching"]["rows"][1][1], "マルティネス")


class ScoresBoxTest(unittest.TestCase):
    def setUp(self):
        game = {"id": "2026032701085", "date": "2026-03-27", "away": "T", "home": "G",
                "awayScore": 1, "homeScore": 3, "stage": "regular"}
        self.box = s.parse_scores_box(SCORES_BOX, game)

    def test_info(self):
        info = self.box["info"]
        self.assertEqual((info["venue"], info["start"], info["duration"], info["attendance"]),
                         ("東京ドーム", "18:18", "2:23", 42111))
        self.assertEqual((info["winP"], info["loseP"], info["saveP"]), ("竹丸", "村上", "田中瑛"))
        self.assertIn("キャベッジ", info["homeRuns"])
        self.assertEqual(info["series"], "第1戰")

    def test_tables(self):
        self.assertTrue(self.box["ok"])
        self.assertEqual(self.box["linescore"]["headers"][-3:], ["R", "H", "E"])
        self.assertEqual(self.box["linescore"]["rows"][1][9], "x")
        bat = self.box["teams"]["T"]["batting"]
        self.assertEqual((bat["rows"][0][2], bat["pids"][0]), ("近本", "71075138"))
        pit = self.box["teams"]["T"]["pitching"]
        self.assertEqual(pit["rows"][0][4], "5 2/3")
        self.assertEqual(s.innings_to_outs(pit["rows"][0][4]), 17)
        self.assertEqual(len(self.box["teams"]["G"]["pitching"]["rows"]), 2)

    def test_bat_line_from_plays(self):
        bat = self.box["teams"]["T"]["batting"]
        line = dict(zip(s.BAT_LOG, s.bat_line(bat["headers"], bat["rows"][0])))
        self.assertEqual((line["AB"], line["BB"], line["SO"], line["HR"]), (4, 1, 0, 0))


class OtherPagesTest(unittest.TestCase):
    def test_schedule_detail(self):
        rows = s.parse_schedule_detail(SCHEDULE_DETAIL, 2026)
        self.assertEqual(len(rows), 3)
        self.assertEqual((rows[0]["home"], rows[0]["away"], rows[0]["venue"], rows[0]["time"]),
                         ("S", "C", "神宮", "18:00"))
        self.assertEqual(rows[0]["probables"], {"home": "吉村", "away": "栗林"})
        self.assertEqual(rows[0]["scores"], "/scores/2026/1004/s-c-25/")
        self.assertEqual((rows[1]["date"], rows[1]["home"]), ("2026-10-04", "DB"))
        self.assertEqual((rows[2]["date"], rows[2]["away"]), ("2026-10-05", "H"))

    def test_stats(self):
        bat = s.parse_stats_page(STATS_BAT, False)
        self.assertEqual(bat[0]["name"], "秋広 優人")
        self.assertEqual((bat[1]["HR"], bat[1]["AVG"], bat[1]["PA"]), (15, 0.328, 290))
        pit = s.parse_stats_page(STATS_PIT, True)
        self.assertEqual((pit[0]["OUTS"], pit[0]["IP"], pit[0]["ERA"]), (37, "12 1/3", 5.84))

    def test_profile(self):
        p = s.parse_profile(PROFILE, "11215114")
        self.assertEqual((p["fullName"], p["kana"], p["number"]), ("田中 将大", "たなか・まさひろ", "11"))
        self.assertNotIn("photo", p)
        self.assertEqual(p["fields"]["投打"], "右投右打")

    def test_names(self):
        self.assertEqual(s.match_name("中村悠", ["中村 悠平", "中村 晃"]), "中村 悠平")
        self.assertEqual(s.match_name("岡本", ["岡本 和真"]), "岡本 和真")
        self.assertIsNone(s.match_name("中村", ["中村 悠平", "中村 晃"]))

    def test_innings(self):
        self.assertEqual(s.innings_to_outs("7 2/3"), 23)
        self.assertEqual(s.innings_to_outs("12.1"), 37)
        self.assertEqual(s.innings_to_outs("8"), 24)
        self.assertEqual(s.innings_to_outs(".2"), 2)


if __name__ == "__main__":
    unittest.main()
