-- Open WebUI Web-side visual response policy, revision 2.
--
-- The initial policy asked models to create an HTML Artifact first.  Local
-- models often interpreted that as a text-only task and replied with an ASCII
-- code block.  Open WebUI's local frontend has a Mermaid renderer, so this
-- revision makes a valid `mermaid` fence the required static-diagram protocol.
-- It updates only Wilson's account, model prompts already carrying the policy,
-- and the /visual workspace prompt.

BEGIN IMMEDIATE;

UPDATE user
SET settings = json_set(
  COALESCE(settings, '{}'),
  '$.ui.system',
  substr(
    COALESCE(json_extract(settings, '$.ui.system'), ''),
    1,
    instr(COALESCE(json_extract(settings, '$.ui.system'), ''), '<openwebui-desktop-visual-response-policy>') - 1
  ) || '

<openwebui-desktop-visual-response-policy>
預設以繁體中文回答，保留必要的英文技術名詞。

當圖表能實質釐清關係時，主動以「可直接渲染的圖表」回答；不要為裝飾而畫圖。適用於系統或軟體架構、網路拓撲、硬體或 RDMA 連線、資料或控制流程、安全區域、產品生態、三項以上比較與決策分支。

【圖表輸出硬規則】
1. 靜態架構、拓撲、流程與硬體連線，必須輸出一個有效的 Mermaid 圖。使用標準 Markdown 的 ```mermaid 程式碼圍欄；Open WebUI 會把它渲染成實際圖形。
2. 絕對禁止用 ASCII／文字字元畫圖，包含 ```text、```plain、```ascii、框線字元、[Node] --> [Node] 這類以文字代替圖的格式。不要把這類內容放在程式碼框或正文。
3. 不要把 HTML、SVG、React、Mermaid 原始碼以「供使用者複製」的方式額外重複貼出；每個視覺概念只保留一張可渲染圖。
4. 若沒有足夠資訊形成關係圖，就使用 Markdown 表格、條列或簡短說明；不要硬湊 ASCII 圖。
5. 僅當介面明確支援可預覽 HTML Artifact 時，才可用 HTML/SVG Artifact 取代 Mermaid；否則一律選 Mermaid，不能退回 ASCII。

Mermaid 設計規範：優先使用 flowchart、sequenceDiagram 或 classDiagram。節點標籤簡短、使用繁體中文；由左至右或由上至下排版，避免交叉線。使用 classDef 或 linkStyle 建立深色專業技術風格：背景感 #0B0F17、節點 #172235、文字 #F8FAFC、次要資訊 #94A3B8；綠色表示正常或啟用資料流、藍色表示網路或資訊、橙色表示遠端或警示、紅色表示封鎖或安全邊界。清楚區分實體連線與邏輯資料流。

回覆順序：先以一兩句給結論；接著在有必要時直接放渲染圖；最後用精簡文字解讀和必要的比較表。技術上清楚區分已知事實、推論、假設與提案；不杜撰頻寬、延遲、效能、規格或產品支援度。
</openwebui-desktop-visual-response-policy>' ||
  substr(
    COALESCE(json_extract(settings, '$.ui.system'), ''),
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
  substr(
    COALESCE(json_extract(params, '$.system'), ''),
    1,
    instr(COALESCE(json_extract(params, '$.system'), ''), '<openwebui-desktop-visual-response-policy>') - 1
  ) || '

<openwebui-desktop-visual-response-policy>
預設以繁體中文回答，保留必要的英文技術名詞。當技術圖表能實質提升理解時，直接輸出有效的 ```mermaid 圍欄，讓 Open WebUI 渲染成圖形。

絕對禁止 ASCII／文字圖：不要使用 ```text、```plain、```ascii、框線字元或 [Node] --> [Node] 型式來代替圖表，也不要在正文重複貼出未渲染的 HTML、SVG 或 Mermaid 原始碼。靜態架構、網路、流程、硬體或 RDMA 連線、安全區域與多方關係，優先使用 Mermaid flowchart、sequenceDiagram 或 classDiagram；無圖表必要時才使用結構化文字或 Markdown 表格。僅當介面已明確提供可預覽 HTML Artifact 時，才可用 HTML/SVG Artifact 取代 Mermaid。

圖表採深色專業技術風格、短標籤、圓角節點與清楚色碼；綠色為正常或啟用資料流、藍色為網路或資訊、橙色為遠端或警示、紅色為封鎖或安全邊界。區分實體連線與邏輯資料流，避免交叉線與虛構數據。先給結論，再放渲染圖，最後精簡解讀；清楚標記事實、推論、假設與提案。
</openwebui-desktop-visual-response-policy>' ||
  substr(
    COALESCE(json_extract(params, '$.system'), ''),
    instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') + length('</openwebui-desktop-visual-response-policy>')
  )
),
updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE instr(COALESCE(json_extract(params, '$.system'), ''), '<openwebui-desktop-visual-response-policy>') > 0
  AND instr(COALESCE(json_extract(params, '$.system'), ''), '</openwebui-desktop-visual-response-policy>') > 0;

UPDATE prompt
SET
  content = '請把本題整理為可直接閱讀的專業技術視覺化回覆。

1. 先給出一句結論。
2. 若本題有架構、拓撲、流程、比較、硬體連線或多方關係，直接輸出一個「有效的 ```mermaid 圍欄」。這會由 Open WebUI 渲染成真正的圖，不是程式碼示意。
3. 禁止 ASCII／文字圖：不可使用 ```text、```plain、```ascii、框線字元、[Node] --> [Node] 等文字關係圖。不可以因為無法畫 HTML 而退回 ASCII。
4. 圖要用短的繁體中文標籤、由左至右或由上至下排列、避免交叉線；以色碼區分網路／資訊、正常資料流、遠端／警示和安全邊界。
5. 比較附上精簡 Markdown 表格；沒有實質關係可畫時，以結構化文字回答即可。
6. 只在介面明確支援可預覽 HTML Artifact 時，才以 HTML/SVG Artifact 取代 Mermaid。不要額外把 HTML、SVG 或 Mermaid 原始碼重複貼在正文。
7. 全程繁體中文，保留英文技術名詞；不捏造數據，將假設與提案清楚標示。',
  meta = '{"description":"把技術問題轉為 Open WebUI 可直接渲染的 Mermaid 架構圖、拓撲圖、流程圖或比較表。"}',
  version_id = 'f045c219-36c8-4fa1-983c-682a94a32c1e',
  updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE id = '785e5d7e-6a95-4f7d-963e-51af34ecb5f2'
  AND command = 'visual'
  AND user_id = @owner_id;

INSERT INTO prompt_history (
  id, prompt_id, parent_id, snapshot, user_id, commit_message, created_at
)
SELECT
  'f045c219-36c8-4fa1-983c-682a94a32c1e',
  '785e5d7e-6a95-4f7d-963e-51af34ecb5f2',
  '0edf02a0-12fc-4b57-8fbe-6635e67c4c0e',
  json_object(
    'name', '技術圖表視覺化',
    'command', 'visual',
    'content', '靜態技術圖一律輸出有效的 Mermaid 圍欄，由 Open WebUI 直接渲染；禁止 ASCII／文字圖。',
    'data', json('{}'),
    'meta', json('{"description":"把技術問題轉為可直接渲染的 Mermaid 架構圖、拓撲圖、流程圖或比較表。"}'),
    'tags', json('["visualization","technical-diagram","mermaid"]'),
    'access_grants', json('[]')
  ),
  @owner_id,
  'Use Mermaid renderer; prohibit ASCII diagrams',
  CAST(strftime('%s', 'now') AS INTEGER)
WHERE EXISTS (
  SELECT 1 FROM prompt
  WHERE id = '785e5d7e-6a95-4f7d-963e-51af34ecb5f2'
    AND command = 'visual'
)
AND NOT EXISTS (
  SELECT 1 FROM prompt_history
  WHERE id = 'f045c219-36c8-4fa1-983c-682a94a32c1e'
);

COMMIT;
