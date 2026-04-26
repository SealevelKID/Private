import requests
import pandas as pd
import numpy as np
import yfinance as yf
import json
import time
import urllib.parse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import urllib3 
import os
import sys
import random 
import argparse # 🆕 引入 argparse 以支援測試模式

# 停用不安全請求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常見瀏覽器的 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
]

# 台灣 50 (0050) 成分股名單
TW_50_LIST = [
    "2330", "2317", "2454", "2308", "2382", "2303", "2881", "2882", "2891", "2886", 
    "2884", "1216", "2885", "3231", "2002", "2892", "2880", "2883", "2887", "1101", 
    "2345", "2357", "2379", "2912", "5871", "2395", "2890", "2207", "1303", "1301", 
    "2412", "3711", "5880", "3034", "1326", "2603", "3045", "2324", "4938", "3008", 
    "6669", "2408", "1590", "1102", "3037", "2301", "2609", "1402", "6505", "2353"
]

# 🆕 政府特許金控業名單
FINANCIAL_HOLDINGS = [
    "2880", "2881", "2882", "2883", "2884", "2885", "2886", "2887", 
    "2888", "2889", "2890", "2891", "2892", "5880"
]

def get_all_tw_stocks():
    print("🔍 正在連線至證交所 OpenAPI，獲取最新台股名單...")
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            
            # 攔截 429 Too Many Requests 或 403 拒絕連線
            if response.status_code in [403, 429]:
                raise ConnectionError(f"伺服器拒絕連線 (HTTP {response.status_code})")
            response.raise_for_status() 
            
            data = response.json()
            stock_dict = {}
            for item in data:
                code = item.get('Code', '').strip()
                name = item.get('Name', '').strip()
                if len(code) == 4 and code.isdigit() and not code.startswith('0'):
                    yf_symbol = f"{code}.TW" 
                    stock_dict[yf_symbol] = name
                    
            print(f"✅ 成功獲取名單！共計找出 {len(stock_dict)} 檔上市普通股。")
            return stock_dict
            
        except Exception as e:
            if attempt < max_retries - 1:
                # 指數型休眠：3秒 -> 6秒 -> 12秒 + Jitter(隨機微調)
                sleep_time = (2 ** attempt) * 3 + random.uniform(0.5, 1.5)
                print(f"  ⚠️ 獲取名單失敗 ({e})，等待 {sleep_time:.1f} 秒後重試...")
                time.sleep(sleep_time)
            else:
                print(f"❌ 嚴重錯誤：獲取清單連續失敗 {max_retries} 次，程式終止。")
                sys.exit(1)

def check_listing_years(ticker_obj, target_years=10):
    try:
        hist = ticker_obj.history(period="max")
        if hist.empty: return False, None
        first_trade_date = hist.index.min().to_pydatetime().date()
        listing_years = (datetime.now().date() - first_trade_date).days / 365.25
        return listing_years >= target_years, first_trade_date.strftime("%Y-%m-%d")
    except Exception:
        return False, None

def get_eps_history(ticker_obj, years=5):
    try:
        financials = ticker_obj.financials
        if financials.empty: return None, False
        
        if 'Basic EPS' in financials.index:
            eps_row = financials.loc['Basic EPS']
        elif 'Diluted EPS' in financials.index:
            eps_row = financials.loc['Diluted EPS']
        else:
            return None, False

        eps_data = eps_row.dropna().head(years).astype(float).tolist()
        if not eps_data or len(eps_data) < 4: 
            return eps_data, False
            
        eps_data.reverse()
        profitable_years = sum(1 for eps in eps_data if eps is not None and eps > 0)
        last_year_profitable = (eps_data[-1] is not None) and (eps_data[-1] > 0)
        return eps_data, (profitable_years >= 4) and last_year_profitable
    except Exception:
        return None, False

def calculate_beta_and_latest_price(symbol, target_ticker):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        data = yf.download([symbol, "^TWII"], start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)['Close']
        if data.empty or symbol not in data.columns or "^TWII" not in data.columns: return None, None
            
        data = data.dropna()
        returns = data.pct_change().dropna()
        if returns.empty: return None, None
            
        cov_matrix = np.cov(returns[symbol], returns["^TWII"])
        beta = cov_matrix[0, 1] / cov_matrix[1, 1]
        latest_price = float(data[symbol].iloc[-1])
        return round(beta, 4), round(latest_price, 2)
    except Exception:
        return None, None

