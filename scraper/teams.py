"""NPB 球隊基本資料（代碼依 npb.jp 英文版 BIS 使用的縮寫）。"""

TEAMS = {
    # セントラル・リーグ
    "G": {"league": "C", "zh": "讀賣巨人", "short": "巨人", "ja": "巨人",
          "home": "東京ドーム", "color": "#F97709"},
    "T": {"league": "C", "zh": "阪神虎", "short": "阪神", "ja": "阪神",
          "home": "阪神甲子園球場", "color": "#FFE201"},
    "DB": {"league": "C", "zh": "橫濱DeNA海灣之星", "short": "DeNA", "ja": "ＤｅＮＡ",
           "home": "横浜スタジアム", "color": "#0055A5"},
    "C": {"league": "C", "zh": "廣島東洋鯉魚", "short": "廣島", "ja": "広島",
          "home": "MAZDA Zoom-Zoom スタジアム広島", "color": "#E50012"},
    "S": {"league": "C", "zh": "東京養樂多燕子", "short": "養樂多", "ja": "ヤクルト",
          "home": "明治神宮野球場", "color": "#00AB5C"},
    "D": {"league": "C", "zh": "中日龍", "short": "中日", "ja": "中日",
          "home": "バンテリンドーム ナゴヤ", "color": "#002569"},
    # パシフィック・リーグ
    "H": {"league": "P", "zh": "福岡軟銀鷹", "short": "軟銀", "ja": "ソフトバンク",
          "home": "みずほPayPayドーム福岡", "color": "#F5C700"},
    "F": {"league": "P", "zh": "北海道日本火腿鬥士", "short": "火腿", "ja": "日本ハム",
          "home": "エスコンフィールドHOKKAIDO", "color": "#01609A"},
    "M": {"league": "P", "zh": "千葉羅德海洋", "short": "羅德", "ja": "ロッテ",
          "home": "ZOZOマリンスタジアム", "color": "#221815"},
    "E": {"league": "P", "zh": "東北樂天金鷲", "short": "樂天", "ja": "楽天",
          "home": "楽天モバイル 最強パーク宮城", "color": "#85010F"},
    "B": {"league": "P", "zh": "歐力士猛牛", "short": "歐力士", "ja": "オリックス",
          "home": "京セラドーム大阪", "color": "#000019"},
    "L": {"league": "P", "zh": "埼玉西武獅", "short": "西武", "ja": "西武",
          "home": "ベルーナドーム", "color": "#1F366A"},
}

# 舊代碼或其他寫法 → 現行代碼
ALIASES = {
    "YB": "DB", "Y": "DB", "BS": "B", "BU": "B", "SH": "H", "FH": "H",
    "GIANTS": "G", "TIGERS": "T", "BAYSTARS": "DB", "CARP": "C",
    "SWALLOWS": "S", "DRAGONS": "D", "HAWKS": "H", "FIGHTERS": "F",
    "MARINES": "M", "EAGLES": "E", "BUFFALOES": "B", "LIONS": "L",
}

# 日文隊名（出現在比賽頁面）→ 代碼
JA_NAMES = {
    "巨人": "G", "読売": "G", "阪神": "T", "ＤｅＮＡ": "DB", "DeNA": "DB", "横浜": "DB",
    "広島": "C", "ヤクルト": "S", "中日": "D", "ソフトバンク": "H", "日本ハム": "F",
    "ロッテ": "M", "楽天": "E", "オリックス": "B", "西武": "L",
}

# 已知球場名稱（比對頁面文字用；越長越前面以免被短名稱搶先匹配）
VENUES = sorted({
    "東京ドーム", "阪神甲子園球場", "甲子園", "横浜スタジアム", "横浜",
    "MAZDA Zoom-Zoom スタジアム広島", "マツダスタジアム", "明治神宮野球場", "神宮",
    "バンテリンドーム ナゴヤ", "バンテリンドーム", "ナゴヤドーム",
    "みずほPayPayドーム福岡", "みずほPayPayドーム", "福岡PayPayドーム", "PayPayドーム",
    "エスコンフィールドHOKKAIDO", "エスコンフィールド", "札幌ドーム",
    "ZOZOマリンスタジアム", "ZOZOマリン", "楽天モバイル 最強パーク宮城",
    "楽天モバイルパーク宮城", "楽天生命パーク宮城", "楽天モバイルパーク", "京セラドーム大阪",
    "京セラD大阪", "ほっともっとフィールド神戸", "ほっと神戸", "ベルーナドーム", "メットライフドーム",
    "ほっともっと神戸", "東京ドーム", "倉敷", "那覇", "秋田", "富山", "金沢", "長野",
    "静岡", "岐阜", "松山", "坊っちゃん", "郡山", "いわき", "盛岡", "旭川", "函館",
    "鹿児島", "北九州", "熊本", "長崎", "沖縄セルラー", "ひたちなか", "宇都宮", "前橋",
    "上毛新聞敷島", "県営大宮", "大宮", "福山", "三次", "米子", "松本", "新潟",
    "HARD OFF ECOスタジアム新潟", "ハードオフ新潟", "きらやかスタジアム", "山形",
    "弘前", "青森", "帯広", "釧路",
}, key=len, reverse=True)


def resolve(code):
    """把任意縮寫轉成現行代碼；不認得就原樣回傳。"""
    if not code:
        return code
    c = code.strip()
    if c in TEAMS:
        return c
    u = c.upper()
    if u in TEAMS:
        return u
    return ALIASES.get(u, c)


def resolve_ja(text):
    """在一段日文字串中找出球隊代碼。"""
    for name, code in sorted(JA_NAMES.items(), key=lambda kv: -len(kv[0])):
        if name in text:
            return code
    return None
