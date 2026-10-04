#!/usr/bin/env python3
"""
從維基百科官方 API 取得選手／球隊介紹與自由授權照片，產生附出處與授權標示的靜態 JSON。

  * 文字：MediaWiki Action API（prop=extracts，只取導言純文字），中文（台灣正體）優先，找不到再用日文。
  * 照片：條目的代表圖（prop=pageimages，pilicense=free 只取自由授權圖片），
          再以 prop=imageinfo 讀取維基共享資源上的作者與授權（extmetadata）。
          只接受 CC BY / CC BY-SA / CC0 / 公有領域。
  * 摘要：預設節錄導言前幾句（300 字內）。設定 ANTHROPIC_API_KEY 時改用 Claude 改寫成 200–300 字繁體中文摘要。
          無論哪一種，都屬於維基百科內容的衍生，網頁一律標示來源條目與 CC BY-SA 4.0。

輸出：
  data/wiki/p/{選手ID}.json   選手
  data/wiki/t/{球隊代碼}.json  球隊
每筆只抓一次；查無條目的紀錄 90 天後才會重試。

用法：python scraper/wiki.py --seasons current
"""

import argparse
import datetime as dt
import html
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from npb_scraper import DATA, now_jst, nospace, parse_years, read_json, write_json  # noqa: E402

DELAY = float(os.environ.get("WIKI_DELAY", "1.0"))
BATCH = 20  # prop=extracts 搭配 exintro 每次最多 20 頁
RETRY_MISSING_DAYS = 90
SUMMARY_MAX = 300
# 隊徽、標誌即使在維基共享資源標為公有領域，仍是球團商標，不採用
LOGO_FILE = re.compile(r"logo|emblem|insignia|wordmark|cap[ _]insignia|ロゴ|標誌|隊徽|徽章", re.I)
FREE_LICENSE = re.compile(r"^(CC[ -]BY(-SA)?([ -]\d\.\d)?|CC0|Public domain|PD\b|公有領域)", re.I)
BASEBALL_WORDS = ("野球", "棒球", "投手", "捕手", "內野手", "内野手", "外野手", "球員", "選手", "球團", "球団", "プロ野球", "職棒")

TEAM_TITLES = {
    "G": ("讀賣巨人", "読売ジャイアンツ"), "T": ("阪神虎", "阪神タイガース"),
    "DB": ("橫濱DeNA海灣之星", "横浜DeNAベイスターズ"), "C": ("廣島東洋鯉魚", "広島東洋カープ"),
    "S": ("東京養樂多燕子", "東京ヤクルトスワローズ"), "D": ("中日龍", "中日ドラゴンズ"),
    "H": ("福岡軟銀鷹", "福岡ソフトバンクホークス"), "F": ("北海道日本火腿鬥士", "北海道日本ハムファイターズ"),
    "M": ("千葉羅德海洋", "千葉ロッテマリーンズ"), "E": ("東北樂天金鷲", "東北楽天ゴールデンイーグルス"),
    "B": ("歐力士猛牛", "オリックス・バファローズ"), "L": ("埼玉西武獅", "埼玉西武ライオンズ"),
}

session = requests.Session()
session.headers.update({
    # 維基媒體 API 要求可辨識的 User-Agent 與聯絡方式
    "User-Agent": "NPBFanScheduleSite/1.0 (https://github.com/toothbrushh/npb; fan-made non-commercial site)",
})


# ---------------------------------------------------------------- API

def api(lang, params):
    params = {"action": "query", "format": "json", "formatversion": "2", **params}
    if lang == "zh":
        params["variant"] = "zh-tw"
    for attempt in range(4):
        time.sleep(DELAY * (attempt + 1))
        try:
            r = session.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  wiki {lang} retry: {e}")
            continue
        if r.status_code == 429 or r.status_code >= 500:
            wait = int(r.headers.get("retry-after", "10"))
            print(f"  wiki {lang} HTTP {r.status_code}, waiting {wait}s")
            time.sleep(min(wait, 60))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"wikipedia {lang} API unavailable")