def get_advanced_defense_stats(ticker_obj, eps_data, dividend_history):
    """
    計算 v2.0 深度防禦指標：盈餘純度推估 & 股本異動
    """
    pure_eps_ratio_avg = 100.0
    capital_event = ""
    
    try:
        # 1. 股本異動偵測 (透過 yfinance 的 shares_full 取得歷史股數)
        shares = ticker_obj.get_shares_full(start=datetime.now() - timedelta(days=365), end=None)
        if shares is not None and not shares.empty and len(shares) >= 2:
            oldest_shares = shares.iloc[0]
            latest_shares = shares.iloc[-1]
            if oldest_shares > 0:
                share_change_pct = ((latest_shares - oldest_shares) / oldest_shares) * 100
                if abs(share_change_pct) > 5.0:
                    capital_event = f"股本大幅變動 ({share_change_pct:+.1f}%)"

        # 2. 盈餘純度防禦 (用發放率 Proxy 推估：若股息大於 EPS，代表可能拿老本/資本公積來配)
        # eps_data 是由近到遠的 list
        if eps_data and dividend_history and len(eps_data) >= 3:
            purity_scores = []
            for i in range(min(len(eps_data), 3)):
                eps = eps_data[i]
                # 尋找對應年份的股息 (簡化對應，抓歷史前幾筆)
                div = dividend_history[i]['amount'] if i < len(dividend_history) else 0
                
                if eps is not None and eps > 0 and div > 0:
                    # 如果發的錢大於賺的錢，純度下降
                    payout_ratio = div / eps
                    if payout_ratio > 1.0:
                        # 比如賺 1 元發 1.2 元，純度算 1/1.2 = 83%
                        purity_scores.append((1 / payout_ratio) * 100)
                    else:
                        purity_scores.append(100.0)
                        
            if purity_scores:
                pure_eps_ratio_avg = round(sum(purity_scores) / len(purity_scores), 1)

    except Exception as e:
        pass # 容錯處理，拿不到資料就保持預設值

    return pure_eps_ratio_avg, capital_event

