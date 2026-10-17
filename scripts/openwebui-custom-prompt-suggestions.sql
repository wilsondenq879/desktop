BEGIN IMMEDIATE;

INSERT INTO config(key, value, updated_at)
VALUES(
  'ui.prompt_suggestions',
  '[{"title":["研究 ASUS 路由器市場","比較產品、競品與市場趨勢"],"content":"請分析 ASUS 路由器市場，整理主要競品、產品定位、Wi‑Fi／AI 網通趨勢與值得追蹤的機會。請用繁體中文回答。"},{"title":["畫出 Local AI 分層架構圖","呈現算力、網路、資料與遠端存取"],"content":"請繪製一張 React＋SVG 風格的 Local AI 分層架構圖，從遠端使用者、管理層、10G 資料邊緣、25G RDMA AI 骨幹到 AI 工作站與儲存層，標示資料流與控制流；直接產生成品圖，不要輸出 Mermaid、ASCII 或繪圖原始碼。"},{"title":["建立 ASUS AI 生態階層圖","從裝置、交換器到應用服務"],"content":"請繪製 ASUS 落地 AI 生態圈階層圖，將 GX10／AI 工作站、Intel E800 RDMA NIC、25G RDMA switch、10G access switch、路由器／VPN 與使用者服務分層排列，使用清楚的 SVG 架構圖說明角色與連線；只回傳成品圖與繁體中文重點。"}]',
  CAST(strftime('%s','now') AS INTEGER)
)
ON CONFLICT(key) DO UPDATE SET
  value = excluded.value,
  updated_at = excluded.updated_at;

COMMIT;