def resolve_titles(query, titles):
    """把要求的標題對應到最終頁面標題（依 normalized → converted → redirects 依序轉換）。"""
    maps = [{x["from"]: x["to"] for x in query.get(k, [])} for k in ("normalized", "converted", "redirects")]
    out = {}
    for t in titles:
        cur = t
        for m in maps:
            cur = m.get(cur, cur)
        out[t] = cur
    return out


def fetch_pages(lang, titles):
    """回傳 {要求的標題: 頁面資料}；查無、消歧義頁不回傳。"""
    found = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        data = api(lang, {
            "titles": "|".join(chunk), "redirects": 1, "converttitles": 1,
            "prop": "extracts|pageimages|info|pageprops", "exintro": 1, "explaintext": 1, "exlimit": "max",
            "piprop": "name", "pilicense": "free", "inprop": "url", "ppprop": "disambiguation",
        })
        q = data.get("query", {})
        pages = {p["title"]: p for p in q.get("pages", []) if not p.get("missing") and not p.get("invalid")}
        for req, final in resolve_titles(q, chunk).items():
            p = pages.get(final)
            if p and p.get("extract") and "disambiguation" not in p.get("pageprops", {}):
                found[req] = p
    return found


def strip_html(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def fetch_image_info(lang, files):
    """回傳 {檔名: 照片資訊}；只保留自由授權。"""
    out = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        data = api(lang, {
            "titles": "|".join(f"File:{f}" for f in chunk), "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": 400,
            "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|Credit",
            "iiextmetadatalanguage": "zh-tw" if lang == "zh" else "ja",
        })
        q = data.get("query", {})
        back = {v: k for k, v in resolve_titles(q, [f"File:{f}" for f in chunk]).items()}
        for p in q.get("pages", []):
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            # 沒有中繼資料時 API 會回傳空陣列 [] 而不是物件
            meta = ii.get("extmetadata") if isinstance(ii.get("extmetadata"), dict) else {}
            field = lambda k: strip_html((meta.get(k) or {}).get("value") if isinstance(meta.get(k), dict) else "")
            lic = field("LicenseShortName")
            if not FREE_LICENSE.match(lic):
                continue
            name = back.get(p["title"], p["title"]).split(":", 1)[-1]
            out[name] = {
                "src": ii.get("thumburl") or ii.get("url"),
                "page": ii.get("descriptionurl"),
                "artist": field("Artist") or "佚名",
                "license": lic,
                "licenseUrl": field("LicenseUrl") or None,
            }
    return out


# ---------------------------------------------------------------- 摘要

def excerpt(text, limit=SUMMARY_MAX):
    """節錄導言：取完整句子直到接近上限；第一句就超過時截斷並加刪節號。"""
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"[（(][^（）()]*[）)]", "", text, count=1) if len(text) > limit else text  # 去掉開頭的讀音／外文括號
    sents = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    out = ""
    for s in sents:
        if len(out) + len(s) > limit:
            break
        out += s
    if not out:
        out = text[:limit - 1] + "…"
    return out.strip()


_claude = None


def claude_client():
    global _claude
    if _claude is None:
        _claude = False
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            try:
                import anthropic
                _claude = anthropic.Anthropic()
            except ImportError:
                print("anthropic package not installed; using excerpts")
    return _claude or None


REWRITE_SYSTEM = (
    "你是棒球網站的編輯。請把使用者提供的維基百科條目導言，改寫成 200 到 300 字的繁體中文（台灣用語）介紹。"
    "只能使用原文中有的事實，不要加入原文沒有的資訊、評價或推測；人名、隊名保留原文中的寫法即可。"
    "只輸出改寫後的段落本身，不要標題、不要引號、不要任何說明。"
)


