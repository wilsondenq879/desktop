---
name: fireworks-tech-graph
openwebui-name: Fireworks 技術架構圖
openwebui-description: 使用完整 Fireworks runtime 產生並檢查 SVG 技術架構圖，可輸出 PNG 與離線 HTML；適用於網路拓撲、GPU／RDMA、API／MCP、UML、Agent、Cloud 與技術流程。
description: >-
  Create precise SVG technical diagrams, export PNG or offline HTML, and animate
  supported semantic SVGs to GIF. Use for 技術架構、網路拓撲、GPU/RDMA、UML、
  agent、cloud、API/MCP 或 workflow diagrams；不適用於照片、裝飾插畫或統計圖表。
---

# Fireworks Tech Graph

## Open WebUI server runtime

在 Open WebUI 中，這個 Skill 是「實際產生成品」的工作流程，不是只提供繪圖建議或
把 JSON／SVG 原始碼貼在對話裡。預設使用繁體中文標題、節點與說明，技術名詞保留
通用英文。使用者要求架構圖、拓撲圖、硬體連線圖、API／MCP 整合圖、GPU／RDMA
架構或技術流程時，優先使用本 Skill。

使用實際工具 `render_technical_architecture`，在 Open WebUI 伺服器產生 PNG 與 SVG。
不需要桌面或手機的 Open Terminal 連線；不要用 `run_command`、`execute` 或 shell 繪圖。
傳入本題的 title、nodes、edges、groups、visual_family、layout。nodes 含 id、label、level
（由上至下從 0 起），可含 detail、group、tone、icon、port_groups；edges 含 from、to，可含 label、tone、dashed、direction。
工具不在清單時明確回報伺服器 Renderer 未啟用，不要誤稱手機不支援繪圖。
先快速用 2–3 句繁體中文說明本題的架構分層、設備角色與主要連線，再呼叫繪圖工具；
不要只說「我正在畫圖」，也不要等圖片完成才給答案。正常說明先顯示，繪圖期間顯示進度。
禁止在對話串流 JSON、Mermaid、SVG、HTML、Canvas、React 或任何繪圖程式碼。
工具完成後保留前面的文字並附回成品圖，不另寫長篇重複說明。

1. 不要把 JSON、Mermaid、ASCII 或 SVG 原始碼當成最終回答；它們只能作為隱藏的工具輸入。
2. 伺服器 Renderer 管理成品位置，直接使用工具回傳的可預覽網址，不要猜測本機路徑。
3. 至少產出 SVG；環境支援時再產出 1920px PNG 與離線 HTML。完成後必須把 SVG／PNG
   或 HTML 成品附回對話並提供可預覽入口，不能只回報本機路徑。
4. 不輸出 Mermaid、ASCII 方塊圖或 `openwebui-diagram` JSON 來冒充 Fireworks 成品。
5. 不得為了排版刪減設備或連線；保留同層設備、分支與雙向關係，不套用固定 Local AI 圖。
6. Renderer 已安裝 Lucide、Lobe Icons、Dashboard Icons、Simple Icons，與原創設備 SVG。用 `icon` 指定設備／服務的圖示 ID；
   未指定會依節點名稱自動配對。常用 `nas`、`workstation`、`mini-pc`、`gpu`、`network-card`、
   `router`、`switch`、`rdma-switch`、`aggregation-switch`、`vpn`、`users`、`ai-model`、
   `agent`、`api`、`mcp`、`cloud`、`vector-db`。完整清單見 [圖示目錄](references/architecture-icon-catalog.md)。
   圖示代表通用設備類別；品牌產品只有使用已核實的官方素材才可宣稱外觀一致。
   本機圖庫以命名空間區分，例如 `lucide:router`、`lobe:ollama`、`lobe:qwen-color`、`simple:asus`、
   `dashboard:docker`。專用硬體元件包括 `hardware:mini-ai-pc`、`hardware:ai-workstation`、
   `hardware:pcie-nic`、`hardware:desktop-switch`、`hardware:mini-rack`；非官方產品外觀或規格。
   原生工具模式不確定 ID 時才呼叫 `search_diagram_assets(query,limit=8)`；不要載入整份圖庫。
   沒有指定時伺服器自動選取設備符號及品牌小徽章，品牌標誌只識別、不表示背書。
7. 已知交換器埠數時，可用 `port_groups:[{label:"25G",count:4,tone:"active"},{label:"10G",count:4,tone:"network"}]`
   產生埠位面板；未提供埠數則省略，不能為美觀發明規格。`direction:"none"` 是無箭頭的實體連線，
   `forward`／`both` 用於單向／雙向邏輯流。藍色用一般資料，青綠用高速資料，琥珀用遠端／控制，虛線須有實質意義。
8. 視圖太寬或手機不易讀時，保留工具回傳的「放大互動預覽」連結；不要把字縮成難以閱讀。
9. 構圖 `layout`：`layered` 分層、`star` 中心拓撲、`dual_compute` 雙欄主機、`rack` 機櫃配置、
   `dataflow` 橫向資料流、`ecosystem` 生態圈；不確定選 `auto`。只改幾何、不改設備與連線。
   機櫃配置必須以 `group:"rack"` 明確指定架內設備，尺寸、散熱與固定相容性未知須寫待核實。
   圖示來源／授權入口由工具附上，下載 SVG 內也保留來源及授權中繼資料。

