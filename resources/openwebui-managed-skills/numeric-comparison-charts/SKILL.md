---
name: numeric-comparison-charts
description: 用現成統計樣板繪製比較、趨勢、組成、分佈與時程；支援長條、旋風、雷達、儀表、面積、瀑布、圓餅、環形、堆積、樹狀、散點、氣泡、甘特、漏斗及四象限圖，先文字後成品。
---

# 數值比較與趨勢圖

適用於資料足以支持圖型的回答：比較／趨勢通常兩個以上資料點；單指標儀表可一個數值，甘特可一項任務。不把任何出現數字的問題都硬畫圖。
以繁體中文先給簡短結論，呼叫 Open WebUI 伺服器原生工具 `render_data_chart`，
再附成品與限制。這不是桌面工具，不需要 Open Terminal、手機配對或 shell。

## 選圖

- 類別、產品或效能比較：`chart_type=auto` 或 `bar`。
- 長名稱或較多項：`horizontal_bar`。
- 同單位的多組比較：提供多個 series，產生分組長條圖。
- 依時間排列的數據：`line`，labels 必須按時間順序。
- 趨勢與數量面積：`area`，多組為重疊而非堆積，不解讀為累計總量。
- A/B 對應比較／人口金字塔：`tornado`（亦接受 `butterfly`），兩組非負，左右相同尺度；不能將左側誤稱負值。
- 多面向能力：`radar`，3–8 軸、最多 3 組共同量尺，`options={max:100}`。沒有測量／共同量尺不可編造品牌評分，不同維度單位必須先有明確的正規化方法。
- 單項進度／KPI：`gauge`，一個 label、一組數值，`options={min:0,max:100,target:85}`。上下限與目標依資料，不自行設定績效標準。
- 增減到總額：`waterfall`，單組第一項為期初，其餘預設增減，工具自算合計；若已提供中／期末總額，`options.roles` 等長，如 `['total','change','change','total']`，工具驗證累計。
- 組成：`pie`／`doughnut`，單組非負、最多 7 類，分母為提供項目合計；資料不完整不能宣稱整體市佔。
- 總量與組成：`stacked_column`；只比較每類佔比：`percent_stacked_column`。輸入仍是原始非負數，百分比由工具計算。
- 層級與權重：`treemap`，單組葉節點數值；可 `options.parents=['硬體/算力','硬體/網路','軟體']`，不另把父層合計當葉節點再計一次。
- 兩個連續變數：`scatter`，series 順序 X、Y，`options={x_unit:'W',y_unit:'tokens/s'}`。
- 三個量：`bubble`，series 順序 X、Y、氣泡面積，`options={x_unit:'W',y_unit:'tokens/s',size_unit:'萬元'}`，第三項必須大於零。分軸標示，不推論因果。
- 專案時程：`gantt`，labels=任務，series=[]，`options.tasks=[{start:'2026-10-01',end:'2026-10-05',progress:40},...]`；progress 未知則省略，不能補零。若要對比計畫，每項任務均提供 planned_start/planned_end。同日畫里程碑。也支援開始／結束數字對，unit 為日／週，options.progress 與 labels 等長。
- 單向階段轉換：`funnel`，單組同母體非負且遞減，自算上階轉換率。寬度正比數量，不用誤導的梯形面積。不符合遞減流程改長條。
- 相對品牌／方案定位：`quadrant`，X/Y 兩組 0–1 相對座標，主觀定位用 illustrative 並明示非市場調查、非市佔。
- 架構、拓撲、流程圖改用 Fireworks 技術架構圖，不把節點關係當統計數據。

完整資料範例見 `references/chart-template-catalog.json`，按需查閱，不將整份目錄塞入每次上下文。
視覺預覽：`/static/statistical-charts/v1/preview.html`。不可將樣板示意數字當目前問題的事實。

## 工具參數與資料約束

`title`、`labels`、`series=[{name,values}]`、`unit`、`data_kind` 必填。
每個 values 必須是數值且長度等於 labels，類別比較的所有 series 同單位、同測試條件才比較。
散點／氣泡的 X/Y/大小是不同變數，依各自 options 單位標示。日期甘特依 tasks 提供完整日期，series 為空。
`data_kind` 分 measured（實測）、reported（引用）、estimated（估算）、
illustrative（示意）、user_provided（使用者提供）。引用／實測須有 sources，
包含來源、日期、測試條件；估算／示意須有 note 說明假設或非實測性質。

未知資料不得編造，不得補零，不得將型號、IP、版本、埠號當效能。
不同單位分圖；條件不可比應說明，不製造假比較。沒有可靠數據就用文字說明缺資料。
兩類別單組的相對變化交由工具算；`better=higher/lower/neutral` 表達指標好壞，
例如延遲通常 lower，價格是否更好依情境，不一律當數值增加就是改善。

## 輸出

工具提供對話內 PNG、可編輯 SVG、HTML 數據表和 CSV，直接用真實回傳連結。
保留重點分析、數據來源和限制。不猜測網址，不貼 JSON／React／SVG／Mermaid／
HTML 或 ASCII，不要讓使用者看到繪圖原始碼串流。工具成功後不要重複繪製。
