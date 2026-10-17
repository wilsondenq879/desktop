# ASUSWRT MCP（Open WebUI 第一版）

這個資料夾提供一個不需要額外 Python 套件的 MCP stdio server。它由 Open WebUI 啟動，透過 Windows/macOS 的 `ssh` 連到 ASUSWRT 或 Asuswrt-Merlin，讓模型可以查詢路由器狀態，並在明確 `confirm=true` 時執行少數受限控制。

桌面版已新增 `設定 → ASUSWRT MCP` 分頁，可直接填 Router IP、SSH 埠號、使用者、私鑰路徑與 Known Hosts 路徑；按「測試連線」確認後，再按「儲存並啟用」。不需要手動編輯 JSON。

## 先講結論：ASUSWRT 有沒有公開 API？

ASUS 沒有提供一個穩定、公開、版本保證的 REST API 給第三方整合。ASUSWRT 內建 HTTP daemon 確實包含給 ASUS Router App 使用的 `appGet.cgi`、token 與 JSON 回應路徑，但那是韌體內部介面，會隨型號/版本改變，不適合當唯一依賴。開源的 `asusrouter` 也以 HTTP(S) 封裝 stock AsusWRT 與 Merlin，但它是第三方逆向/相容層，不是 ASUS 官方 API。

因此這個第一版選擇：

1. 用 SSH 做可控、可測試的管理通道。
2. 只開放固定的唯讀查詢指令，不提供任意 shell。
3. WAN 重連、重啟 Wi-Fi、重開機必須明確 `confirm=true`。
4. 後續若要做更多資料，可再加 HTTP adapter，但不把內部 CGI 當成穩定契約。

查證依據：ASUSWRT-Merlin 的 httpd source 可看到 app `appGet.cgi` 與 token 流程；第三方 `asusrouter` 封裝了 stock/Merlin 的 HTTP(S) 查詢與 action，但兩者都不是 ASUS 對第三方發布的穩定 API 契約。