def get_dividend_stats(ticker_obj, symbol, latest_price):
    try:
        dividends = ticker_obj.dividends
        # 🆕 擴充回傳兩個布林值: is_outlier_warning, is_fast_fill，發生錯誤時預設給 False
        if dividends.empty: return [], None, 0, False, False, False, False, 0, False, 0, False, False
            
        one_year_ago = datetime.now(dividends.index.tzinfo) - timedelta(days=365)
        recent_1y_divs = dividends[dividends.index >= one_year_ago]
        total_div_1y = float(recent_1y_divs.sum()) if not recent_1y_divs.empty else 0
        dividend_yield = (total_div_1y / latest_price) * 100 if latest_price > 0 else 0

        ten_years_ago = datetime.now(dividends.index.tzinfo) - timedelta(days=10*365)
        divs_10y = dividends[dividends.index >= ten_years_ago]
        is_long_dividend_10y = len(set(d.year for d in divs_10y.index)) >= 9

        fifteen_years_ago = datetime.now(dividends.index.tzinfo) - timedelta(days=15*365)
        divs_15y = dividends[dividends.index >= fifteen_years_ago]
        is_long_dividend_15y = len(set(d.year for d in divs_15y.index)) >= 14

        five_years_ago = datetime.now(dividends.index.tzinfo) - timedelta(days=5*365)
        divs_5y = dividends[dividends.index >= five_years_ago]
        yearly_divs = divs_5y.groupby(divs_5y.index.year).sum()
        
        has_volatility = False
        is_dividend_spike = False 
        
        if len(yearly_divs) < 4: 
            has_volatility = True
        elif len(yearly_divs) >= 3:
            max_div = yearly_divs.max()
            min_div = yearly_divs.min()
            if min_div <= 0 or (max_div / min_div) >= 2.0:
                has_volatility = True
            
            div_median = np.median(yearly_divs)
            if yearly_divs.iloc[-1] > (div_median * 1.5):
                is_dividend_spike = True

        # ==========================================
        # 🆕 任務 1.5：拉長 5 年歷史填息中位數計算
        # ==========================================
        hist_prices_5y = ticker_obj.history(start=five_years_ago - timedelta(days=30))
        fill_days_list_5y = []
        
        for date, amount in divs_5y.items():
            prices_before = hist_prices_5y[hist_prices_5y.index < date]
            if not prices_before.empty:
                target_price = prices_before['Close'].iloc[-1]
                prices_after = hist_prices_5y[hist_prices_5y.index >= date]
                filled = prices_after[prices_after['Close'] >= target_price]
                if not filled.empty:
                    fill_days_list_5y.append((filled.index[0] - date).days)

        median_fill_days = np.median(fill_days_list_5y) if fill_days_list_5y else 999

        # ==========================================
        # 🆕 任務 1.5：近 3 年紅線抽驗與 Fast Fill 判定
        # ==========================================
        three_years_ago = datetime.now(dividends.index.tzinfo) - timedelta(days=3*365)
        recent_divs = dividends[dividends.index >= three_years_ago]
        
        if recent_divs.empty: 
            return [], None, dividend_yield, False, is_long_dividend_10y, is_long_dividend_15y, has_volatility, 0, is_dividend_spike, total_div_1y, False, False

        current_year = datetime.now().year
        has_current_year = any(d.year == current_year for d in recent_divs.index)
        is_estimated = False
        history = []
        
        fault_count_90d = 0   # 統計超過 90 天的次數
        is_fast_fill = True   # 預設為優良，遇到 > 30 天即破功
        now_tz = datetime.now(dividends.index.tzinfo)

        for date, amount in recent_divs.items():
            date_str = date.strftime("%Y-%m-%d")
            history.append({"ex_dividend_date": date_str, "amount": float(amount)})
            
            prices_before = hist_prices_5y[hist_prices_5y.index < date] # 沿用 5 年價格表
            if not prices_before.empty:
                target_price = prices_before['Close'].iloc[-1]
                prices_after = hist_prices_5y[hist_prices_5y.index >= date]
                filled = prices_after[prices_after['Close'] >= target_price]
                
                if not filled.empty:
                    days_to_fill = (filled.index[0] - date).days
                    if days_to_fill > 90:
                        fault_count_90d += 1
                    if days_to_fill > 30:
                        is_fast_fill = False
                else:
                    # 尚未填息：計算至今經過天數是否超過 90 天
                    days_since_ex = (now_tz - date).days
                    if days_since_ex > 90:
                        fault_count_90d += 1
                    is_fast_fill = False # 尚未填息就不算 fast fill

        # 單次容錯判定：剛好 1 次失誤，且 5 年中位數極為優秀(<=15)
        is_outlier_warning = bool((fault_count_90d == 1) and (median_fill_days <= 15))
        
        if not has_current_year and len(history) > 0:
            history.append({"ex_dividend_date": f"{current_year}-XX-XX", "amount": float(history[-1]['amount']), "is_estimated": True})
            is_estimated = True
            
        # 👇 回傳值擴充，加上 is_outlier_warning 與 is_fast_fill
        return history, round(float(median_fill_days), 1), round(dividend_yield, 2), is_estimated, is_long_dividend_10y, is_long_dividend_15y, has_volatility, fault_count_90d, is_dividend_spike, total_div_1y, is_outlier_warning, is_fast_fill
    except Exception:
        return [], None, 0, False, False, False, False, 0, False, 0, False, False

