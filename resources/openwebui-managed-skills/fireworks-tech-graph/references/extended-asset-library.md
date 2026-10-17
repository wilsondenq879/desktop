# Open WebUI 本機技術圖庫 v2

原有 64 個通用符號與 10 個原創網通／Local AI 元件，加上四套清理過的 SVG 圖庫。
這不是四套 Codex skills；資料與工具安裝於 Open WebUI 伺服器，手機與網頁共用。

| 命名空間 | 用途 | 固定來源版本 | 授權 |
|---|---|---|---|
| lucide: | 一致線條的通用符號 | lucide-static 1.59.0 | ISC，部分沿用 MIT |
| lobe: | AI／LLM 品牌 | @lobehub/icons-static-svg 1.95.1 | MIT，商標規範另計 |
| dashboard: | 自架服務、應用程式 | 6d31345986eba2067a63eb41c1a5a87d4e8e850a | Apache-2.0，第三方圖像權利另計 |
| simple: | 品牌識別 | simple-icons 16.35.0 | CC0-1.0，商標規範另計 |
| hardware: | 迷你 AI PC、工作站、網卡、交換器、NAS、機櫃、線纜 | Local original v2 | MIT |

圖庫預覽：`/static/architecture-icons/v2/preview.html`；來源與完整授權：`NOTICE.html`。
不能把圖庫授權當成商標使用的全面許可，更不能藉通用設備符號推定埠數、尺寸或相容性。

## 按需使用

原生工具模式：不知道 ID 時才呼叫 `search_diagram_assets("ollama",8)`，再把回傳 ID 傳給
`render_technical_architecture` 的 nodes[].icon。不要將 9,000 多個名稱或 SVG 全塞進提示詞。
也可完全省略 icon，伺服器會以中文類別／英文品牌選擇設備符號與品牌徽章。

特定圖示例：`lucide:router`、`lobe:ollama`、`lobe:qwen-color`、`dashboard:docker`、`simple:asus`、
`hardware:mini-ai-pc`、`hardware:pcie-nic`、`hardware:ai-workstation`、`hardware:desktop-switch`。
品牌只作識別；例如 GX10 仍畫成設備，不會只剩 ASUS 商標，也不會畫成可插 Intel E800 的機箱。

## 六種構圖

`layered` 保留 level 分層；`star` 中心拓撲；`dual_compute` 雙欄主機，可用兩個 group 各代表一台；
`rack` 以 group=rack 明確指定示意架內設備、外部設備放一側；`dataflow` 按 level 由左至右；
`ecosystem` 依真實連線保留同一分支的相關節點。不確定選 `auto`。

模板僅決定幾何，不新增或刪減節點／連線。機櫃配置為概念，不宣稱產品尺寸、供電、散熱或安裝
方式相容。檢查仍維持零交叉與最短線段要求；若某拓撲無法達標，不冒充成功成品。
