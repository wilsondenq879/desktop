-- Native tool_ids resolve from tool, never function(type='tool').
BEGIN IMMEDIATE;
INSERT INTO tool (id, user_id, name, content, specs, meta, valves, updated_at, created_at)
VALUES (
  'openwebui_fireworks_renderer', @owner_id,
  'Fireworks 架構圖 Renderer',
  CAST(readfile('scripts/openwebui-fireworks-renderer-tool.py') AS TEXT),
  CAST(readfile('scripts/openwebui-fireworks-renderer-specs.json') AS TEXT),
  '{"description":"伺服器架構圖與數值比較圖工具，64 個 SVG 圖示、設備面板、長條／折線圖及資料表。","manifest":{"version":"4.1.0"}}',
  '{}', CAST(strftime('%s','now') AS INTEGER), CAST(strftime('%s','now') AS INTEGER)
)
ON CONFLICT(id) DO UPDATE SET content=excluded.content, specs=excluded.specs,
  meta=excluded.meta, updated_at=excluded.updated_at;
-- Retain the old record for rollback, but stop loading it as a Function.
UPDATE function SET is_active=0, is_global=0 WHERE id='openwebui_fireworks_renderer';
COMMIT;
