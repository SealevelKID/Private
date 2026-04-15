let stockData = {};
let currentCategory = 'defensive_stocks';

// 🚀 修正 1：確保讀取 v2.0 的新檔名 stock_data.json
fetch('stock_data.json')
    .then(response => response.json())
    .then(data => {
        stockData = data;
        renderTable();
        if (data.last_update) {
            document.getElementById('updateDate').innerText = `最後更新：${data.last_update}`;
        }
    })
    .catch(error => {
        console.error('資料載入失敗:', error);
        document.getElementById('stockTable').innerHTML = '<tr><td colspan="3" style="text-align:center; color:red;">無法載入 stock_data.json，請確認 Python 腳本已執行。</td></tr>';
    });

const renderTable = () => {
    const stockTableBody = document.querySelector('#stockTable tbody');
    if (!stockTableBody) return;

    // 取得當前分頁的原始資料
    let rawStocks = stockData[currentCategory] || [];

    // 🚀 新增 1：取得目前的排序方式與股價上限
    const sortSelect = document.getElementById('sortSelect');
    const maxPriceInput = document.getElementById('maxPriceInput');
    const sortType = sortSelect ? sortSelect.value : 'price_asc';
    // 若沒有輸入股價上限，預設為無限大 (Infinity)
    const maxPrice = maxPriceInput && maxPriceInput.value !== '' ? parseFloat(maxPriceInput.value) : Infinity;

    const excludeKeywords = ["超商", "7-11", "全家", "萊爾富", "OK", "商品卡", "禮物卡", "抵用券"];

    // 🚀 新增 2：執行過濾 (紀念品 + 股價上限)
    let filteredStocks = rawStocks.filter(stock => {
        let giftName = (stock.gift_name || "").replace(/參考圖/g, "").trim();
        const isConvenienceStore = excludeKeywords.some(kw => giftName.includes(kw));

        // 紀念品分頁的過濾
        if (currentCategory === 'souvenir_stocks' || currentCategory === 'expired_souvenir_stocks') {
            if (giftName === "" || isConvenienceStore) return false;
        }

        // 股價上限過濾
        if (stock.latest_price !== undefined && stock.latest_price > maxPrice) {
            return false;
        }

        return true; 
    });

    // 🚀 新增 3：執行排序邏輯
    filteredStocks.sort((a, b) => {
        const priceA = parseFloat(a.latest_price) || 0;
        const priceB = parseFloat(b.latest_price) || 0;
        const yieldA = parseFloat(a.dividend_yield_pct) || 0;
        const yieldB = parseFloat(b.dividend_yield_pct) || 0;

        if (sortType === 'price_asc') {
            return priceA - priceB; // 股價由低到高
        } else if (sortType === 'price_desc') {
            return priceB - priceA; // 股價由高到低
        } else if (sortType === 'dividend_desc') {
            return yieldB - yieldA; // 殖利率由高到低
        }
        return 0;
    });

    const rows = filteredStocks.map(stock => {
        // 清洗紀念品名稱（用於顯示）
        let displayGift = (stock.gift_name || "").replace(/參考圖/g, "").trim();
        const isConvenienceStore = excludeKeywords.some(kw => displayGift.includes(kw));
        if (isConvenienceStore) displayGift = ""; // 超商類禮物不顯示名稱

        // 🏅 v2.0 勳章判定系統
        let medals = '';
        if (stock.is_0050) medals += '<span title="🏆 權值資優生" style="cursor:help; margin-left: 4px;">🏆</span>';
        if (stock.is_financial_holding) medals += '<span title="🏦 金控大本營" style="cursor:help; margin-left: 4px;">🏦</span>';
        if (stock.is_super_yield && !stock.is_dividend_spike) medals += '<span title="🔥 高息人氣王" style="cursor:help; margin-left: 4px;">🔥</span>';
        if (stock.is_fast_fill) medals += '<span title="⚡ 閃電填息" style="cursor:help; margin-left: 4px;">⚡</span>';
        if (stock.is_long_dividend) medals += '<span title="🏅 配息長跑王" style="cursor:help; margin-left: 4px;">🏅</span>';
        if (stock.pure_eps_ratio_avg >= 95.0) medals += '<span title="💎 真金白銀：純度極高" style="cursor:help; margin-left: 4px;">💎</span>';
        if (stock.capital_event || stock.major_news_event) medals += '<span title="🚨 企業重大變動" style="cursor:help; margin-left: 4px;">🚨</span>';
        // 🆕 任務二：新增冷門穩健標籤 (冰塊圖示)
        if (stock.is_niche_stable) {
            medals += '<span title="🧊 冷門穩健標的：交易量較低，建議分批布局" style="cursor:help; margin-left: 4px;">🧊</span>';
        }

        // 🎁 紀念品 UI 區塊
        let souvenirTag = '';
        if (displayGift !== '') {
            const isExpired = currentCategory === 'expired_souvenir_stocks';
            const dateStr = stock.gift_last_buy_date ? `<span style="color: ${isExpired ? '#9ca3af' : '#dc2626'}; margin-left: 8px;">⏳ 最後買進：${stock.gift_last_buy_date}</span>` : '';
            
            souvenirTag = `
                <div style="margin-top: 8px;">
                    <div style="font-size: 0.85rem; padding: 6px 12px; border-radius: 6px; border: 1px solid ${isExpired ? '#d1d5db' : '#fde68a'}; background-color: ${isExpired ? '#f3f4f6' : '#fef3c7'}; color: ${isExpired ? '#6b7280' : '#b45309'}; display: inline-block;">
                        🎁 <strong>紀念品：</strong>${displayGift} ${dateStr}
                    </div>
                </div>`;
        }
        // 🆕 任務四：跌出榜單警示 UI 區塊
        let droppedWarning = '';
        if (currentCategory === 'dropped_stocks') {
            droppedWarning = `
                <div style="margin-top: 8px;">
                    <div style="font-size: 0.9rem; padding: 6px 12px; border-radius: 6px; border: 1px solid #feb2b2; background-color: #fff5f5; color: #c53030; display: inline-block;">
                        <strong>⚠️ 淘汰原因：</strong>${stock.reason || '未達標'}
                    </div>
                </div>`;
        }

        // 🚀 防呆機制：如果沒有抓到金額，顯示 ---
        let displayAmount = stock.dividend_amount !== undefined ? stock.dividend_amount : '---';
        let latestPrice = stock.latest_price !== undefined ? stock.latest_price : '---';
        
        // 取得目前的持股數來計算預計領取總額
        const sharesInput = document.getElementById('sharesInput');
        const shares = sharesInput ? (parseFloat(sharesInput.value) || 1000) : 1000;
        let expectedTotal = stock.dividend_amount !== undefined ? (stock.dividend_amount * shares).toLocaleString() : '---';

        // 🆕 任務三：皇冠圖示與走勢圖連結 (統一導向 Yahoo 股市)
        const evergreenCrown = stock.is_evergreen ? '<span title="👑 年度長青樹" style="cursor:help; margin-right: 6px;">👑</span>' : '';
        const financeUrl = `https://tw.stock.yahoo.com/quote/${stock.symbol}`;

        return `
            <tr data-symbol="${stock.symbol}">
                <td>
                    <div style="margin-bottom: 6px; font-size: 1.15rem; display: flex; align-items: center;">
                        ${evergreenCrown}
                        <a href="${financeUrl}" target="_blank" class="stock-link" title="點擊查看股價走勢">
                            ${stock.name} (${stock.symbol})
                        </a>
                        ${medals}
                    </div>
                    <div style="font-size: 0.95rem; color: #6b7280; margin-bottom: 8px;">
                        現價：${latestPrice} 元
                    </div>
                    ${souvenirTag}
                    ${droppedWarning} </td>
                <td style="vertical-align: middle; text-align: center;">
                    <div style="font-size: 0.8rem; color: #718096; margin-bottom: 4px;">近一年累計</div>
                    <button class="dividend-btn" data-symbol="${stock.symbol}">
                        約 ${displayAmount} 元
                    </button>
                </td>
                <td style="vertical-align: middle; text-align: center;">
                    <strong class="expected-dividend-cell" style="color: #e53e3e; font-size: 1.15rem;">$${expectedTotal}</strong>
                </td>
            </tr>
        `;
    }).join('');

    stockTableBody.innerHTML = rows || '<tr><td colspan="3" style="text-align:center;">此類別目前無符合條件的股票</td></tr>';
};

