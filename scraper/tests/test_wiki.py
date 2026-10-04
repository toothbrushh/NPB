"""維基百科模組測試：以 MediaWiki Action API（formatversion=2）回應格式的模擬資料測試，不連網。"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import npb_scraper  # noqa: E402
import wiki  # noqa: E402

EXTRACT = ("泉口友汰（日語：泉口 友汰，1999年5月17日－），日本職業棒球選手，出身於大阪府，"
           "司職內野手，現效力於日本職棒中央聯盟讀賣巨人。右投左打。"
           "高中就讀大阪桐蔭高等學校，之後進入青山學院大學與NTT西日本。2023年選秀會第4指名加入巨人。")


def fake_api(lang, params):
    if params.get("prop", "").startswith("extracts"):
        titles = params["titles"].split("|")
        q = {"normalized": [], "redirects": [], "pages": []}
        if lang == "zh":
            if "泉口友汰" in titles:
                q["pages"].append({"pageid": 1, "title": "泉口友汰", "extract": EXTRACT,
                                   "pageimage": "Izuguchi_2024.jpg", "fullurl": "https://zh.wikipedia.org/wiki/泉口友汰"})
            if "田中將大" in titles or "田中将大" in titles:
                q["converted"] = [{"from": "田中将大", "to": "田中將大"}]
                q["pages"].append({"pageid": 2, "title": "田中將大", "extract": "田中將大是日本職業棒球投手。",
                                   "pageimage": "Nonfree.jpg", "fullurl": "https://zh.wikipedia.org/wiki/田中將大"})
            if "中村一郎" in titles:
                q["pages"].append({"pageid": 3, "title": "中村一郎", "extract": "中村一郎是日本政治人物。"})
            if "佐藤太郎" in titles:
                q["pages"].append({"pageid": 4, "title": "佐藤太郎", "extract": "佐藤太郎可以指：",
                                   "pageprops": {"disambiguation": ""}})
            for t in titles:
                if t not in {p["title"] for p in q["pages"]} and t not in ("田中将大",):
                    q["pages"].append({"title": t, "missing": True})
        else:
            for t in titles:
                q["pages"].append({"title": t, "missing": True})
        return {"query": q}
    if params.get("prop") == "imageinfo":
        pages = []
        for t in params["titles"].split("|"):
            lic = "CC BY-SA 4.0" if "Izuguchi" in t else "Fair use"
            pages.append({"title": t, "imageinfo": [{
                "thumburl": f"https://upload.wikimedia.org/thumb/{t}", "descriptionurl": f"https://commons.wikimedia.org/wiki/{t}",
                "extmetadata": {"Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Foo">Foo Bar</a>'},
                                "LicenseShortName": {"value": lic},
                                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]})
        return {"query": {"pages": pages}}
    raise AssertionError(params)


class WikiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(wiki, "DATA", self.tmp.name),
                        mock.patch.object(wiki, "api", side_effect=fake_api),
                        mock.patch.object(wiki, "claude_client", return_value=None)]
        for p in self.patches:
            p.start()
        players = os.path.join(self.tmp.name, "players")
        os.makedirs(players)
        for pid, name, kana in (("1", "泉口　友汰", "いずぐち・ゆうた"), ("2", "田中　将大", "たなか・まさひろ"),
                                ("3", "中村　一郎", "なかむら・いちろう"), ("4", "佐藤　太郎", "さとう・たろう"),
                                ("5", "Ｔ．キャベッジ", "トレイ・キャベッジ (TREY CABBAGE)")):
            npb_scraper.write_json(os.path.join(players, f"{pid}.json"), {"id": pid, "fullName": name, "kana": kana})

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def read(self, key):
        return npb_scraper.read_json(os.path.join(self.tmp.name, "wiki", "p", f"{key}.json"))

    def test_candidates(self):
        self.assertEqual(wiki.candidate_titles("1"), ["泉口友汰"])
        self.assertEqual(wiki.candidate_titles("5"), ["トレイ・キャベッジ"])

    def test_collect(self):
        wiki.collect({k: wiki.candidate_titles(k) for k in "12345"}, "p")
        e = self.read("1")
        self.assertEqual((e["title"], e["lang"], e["method"]), ("泉口友汰", "zh", "excerpt"))
        self.assertLessEqual(len(e["summary"]), wiki.SUMMARY_MAX)
        self.assertTrue(e["summary"].endswith("。"))
        self.assertEqual(e["photo"]["artist"], "Foo Bar")
        self.assertEqual(e["photo"]["license"], "CC BY-SA 4.0")
        self.assertTrue(e["photo"]["page"].startswith("https://commons.wikimedia.org/"))
        # 簡繁轉換後的標題仍能對應；非自由授權照片不採用
        e2 = self.read("2")
        self.assertEqual(e2["title"], "田中將大")
        self.assertIsNone(e2["photo"])
        # 同名但非棒球人物、消歧義頁、查無條目 → 記為 none
        for k in "345":
            self.assertTrue(self.read(k)["none"])

    def test_excerpt(self):
        long = "甲" * 50 + "。" + "乙" * 400 + "。"
        self.assertEqual(wiki.excerpt(long), "甲" * 50 + "。")
        self.assertTrue(wiki.excerpt("丙" * 500).endswith("…"))


if __name__ == "__main__":
    unittest.main()
