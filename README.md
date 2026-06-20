# 📈 存股小幫手 (Personal Stock Screener)

## 📝 專案初衷
這是一個專為「不擅長看盤、不懂股票」的投資者（也就是我自己）所打造的台股自動化排雷系統。
本專案為**個人自用**，核心目標是透過程式自動化抓取財報與配息紀錄，並加上嚴格的過濾條件（如：填息天數、連續配息年數、盈餘純度、新聞司法排雷等），濾除高風險標的，最終只留下「絕對安全」的資優生名單。

---

## 📂 檔案架構與功能說明

本專案採前端（HTML/CSS/JS 模組化分離）與後端（Python 爬蟲與篩選）完全獨立的架構：

### 核心爬蟲與分析引擎 (Python)
* **`fetch_and_analyze.py`**：系統的主心骨。負責連線抓取台股數據，執行嚴格的分類與淘汰邏輯，並內建 0050 成分股調整月份（3,6,9,12月）的自動提醒機制。
* **`gift_fetcher.py`**：專門用來抓取與更新「股東紀念品（股東禮）」資訊的輔助腳本。
* **`requirements.txt`**：記錄本專案 Python 環境所需的依賴套件名單。

### 資料庫 (JSON / Excel)
* **`stock_data.json`**：爬蟲執行完畢後，產生的「合格資優生」資料庫，供前端網頁讀取。
* **`rejected_stocks.json`**：記錄被系統淘汰的股票及其「淘汰原因」，方便日後回溯與觀察。
* **`stock_souvenir.xlsx`**：手動整理或輔助對照的股東紀念品清單。

### 前端互動儀表板 (Web)
* **`stockindex.html`**：網頁主架構，包含頁籤切換、股價試算器與底部的 0050 快捷查詢網址。
* **`stockstyle.css`**：網頁的視覺外觀與版面排版設定。
* **`stockscript.js`**：負責讀取 JSON 資料並動態生成表格、處理排序與搜尋等前端互動邏輯。

### 自動化設定 (GitHub Actions)
* **`.github/workflows/`** (內含 `stock_sync.yaml`)：負責排程自動化。設定每週六自動執行 Python 腳本更新資料，並結合「隨機休眠機制」模仿人類操作以防止伺服器阻擋。若為手動觸發則會自動跳過等待時間。

---

## ⚙️ 備忘：環境變數與自動化設定

此專案依賴 GitHub Actions 進行每週自動更新與推送。若要在全新的環境中運行，需要在 GitHub Repository 的 `Settings > Secrets and variables > Actions` 中設定以下機密變數（Secrets）：

* **`TELEGRAM_BOT_TOKEN`**：Telegram 機器人的 API Token，用於發送執行完畢的統計報告。
* **`TELEGRAM_CHAT_ID`**：接收 Telegram 通知的聊天室 ID。
* *(註：若程式中有串接其他政府開放資料 API，亦需確保對應的金鑰已設定)。*
