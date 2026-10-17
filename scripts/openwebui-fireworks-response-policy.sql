-- Replaces the retired inline JSON renderer contract with native Fireworks Tool calls.
-- The resulting artifact is an SVG attachment, so no JSON/SVG code needs to stream
-- through a phone or browser chat view.
BEGIN IMMEDIATE;

UPDATE user
SET settings = json_set(
  COALESCE(settings, '{}'),
  '$.ui.system',
  substr(COALESCE(json_extract(settings, '$.ui.system'), ''), 1,
    instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '<openwebui-desktop-visual-response-policy>') - 1
  ) || '

<openwebui-desktop-visual-response-policy>
預設以臺灣正體中文回答。遇到架構、網路拓撲、RDMA／硬體連線、流程、分層關係或有實質比較價值的題目，若 `openwebui_fireworks_renderer` Tool 可用，必須呼叫它產生真實 Fireworks SVG 成品。

呼叫 Tool 時只傳入標題、短副標、節點、連線、群組與 visual_family；不要在對話輸出或串流 JSON、Mermaid、ASCII、SVG、HTML、Canvas、React 原始碼或任何繪圖資料。繪圖進行中只顯示工具的狀態，完成後保留 Tool 回傳的成品圖片，再用一兩句繁體中文說明即可。若 Tool 不可用，改用 Markdown 表格或結構化文字，不要退回舊的 openwebui-diagram 程式碼圍欄。不要杜撰資料、規格或效能數據。
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
預設繁體中文。技術關係需要圖表時，優先呼叫可用的 `openwebui_fireworks_renderer` Tool 產生 Fireworks SVG。Tool 呼叫前後都禁止輸出或串流 JSON、Mermaid、ASCII、SVG、HTML、Canvas、React 原始碼、openwebui-diagram 圍欄或其他繪圖程式碼；只保留 Tool 成品與簡短的繁體中文結論。沒有 Tool 時，改用 Markdown 表格或條列。
</openwebui-desktop-visual-response-policy>' ||
  substr(COALESCE(json_extract(params, '$.system'), ''),
    instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') + length('</openwebui-desktop-visual-response-policy>')
  ),
  '$.function_calling', 'native'
),
updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE instr(COALESCE(json_extract(params, '$.system'), ''), '<openwebui-desktop-visual-response-policy>') > 0
  AND instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') > 0;

UPDATE prompt
SET content = '技術關係需要圖表時，呼叫 openwebui_fireworks_renderer 產生 Fireworks SVG 成品。禁止輸出或串流 JSON、Mermaid、ASCII、SVG、HTML、Canvas、React 或 openwebui-diagram 程式碼；只保留成品與短結論。',
  meta = '{"description":"以 Fireworks Renderer Tool 產生 SVG 技術架構圖，不串流繪圖原始資料。"}',
  updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE id = '785e5d7e-6a95-4f7d-963e-51af34ecb5f2'
  AND command = 'visual'
  AND user_id = @owner_id;

COMMIT;
