-- Installs the Fireworks Tech Graph runtime instructions as a native Open WebUI Skill.
BEGIN IMMEDIATE;

INSERT INTO skill (
  id, user_id, name, description, content, meta, is_active, updated_at, created_at
)
VALUES (
  'fireworks-tech-graph',
  @owner_id,
  'Fireworks 技術架構圖',
  '使用完整 Fireworks Tech Graph runtime 產生並檢查 SVG 技術架構圖，可輸出 PNG 與離線 HTML；適用於網路拓撲、GPU／RDMA、API／MCP、UML、Agent、Cloud 與技術流程。',
  CAST(readfile('resources/openwebui-managed-skills/fireworks-tech-graph/SKILL.md') AS TEXT),
  '{"tags":["desktop","visualization","architecture","network","rdma","svg"],"source":"desktop-managed","upstream":"https://github.com/yizhiyanhua-ai/fireworks-tech-graph","version":"1.2.0","license":"MIT","runtime":"OPENWEBUI_FIREWORKS_SKILL_ROOT"}',
  1,
  CAST(strftime('%s', 'now') AS INTEGER),
  CAST(strftime('%s', 'now') AS INTEGER)
)
ON CONFLICT(id) DO UPDATE SET
  name = excluded.name,
  description = excluded.description,
  content = excluded.content,
  meta = excluded.meta,
  is_active = excluded.is_active,
  updated_at = excluded.updated_at;

UPDATE skill
SET
  name = '內嵌技術架構圖（備援）',
  description = '當 Fireworks runtime 或桌面檔案工具不可用時，使用 Open WebUI 內嵌 React+SVG 圖卡。',
  content = CAST(readfile('resources/openwebui-managed-skills/technical-architecture-diagram/SKILL.md') AS TEXT),
  updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE id = 'technical-architecture-diagram';

COMMIT;
