-- Installs the global visual-response inlet filter from the sibling Python file.
-- It is idempotent and leaves the existing terminology guard untouched.
BEGIN IMMEDIATE;

INSERT INTO function (
  id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at
)
VALUES (
  'openwebui_visual_diagram_guard',
  @owner_id,
  'Fireworks 技術圖表守門員',
  'filter',
  CAST(readfile('scripts/openwebui-visual-diagram-filter.py') AS TEXT),
  '{"description":"伺服器原生 Renderer 與結構化輸出同步；不串流程式碼。","manifest":{"title":"Fireworks 技術圖表守門員","description":"以 Fireworks Tool 產生可在手機、瀏覽器與桌面預覽的 PNG 架構圖。","version":"6.0.0"}}',
  '{}',
  1,
  1,
  CAST(strftime('%s', 'now') AS INTEGER),
  CAST(strftime('%s', 'now') AS INTEGER)
)
ON CONFLICT(id) DO UPDATE SET
  name = excluded.name,
  type = excluded.type,
  content = excluded.content,
  meta = excluded.meta,
  valves = excluded.valves,
  is_active = excluded.is_active,
  is_global = excluded.is_global,
  updated_at = excluded.updated_at;

COMMIT;