def rewrite(title, text):
    """有設定 Claude API 金鑰時改寫；失敗或未設定時回傳 None。"""
    client = claude_client()
    if not client:
        return None
    import anthropic
    try:
        resp = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=2000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=REWRITE_SYSTEM,
            messages=[{"role": "user", "content": f"條目：{title}\n\n{text[:4000]}"}],
        )
    except anthropic.RateLimitError:
        time.sleep(30)
        return None
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        print(f"  rewrite failed for {title}: {e}")
        return None
    if resp.stop_reason == "refusal":
        return None
    out = "".join(b.text for b in resp.content if b.type == "text").strip()
    return out if 80 <= len(out) <= 450 else None


# ---------------------------------------------------------------- 選手與球隊

def looks_like_baseball(extract):
    return any(w in extract for w in BASEBALL_WORDS)


def make_entry(page, lang, photos):
    text = page.get("extract", "")
    summary = rewrite(page["title"], text)
    entry = {
        "title": page["title"],
        "url": page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{page['title']}",
        "lang": lang,
        "summary": summary or excerpt(text),
        "method": "rewrite" if summary else "excerpt",
        "license": "CC BY-SA 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hant",
        "photo": photos.get(page.get("pageimage")),
        "fetched": now_jst().date().isoformat(),
    }
    return entry


def due(path):
    old = read_json(path)
    if not old:
        return True
    if old.get("none"):
        try:
            age = (now_jst().date() - dt.date.fromisoformat(old.get("fetched", "2000-01-01"))).days
        except ValueError:
            age = RETRY_MISSING_DAYS
        return age >= RETRY_MISSING_DAYS
    return False


def candidate_titles(pid):
    """依選手個人資料產生要查詢的條目名稱。日籍：全名（去空白）；外籍：片假名全名。"""
    prof = read_json(os.path.join(DATA, "players", f"{pid}.json")) or {}
    full = prof.get("fullName") or ""
    kana = (prof.get("kana") or "").split("(")[0].split("（")[0].strip()
    titles = []
    if re.search(r"[\s　]", full) and not re.search(r"[．.]", full):
        titles.append(nospace(full))
    if re.search(r"[ァ-ヶ]", kana) and "・" in kana:
        titles.append(kana.replace(" ", ""))
    return titles


def collect(items, kind):
    """items: {key: [候選標題…]}；依中文→日文查詢，寫入 data/wiki/{kind}/{key}.json。"""
    todo = {k: v for k, v in items.items() if v and due(os.path.join(DATA, "wiki", kind, f"{k}.json"))}
    print(f"wiki {kind}: {len(todo)} to fetch")
    results = {}
    for lang in ("zh", "ja"):
        pending = {k: v for k, v in todo.items() if k not in results}
        titles = sorted({t for v in pending.values() for t in v})
        if not titles:
            continue
        pages = fetch_pages(lang, titles)
        hits = {}
        for k, cands in pending.items():
            for t in cands:
                p = pages.get(t)
                if p and (kind == "t" or looks_like_baseball(p["extract"])):
                    hits[k] = p
                    break
        files = sorted({p["pageimage"] for p in hits.values()
                        if p.get("pageimage") and not LOGO_FILE.search(p["pageimage"])})
        photos = fetch_image_info(lang, files) if files else {}
        for k, p in hits.items():
            results[k] = make_entry(p, lang, photos)
        print(f"  {lang}: {len(hits)} found")
    today = now_jst().date().isoformat()
    for k in todo:
        write_json(os.path.join(DATA, "wiki", kind, f"{k}.json"),
                   results.get(k) or {"none": True, "fetched": today}, pretty=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch Wikipedia intros and free photos")
    ap.add_argument("--seasons", default="current")
    args = ap.parse_args(argv)
    collect({c: list(t) for c, t in TEAM_TITLES.items()}, "t")
    pids = set()
    for y in parse_years(args.seasons):
        p = read_json(os.path.join(DATA, str(y), "players.json"), {}) or {}
        pids.update(x["id"] for k in ("batting", "pitching") for x in p.get(k, []) if x.get("id"))
    collect({pid: candidate_titles(pid) for pid in sorted(pids)}, "p")


if __name__ == "__main__":
    main()