def get_recent_news(symbol, name):
    """取得過去 7 天內的 Google 財經新聞，並偵測重大風險事件"""
    try:
        # 🆕 任務一：精準打擊！利用 site: 指令限定只抓取 Yahoo 股市與三大權威財經網
        search_query = f"{symbol} {name} (site:tw.stock.yahoo.com OR site:cnyes.com OR site:money.udn.com)"
        query = urllib.parse.quote(search_query)
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        
        # 🚨 定義重大風險關鍵字
        major_keywords = ["合併", "私募", "處分資產", "增資", "減資", "掏空", "調查"]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                res = requests.get(url, headers=headers, timeout=10, verify=False)
                
                if res.status_code in [403, 429]:
                    raise ConnectionError(f"HTTP {res.status_code}")
                res.raise_for_status()
                
                root = ET.fromstring(res.content)
                seven_days_ago = datetime.now() - timedelta(days=7)
                
                has_news = False
                news_url = ""
                major_news_event = False
                
                for item in root.findall('.//item'):
                    pub_date_str = item.find('pubDate').text
                    try:
                        pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                        if pub_date > seven_days_ago:
                            title = item.find('title').text
                            # 檢查是否有危險關鍵字
                            if any(kw in title for kw in major_keywords):
                                major_news_event = True
                            
                            if not has_news: # 只抓第一篇最新的當作連結
                                has_news = True
                                news_url = item.find('link').text
                                
                    except Exception:
                        continue
                        
                return has_news, news_url, major_news_event
                
            except Exception as e:
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 1.5 + random.uniform(0.5, 1.5)
                    time.sleep(sleep_time)
                else:
                    return False, "", False
    except Exception:
        return False, "", False
    
def save_progress(filename, data):
    # 🆕 寫入最後更新日期
    data["last_update"] = datetime.now().strftime("%Y-%m-%d")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    with open('rejected_stocks.json', 'w', encoding='utf-8') as f:
        json.dump(data.get("rejected_stocks", []), f, ensure_ascii=False, indent=4)

