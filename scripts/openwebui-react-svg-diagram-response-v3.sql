-- Switch previously installed Mermaid policies to the React + SVG diagram
-- protocol. The renderer is loaded by the local Open WebUI frontend.
BEGIN IMMEDIATE;

UPDATE user
SET settings = json_set(
  COALESCE(settings, '{}'),
  '$.ui.system',
  substr(COALESCE(json_extract(settings, '$.ui.system'), ''), 1,
    instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '<openwebui-desktop-visual-response-policy>') - 1
  ) || '

<openwebui-desktop-visual-response-policy>
預設以臺灣正體中文回答。架構、網路拓撲、RDMA／硬體連線、流程、分層關係或有實質比較價值的題目，使用 Open WebUI 的 React + SVG 技術圖卡；不要使用 Mermaid 或 ASCII 圖。

先給一兩句結論。需要視覺化時，輸出一個且僅一個有效的 ```openwebui-diagram JSON 圍欄。JSON 必須含 kind（topology、flow、layers 或 comparison）、title、nodes 和 edges。每個 node 使用英文 id、短的繁體中文 label/detail、0 到 5 的 level 與 default/network/active/remote/blocked tone；每個 edge 的 from/to 精準對應 node id。圖卡元件負責 SVG 版面、箭頭、配色和縮放。

絕對禁止 Mermaid、ASCII、文字框線、[Node] --> [Node]、```text、```plain、```ascii 和任何 HTML／SVG／React 原始碼。無法形成安全 JSON 時，用 Markdown 表格或結構化文字代替。不要杜撰資料、規格或效能數據。
</openwebui-desktop-visual-response-policy>' ||
  substr(COALESCE(json_extract(settings, '$.ui.system'), ''),
    instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '</openwebui-desktop-visual-response-policy>') + length('</openwebui-desktop-visual-response-policy>')
  )
)
WHERE id = @owner_id
  AND instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '<openwebui-desktop-visual-response-policy>') > 0
  AND instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '</openwebui-desktop-visual-response-policy>') > 0;

UPDATE model
SET params = json_set(
  COALESCE(params, '{}'),
  '$.system',
  substr(COALESCE(json_extract(params, '$.system'), ''), 1,
    instr(COALESCE(json_extract(params, '$.system'), ''), '<openwebui-desktop-visual-response-policy>') - 1
  ) || '

<openwebui-desktop-visual-response-policy>
預設繁體中文。技術關係需要圖表時，輸出一個有效 ```openwebui-diagram JSON 圍欄給 Open WebUI 的 React + SVG 圖卡渲染。JSON 只包含 kind、title、可選 subtitle、nodes 與 edges；node 的英文 id 必須和 edge from/to 完全對應，label/detail 簡短且為繁體中文，level 為 0 到 5，tone 只用 default/network/active/remote/blocked。

禁止 Mermaid、ASCII、文字框線、[Node] --> [Node]、HTML、SVG、Canvas 或 React 原始碼。沒有安全圖表資料時，改用 Markdown 表格或條列；不要捏造數據。
</openwebui-desktop-visual-response-policy>' ||
  substr(COALESCE(json_extract(params, '$.system'), ''),
    instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') + length('</openwebui-desktop-visual-response-policy>')
  )
),
updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE instr(COALESCE(json_extract(params, '$.system'), ''), '<openwebui-desktop-visual-response-policy>') > 0
  AND instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') > 0;

UPDATE prompt
SET content = '請把本題整理為可直接閱讀的專業技術視覺化回覆。先給一句結論；若有架構、拓撲、流程、比較、硬體連線或多方關係，直接輸出一個嚴格有效的 ```openwebui-diagram JSON 圍欄。Open WebUI 會以 React + SVG 將其渲染成實際圖卡。JSON 必須使用 kind、title、nodes、edges；node id 為英文，edge from/to 精準對應 id，label/detail 用短的繁體中文、level 為 0 到 5，tone 限 default/network/active/remote/blocked。禁止 Mermaid、ASCII、文字框線、HTML、SVG、Canvas、React 原始碼與 [Node] --> [Node]。無法安全畫圖時用 Markdown 表格；不要捏造數據。',
  meta = '{"description":"把技術問題轉為由 Open WebUI React + SVG 圖卡直接渲染的安全 JSON 架構圖、拓撲圖、流程圖或比較圖。"}',
  updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE id = '785e5d7e-6a95-4f7d-963e-51af34ecb5f2'
  AND command = 'visual'
  AND user_id = @owner_id;

COMMIT;
