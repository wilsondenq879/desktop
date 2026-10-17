# 架構圖示庫與 Open WebUI 整合

這是現有 Fireworks 架構圖功能的擴充。使用者提供的參考圖確立黑底、線性設備圖示、青綠高速資料與藍色一般資料的方向。主流程仍由模型提供節點與關係，伺服器負責排版和產生成品，串流守門員不公開繪圖程式碼。

## 圖示資產

`resources/architecture-icon-pack/manifest.json` 是唯一圖示來源，包含 64 個不同造形、中文名稱、分類、語意別名與可信任的 SVG 片段。採用 48px 網格、1.8px 線條與圓角端點；不使用品牌商標或冒充產品官方照片。建置後有 192 個色彩版本、Sprite、Manifest、離線圖庫與三個架構範例。

```sh
python scripts/render-architecture-icon-examples.py
python scripts/build-architecture-icon-pack.py --png --demo-svg deliverables/architecture-diagram-examples/smb-topology.svg
```

Python 環境須有 CairoSVG。範例透過正式伺服器 Renderer 執行，檢查節點、連線、圖示及成品格式，保留 Fireworks 的單線兩轉彎、間距、文字及交叉檢查；總轉彎上限按連線數量計算。

## 模型輸入

`nodes[].icon` 可指定目錄內 ID；未指定時，工具使用具邊界的英文／中文別名配對，無匹配時使用中性的 app。不能藉 icon ID 讀取任意路徑，也不接受模型提供 SVG 原始碼。交換器節點若獨佔一層，會畫成較寬設備面板。

```json
{"id":"core","label":"匯聚交換器","level":1,"icon":"aggregation-switch","port_groups":[{"label":"25G","count":4,"tone":"active"},{"label":"10G","count":4,"tone":"network"}]}
```

埠數與速度必須來自使用者或已核實資料；未知就省略。實體連線使用 direction=none，邏輯流使用 forward/both，控制／遠端預設琥珀色且虛線僅用於有意義的區別。

## 佈署

```sh
python scripts/deploy-architecture-icon-pack.py /path/to/OpenWebUIRuntime
```

佈署先建立一致的 SQLite 備份，安裝持久資產到 runtime 的 data/architecture-icons 與 skills/fireworks-tech-graph/assets/icons/technical，並發布至目前套件的 static/architecture-icons。透過 Open WebUI v0.12 的工具、函式與 Skill API 儲存新版本與更新快取，保留原有核准選項和存取權限。

圖庫網址：`/static/architecture-icons/v1/preview.html`。後續重新安裝 Open WebUI 套件時可再執行佈署命令，從資產來源恢復圖庫。

生成圖回傳 PNG、可編輯 SVG 與互動 HTML。PNG 保持手機 WebView 相容性；HTML 提供放大閱讀。圖示圖庫本身使用白色、深色及分類色三種輸出，圖表內預設白色圖示，連線色另行表達關係。