- [RMerl httpd source](https://github.com/RMerl/asuswrt-merlin/blob/master/release/src/router/httpd/httpd.c)
- [Vaskivskyi/asusrouter](https://github.com/Vaskivskyi/asusrouter)
- [Asuswrt-Merlin user scripts](https://github.com/RMerl/asuswrt-merlin/wiki/User-scripts/708cfbf6c14d5f521c0d2af2033f9dc18f8755c2)

## Demo 需要開路由器 SSH 嗎？

需要。第一版 demo 不需要在路由器安裝 MCP，也不需要把 SSH 直接暴露到網際網路；只要讓「跑 Open WebUI/MCP 的電腦」能以 SSH 連到路由器的 LAN 位址即可。

推薦拓撲：

```text
手機/遠端瀏覽器
        │  ZeroTier 或 Tailscale
        ▼
Windows Open WebUI Desktop + asuswrt-mcp
        │  LAN SSH（例如 192.168.50.1:22）
        ▼
ASUSWRT / Asuswrt-Merlin 路由器
```

遠端時不要做 WAN port forwarding，也不要把路由器管理頁或 SSH 開到公網。ZeroTier/Tailscale 只需要讓遠端裝置到達那台 Windows MCP 主機；MCP 主機本身在 LAN 內就能連路由器。若是 Open WebUI 跑在另一台雲端/伺服器，則該環境需要能安全連到 MCP host（通常用 Tailscale/ZeroTier，或改成有驗證的 HTTPS MCP gateway）。

### 路由器端設定

在 ASUSWRT 管理頁找 `Administration / System / SSH`（不同型號文字可能略有不同）：

- 只允許 LAN 內 SSH。
- 使用 SSH key；不要為了 demo 把 SSH password 登入暴露到 WAN。
- 若是 Asuswrt-Merlin，可另外啟用 JFFS custom scripts，之後才能放置 router-side scripts；本 MCP 第一版不要求你先安裝 JFFS 腳本。
- 先確認路由器 LAN IP，例如 `192.168.50.1`。

Windows 11 通常已有 OpenSSH Client；PowerShell 測試：

```powershell
ssh -V
ssh -i "$env:USERPROFILE\.ssh\asuswrt_ed25519" admin@192.168.50.1 "nvram get productid"
```

若你的韌體沒有 SSH 選項，這版不能使用 SSH adapter；可以改做同 LAN 的 HTTPS/`appGet.cgi` adapter，但那個是非官方、容易因韌體更新失效的 fallback。

## Windows 設定

在專案資料夾建立環境變數（不要把密碼或私鑰寫進 Git）：

```powershell
$env:ASUSWRT_HOST="192.168.50.1"
$env:ASUSWRT_SSH_USER="admin"
$env:ASUSWRT_SSH_KEY="$env:USERPROFILE\.ssh\asuswrt_ed25519"
$env:ASUSWRT_SSH_PORT="22"
```

若想鎖定 host key：

```powershell
$env:ASUSWRT_SSH_KNOWN_HOSTS="$env:USERPROFILE\.ssh\known_hosts"
```

第一次只做不連線的 MCP protocol smoke test：

```powershell
$env:ASUSWRT_DRY_RUN="1"
@'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"router_get_status","arguments":{}}}
'@ | py -3 tools\asuswrt-mcp\server.py
```

真正測試前移除 dry-run：

```powershell
Remove-Item Env:ASUSWRT_DRY_RUN -ErrorAction SilentlyContinue
```

## Open WebUI MCP 設定

把 `tools/asuswrt-mcp/openwebui-mcp-entry.json` 的內容合併到 Open WebUI Desktop 的 MCP server 設定。Windows 範例：

也可以在 PowerShell 直接執行專案附帶的設定器，它會先備份現有的 `mcp-servers.json`，再新增/更新 `asuswrt` entry：

```powershell
.\scripts\setup-asuswrt-mcp.ps1 `
  -RouterHost "192.168.50.1" `
  -SshKey "$env:USERPROFILE\.ssh\asuswrt_ed25519"
```

這個設定器只寫入路由器位址與私鑰檔案路徑，不會把私鑰內容寫進設定檔。它會優先尋找 Open WebUI Desktop 的 bundled Python；若找不到才使用系統 `py`/`python`。也可以手動指定：

```powershell
.\scripts\setup-asuswrt-mcp.ps1 `
  -RouterHost "192.168.50.1" `
  -SshKey "$env:USERPROFILE\.ssh\asuswrt_ed25519" `
  -PythonCommand "C:\\path\\to\\python.exe"
```

安裝版／免安裝版會把 server 放在 `resources\tools\asuswrt-mcp\server.py`；若你是在已安裝的 Windows 版本執行設定器，可用 `-ServerPath` 指向該檔案。開發版則可直接使用設定器的預設路徑。

```json
{
  "asuswrt": {
    "type": "stdio",
    "command": "py",
    "args": ["C:\\path\\to\\open-webui-desktop\\tools\\asuswrt-mcp\\server.py"],
    "env": {
      "ASUSWRT_HOST": "192.168.50.1",
      "ASUSWRT_SSH_USER": "admin",
      "ASUSWRT_SSH_KEY": "C:\\Users\\YOUR_NAME\\.ssh\\asuswrt_ed25519",
      "ASUSWRT_SSH_PORT": "22"
    }
  }
}
```

使用者在 Open WebUI 對話可直接問：

- `目前路由器 WAN、韌體和 uptime 是什麼？`
- `列出目前看到的用戶端。`
- `先告訴我重連 WAN 會做什麼，沒有我的確認不要執行。`
- `確認，重連 WAN。`

Open WebUI 若使用單獨的 launchd/runtime 設定，請在該 runtime 的 MCP JSON 中加入同一個 server entry；不要把私鑰內容貼進對話或 skill。

## 安全邊界

- 沒有任意命令執行工具。
- NVRAM 只能讀取白名單 key。
- 控制工具沒有 `confirm=true` 會拒絕。
- 建議把 MCP server 留在 Windows LAN 主機，遠端只透過 ZeroTier/Tailscale 到 Open WebUI。
- 第一次連線建議填 `ASUSWRT_SSH_KNOWN_HOSTS` 鎖定 host key；未填時為方便 demo 使用 `accept-new`。

## 已知限制與下一版

- 不同 ASUS 型號的 `wl` 介面、service 名稱與輸出格式不同；工具會回傳原始文字，方便確認型號差異。
- 第一版沒有修改 SSID、密碼、防火牆規則等高風險設定。
- 下一版可以加入可選的 HTTP adapter、事件輪詢、變更 diff，以及 Open WebUI 設定頁的「測試連線」按鈕。