def main():
    import time # 確保有載入 time
    start_time = time.time() # 🆕 記錄起始時間
    
    parser = argparse.ArgumentParser(description="台灣股市除權息過濾與分類系統")
    parser.add_argument('--test', action='store_true', help="僅測試 0050 成分股以加速開發")
    args = parser.parse_args()

    print("啟動財務數據工程師腳本 (全台股嚴選資優生版 + 淘汰追蹤)...")
    schedule = get_all_tw_stocks()
    
    # 🆕 若啟用 --test，覆寫 schedule 只保留 0050 名單
    if args.test:
        print("\n🧪 [測試模式] 已啟動！僅掃描 0050 內成分股...")
        schedule = {k: v for k, v in schedule.items() if k.split('.')[0] in TW_50_LIST}

    output_filename = "stock_data.json" 
    
    # 🆕 擴充 JSON 結構
    results = {
        "defensive_stocks": [], 
        "growth_stocks": [], 
        "financial_stocks": [], 
        "souvenir_stocks": [],  
        "recent_dropped_stocks": [], # 🆕 正名：近期移出名單
        "processed_symbols": [],
        "rejected_stocks": [],
        "last_update": ""
    }
    
    history_listed_counts = {} # 🆕 紀錄歷史上榜次數
    previous_good_stocks = {}  # 🆕 紀錄上週的合格名單

    if os.path.exists(output_filename):
        print(f"📦 發現既有存檔 {output_filename}，正在提取歷史上榜紀錄...")
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                
                # 提取舊榜單，用於比對跌出榜單與累計次數
                for cat in ["defensive_stocks", "growth_stocks", "financial_stocks"]:
                    for s in saved_data.get(cat, []):
                        sym = s["symbol"]
                        previous_good_stocks[sym] = s
                        history_listed_counts[sym] = s.get("listed_count", 1)

                # ==========================================
                # 👇 任務一的程式碼貼在這裡！👇
                # ==========================================
                now = datetime.now()
                # 讀取舊名單 (相容舊版 dropped_stocks 或新版 recent_dropped_stocks)
                dropped_list = saved_data.get("recent_dropped_stocks", saved_data.get("dropped_stocks", [])) 
                recent_dropped = []
                seen_dropped_symbols = set() # 🆕 加入 Set 用於追蹤已加入的股票代號，防止載入時重複
                
                for s in dropped_list:
                    sym = s.get("symbol")
                    if sym in seen_dropped_symbols:
                        continue # 如果已經處理過這檔，直接跳過

                    drop_date_str = s.get("drop_date", "")
                    if drop_date_str:
                        drop_date = datetime.strptime(drop_date_str, "%Y-%m-%d")
                        if (now - drop_date).days <= 30: # 僅保留 30 天內的
                            recent_dropped.append(s)
                            seen_dropped_symbols.add(sym)
                    else:
                        # 若無日期 (剛升級)，補上今日並保留
                        s["drop_date"] = now.strftime("%Y-%m-%d")
                        recent_dropped.append(s)
                        seen_dropped_symbols.add(sym)
                
                # 將清理後的名單寫回準備輸出的 results 字典中
                results["recent_dropped_stocks"] = recent_dropped
                # ==========================================
                # 👆 任務一結束 👆
                # ==========================================

            print(f"✅ 成功載入歷史紀錄！(本週執行將強制重新向 yfinance 獲取最新數據)")
        except Exception as e:
            print(f"⚠️ 讀取存檔失敗 ({e})，將以全新進度開始。")

    count = 0
    total = len(schedule)
    session_processed_count = 0 
    
    try:
        for yf_symbol, name in schedule.items():
            count += 1
            code = yf_symbol.split('.')[0] 
            
            if code in results["processed_symbols"]:
                print(f"\n[{count}/{total}] ⏩ {code} {name} 已經處理過，跳過...")
                continue
                
            print(f"\n[{count}/{total}] 正在分析 {code} {name} ({yf_symbol})...")

            # 🌟 就是這裡！請補上這行，初始化 yfinance 的 Ticker 物件
            ticker_obj = yf.Ticker(yf_symbol)

            classified = False
            reject_reason = ""
            
            # 🆕 網路請求退避策略 (Exponential Backoff)
            max_retries = 3
            fetch_success = False
            
            for attempt in range(max_retries):
                try:
                    # ==========================================
                    # 🛡️ Stage 1: 基礎流動性快篩 (門檻下調至 300 張) & 均線計算
                    # ==========================================
                    hist_1y = ticker_obj.history(period="1y") # 👈 這裡宣告 hist_1y，確保後續抓得到資料
                    if hist_1y.empty or len(hist_1y) < 20:
                        reject_reason = "Stage 1 淘汰：無足夠的近期交易資料"
                        fetch_success = True; break
                        
                    avg_vol_20d = hist_1y['Volume'].tail(20).mean()
                    
                    # 🆕 任務一：門檻由 500,000 (500張) 下調至 300,000 (300張)
                    if avg_vol_20d < 300000: 
                        reject_reason = f"Stage 1 淘汰：流動性不足 (近20日均量僅 {avg_vol_20d/1000:.0f} 張)"
                        fetch_success = True; break
                        
                    # 🆕 判定是否為冷門穩健標的 (300~500張之間)
                    # ⚠️ 加上 bool() 強制轉換，避免 Numpy 型態導致 JSON 存檔崩潰
                    is_niche_stable = bool(300000 <= avg_vol_20d < 500000)
                    
                    latest_price = float(hist_1y['Close'].iloc[-1]) 
                    
                    # 計算均線 (半年線 120MA, 年線 240MA)
                    ma_120 = hist_1y['Close'].tail(120).mean() if len(hist_1y) >= 120 else None
                    ma_240 = hist_1y['Close'].tail(240).mean() if len(hist_1y) >= 240 else None
                        
                    # ==========================================
                    # 🔬 Stage 2: 深度體檢準備 (暫時保留舊邏輯，下一階段擴充)
                    # ==========================================
                    is_old_enough_5, listing_date = check_listing_years(ticker_obj, 5)
                    if not is_old_enough_5:
                        reject_reason = "Stage 2 淘汰：資歷太淺 (上市未滿 5 年)"
                        fetch_success = True; break
                        
                    eps_data, is_profitable = get_eps_history(ticker_obj, 5)
                    if not is_profitable:
                        reject_reason = "獲利不穩：過去 5 年內未能達成至少 4 年獲利且去年無虧損"
                        fetch_success = True; break
                        
                    beta, latest_price = calculate_beta_and_latest_price(yf_symbol, ticker_obj)
                    if beta is None: 
                        reject_reason = "無法計算大盤連動 Beta 值"
                        fetch_success = True; break
                        
                    # 🆕 擴充承接變數，加入 is_outlier_warning 與 is_fast_fill
                    dividend_history, median_fill_days, dividend_yield, is_estimated, is_long_dividend_10y, is_long_dividend_15y, has_volatility, fault_count_90d, is_dividend_spike, total_div_1y, is_outlier_warning, is_fast_fill = get_dividend_stats(ticker_obj, yf_symbol, latest_price)
                    
                    if median_fill_days is None: 
                        reject_reason = "缺乏配息紀錄或除息資料"
                        fetch_success = True; break

                    if dividend_yield <= 1.5:
                        reject_reason = f"利息太低：最新殖利率僅 {dividend_yield:.2f}% (未達 1.5% 基本門檻)"
                        fetch_success = True; break

                    # ==========================================
                    # 🆕 任務 1.5：填息紅線防禦與單次豁免判定
                    # ==========================================
                    if fault_count_90d > 0:
                        if is_outlier_warning:
                            print(f"  ⚠️ [豁免發動] 觸發 90 天填息紅線 1 次，但 5 年中位數優良 ({median_fill_days}天)，給予豁免！")
                        else:
                            reject_reason = f"填息紅線：近 3 年有 {fault_count_90d} 次填息超過 90 天 (或嚴重貼息中)"
                            fetch_success = True; break
                    elif median_fill_days > 15:
                        reject_reason = f"長線填息偏慢：5 年歷史填息中位數 {median_fill_days} 天 (大於 15 天嚴格門檻)"
                        fetch_success = True; break
                    
                    print(f"  [Debug] 🎉 基礎達標！均量 {avg_vol_20d/1000:.0f}張 | 殖利率 {dividend_yield:.2f}% | 填息中位數 {median_fill_days}天 | Beta {beta}")
                    
                    is_financial_holding = code in FINANCIAL_HOLDINGS
                    
                    is_defensive_target = (beta < 0.8 and dividend_yield > 4.0)
                    if (is_financial_holding or is_defensive_target) and has_volatility:
                        reject_reason = "股息發放不穩定（波動過大或曾中斷）"
                        fetch_success = True; break
                    
                    

                    # 1. 呼叫升級版的新聞掃描 (多接一個 major_news_event)
                    has_news, news_url, major_news_event = get_recent_news(code, name)
                    
                    # 2. 呼叫新的深度防禦函數
                    pure_eps_ratio_avg, capital_event = get_advanced_defense_stats(ticker_obj, eps_data, dividend_history)
                    
                    # 3. 🚨 盈餘純度紅線淘汰邏輯 (連續吃老本淘汰)
                    if pure_eps_ratio_avg < 50.0:
                        reject_reason = f"Stage 2 淘汰：盈餘純度過低 ({pure_eps_ratio_avg}%)，有吃老本風險"
                        fetch_success = True; break
                    
                    if is_financial_holding:
                        is_super_yield = dividend_yield >= 5.0
                        is_long_dividend = is_long_dividend_15y
                    else:
                        is_super_yield = dividend_yield >= 6.0
                        is_long_dividend = is_long_dividend_10y
                    # ==========================================
                    # 🚀 新增這一段：安全地取得最新一年的股息金額
                    # ==========================================
                    # 🆕 統一使用「過去 1 年內累積現金配息總和」
                    annual_dividend = round(total_div_1y, 2)
                    
                    # 🆕 嚴格重算殖利率，確保數學邏輯絕對吻合 (公式: 累計股利 / 股價 * 100)
                    strict_dividend_yield = round((annual_dividend / latest_price) * 100, 2) if latest_price > 0 else 0

                    # 🆕 計算累積上榜次數
                    current_listed_count = history_listed_counts.get(code, 0) + 1

                    # ==========================================
                    # 🆕 任務二：半年歸零與長青樹判定
                    # ==========================================
                    now_date = datetime.now()
                    prev_data = previous_good_stocks.get(code, {})
                    last_hit_str = prev_data.get("last_hit_date", "")
                    history_hits = prev_data.get("history_hits", [])

                    # 🆕 專屬五月上線的自動洗白機制
                    # 將所有 "2026-05" 以前的測試月份強制刪除
                    original_len = len(history_hits)
                    history_hits = [m for m in history_hits if m >= "2026-05"]
                    
                    current_listed_count = history_listed_counts.get(code, 0)
                    
                    # 如果過濾後紀錄空了，但原本有資料，代表之前都是四月的測試數據，次數歸零！
                    if len(history_hits) == 0 and original_len > 0:
                        current_listed_count = 0
                        last_hit_str = "" # 同時清空最後達標日，當作全新的一張白紙

                    # 180 天歸零判定
                    if last_hit_str:
                        last_hit = datetime.strptime(last_hit_str, "%Y-%m-%d")
                        if (now_date - last_hit).days > 180:
                            current_listed_count = 0 # 🚨 超過半年沒進榜，穩定度歸零重算
                            history_hits = []

                    current_listed_count += 1
                    current_month_str = now_date.strftime("%Y-%m")
                    if current_month_str not in history_hits:
                        history_hits.append(current_month_str) # 紀錄本次達標月份
                    if len(history_hits) > 24: 
                        history_hits.pop(0) # 僅保留近兩年紀錄避免檔案過大

                    # 皇冠判定：累計 >= 12 個月 且 近 12 個月內有 10 個月在榜
                    recent_12_months = [(now_date.replace(day=1) - timedelta(days=i*30)).strftime("%Y-%m") for i in range(12)]
                    hits_in_last_12 = sum(1 for m in recent_12_months if m in history_hits)
                    is_evergreen = (current_listed_count >= 12) and (hits_in_last_12 >= 10)

                    stock_info = {
                        "symbol": code,
                        "name": name,
                        "is_niche_stable": is_niche_stable, 
                        "listed_count": current_listed_count, 
                        "latest_price": latest_price,
                        "avg_vol_20d_sheets": round(avg_vol_20d / 1000, 0),
                        "dividend_yield_pct": strict_dividend_yield, 
                        "dividend_amount": annual_dividend,          
                        "beta": beta,
                        "avg_fill_dividend_days": median_fill_days,
                        "failed_fill_count": fault_count_90d, # ✅ 修正：統一接住 fault_count_90d 的值
                        "is_dividend_spike": is_dividend_spike,
                        "last_year_eps": eps_data[-1] if eps_data else None,
                        "recent_news_alert": has_news,
                        "google_news_url": news_url,
                        "is_0050": code in TW_50_LIST,
                        "is_financial_holding": is_financial_holding,
                        "is_super_yield": is_super_yield,
                        "is_fast_fill": is_fast_fill,        
                        "is_outlier_warning": is_outlier_warning, 
                        "is_long_dividend": is_long_dividend,
                        "has_volatility_warning": has_volatility or is_dividend_spike,
                        "pure_eps_ratio_avg": pure_eps_ratio_avg, 
                        "capital_event": capital_event,       
                        "major_news_event": major_news_event, 
                        "gift_name": "",         
                        "gift_last_buy_date": "" ,
                        "is_evergreen": bool(is_evergreen)  # 👑 記得補上這行，前端才抓得到皇冠資料！
                    }
                    
                    # 🆕 嚴格均線淘汰邏輯
                    if beta < 0.8 and dividend_yield > 4.0:
                        # 防禦型：股價不可嚴重跌破年線 (容許 5% 誤差)
                        if ma_240 and latest_price < (ma_240 * 0.95):
                            reject_reason = "長線趨勢走弱 (股價跌破年線)"
                        else:
                            results["defensive_stocks"].append(stock_info)
                            classified = True
                            
                    is_eps_growing = len(eps_data) >= 4 and (eps_data[-1] is not None) and (eps_data[-4] is not None) and (eps_data[-1] > eps_data[-4])
                    
                    if 0.8 <= beta <= 1.5 and is_eps_growing:
                        # 成長型：均線需多頭排列 (價格 > 半年線 > 年線)
                        if ma_120 and ma_240 and not (latest_price > ma_120 > ma_240):
                            if not classified: # 避免覆寫已被分類為抗跌的狀態
                                reject_reason = "趨勢未達成長股動能標準 (均線未呈多頭排列)"
                        else:
                            results["growth_stocks"].append(stock_info)
                            classified = True
                    
                    if is_financial_holding:
                        results["financial_stocks"].append(stock_info)
                        classified = True

                    if not classified:
                        if not reject_reason:
                            reject_reason = "處於模糊地帶：未符合四大名單的入選資格"

                    # 順利完成所有 API 抓取與判定
                    fetch_success = True
                    break 
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        # 指數退避：3秒 -> 6秒 -> 12秒 + 隨機微調
                        sleep_time = (2 ** attempt) * 3 + random.uniform(0.5, 1.5)
                        print(f"  ⚠️ 網路或伺服器異常 ({e})，啟動防護機制... 等待 {sleep_time:.1f} 秒後進行第 {attempt+1} 次重試")
                        time.sleep(sleep_time)
                    else:
                        print(f"  ❌ ⚠️ [{code}] 連續抓取失敗 {max_retries} 次，已優雅跳過該檔股票！")
            
            # 🆕 防崩潰優雅跳過：連錯3次直接登記為拒絕，並進入下一檔股票
            if not fetch_success:
                results["rejected_stocks"].append({
                    "symbol": code,
                    "name": name,
                    "reason": "連線失敗或伺服器持續拒絕請求 (可能觸發反爬蟲)"
                })
                if code not in results["processed_symbols"]:
                    results["processed_symbols"].append(code)
                continue 
                
            # --- 接下來是原本處理成功的邏輯 (保持原樣) ---
            if reject_reason:
                print(f"  -> 剔除: {reject_reason}")
                
                # 🆕 任務四：若上週是合格名單，本週被淘汰，則加入 recent_dropped_stocks
                if code in previous_good_stocks:
                    dropped_info = previous_good_stocks[code].copy()
                    dropped_info["reason"] = reject_reason
                    dropped_info["listed_count"] = 0 # 重置穩定度
                    # 👇 1. 補上今天的淘汰日期，讓 30 天保留機制能計算
                    dropped_info["drop_date"] = datetime.now().strftime("%Y-%m-%d") 
                    
                    # 🆕 2. 檢查是否已經在清單內，避免重複加入
                    existing_index = next((i for i, s in enumerate(results["recent_dropped_stocks"]) if s["symbol"] == code), -1)
                    if existing_index >= 0:
                        results["recent_dropped_stocks"][existing_index] = dropped_info # 已存在則更新最新狀態
                    else:
                        results["recent_dropped_stocks"].append(dropped_info)

                results["rejected_stocks"].append({
                    "symbol": code,
                    "name": name,
                    "reason": reject_reason
                })

            if code not in results["processed_symbols"]:
                results["processed_symbols"].append(code)
            
            session_processed_count += 1
            
            if session_processed_count % 20 == 0:
                save_progress(output_filename, results)
                print(f"\n💾 [系統提示] 已自動存檔進度... (總共已處理 {len(results['processed_symbols'])} 檔)")
                
            # 💡 原本的成功抓取休眠 (防被鎖 IP 的節奏控制)
            sleep_time_normal = random.uniform(1.5, 3.5)
            print(f"  ⏳ 隨機休息 {sleep_time_normal:.1f} 秒，模仿人類操作節奏...")
            time.sleep(sleep_time_normal)
            
    except KeyboardInterrupt:
        print("\n\n🚨 [系統警告] 收到中斷指令 (Ctrl+C)，正在儲存最後進度...")
        # 👇 這兩行一定要加回來！這樣意外中斷時才會真的存檔
        save_progress(output_filename, results) 
        print(f"✅ 儲存完畢！目前總計處理了 {len(results['processed_symbols'])} 檔股票。安全結束程式。")
        sys.exit(0)
        
    # === 以下是正常跑完全部股票後的結尾 ===
    end_time = time.time()
    total_seconds = int(end_time - start_time)
    mins, secs = divmod(total_seconds, 60)
    
    save_progress(output_filename, results)
    
    # 計算收錄與淘汰總數
    total_passed = len(results["defensive_stocks"]) + len(results["growth_stocks"]) + len(results["financial_stocks"])
    total_rejected = len(results["rejected_stocks"])
    
    print("\n" + "="*50)
    print("📊 [v2.0 執行統計報告]")
    print(f"⏱️ 總耗時：{mins} 分 {secs} 秒")
    print(f"✅ 成功收錄資優生總數：{total_passed} 檔")
    print(f"❌ 因未達標而淘汰總數：{total_rejected} 檔")
    print(f"💾 資料已匯出至 {output_filename} 以及 rejected_stocks.json")
    print("="*50)

if __name__ == "__main__":
    main()
