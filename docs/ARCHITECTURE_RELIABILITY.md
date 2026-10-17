# 架構圖可靠性修正（Renderer 6.2 / Guard 13.2）

## 根因

實際失敗資料是合法的五節點 GPU cluster：交換機、兩台 GPU 工作站、儲存與管理電腦。管理連線跨越中間一層；原排版器只有一次分層重試，無法取得滿足路由約束的正交連線。Filter 又把實際排版失敗顯示成「模型沒有提供有效資料」，掩蓋原因。

合成壓力探查也重現：固定的 30 組扇出／跨層／群組場景，在原幾何流程有 24 組未通過。這不是所有模型或所有用戶的失敗率，只是該固定測試組。

## 修正

- 星狀 hub 高度與埠距跟分支列距一致，不再把大量分支擠到 36px 埠距。
- 群組若分散於畫布兩側，以相同名稱的區域表示，不以巨框誤包其他設備。
- 中文 ID 使用穩定映射；拒絕重複 ID、未知端點、自我連線和超出範圍資料，不悄悄改連線。
- 卡片依最終寬度計算換行與高度；最多 48 埠分列，避免負寬與文字截斷。名稱決定設備類別，細節裡的 NIC/SFP 不再取代主機／交換機圖示。
- 排版採有時間上限的多候選重排。若一張全域圖仍不合格，使用明確標示的「連線分解檢視」：N 編號代表同一設備、L 編號代表原始連線；所有設備、群組、方向與邊完整保留，未改成假拓撲。
- 每次在裝飾圖示、完成換行後，對**最終 SVG** 執行 XML、marker、collision、geometry、composition 檢查，再匯出 PNG。不把中間草稿成功當成成品成功。
- SVG 含 canonical graph metadata，逐一核對設備與連線；PNG 有實際尺寸／像素預算檢查。圖示只來自本機清理後圖庫，不執行模型程式碼。
- 介面通知斷線、可選診斷報告寫入失敗，不再把已驗證成品改成失敗。實際輸入／匯出錯誤仍保留，不偽裝成功。
- 真正的模型資料不足與 Renderer 失敗分開回報。失敗的正規化幾何只寫至私有 `DATA_DIR/visual-profile/render-failures`，不放公開 static 或 repo。
- 冷模型沒有及時給出先行文字時，改由使用者原句中的設備名稱產生規劃前言；不因可選的前言逾時而只留下空白等圖片，也不因此編造工程結論。

## 品質與介面

依 ui-ux-pro-max 的關係圖、可讀性與錯誤回復指引，維持節點文字字級，以標籤、圖示、箭頭與線型共同表達語意，不僅靠顏色。複雜圖提供分解圖及放大預覽，不縮字硬塞、不只留下紅字。

## 驗證方法與界線

```sh
python scripts/probe-architecture-layouts.py --count 30 --layout star
python scripts/test-architecture-reliability.py --count 40
python scripts/test-render-notifications.py
python scripts/test-mixed-visual-reports.py
```

使用已安裝 `scripts/visual-profile-requirements.txt` 的 Python 環境。第二個測試實際輸出 40 組 SVG/PNG/HTML，加 1 組強制主排版失敗；驗證最終 SVG、canonical IDs、所有邊／方向／虛線、中文 ID、48 埠與無假成功。產物和 JSON 結果在被 Git 忽略的 `deliverables/architecture-reliability-v1`。

對模型端另以 `verify-diagram-live.py` 驗證真實 API、先行文字、無繪圖代碼串流、HTTP PNG/SVG、content/output 一致、重開對談。合成測試對談在程式結束時封存，包括測試未通過的情況。

支援的單圖輸入為 2–14 個唯一節點、1–22 條有效連線。這不是對任意模型、任意輸入或服務斷線宣稱 100% 成功；缺少節點／關係、模型超時、儲存耗盡等仍須如實回報。目標是合法拓撲不再因固定版型、跨線或通知失敗而白白丟失成品。