// 頁籤切換邏輯
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategory = btn.getAttribute('data-target');
        renderTable();
    });
});
// 🆕 頂部「跌出榜單」按鈕切換邏輯
const droppedTabBtn = document.getElementById('droppedTabBtn');
if (droppedTabBtn) {
    droppedTabBtn.addEventListener('click', () => {
        // 移除下方所有主頁籤的亮起狀態
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        // 將當前類別切換為跌出榜單並重新渲染表格
        currentCategory = 'dropped_stocks';
        renderTable();
    });
}

// 修改後的點擊展開邏輯
document.querySelector('#stockTable').addEventListener('click', (e) => {
    const btn = e.target.closest('.dividend-btn');
    if (!btn) return;

    const symbol = btn.getAttribute('data-symbol');
    const row = btn.closest('tr');
    const nextRow = row.nextElementSibling;

    // 單一展開邏輯：先尋找並關閉所有已經打開的面板
    let isAlreadyOpen = false;
    document.querySelectorAll('.history-row').forEach(openRow => {
        if (openRow === nextRow) {
            isAlreadyOpen = true; // 點擊的是目前已經打開的這一個
        }
        openRow.remove(); // 收起面板
    });

    // 如果點擊的是原本就打開的，上面已經移除了，就直接結束動作
    if (isAlreadyOpen) return; 

    let allStocks = [];
    Object.values(stockData).forEach(cat => { if(Array.isArray(cat)) allStocks = allStocks.concat(cat); });
    const stock = allStocks.find(s => s.symbol === symbol);

    if (stock) {
        // 點開時自動將該股資料送往上方計算器
        updateTopCalculatorWithStock(stock);

        // 🛠️ 修正錯誤：必須先建立 tr 元素！
        const historyTr = document.createElement('tr');
        historyTr.classList.add('history-row');

        // 🆕 任務三：體檢面板深度收納 (包含累計月數與新聞按鈕)
        historyTr.innerHTML = `
            <td colspan="3" style="padding: 16px 20px; background-color: #fafbfc;"> 
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="color: #4A5568; font-size: 1rem; font-weight: bold;">
                        📊 股票體檢 <span style="font-size: 0.9rem; color: #b7791f; margin-left: 8px;">(⭐ 歷史累計在榜：${stock.listed_count || 1} 個月)</span>
                    </div>
                    <a href="${stock.google_news_url || '#'}" target="_blank" style="background: #edf2f7; color: #4a5568; font-size: 0.85rem; font-weight: bold; padding: 6px 12px; border-radius: 6px; text-decoration: none; border: 1px solid #e2e8f0;">
                        📰 相關新聞
                    </a>
                </div>
                <div class="history-tags" style="display: flex; gap: 12px; flex-wrap: wrap;">
                    <span class="history-tag" style="color: #c53030; font-weight: bold; border-color: #feb2b2;">
                        殖利率：${stock.dividend_yield_pct}%
                    </span>
                    <span class="history-tag" style="border-color: #e2e8f0;">去年 EPS：${stock.last_year_eps || '無資料'}</span>
                    <span class="history-tag" style="border-color: #e2e8f0;">填息：${stock.avg_fill_dividend_days} 天</span>
                    <span class="history-tag" style="border-color: #e2e8f0;">Beta：${stock.beta}</span>
                    <span class="history-tag" style="background: #EBF8FF; color: #2B6CB0; border-color: #90CDF4; font-weight: bold;">
                        盈餘純度：${stock.pure_eps_ratio_avg ? stock.pure_eps_ratio_avg + '%' : '計算中'}
                    </span>
                </div>
            </td>`;
        
        row.after(historyTr);
    }
});

