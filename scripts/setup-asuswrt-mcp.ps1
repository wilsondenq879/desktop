param(
  [Parameter(Mandatory = $true)]
  [string]$RouterHost,
  [string]$RouterUser = "admin",
  [int]$SshPort = 22,
  [Parameter(Mandatory = $true)]
  [string]$SshKey,
  [string]$KnownHosts = "",
  [string]$PythonCommand = "",
  [string]$ServerPath = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SshKey -PathType Leaf)) {
  throw "找不到 SSH key：$SshKey"
}

if ([string]::IsNullOrWhiteSpace($ServerPath)) {
  $ServerPath = Join-Path $PSScriptRoot "..\tools\asuswrt-mcp\server.py"
}
$ServerPath = (Resolve-Path -LiteralPath $ServerPath).Path

if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
  $pythonCandidates = @(
    (Join-Path $env:APPDATA "OpenWebUIRuntime\python\python.exe"),
    (Join-Path $env:APPDATA "Open WebUI\python\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Open WebUI\python\python.exe")
  )
  $PythonCommand = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
  if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) { $PythonCommand = $py.Source }
  }
  if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) { $PythonCommand = $python.Source }
  }
  if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
    throw "找不到 Python。請先在 Open WebUI Desktop 安裝 Python runtime，或用 -PythonCommand 指定 python.exe。"
  }
}

$mcpDir = Join-Path $env:APPDATA "OpenWebUIRuntime\mcp"
$configPath = Join-Path $mcpDir "mcp-servers.json"
New-Item -ItemType Directory -Force -Path $mcpDir | Out-Null

if (Test-Path -LiteralPath $configPath -PathType Leaf) {
  $backupPath = "$configPath.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
  Copy-Item -LiteralPath $configPath -Destination $backupPath
  $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
} else {
  $config = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
}

if ($null -eq $config.mcpServers) {
  $config | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([pscustomobject]@{})
}

$entry = [ordered]@{
  type    = "stdio"
  command = $PythonCommand
  args    = @($ServerPath)
  env     = [ordered]@{
    ASUSWRT_HOST           = $RouterHost
    ASUSWRT_SSH_USER       = $RouterUser
    ASUSWRT_SSH_PORT       = [string]$SshPort
    ASUSWRT_SSH_KEY        = (Resolve-Path -LiteralPath $SshKey).Path
    ASUSWRT_SSH_KNOWN_HOSTS = $KnownHosts
  }
}

# ConvertFrom-Json returns PSCustomObject; replace/add the named server safely.
$config.mcpServers | Add-Member -MemberType NoteProperty -Name asuswrt -Value ([pscustomobject]$entry) -Force
$json = $config | ConvertTo-Json -Depth 12
Set-Content -LiteralPath $configPath -Value $json -Encoding UTF8

Write-Host "已寫入 ASUSWRT MCP：$configPath"
Write-Host "Server：$ServerPath"
Write-Host "路由器：$RouterUser@$RouterHost`:$SshPort"
Write-Host "請重新啟動 Open WebUI Desktop，然後先詢問：目前路由器韌體和 WAN 狀態是什麼？"
