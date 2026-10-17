# 對話內數值圖表

數值比較、效能、功耗、延遲、價格、市佔、營收與時間趨勢，會自動提供原生伺服器工具
`render_data_chart`。不需要更新 Windows／Mac／iOS 外殼，也不需要 Open Terminal。

- `auto`：簡短類別用直向長條圖，較長／較多類別用橫向長條圖。
- `bar`／`horizontal_bar`：多組同單位數據自動畫分組長條圖。
- `line`：依使用者資料順序畫時間趨勢，不重排時間。
- 圖中標示單位、每個數值、資料性質、備註、來源；長條軸包含零，可畫負值。
- 單組兩項比較，以第一項為基準自算相對變化；基準非正數時不計算百分比。
- `better` 只影響好壞顏色；「數字變大」不會一律被稱為改善。
- 引用／實測須有來源，估算／示意須寫明假設。工具只能驗證欄位，無法證明模型提供的來源為真；模型仍須核實數據及可比性。
- 不同單位應分圖；缺失值不得補零，沒有可靠數據不應硬畫圖。
- IP、埠號、型號不觸發統計圖；要求架構圖仍用原先設備圖示與拓撲工具。
- 隱藏繪圖代碼串流，完成後保留繁體中文分析，附 PNG 預覽、SVG、HTML 數據表及 CSV。
- HTML 不執行模型產生的程式碼，離線可檢視；CSV 防護文字公式注入。

測試：`python3 scripts/test-data-charts.py`。使用已安裝 CairoSVG 的 Python，設定
`OPENWEBUI_TEST_RENDER=1` 可額外輸出六種範例到 `deliverables/data-chart-examples/`。

部署：使用 runtime venv 執行 `scripts/deploy-data-charts.py <runtime>`。
先備份資料庫，再經 Open WebUI 的版本化 API 更新工具與全域 Filter，不直接改資料表。
# 四象限定位圖修正

`chart_type=quadrant` 使用兩組 X/Y 相對座標（0–1）及品牌 labels。主觀品牌定位必須標示 `illustrative`，不可冒充市佔率、實測或市場調查。PNG 採平台單一 CJK 字型，SVG 保留向量，HTML 提供可閱讀資料表及 CSV。以編號對應品牌避免密集標籤重疊。

明確「圖表／定位矩陣／四象限」請求會啟用伺服器圖表工具；舊版模型若仍回傳 Mermaid `quadrantChart`，只解析受限座標資料轉成真正 PNG，不執行模型程式碼，也不依賴前端 Mermaid。一般長條與折線支援不變。

定位圖不能取代使用者要求的市佔率：沒有可靠比例，必須說明缺少資料，不能編造數值。此次修復保留原模型座標並標記為未查證的定性示意，也修正原文與自己座標相反的象限描述。

## 可重用統計圖表樣板 v1

本次是既有系統的 Extension：保留原有架構圖、品牌圖庫、工具 ID、輸出連結、繁體中文與 tokens/s。
沿用先前已選定的深色分析風格：背景 #0B0F17、文字 #F8FAFC／#94A3B8，藍／青綠為系列，琥珀為目標；紅色僅在瀑布表示減少，不推論為壞事。
Design Read：研究者閱讀的數據視覺化，Variance 3、Motion 1、Density 7、Assets 1、Fidelity 10。
具體結果：穩定版式、無裝飾動畫、標示單位／來源、向量與資料表優先、不下載新圖表程式庫。
字型使用既有系統 CJK 字型，8px 節奏、16–18px 標籤；樣板縮圖提供放大入口，手機圖面可左右捲動、資料表獨立捲動，不強縮成難讀的字。

18 種圖型＋分組長條配置（目錄共 19 項）：

| 用途 | chart_type | 檢查與選項 |
|---|---|---|
| 比較 | bar / horizontal_bar | 多 series 即分組比較，保留零基準 |
| 左右 A/B | tornado（butterfly 別名） | 恰兩組非負值、左右同尺度 |
| 多維比較 | radar | 3–8 軸，最多3組，共同 0–options.max 量尺 |
| 單指標 | gauge | 1類別1數值，min/max/target，不截斷超量尺值 |
| 趨勢 | line / area | 原順序，area 多組重疊不堆疊 |
| 增減 | waterfall | 首值總額，其餘預設增減；roles 指 total/change，總額不符拒絕 |
| 組成 | pie / doughnut | 單組非負，最多7類，總和大於零；分母明示 |
| 總量與組成 | stacked_column | 非負值，可比較絕對總額 |
| 組成百分比 | percent_stacked_column | 每類別合計需大於零，自算100%，CSV保留原值 |
| 層級與權重 | treemap | 葉節點權重；parents 支援 / 路徑，最多4層 |
| 關聯 | scatter / bubble | X/Y或X/Y/面積；x_unit/y_unit/size_unit，不暗示因果 |
| 時程 | gantt | tasks 日期，或開始/結束數值對；可附計畫與已知進度 |
| 轉換 | funnel | 同母體非負遞減；階段寬度正比數量，上階轉換率自算 |
| 定位 | quadrant | 原有0–1定性示意，非市佔 |

`render_data_chart` 增加可選 `options`，不改舊呼叫參數。只驗證並繪製資料，絕不執行模型程式碼。
模板函式可重用；每次仍用本次資料計算，不共用舊回答內容或圖片。選圖規則在全域 Filter 與 Open WebUI 的 `numeric-comparison-charts` skill 中，完整資料格式按需讀 reference，不全塞進每次上下文。

實際驗證發現 gemma4:26b-mlx 的原生工具模式可能只有「這份雷達圖…」文字，沒有任何成品。
因此此已知相容性模型的圖表請求使用小上下文資料規劃：先有短文字，再由模型輸出資料、伺服器驗證並套版。
供應商邊界清除互相矛盾的工具／skills 指令，不執行模型程式碼；其他模型仍使用原生工具。
所有路徑若未有實際成品，明示圖表未完成，不再把成功語氣文字當作已畫好；content/output 與重開對話保持相同。
不把未測試模型宣稱全部相容。每張圖仍需有足夠資料，樣板不取代查證來源或模型推理。

樣板原始資料：`resources/statistical-chart-templates/catalog.json`。
生成目錄：runtime Python 執行 `scripts/build-statistical-chart-templates.py`。
測試：`scripts/test-statistical-chart-templates.py`（19項版式、比例、累計、空值、日期、跳脫、串流、JSON recovery）。
部署：runtime Python 執行 `scripts/deploy-statistical-chart-templates.py <runtime>`，先備份 DB／現有檔案，再更新版本化 API；不修改聊天或使用者權限。
預覽：`/static/statistical-charts/v1/preview.html`；持久副本在 runtime `data/statistical-charts/v1`，套件升級若覆蓋 static 可重跑部署恢復。
