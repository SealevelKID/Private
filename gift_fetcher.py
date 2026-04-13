import pandas as pd
import json
import os
from datetime import datetime

# 檔案路徑設定
JSON_FILE = "stock_data.json"
EXCEL_FILE = "stock_souvenir.xlsx"

def load_stock_excel(filepath):
    """讀取 Excel 紀念品清單 (支援多分頁與欄位自動容錯)"""
    if not os.path.exists(filepath):
        print(f"⚠️ 找不到紀念品檔案 {filepath}，請確認檔案是否存在。")
        return {}

    try:
        print(f"📂 正在讀取紀念品清單: {filepath} ...")
        # 🌟 升級 1：讀取所有分頁 (sheet_name=None)
        all_sheets = pd.read_excel(filepath, engine='openpyxl', sheet_name=None)
        souvenir_data = {}
        total_rows = 0
        
        for sheet_name, df in all_sheets.items():
            print(f"  -> 正在掃描分頁：【{sheet_name}】")
            
            # 🌟 升級 2：清理欄位名稱 (去除所有隱藏空白)
            df.columns = [str(col).strip() for col in df.columns]
            
            # 🌟 升級 3：擴充智慧搜尋清單，精準對接你的 Excel 欄位
            code_col = next((col for col in df.columns if col in ['代號', '股票代號', '股號', 'Symbol']), None)
            
            # 這裡加上 '股東會紀念品'
            item_col = next((col for col in df.columns if col in ['股東會紀念品', '紀念品', '物品', '發放紀念品', '紀念品名稱']), None)
            
            # 這裡你的 Excel 是 '最後買進日'，已經在清單內了
            date_col = next((col for col in df.columns if col in ['最後買進日', '買進日', '日期', '最後買進日期']), None)
            
            if not code_col or not item_col:
                print(f"    ⚠️ 略過此分頁：找不到代號或紀念品欄位。目前抓到的欄位有：{df.columns.tolist()}")
                continue
                
            for index, row in df.iterrows():
                code = str(row.get(code_col, '')).strip()
                item = str(row.get(item_col, '')).strip()
                last_buy_date_raw = row.get(date_col, '') if date_col else ''
                
                # 去除包含 .0 的浮點數代號 (例如 2330.0 -> 2330)
                if code.endswith('.0'): code = code[:-2]
                
                if not code or code == 'nan' or not item or item == 'nan':
                    continue
                    
                # 處理日期格式與過期判定
                last_buy_date = ""
                is_expired = False
                
                if pd.notna(last_buy_date_raw):
                    if isinstance(last_buy_date_raw, datetime):
                        last_buy_date = last_buy_date_raw.strftime('%Y-%m-%d')
                    else:
                        last_buy_date = str(last_buy_date_raw)[:10].strip()
                    
                    try:
                        buy_datetime = datetime.strptime(last_buy_date, '%Y-%m-%d')
                        if buy_datetime.date() < datetime.now().date():
                            is_expired = True
                    except ValueError:
                        pass 
                
                souvenir_data[code] = {
                    "item": item,
                    "last_buy_date": last_buy_date,
                    "is_expired": is_expired
                }
                total_rows += 1
                
        print(f"✅ 成功從所有分頁中讀取 {total_rows} 筆有效紀念品資料！")
        return souvenir_data
        
    except Exception as e:
        print(f"❌ 讀取 Excel 失敗: {e}")
        return {}

def main():
    print("🎁 啟動紀念品模組 (季節性增強)...")
    
    # 1. 讀取核心引擎產出的 JSON
    if not os.path.exists(JSON_FILE):
        print(f"❌ 找不到 {JSON_FILE}！請先執行 daily_analyzer.py 產生基礎數據。")
        return
        
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        stock_data = json.load(f)
        
    # 2. 讀取 Excel 紀念品清單
    excel_data = load_stock_excel(EXCEL_FILE)
    if not excel_data:
        print("⏭️ 沒有紀念品資料，無需更新，程式結束。")
        return

    # 3. 清空舊的紀念品頁籤資料 (準備重新整理)
    stock_data["souvenir_stocks"] = []
    stock_data["expired_souvenir_stocks"] = []
    
    # 定義要掃描的資優生板塊
    target_categories = ["defensive_stocks", "growth_stocks", "financial_stocks"]
    added_to_souvenir_tab = set() # 用來防止同一檔股票重複加入紀念品頁籤
    update_count = 0
    
    # 4. 開始比對並回填
    for category in target_categories:
        for stock in stock_data.get(category, []):
            symbol = stock["symbol"]
            
            # 如果這檔資優生有發放紀念品
            if symbol in excel_data:
                gift_info = excel_data[symbol]
                
                # 寫入 v2.0 的新欄位 (供前端讀取)
                stock["has_souvenir"] = True
                stock["gift_name"] = gift_info["item"]
                stock["souvenir_title"] = gift_info["item"] # 相容舊版 JS
                stock["gift_last_buy_date"] = gift_info["last_buy_date"]
                stock["souvenir_last_buy_date"] = gift_info["last_buy_date"] # 相容舊版 JS
                
                update_count += 1
                
                # 複製一份到獨立的紀念品頁籤中
                if symbol not in added_to_souvenir_tab:
                    if gift_info["is_expired"]:
                        stock_data["expired_souvenir_stocks"].append(stock)
                    else:
                        stock_data["souvenir_stocks"].append(stock)
                    added_to_souvenir_tab.add(symbol)
                    
    # 5. 存回 JSON 檔案
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(stock_data, f, ensure_ascii=False, indent=4)
        
    print("\n" + "="*40)
    print("🎉 [紀念品回填完成]")
    print(f"🔄 總計為 {update_count} 檔資優生加上了紀念品標籤")
    print(f"🎁 現有福利名單：{len(stock_data['souvenir_stocks'])} 檔")
    print(f"🕰️ 過期福利名單：{len(stock_data['expired_souvenir_stocks'])} 檔")
    print("="*40)

if __name__ == "__main__":
    main()