以下 CLI 指令僅供其他 Agent 環境的技術參考。在 Open WebUI 必須使用上述原生伺服器工具。

One portable Agent Skill for Codex and Claude Code. SVG is the canonical artifact;
PNG, offline HTML and supported GIF motion are output routes. Preserve requested
labels, topology and meaning; a successful command is not a visual quality verdict.

## Locate and select

Resolve the directory containing this file as `SKILL_ROOT`. In Open WebUI use the
runtime resolution above. In other supported agents, use
`${CLAUDE_SKILL_DIR}` in Claude Code or the absolute directory in Codex's loaded
skill metadata. Do not assume cwd or a previous shell variable persists.

Use the installed version for the task. Run `version` for source/version questions
and `doctor` when diagnosing a missing renderer, font or dependency; do not make
installation, updates or a complete test suite prerequisites for every diagram.

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"
"${FIREWORKS_PYTHON:-python3}" "$SKILL_ROOT/scripts/fireworks.py" version
```

- Honor the user's diagram type, content and style; choose sensible reversible
  details from the brief. Ask only for a material missing engineering fact or
  a choice the user explicitly reserved. A request to draw includes local rendering.
- For network, hardware, RDMA and product-ecosystem architecture, use a true
  topology rather than a single process line: place a core or aggregation node,
  then create at least two parallel downstream branches (for example compute A/B,
  storage, management or remote access). Keep data flow, control flow and trust
  boundaries visually distinct. Do not invent unsupported specifications merely
  to add branches; use the user's named devices and clearly mark proposed nodes.
- Styles 1–7 and 9–12 have JSON generators. Style 8 (Dark Luxury) remains
  AI-authored SVG: use its style reference, then the same validation/export gates.
- Default to Style 1 Flat Icon when no user/workspace preference applies. Load the
  actual matching file from [the style matrix](references/style-diagram-matrix.md).
  Read other styles only for a requested comparison.
- Styles 9–12 default to C4, cloud, event and observability semantic contracts.
  Validate facts before layout; do not invent responsibilities, protocols or metrics.
- Adapt an existing valid SVG directly when appropriate. JSON generation is not
  required for every edit. Use [diagram/layout guidance](references/diagram-layout-reference.md)
  and [icons](references/icons.md) only for the relevant type or symbols.

## Generate and check

Reuse the user's current brief and artifact; an extra planning document is optional.
For JSON work, select `text_policy: "strict"` when all labels must be visible exactly.
The compatible `report` default preserves full labels in SVG metadata and reports
any visible truncation. Resolve that warning before claiming complete exact text.
For polished work apply the [composition contract](references/composition-quality-contract.md).

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"
"${FIREWORKS_PYTHON:-python3}" "$SKILL_ROOT/scripts/fireworks.py" validate architecture input.json
"${FIREWORKS_PYTHON:-python3}" "$SKILL_ROOT/scripts/fireworks.py" render architecture input.json diagram.svg --report layout.json
"${FIREWORKS_PYTHON:-python3}" "$SKILL_ROOT/scripts/fireworks.py" check diagram.svg
"${FIREWORKS_PYTHON:-python3}" "$SKILL_ROOT/scripts/fireworks.py" export-png diagram.svg diagram.png --width 1920
```

`check` validates SVG identity, marker references, generic collisions, semantic
geometry and composition. Inspect the report's typography and palette scope;
heuristic text widths do not replace inspecting the actual rendered font.
Use [visual quality guidance](references/visual-quality.md) for readability and
style-specific refinements. Keep one semantic connector per business edge.

## Additional outputs

- **PNG:** prefer `export-png`, which reads root canvas dimensions, limits output
  size, writes atomically and reads the PNG dimensions back. Alternate renderer
  details are in [PNG export](references/png-export.md).
- **HTML:** `fireworks.py export-html diagram.svg diagram.html`. One sanitized
  offline file provides pan/zoom, source copy and static image downloads.
- **GIF:** “Generate a GIF”, “Animate this diagram”, “生成 GIF”, “制作 GIF” and
  “让这张图动起来” select the existing semantic SVG's motion route. Styles 1–12 are enabled
  for the documented scene contracts; arbitrary same-style topologies are not
  promised. Load [motion effects](references/motion-effects.md) and run
  `fireworks.py animate diagram.svg diagram.gif`. Default is 960px, 20fps, 5.75s
  with the `+2s-settled-flow` preset and a `.motion.json` report. Historical
  `user-approved` fields describe maintainer-reviewed presets, not authorization
  from the current user to publish, spend or send data.

## Verify the requested outcome

Inspect the final PNG at intended reading size when image viewing is available:
check text completeness, contrast, font substitution, hierarchy, spacing, clipping,
arrow direction, crossings and labels. Preserve style palette and material while
fixing defects. Reuse an unchanged reviewed render; do not keep adding tests or
polish after acceptance passes. If viewing is unavailable, explicitly mark the
visual check skipped and do not claim visual correctness.

After a failed check, use its element IDs and geometry to make a focused repair;
change the approach after two unchanged failures. Widen/split an overfull diagram
instead of hiding required copy or endlessly shrinking type. Do not silently
weaken semantic or composition constraints to obtain a pass.

Complete every requested local output and its applicable checks, then report file
paths, dimensions, visual review and residual limitations. A first SVG does not
complete a requested PNG/GIF/HTML package. Publication or remote delivery requires
its own scope-matching authorization; existing authorization is not requested twice.