// 全域變數，紀錄當前「選中」要試算的股票
let selectedStockForCalc = null;

const updateTopCalculatorWithStock = (stock) => {
    selectedStockForCalc = stock; // 紀錄目前點開的是哪一檔
    calculateTotal(); // 執行計算
};

// 🛠️ 修正錯誤：整合並修復大括號錯亂的計算邏輯
const calculateTotal = () => {
    const sharesInput = document.getElementById('sharesInput');
    const totalResult = document.getElementById('calcTotalDividend');

    if (!sharesInput || !totalResult) return;

    const shares = parseFloat(sharesInput.value) || 0;
    
    // 1. 更新頂部總額 (根據當前點開的股票)
    if (selectedStockForCalc && selectedStockForCalc.dividend_amount !== undefined) {
        const totalDividend = selectedStockForCalc.dividend_amount * shares;
        totalResult.innerText = `$${Math.round(totalDividend).toLocaleString()}`;
    } else {
        totalResult.innerText = "$0";
    }

    // 2. 即時更新表格內「所有股票」的預計領取金額
    document.querySelectorAll('#stockTableBody tr:not(.history-row)').forEach(tr => {
        const symbol = tr.getAttribute('data-symbol');
        let allStocks = [];
        Object.values(stockData).forEach(cat => { if(Array.isArray(cat)) allStocks = allStocks.concat(cat); });
        const stock = allStocks.find(s => s.symbol === symbol);
        
        if (stock && stock.dividend_amount !== undefined) {
            const expectedTd = tr.querySelector('.expected-dividend-cell');
            if (expectedTd) {
                expectedTd.innerText = '$' + (stock.dividend_amount * shares).toLocaleString();
            }
        }
    });
};

// 監聽持股數輸入框，當使用者手動改股數時，上方總額與表格都會跟著跳動
document.getElementById('sharesInput').addEventListener('input', calculateTotal);
// 監聽排序選單與股價上限變動，自動重新渲染表格
document.getElementById('sortSelect').addEventListener('change', renderTable);
document.getElementById('maxPriceInput').addEventListener('input', renderTable);

