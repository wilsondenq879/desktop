import { app } from 'electron'
import { execFile } from 'child_process'
import fs from 'fs'
import path from 'path'
import { promisify } from 'util'

import { getUserDataPath } from './index'

const execFileAsync = promisify(execFile)

export interface AsuswrtMcpConfig {
  enabled: boolean
  host: string
  sshPort: number
  username: string
  keyPath: string
  knownHostsPath: string
}

export const DEFAULT_ASUSWRT_MCP_CONFIG: AsuswrtMcpConfig = {
  enabled: false,
  host: '',
  sshPort: 22,
  username: 'admin',
  keyPath: '',
  knownHostsPath: ''
}

const hostPattern = /^[A-Za-z0-9_.:-]+$/

const normalizeConfig = (value: Partial<AsuswrtMcpConfig> = {}): AsuswrtMcpConfig => ({
  ...DEFAULT_ASUSWRT_MCP_CONFIG,
  ...value,
  enabled: value.enabled === true,
  host: String(value.host ?? '').trim(),
  sshPort: Number(value.sshPort ?? 22),
  username: String(value.username ?? 'admin').trim() || 'admin',
  keyPath: String(value.keyPath ?? '').trim(),
  knownHostsPath: String(value.knownHostsPath ?? '').trim()
})

const validateConfig = (value: Partial<AsuswrtMcpConfig>): AsuswrtMcpConfig => {
  const config = normalizeConfig(value)
  if (config.enabled && !config.host) throw new Error('請先填寫 Router IP 或主機名稱。')
  if (config.host && !hostPattern.test(config.host)) throw new Error('Router IP/主機名稱含有不支援的字元。')
  if (!Number.isInteger(config.sshPort) || config.sshPort < 1 || config.sshPort > 65535) {
    throw new Error('SSH 埠號必須介於 1 到 65535。')
  }
  if (config.keyPath && !fs.existsSync(config.keyPath)) throw new Error(`找不到 SSH 私鑰：${config.keyPath}`)
  if (config.knownHostsPath && !fs.existsSync(config.knownHostsPath)) {
    throw new Error(`找不到 Known Hosts 檔案：${config.knownHostsPath}`)
  }
  return config
}

export const getAsuswrtMcpServerPath = (): string => {
  const packaged = path.join(process.resourcesPath, 'tools', 'asuswrt-mcp', 'server.py')
  if (app.isPackaged && fs.existsSync(packaged)) return packaged
  return path.normalize(path.join(app.getAppPath(), 'tools', 'asuswrt-mcp', 'server.py'))
}

export const getAsuswrtMcpConfigPath = (): string =>
  path.join(getUserDataPath(), 'mcp', 'mcp-servers.json')

const getAsuswrtMcpConfigPaths = (): string[] => {
  const paths = [getAsuswrtMcpConfigPath()]
  // Open WebUI Desktop and the managed OpenWebUI runtime can use separate
  // user-data roots. If the runtime root already exists, keep its MCP config
  // in sync as well so the setting takes effect without manual JSON editing.
  const siblingRuntime = path.join(path.dirname(getUserDataPath()), 'OpenWebUIRuntime', 'mcp', 'mcp-servers.json')
  if (siblingRuntime !== paths[0] && fs.existsSync(path.dirname(siblingRuntime))) paths.push(siblingRuntime)
  return paths
}

const getServerEntry = (config: AsuswrtMcpConfig, pythonPath: string) => ({
  type: 'stdio',
  command: pythonPath || 'python',
  args: [getAsuswrtMcpServerPath()],
  env: {
    ASUSWRT_HOST: config.host,
    ASUSWRT_SSH_USER: config.username,
    ASUSWRT_SSH_PORT: String(config.sshPort),
    ...(config.keyPath ? { ASUSWRT_SSH_KEY: config.keyPath } : {}),
    ...(config.knownHostsPath ? { ASUSWRT_SSH_KNOWN_HOSTS: config.knownHostsPath } : {})
  }
})

export const syncAsuswrtMcpConfig = async (
  value: Partial<AsuswrtMcpConfig>,
  pythonPath = ''
): Promise<{ config: AsuswrtMcpConfig; configPath: string; serverPath: string }> => {
  const config = validateConfig(value)
  const configPaths = getAsuswrtMcpConfigPaths()
  for (const configPath of configPaths) {
    const configDir = path.dirname(configPath)
    await fs.promises.mkdir(configDir, { recursive: true })

    let runtimeConfig: Record<string, any> = { mcpServers: {} }
    if (fs.existsSync(configPath)) {
      const raw = await fs.promises.readFile(configPath, 'utf8')
      runtimeConfig = JSON.parse(raw)
    }
    runtimeConfig.mcpServers = runtimeConfig.mcpServers ?? {}
    if (config.enabled) runtimeConfig.mcpServers.asuswrt = getServerEntry(config, pythonPath)
    else delete runtimeConfig.mcpServers.asuswrt

    const tempPath = `${configPath}.tmp`
    await fs.promises.writeFile(tempPath, JSON.stringify(runtimeConfig, null, 2), 'utf8')
    await fs.promises.rename(tempPath, configPath)
  }
  return { config, configPath: configPaths.join('；'), serverPath: getAsuswrtMcpServerPath() }
}

export const testAsuswrtSsh = async (
  value: Partial<AsuswrtMcpConfig>
): Promise<{ ok: boolean; message: string; detail?: string }> => {
  const config = validateConfig({ ...value, enabled: true })
  const args = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
  if (config.knownHostsPath) {
    args.push('-o', 'StrictHostKeyChecking=yes', '-o', `UserKnownHostsFile=${config.knownHostsPath}`)
  } else {
    args.push('-o', 'StrictHostKeyChecking=accept-new')
  }
  args.push('-p', String(config.sshPort))
  if (config.keyPath) args.push('-i', config.keyPath)
  args.push(`${config.username}@${config.host}`, 'nvram get productid; nvram get firmver; uptime')

  try {
    const result = await execFileAsync('ssh', args, {
      timeout: 11000,
      windowsHide: true,
      maxBuffer: 64 * 1024,
      encoding: 'utf8'
    })
    return { ok: true, message: 'SSH 連線成功。', detail: String(result.stdout ?? '').trim() }
  } catch (error: any) {
    const detail = String(error?.stderr || error?.message || 'SSH 連線失敗').trim()
    return { ok: false, message: 'SSH 連線失敗。', detail: detail.slice(-1200) }
  }
}
