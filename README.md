# NPB 日本職棒賽程戰績

日本職棒（NPB）各年度的賽程、比分、戰績與單場球員數據網頁，介面風格參考 F1 官網的賽季頁。

## 功能

- **年度切換**：右上角選擇年度，可查詢所有已抓取的球季。
- **賽程**：例行賽、明星賽、高潮系列賽（CS）、日本一系列賽，含已賽與未賽比賽的日期、開賽時間、球場、比分、勝敗投手；顯示「下一場」倒數與最新賽果；可依球隊、賽事類別篩選。
- **單場數據**：點擊比賽卡片可看逐局比分、球場、觀眾數、比賽時間、勝敗救援投手、全壘打，雙方打者名單與當場打擊數據（含每個打席的結果），投手當場數據（含用球數）。
- **未賽比賽**：顯示開賽時間、球場與預告先發投手。
- **戰績**：中央聯盟／太平洋聯盟排名（勝率、勝差、主客場、交流戰、得失分、剩餘場次、近 10 場、連勝敗）與「貯金」走勢圖。
- **季後賽**：各系列賽對戰組合與勝場數。
- **個人成績**：NPB 官方年度打擊／投手成績（打擊率、上壘率、長打率、防禦率、中繼…），可排序、篩選球隊、只看達規定打席／局數者。
- **球隊頁**：球隊徽章、中文／日文隊名、創立年、所在地、主場、官網連結、維基百科「球隊故事」（含圖片）、本季出賽球員（附照片）、對各隊成績、全季賽程。
- **選手頁**：照片、全名與假名、背號、守備位置、生日等個人資料、維基百科「選手故事」、年度成績、逐場紀錄（點擊可開啟該場比賽）。比分表、個人成績表中的姓名都可點進選手頁。

## 球隊隊徽

網頁預設直接顯示 npb.jp 上**該年度**的官方隊徽圖檔（`p.npb.jp/img/common/logo/{年}/logo_{隊}_m.gif`，不下載、不收進本專案），所以查詢過去年度時會看到當年的隊徽。
圖檔載入失敗時改用本站自製的隊色徽章 `assets/logos/{代碼}.svg`。若只想用自製徽章，把 `assets/app.js` 的 `LOGO_SOURCE` 改成 `'local'`。

## 照片與故事

- 選手照片：單場成績頁的選手連結帶有 npb.jp 選手 ID，爬蟲據此抓取選手個人頁（全名、假名、背號、守備位置、投打、身高體重、生日、經歷、選秀），並記錄照片網址（不下載照片）。每位選手只抓一次，存在 `data/players/{ID}.json`。
- 故事：瀏覽者開啟球隊／選手頁時，網頁直接向維基百科 API 查詢摘要（中文正體優先，找不到再用日文），依 CC BY-SA 4.0 標示出處。照片載入失敗時改用維基百科圖片，再不行則顯示姓氏首字頭像。

## 架構

```
index.html, assets/        靜態網頁（無需建置，GitHub Pages 直接發布）
scraper/npb_scraper.py     爬蟲：從 npb.jp 抓資料並輸出 JSON
data/seasons.json          年度清單
data/{年}/schedule.json    該年度所有比賽
data/{年}/games/{ID}.json  單場詳細數據
data/{年}/players.json     官方年度個人成績
data/{年}/players/{key}.json  選手逐場紀錄
data/{年}/names.json       單場成績表上的簡稱 → 選手
data/players/{ID}.json     選手個人資料（全名、照片網址、背號…）
assets/logos/              自製球隊徽章（官方隊徽載入失敗時使用）
.github/workflows/update-data.yml  定時自動更新
```

### 不重複抓取的規則

- 已結束比賽的單場數據寫入 `data/{年}/games/` 後**永不重抓**。
- 過去年度所有比賽都結束且數據齊全後，`schedule.json` 會標記 `"complete": true`，之後**整季跳過**，不再連線 npb.jp。
- 只有當季（`current`）會在每天定時更新。

## 使用方式

1. **開啟 GitHub Pages**：Settings → Pages → Source 選 *Deploy from a branch*，分支選 `main`、資料夾 `/ (root)`。
2. **第一次抓資料**：Actions → *Update NPB data* → *Run workflow*，`seasons` 填入想要的年度，例如：
   - `current`：當季
   - `2024-current`：2024 年至今
   - `2015-2023`：補抓過去年度（每季約 900 場，每場間隔 1 秒，約 20–30 分鐘）
3. 之後排程會自動更新當季資料；過去年度抓完即封存。

### 本機執行

```bash
pip install -r scraper/requirements.txt
python scraper/npb_scraper.py --seasons current          # 當季
python scraper/npb_scraper.py --seasons 2023-2025        # 指定年度
python scraper/npb_scraper.py --seasons 2025 --no-boxes  # 只抓賽程
python -m http.server 8000                               # 開 http://localhost:8000
```

測試：`cd scraper && python -m unittest -v`

## 資料來源

[日本野球機構 NPB.jp](https://npb.jp/)：
- 賽程與比分：`/bis/eng/{年}/calendar/index_{月}.html`
- 單場成績：`/scores/{年}/{月日}/{主}-{客}-{第幾戰}/box.html`（備援：`/bis/{年}/games/s{ID}.html`、英文版）
- 未賽場地、預告先發：`/games/{年}/schedule_{月}_detail.html`
- 年度個人成績：`/bis/{年}/stats/idb1_{隊}.html`、`idp1_{隊}.html`
- 選手個人資料：`/bis/players/{ID}.html`

各頁面請求間隔 1 秒。npb.jp 聲明網站內容禁止二次利用與轉載，本專案僅供個人查詢使用；若要公開散布，請自行確認使用權限。
