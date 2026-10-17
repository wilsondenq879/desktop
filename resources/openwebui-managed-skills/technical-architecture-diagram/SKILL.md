---
name: 內嵌技術架構圖（備援）
description: 當 Fireworks runtime 或桌面檔案工具不可用時，將網路拓撲、AI／GPU／RDMA 架構與技術流程轉成 Open WebUI 內嵌 React+SVG 圖卡；正常情況優先使用 Fireworks Tech Graph。
---

# 技術架構圖設計

這是無法執行 Fireworks renderer 時的備援 Skill。若已載入
`fireworks-tech-graph`，停止使用本 Skill 的 `openwebui-diagram` 格式，交由 Fireworks
產生可預覽的 SVG／PNG／HTML 成品，避免兩套 renderer 同時輸出。

當圖能實質釐清元件、層級、邊界或資料流時使用。先用一至兩句繁體中文給結論，再輸出一個 `openwebui-diagram` JSON 圍欄；圍欄外可補充必要的技術解釋，但不要重複逐項朗讀圖中內容。

## 選圖原則

- 實體網路、硬體連接、GPU／RDMA：`topology`
- 使用者、服務、API、MCP 的步驟與方向：`flow`
- 硬體、網路、平台、應用的上下層關係：`layers`
- 兩種方案的同欄位對照：`comparison`
- 階層與資料流優先使用 `TB`；簡短的端到端鏈路可使用 `LR`。Renderer 會在手機自動改成直向。

## 圖表資料格式

只輸出嚴格有效 JSON，不含註解、尾端逗號、HTML、SVG、Mermaid 或 ASCII 圖。

```openwebui-diagram
{
  "kind": "topology",
  "direction": "TB",
  "title": "25G RoCE v2 AI Fabric",
  "subtitle": "運算節點透過無損乙太網路交換梯度與模型資料",
  "groups": [
    {"id":"compute","label":"AI 運算區","tone":"active","nodeIds":["host-a","host-b"]},
    {"id":"fabric","label":"AI 網路骨幹","tone":"network","nodeIds":["switch"]}
  ],
  "nodes": [
    {"id":"host-a","label":"AI 主機 A","detail":"GPU + 25G NIC","type":"gpu","group":"compute","level":0,"tone":"default"},
    {"id":"host-b","label":"AI 主機 B","detail":"GPU + 25G NIC","type":"gpu","group":"compute","level":0,"tone":"default"},
    {"id":"switch","label":"25G RDMA Switch","detail":"RoCE v2／PFC／ECN","type":"switch","group":"fabric","level":1,"tone":"network"}
  ],
  "edges": [
    {"from":"host-a","to":"switch","label":"25GbE／RoCE v2","tone":"active","bidirectional":true},
    {"from":"host-b","to":"switch","label":"25GbE／RoCE v2","tone":"active","bidirectional":true}
  ]
}
```

## 語意規則

- `id`、`from`、`to`、`group` 使用英文、數字、`-`、`_`，且連線端點必須存在。
- `type` 從 `client`、`switch`、`router`、`firewall`、`server`、`gpu`、`nic`、`storage`、`cloud`、`service`、`database`、`default` 選擇，讓圖卡顯示正確設備圖示。
- `level` 表示真正的架構層級；同層只放平行或對等元件，不要把整條鏈路全部塞在同一層。
- `groups` 只用於有意義的區域或安全邊界，例如使用者端、Access、Core、DMZ、AI Fabric、資料中心；不要為每個節點各畫一個群組。
- `tone` 從 `default`、`network`、`active`、`remote`、`blocked` 選擇。顏色必須承載語意，不能只是裝飾。
- 實體纜線與正常資料流用實線；備援、遠端或邏輯關聯才使用 `dashed:true`。
- 雙向交換使用 `bidirectional:true`。不要用兩條方向相反的 edge 重複表示。
- 節點標籤應是設備或服務名稱；`detail` 才放介面、協定、速率或角色。保持短句，避免段落。

## 品質門檻

- 一張圖聚焦一個主要問題，通常 3–9 個節點；超過 12 個節點時拆圖。
- 網路圖至少讓讀者看出端點、交換／路由層、核心服務或資料目的地。
- 區分實體連線、邏輯控制與資料流，不要混用同一種線條。
- 不虛構頻寬、延遲、產品功能或協定支援；不確定時省略數值並在文字中標示假設。
- 如果關係不足以形成有意義的圖，改用 Markdown 表格，不要為了畫圖而畫圖。
