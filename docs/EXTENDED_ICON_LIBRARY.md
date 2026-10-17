# Open WebUI 技術圖庫 v2

部署位置是 Open WebUI 伺服器，不是 Codex 的 skills 目錄；網頁與手機 App 共用，不需重裝 App。

## 內容

- Lucide：2,159 個（lucide-static 1.59.0）
- Lobe Icons：948 個（@lobehub/icons-static-svg 1.95.1）
- Dashboard Icons：2,654 個（commit `6d31345986eba2067a63eb41c1a5a87d4e8e850a`）
- Simple Icons：3,466 個（simple-icons 16.35.0）
- 原有 64 個通用符號＋10 個新硬體元件；總計 9,301 個可用圖示。

安全清理排除 981 個不符合目前向量子集的檔案，包括 style/filter、圖片冒用 SVG 副檔名、
非標準 ID、無法安全解析的向量。不是宣稱上游內容惡意；排除明細在 sources.lock.json。
沒有執行下載套件的 JS、npm lifecycle 或模型提供的 SVG 程式碼。

新增硬體符號：迷你 AI 電腦、桌上型一般／高速交換器、工作站、PCIe 網卡、NAS、mini rack、
SFP 類介面、DAC、GPU。它們是原創通用設備類別，**不是官方產品外觀、埠數或安裝相容性證明**。

## 選圖與效能

`nodes[].icon` 可用 `lucide:router`、`lobe:ollama`、`lobe:qwen-color`、`dashboard:docker`、
`simple:asus`、`hardware:mini-ai-pc` 等命名空間，舊的 nas/router/vpn ID 完全保留。

`search_diagram_assets(query,limit=8)` 只回小份 ID、名稱、來源與授權；不將 25MB 圖庫或
9,301 個名字塞進提示詞。catalog 按路徑與 mtime 快取，未指定 icon 時只用原創類別與
精選品牌別名自動選取。實體硬體保持設備符號，品牌小徽章補充辨識，不用商標取代機箱。
品牌原色不重繪；白色變體採深底板，其餘採淺底板。通用線條統一為 48px 上的 1.8px。

## 構圖

`layout=auto/layered/star/dual_compute/rack/dataflow/ecosystem`。幾何模板不改工程關係；
星狀／生態圈保留同支路節點在同一側；機櫃旁走線避開設備，group=rack 才算架內概念。
沒有捏造機箱尺寸、掛耳、承重、散熱或擴充相容性。特定拓撲若未通過原交叉／走線品質
檢查，只允許保留所有設備與連線重試分層構圖一次，並明確標示實際改用分層；不放寬品質門檻。

## 安全與授權

上游版本固定，npm tarball 核對 SHA-512；Dashboard 使用固定 commit。保留授權與來源，
Lobe 靜態 npm 套件缺少 LICENSE，另從同一發布 commit 取得 MIT notice。開源圖庫授權
不取代第三方商標、品牌使用規範或背書許可。

離線 SVG 拒絕 DTD、外部 href、腳本、事件、外部 paint URL；模型只能指定本機 ID，不能讀
任意檔案或執行 SVG。輸出內部 gradient／clip ID 依節點重新加前綴，避免多圖示衝突。
下載 SVG 的 desc 保留所用圖示來源與授權全文，對談另附來源／授權入口。

## 預覽與部署

伺服器 `/static/architecture-icons/v2/preview.html`：可搜尋、依來源過濾、分頁每頁 60 個，
縮圖延遲載入，手機為雙欄；包含六種示意成品與 `NOTICE.html`。

建置 `scripts/build-extended-icon-library.py` → `scripts/test-extended-icons.py`（設定
OPENWEBUI_TEST_RENDER=1）→ `scripts/build-icon-library-preview.py`。
runtime Python 執行 `scripts/deploy-extended-icons.py <runtime>`，先備份 SQLite 和既有
檔案，先安裝資產再透過版本化 Tool／Function／Skill API 發布；保留使用者的核准和存取權設定。

驗證包含：四來源及圖示安全／快取／語意／搜尋測試、六種真實 PNG/SVG/HTML 匯出與全節點／
連線檢查、原有三種網路架構範例、response feedback 與數值圖表回歸。
已實際用 gemma4:26b-mlx 新建驗證對談：先行文字 8.27 秒，renderer 14.65 秒開始，
品牌圖示 PNG 成功、無代碼串流、content/output 與重開一致，完成後封存測試對談。
上述秒數僅該次環境觀測，不代表效能保證；未在實體 iPhone 完整驗證。
