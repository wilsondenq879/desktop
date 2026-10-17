# v0.0.34 跨平台備份與還原

這是非官方客製 fork。桌面版為 Electron；iPhone 為 SwiftUI/WKWebView，用同一個 Open WebUI 網頁後端。手機不需重複內嵌整套 SVG，連上更新過的後端即可使用相同圖庫、統計樣板與背景規則。

## 備份範圍

- Windows/macOS 桌面、iOS App 原始碼，以及 ASUSWRT MCP。
- 9,301 個經清理的 SVG（`resources/architecture-icon-pack/extended/catalog.json` 與原創硬體資產）、固定版本、原始授權及來源。
- Fireworks runtime、19 種統計圖配置、React/SVG 呈現、手機跟進問題排版。
- `resources/openwebui-server-profile/profile.json`：四個全域 Filter、一個原生 Renderer Tool、允許清單內的背景提示詞／建議問題／模型解碼設定。
- 本機產生的安裝包與雜湊放在 `deliverables/v0.0.34`，不放入 Git 歷史。

不備份資料庫、聊天紀錄、帳號 ID／授權清單、API 金鑰、連線設定、SSH 私鑰、手機配對、Apple 憑證或 provisioning profile。舊版 SQL 僅作遷移歷史參考；現行版本請使用有備份與版本檢查的 Python/API 部署流程，勿直接對新版本資料庫執行舊 SQL。SQL 中 `@owner_id` 必須由操作者明確指定。

## 從乾淨 clone 建置

需要 Node/npm、Python 3.12；圖表匯出可用固定版 resvg-py binary wheel，不必另裝 Cairo/GTK；既有 CairoSVG 路徑也保留。現行後端驗證基準為 Open WebUI 0.12.3；不代表相容所有未來版本。

```sh
npm ci
python3 -m pip install -r scripts/visual-profile-requirements.txt
python3 scripts/build-architecture-icon-pack.py
python3 scripts/render-architecture-icon-examples.py
OPENWEBUI_TEST_RENDER=1 python3 scripts/test-extended-icons.py
python3 scripts/build-icon-library-preview.py
python3 scripts/build-statistical-chart-templates.py
npm run prepare:profile
npm run build
```

上列 `python3` 應使用已安裝所需依賴的環境；請參閱各腳本的參數說明。圖庫 canonical catalog 已包含在 repo，不必再次下載來源套件。只有更新圖庫版本才需執行 `build-extended-icon-library.py`；它會核對固定版本與來源雜湊。

```sh
# Windows x64：建議於 Windows 原生驗證
npx electron-builder --win nsis portable --x64 --publish never
# Mac Apple Silicon 與 Intel
npx electron-builder --mac dmg zip --arm64 --x64 --publish never
```

正式散布需要自己的程式碼簽章／Apple notarization；此交付的 Mac arm64 為 ad-hoc 簽署，Intel 與 Windows 未提供商業憑證。不要停用作業系統安全檢查。Windows 安裝包可在 Mac 交叉建置，但不等同已在 Windows 實機通過測試。

桌面啟動本機後端前會安裝具 SHA-256 驗證的視覺資產。登入本機 loopback 後端後才同步已備份的 managed profile；單純連到遠端伺服器**不會**自動改寫其設定。相同 profile 雜湊會略過重複套用，原設定另存於本機 DATA_DIR 的 restore-backups。

全新桌面環境首次啟動需要連網下載 Python／Open WebUI 與固定版 resvg-py wheel；這不是完全離線的後端安裝包。手機使用遠端後端的匯出能力。Windows、macOS wheel 支援與字型行為見 [resvg-py 官方安裝說明](https://resvg-py.readthedocs.io/en/latest/installation.html)、[字型說明](https://resvg-py.readthedocs.io/en/latest/fonts.html)；原有 Cairo 路徑的系統依賴見 [CairoSVG 官方說明](https://cairosvg.org/documentation/)。此依賴查證依 deep-research 流程執行；不將 wheel 可用性等同 Windows 實機驗證。

## 既有 Web 伺服器還原

先備份自己的後端。下列腳本預設只列出計畫；`--apply` 才會更動。以環境變數提供短效管理員 Token，不要寫進 repo 或指令歷史。

```sh
python3 scripts/install-server-profile-assets.py --help
python3 scripts/restore-server-profile.py --help
```

依 `--help` 指定 profile、DATA_DIR、套件與前端路徑；還原設定額外使用 `--settings`。遠端明確指定 `--allow-remote` 才能套用，務必使用可信 HTTPS/VPN。工具／Filter 使用版本化 API，保留現有存取權；僅更新已存在的匹配模型，不建立缺少的模型別名。先測試環境驗證，再套用正式站。

## iOS

開啟 `ios/OpenWebUICompanion/OpenWebUICompanion.xcodeproj`，換成自己的 Team 與 bundle ID，使用 Xcode 簽署／安裝。不要提交 `xcuserdata`、憑證、封裝的 .app 或 .ipa。免費 Apple 開發簽署有期限，並非 TestFlight/App Store 發行。

## 授權

桌面程式沿用 repo 的 AGPL-3.0。第三方 SVG／React／Fireworks 各依其授權，見 `docs/EXTENDED_ICON_LIBRARY.md`、來源 lock、LICENSE 與產生的 NOTICE。圖庫集合的開源授權**不等於**品牌商標或所有個別 logo 的使用許可；不要暗示官方背書。

## 驗證

`test-server-profile.py` 驗證所有封裝資源雜湊、安裝冪等、設定允許清單與還原備份。`test-mixed-visual-reports.py` 驗證報告保留、兩類圖同存、內容與 structured output 一致。`verify-diagram-live.py` 對本機已登入站台做實際生成；新建測試對談成功後封存，不修改原有使用者對談。
