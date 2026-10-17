# Open WebUI Companion for iOS

目前交付版為 0.3.0（build 6）。原生 SwiftUI 外框內嵌 WKWebView，主要對談、Tools、Skills、歷史與圖表使用同一套 Open WebUI 網頁，避免另做聊天 UI 造成能力落差。原生程式負責管理不同 server 位址、重新整理與連線外框；不把桌面配對當成純聊天的前提。

## 目前功能

- Open WebUI 登入，Token 使用 iOS Keychain 保存
- 取得模型清單與模型切換
- Chat Completions 串流回應
- 檔案上傳並附加到下一則訊息
- 桌面端 Companion API 位址設定與連線測試介面
- 桌面端 API Key 驗證與遠端工作紀錄同步
- 專案、進度、變更、成品 Canvas 的手機端入口畫面

## 開啟與建置

用 Xcode 開啟 `OpenWebUICompanion.xcodeproj`，選擇 iPhone Simulator 或實機後 Build。

要安裝到真機：在 Xcode 的 Settings → Accounts 登入自己的 Apple ID，選取 target 的 Signing & Capabilities，改用自己的 Team 與 bundle ID，再選擇已配對的 iPhone Run。免費 Apple ID 也可用個人 provisioning，但 profile 需要定期更新。勿提交憑證或 provisioning。

SVG 圖庫、統計圖樣板與背景規則部署在 server，不塞入手機 App。網頁資產更新不必重簽 App；只有原生外框更新才要重新安裝。完整可重建流程與隱私界線見 `docs/BACKUP_RESTORE.md`。

下列原生聊天／Companion 實作保留作為歷史與後續整合參考，不代表目前預設 WebView 的 Tools/Skills 仍由原生 API 清單取代。

Desktop 端會自動啟用 authenticated Companion API（預設埠 `39280`），並在 Desktop 設定的「手機 Companion」頁顯示 API Key。手機填入電腦 LAN、Tailscale 或 ZeroTier 位址與 API Key 後，即可取得工作進度、實際檔案變更與成品摘要；手機端不可使用 Desktop 的 `127.0.0.1` 位址。

## API 預期

Open WebUI 使用既有端點：

- `POST /api/v1/auths/signin`
- `GET /api/models`
- `POST /api/chat/completions`
- `POST /api/v1/files/`

Desktop Companion 端點：

- `GET /health`（Bearer API Key）
- `GET /api/desktop/workspaces`（工作紀錄、變更與成品摘要）
- `GET /api/desktop/workspaces/:id/file?path=...`（Canvas 預覽資料）
- `POST /api/desktop/workspaces/:id/rollback`（復原檢查點）
