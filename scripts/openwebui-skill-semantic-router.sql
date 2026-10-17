-- Installs the global Skill semantic-routing inlet Filter.
BEGIN IMMEDIATE;

INSERT INTO function (
  id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at
)
VALUES (
  'openwebui_skill_semantic_router',
  @owner_id,
  'Skill 語意自動路由',
  'filter',
  CAST(readfile('scripts/openwebui-skill-semantic-router.py') AS TEXT),
  '{"description":"使用本機 multilingual-e5 embedding 與關鍵詞混合評分，自動載入最相關的 Open WebUI Skills；技術架構圖優先使用 Fireworks，手動選擇仍優先。","manifest":{"title":"Skill 語意自動路由","description":"依照訊息語意自動載入少量最相關的 Skills。","version":"1.1.0"}}',
  '{"priority":-100,"enabled":true,"max_skills":2,"min_score":0.9,"show_status":true}',
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