// ==========================================
// 💡 名詞解釋彈窗控制邏輯
// ==========================================
const glossaryBtn = document.getElementById('glossaryBtn');
const glossaryModal = document.getElementById('glossaryModal');
const closeModalBtn = document.getElementById('closeModalBtn');

// 1. 點擊按鈕，打開彈窗
if (glossaryBtn && glossaryModal) {
    glossaryBtn.addEventListener('click', () => {
        glossaryModal.classList.add('show');
    });
}

// 2. 點擊 [X] 按鈕，關閉彈窗
if (closeModalBtn && glossaryModal) {
    closeModalBtn.addEventListener('click', () => {
        glossaryModal.classList.remove('show');
    });
}

// 3. 點擊彈窗外部背景，也能關閉彈窗
if (glossaryModal) {
    glossaryModal.addEventListener('click', (e) => {
        if (e.target === glossaryModal) {
            glossaryModal.classList.remove('show');
        }
    });
}
// ==========================================
// 🔍 萬用搜尋列邏輯 (一秒判定好壞)
// ==========================================
const omniSearchInput = document.getElementById('omniSearchInput');
const omniSearchResults = document.getElementById('omniSearchResults');

if (omniSearchInput && omniSearchResults) {
    omniSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim().toLowerCase();

        // 如果搜尋框是空的，就清空結果區塊
        if (query === '') {
            omniSearchResults.innerHTML = '';
            return;
        }

        // 1. 收集所有股票資料並貼上「分類標籤」
        let allStocks = [];
        const categories = {
            defensive_stocks: '🛡️ 抗跌存股',
            growth_stocks: '🚀 穩健成長',
            financial_stocks: '🏦 金融專區',
            souvenir_stocks: '🎁 股東福利',
            rejected_stocks: '❌ 淘汰名單'
        };

        for (const [catKey, catName] of Object.entries(categories)) {
            if (stockData[catKey] && Array.isArray(stockData[catKey])) {
                stockData[catKey].forEach(stock => {
                    // 檢查這檔股票是否已經被加進搜尋池 (避免同檔股票重複出現)
                    let existingStock = allStocks.find(s => s.symbol === stock.symbol);
                    if (!existingStock) {
                        // 如果是新的，拷貝一份並加上標籤
                        allStocks.push({ ...stock, category_labels: [catName] });
                    } else {
                        // 如果已經存在，把新的標籤合併進去 (例如同時是抗跌 + 紀念品)
                        if (!existingStock.category_labels.includes(catName)) {
                            existingStock.category_labels.push(catName);
                        }
                    }
                });
            }
        }

        // 2. 過濾符合關鍵字的股票 (代號或名稱)
        const results = allStocks.filter(stock =>
            stock.symbol.includes(query) || (stock.name && stock.name.toLowerCase().includes(query))
        );

        // 3. 渲染搜尋結果
        if (results.length === 0) {
            omniSearchResults.innerHTML = '<div style="color: #e53e3e; padding: 12px; font-weight: bold; text-align: center;">找不到符合的股票，可能未在台股清單或缺乏資料。</div>';
        } else {
            const html = results.map(stock => {
                const isRejected = stock.category_labels.includes('❌ 淘汰名單');
                const bgColor = isRejected ? '#fff5f5' : '#f0fff4';
                const borderColor = isRejected ? '#feb2b2' : '#9ae6b4';
                const titleColor = isRejected ? '#c53030' : '#276749';

                // 組合顯示的詳細資訊 (過關的顯示數據，淘汰的顯示死因)
                let detailInfo = '';
                if (isRejected) {
                    detailInfo = `<span style="color: #e53e3e; font-weight: bold;">淘汰原因：</span>${stock.reason || '未達標'}`;
                } else {
                    detailInfo = `<span style="color: #4a5568;">現價：${stock.latest_price || '--'} 元 | 殖利率：${stock.dividend_yield_pct || '--'}%</span>`;
                }

                return `
    <div style="background: ${bgColor}; border: 1px solid ${borderColor}; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="font-size: 1.15rem; color: ${titleColor};">
                <a href="https://tw.stock.yahoo.com/quote/${stock.symbol}" target="_blank" style="color: inherit; text-decoration: none;" title="點擊查看 Yahoo 股市行情">
                    ${stock.name} (${stock.symbol})
                </a>
            </strong>
                            <span style="font-size: 0.9rem; font-weight: bold; color: ${titleColor};">
                                ${stock.category_labels.join(' / ')}
                            </span>
                        </div>
                        <div style="font-size: 0.95rem;">
                            ${detailInfo}
                        </div>
                    </div>
                `;
            }).join('');
            omniSearchResults.innerHTML = html;
        }
    });
}
