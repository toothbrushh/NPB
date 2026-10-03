# NPB 日本職棒賽程戰績

日本職棒（NPB）各年度的賽程、比分、戰績與單場球員數據網頁，介面風格參考 F1 官網的賽季頁。

## 功能

- **年度切換**：右上角選擇年度，可查詢所有已抓取的球季。
- **賽程**：例行賽、明星賽、高潮系列賽（CS）、日本一系列賽，含已賽與未賽比賽的日期、開賽時間、球場、比分、勝敗投手；顯示「下一場」倒數與最新賽果；可依球隊、賽事類別篩選。
- **單場數據**：點擊比賽卡片可看逐局比分、觀眾數、比賽時間、雙方打者名單與當場打擊數據、投手當場投球數據、全壘打、裁判。
- **戰績**：中央聯盟／太平洋聯盟排名（勝率、勝差、主客場、交流戰、得失分、剩餘場次、近 10 場、連勝敗）與「貯金」走勢圖。
- **季後賽**：各系列賽對戰組合與勝場數。
- **個人成績**：由每場成績累計的年度打擊／投手成績，可排序、篩選球隊、只看達規定者。
- **球隊**：單隊戰績、對各隊成績、全季賽程。

## 架構

```
index.html, assets/        靜態網頁（無需建置，GitHub Pages 直接發布）
scraper/npb_scraper.py     爬蟲：從 npb.jp 抓資料並輸出 JSON
data/seasons.json          年度清單
data/{年}/schedule.json    該年度所有比賽
data/{年}/games/{ID}.json  單場詳細數據
data/{年}/players.json     年度個人成績（由單場累計）
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

[日本野球機構 NPB.jp](https://npb.jp/)（月曆：`/bis/eng/{年}/calendar/`；單場：`/bis/{年}/games/`；未賽場地：`/games/{年}/schedule_{月}_detail.html`）。
未賽比賽若官方賽程頁查不到球場，會暫以主隊主場顯示並標註「（預定）」。
