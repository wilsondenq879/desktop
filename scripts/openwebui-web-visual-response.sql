-- Open WebUI Web-side visual response policy.
-- Scope: Wilson's local admin account and existing model presets only.
-- The marker keeps this script idempotent.

BEGIN IMMEDIATE;

UPDATE user
SET settings = json_set(
  COALESCE(settings, '{}'),
  '$.ui.system',
  COALESCE(json_extract(settings, '$.ui.system'), '') || '

<openwebui-desktop-visual-response-policy>
預設以繁體中文回答，保留必要的英文技術名詞。

當圖表能實質釐清關係時，主動使用視覺化；不要為裝飾而畫圖。適用於系統或軟體架構、網路拓撲、硬體或 RDMA 連線、資料或控制流程、安全區域、產品生態、三項以上比較與決策分支。

視覺化選擇：
1. 架構、網路、流程、硬體連線：優先建立可預覽的 HTML Artifact，使用內嵌 SVG。
2. 需要互動或狀態切換：使用 HTML 或 React Artifact。
3. 比較：使用清楚的 Markdown 表格。
4. 數值資料：使用合適圖表；資料不足時不要捏造數字。
5. 無法建立 Artifact 時才使用 Mermaid；不要使用 ASCII 圖。

Artifact 規範：深色專業技術風格（背景 #0B0F17、卡片 #172235、主要文字 #F8FAFC、次要文字 #94A3B8）；以 SVG viewBox、圓角節點與直線或正交連線建立可縮放圖。綠色表示正常或啟用資料流、藍色表示網路或資訊、橙色表示遠端或警示、紅色表示封鎖或安全邊界。標示實體連線與邏輯資料流的差異，避免交叉線與過度裝飾。不要把 HTML 或 SVG 原始碼直接貼在對話正文；請建立可預覽 Artifact，並在下方以精簡文字解讀。

技術正確性：清楚區分已知事實、推論、假設與提案；不杜撰頻寬、延遲、效能、規格或產品支援度。若需求有不確定處，明確標記假設。
</openwebui-desktop-visual-response-policy>'
)
WHERE id = @owner_id
  AND COALESCE(json_extract(settings, '$.ui.system'), '') NOT LIKE '%<openwebui-desktop-visual-response-policy>%';

-- Model-specific params.system overrides the account setting. Preserve every
-- existing model prompt and append the same policy only where one exists.
UPDATE model
SET params = json_set(
  COALESCE(params, '{}'),
  '$.system',
  COALESCE(json_extract(params, '$.system'), '') || '

<openwebui-desktop-visual-response-policy>
預設以繁體中文回答，保留必要的英文技術名詞。當技術圖表能實質提升理解時，主動建立可預覽的 HTML Artifact，優先使用內嵌 SVG：架構、網路、流程、硬體或 RDMA 連線、安全區域、多方關係都適用；比較使用清楚的 Markdown 表格；無法建立 Artifact 時才使用 Mermaid；不要使用 ASCII 圖或在正文貼出未渲染的 HTML/SVG 原始碼。

Artifact 採深色專業技術風格：背景 #0B0F17、卡片 #172235、主要文字 #F8FAFC、次要文字 #94A3B8；以可縮放 SVG viewBox、圓角節點與直線或正交連線呈現。綠色為正常或啟用資料流、藍色為網路或資訊、橙色為遠端或警示、紅色為封鎖或安全邊界。區分實體連線與邏輯資料流，避免交叉線、過度裝飾與虛構數據。清楚標記事實、推論、假設與提案。
</openwebui-desktop-visual-response-policy>'
),
updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE COALESCE(json_extract(params, '$.system'), '') <> ''
  AND COALESCE(json_extract(params, '$.system'), '') NOT LIKE '%<openwebui-desktop-visual-response-policy>%';

INSERT INTO prompt (
  id, command, user_id, name, content, data, meta, is_active, version_id, tags, created_at, updated_at
)
SELECT
  '785e5d7e-6a95-4f7d-963e-51af34ecb5f2',
  'visual',
  @owner_id,
  '技術圖表視覺化',
  '請把本題整理為專業的技術視覺化回覆。

1. 先給出一句結論。
2. 若本題存在架構、拓撲、流程、比較、硬體連線或多方關係，建立可預覽的 HTML Artifact，採內嵌 SVG 技術圖；不要把 HTML/SVG 原始碼貼在訊息正文。
3. 圖表使用深色、高對比、可縮放、圓角節點與清楚的色碼；區分實體連線、邏輯資料流、遠端連線與安全邊界。
4. 需要比較時附上精簡 Markdown 表格。
5. 全程繁體中文，保留英文技術名詞；不捏造數據，將假設與提案清楚標示。
6. 如果圖表不會提升理解，改以結構化文字回答，不要硬畫圖。',
  '{}',
  '{"description":"將技術問題轉為可預覽的架構圖、拓撲圖、流程圖或比較表。"}',
  1,
  '0edf02a0-12fc-4b57-8fbe-6635e67c4c0e',
  '["visualization","technical-diagram"]',
  CAST(strftime('%s', 'now') AS INTEGER),
  CAST(strftime('%s', 'now') AS INTEGER)
WHERE NOT EXISTS (SELECT 1 FROM prompt WHERE command = 'visual');

INSERT INTO prompt_history (
  id, prompt_id, parent_id, snapshot, user_id, commit_message, created_at
)
SELECT
  '0edf02a0-12fc-4b57-8fbe-6635e67c4c0e',
  '785e5d7e-6a95-4f7d-963e-51af34ecb5f2',
  NULL,
  json_object(
    'name', '技術圖表視覺化',
    'command', 'visual',
    'content', '請把本題整理為專業的技術視覺化回覆。',
    'data', json('{}'),
    'meta', json('{"description":"將技術問題轉為可預覽的架構圖、拓撲圖、流程圖或比較表。"}'),
    'tags', json('["visualization","technical-diagram"]'),
    'access_grants', json('[]')
  ),
  @owner_id,
  'Initial version',
  CAST(strftime('%s', 'now') AS INTEGER)
WHERE EXISTS (
    SELECT 1 FROM prompt
    WHERE id = '785e5d7e-6a95-4f7d-963e-51af34ecb5f2'
  )
  AND NOT EXISTS (
    SELECT 1 FROM prompt_history
    WHERE id = '0edf02a0-12fc-4b57-8fbe-6635e67c4c0e'
  );

COMMIT;
