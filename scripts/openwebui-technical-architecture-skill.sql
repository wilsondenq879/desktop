-- Installs the Desktop-managed architecture diagram skill into Open WebUI.
BEGIN IMMEDIATE;

INSERT INTO skill (
  id, user_id, name, description, content, meta, is_active, updated_at, created_at
)
VALUES (
  'technical-architecture-diagram',
  @owner_id,
  '技術架構圖設計',
  '將網路拓撲、AI／GPU／RDMA 架構、軟硬體分層、API／MCP 整合與技術流程轉成可讀的 Open WebUI React+SVG 專業架構圖。',
  CAST(readfile('resources/openwebui-managed-skills/technical-architecture-diagram/SKILL.md') AS TEXT),
  '{"tags":["desktop","visualization","network","architecture"],"source":"desktop-managed"}',
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

COMMIT;
