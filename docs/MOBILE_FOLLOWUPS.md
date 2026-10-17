# 手機跟進問題完整顯示

Open WebUI 0.12.3 的 `FollowUps.svelte` 將 Tooltip 外層和問題內文都設為 `line-clamp-1`。只有移除內層限制仍然會被外層裁切。

新增獨立 CSS，以已核對的元件結構限定範圍：窄螢幕或觸控裝置完整換行、48px 最小點選高度、8px 間距、深淺色卡片、鍵盤焦點。不對所有 `.line-clamp-1` 全域套用，因此模型選單與其他摘要不變。無新增動畫。

新增小型 Tooltip 相容程式：僅停用這些問題在手機佈局的 Tippy 提示，避免觸控後黏住蓋字；桌面恢復原狀。使用 WeakSet 記錄自己停用的實例，不重開原本已停用的提示。Svelte 的問句、aria-label、click handler 與送出／插入設定均未改動。

部署：`scripts/install-mobile-followups.py <open_webui package>`。先備份入口頁、版本資訊與既有同名資源；保留 custom.css 和其他客製。CSS/JS 使用內容雜湊 URL，更新 SvelteKit 版本後重新整理即可，不需重裝 iOS／Windows App。

驗證：CSS 解析、`scripts/test-mobile-followup-tooltip.mjs`；另提供 `scripts/test-mobile-followups.mjs` 產生 375px／390px／767px／桌面與 200% 字體測試頁。實際已登入的 Open WebUI 分頁在 Edge 375px 模擬下確認三個問句換行、無省略號。未在實體 iPhone 上操作。
