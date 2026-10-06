// @ts-nocheck

import crypto from 'crypto'
import fs from 'fs'
import log from 'electron-log'
import os from 'os'
import * as pty from 'node-pty'
import {
  getPythonPath,
  getConfig,
  setConfig,
  installPackage,
  isPackageInstalled,
  isPythonInstalled,
  installPython,
  portInUse
} from './index'
import { ServiceLock, isProcessAlive } from './service-lock'

// ─── State ──────────────────────────────────────────────

let ptyProcess: pty.IPty | null = null
let pid: number | null = null
let url: string | null = null
let apiKey: string | null = null
let status: string | null = null // null | starting | started | stopped | failed
let logBuffer: string[] = []

const lock = new ServiceLock('open-terminal')

// ─── Public API ─────────────────────────────────────────

export const getOpenTerminalInfo = () => ({
  url,
  apiKey,
  status,
  pid
})

export const getOpenTerminalPty = (): pty.IPty | null => ptyProcess
export const getOpenTerminalLog = (): string[] => logBuffer

export interface OpenTerminalProjectFolder {
  connectionId: string
  chatId: string
  path: string
}

const getProjectFolders = (config: Awaited<ReturnType<typeof getConfig>>) =>
  config.openTerminal?.projectFolders ?? {}

/**
 * Return the locally persisted project folder for a connection + chat pair.
 * Paths never leave the desktop app except when they are sent to the local
 * Open Terminal instance.
 */
export const getOpenTerminalProjectFolder = async (
  connectionId: string,
  chatId: string
): Promise<string | null> => {
  if (!connectionId || !chatId) return null
  const config = await getConfig()
  return getProjectFolders(config)[connectionId]?.[chatId] ?? null
}

/**
 * Restore a chat's cwd in Open Terminal. Open Terminal keeps its per-session
 * cwd map in memory, so the desktop reapplies the persisted value after an
 * app or service restart.
 */
export const applyOpenTerminalProjectFolder = async (
  chatId: string,
  folderPath: string
): Promise<string> => {
  if (!chatId) throw new Error('A chat must be open before selecting a project folder.')
  if (!folderPath) throw new Error('No project folder was provided.')

  const info = getOpenTerminalInfo()
  if (info.status !== 'started' || !info.url || !info.apiKey) {
    throw new Error('Open Terminal is not running.')
  }

  const response = await fetch(`${info.url.replace(/\/$/, '')}/files/cwd`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${info.apiKey.trim()}`,
      'Content-Type': 'application/json',
      'X-Session-Id': chatId
    },
    body: JSON.stringify({ path: folderPath })
  })

  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.detail ? `: ${payload.detail}` : ''
    } catch {
      // Keep the HTTP status as the useful fallback.
    }
    throw new Error(`Open Terminal rejected the project folder (${response.status})${detail}`)
  }

  const payload = await response.json()
  return payload?.cwd ?? folderPath
}

export const setOpenTerminalProjectFolder = async (
  connectionId: string,
  chatId: string,
  folderPath: string
): Promise<OpenTerminalProjectFolder> => {
  if (!connectionId) throw new Error('No Open WebUI connection is active.')

  const stat = await fs.promises.stat(folderPath).catch(() => null)
  if (!stat?.isDirectory()) throw new Error('The selected project folder is not available.')

  const resolvedPath = await applyOpenTerminalProjectFolder(chatId, folderPath)
  const config = await getConfig()
  const projectFolders = structuredClone(getProjectFolders(config))
  projectFolders[connectionId] = {
    ...(projectFolders[connectionId] ?? {}),
    [chatId]: resolvedPath
  }

  await setConfig({
    openTerminal: {
      ...config.openTerminal,
      projectFolders
    }
  })

  return { connectionId, chatId, path: resolvedPath }
}

export const clearOpenTerminalProjectFolder = async (
  connectionId: string,
  chatId: string
): Promise<void> => {
  if (!connectionId || !chatId) return

  const config = await getConfig()
  const projectFolders = structuredClone(getProjectFolders(config))
  if (projectFolders[connectionId]) {
    delete projectFolders[connectionId][chatId]
    if (Object.keys(projectFolders[connectionId]).length === 0) {
      delete projectFolders[connectionId]
    }
  }

  await setConfig({
    openTerminal: {
      ...config.openTerminal,
      projectFolders
    }
  })

  if (getOpenTerminalInfo().status === 'started') {
    await applyOpenTerminalProjectFolder(chatId, config.openTerminal?.cwd || os.homedir())
  }
}

export const startOpenTerminal = async (
  port: number | null = null,
  onStatus?: (status: string) => void
): Promise<{ url: string; apiKey: string; pid: number }> => {
  if (!lock.acquire()) {
    return { url, apiKey, pid }
  }

  await stopOpenTerminal()

  if (!isPythonInstalled()) {
    log.info('Python not installed — installing automatically for Open Terminal…')
    onStatus?.('Installing Python…')
    try {
      const ok = await installPython(undefined, onStatus)
      if (!ok) throw new Error('Python installation returned false')
    } catch (err) {
      throw new Error(
        `Python is required for Open Terminal but installation failed: ${err?.message ?? err}`
      )
    }
    if (!isPythonInstalled()) {
      throw new Error(
        'Python was installed but could not be verified. Please restart the app and try again.'
      )
    }
  }

  if (!isPackageInstalled('open-terminal')) {
    log.info('open-terminal not installed, attempting install...')
    onStatus?.('Installing Open Terminal package…')
    try {
      await installPackage('open-terminal')
    } catch (err) {
      throw new Error(
        `Open Terminal is not installed and auto-install failed. ` +
          `Please connect to the internet and try again. (${err?.message ?? err})`
      )
    }
  }

  const pythonPath = getPythonPath()
  const host = '127.0.0.1'
  const config = await getConfig()
  const configEnvVars = config.envVars ?? {}

  // Use persisted API key or generate and save a new one
  let generatedKey = config.openTerminal?.apiKey
  if (!generatedKey) {
    generatedKey = crypto.randomBytes(24).toString('base64url')
    await setConfig({
      openTerminal: { ...config.openTerminal, apiKey: generatedKey }
    })
  }

  // Find available port
  let desiredPort = port || 39284
  let availablePort = desiredPort
  while (await portInUse(availablePort, host)) {
    availablePort++
    if (availablePort > desiredPort + 100) {
      throw new Error('No available port found for Open Terminal')
    }
  }

  const cwd = config.openTerminal?.cwd || os.homedir()

  const commandArgs = [
    '-m',
    'uv',
    'run',
    'open-terminal',
    'run',
    '--host',
    host,
    '--port',
    availablePort.toString(),
    '--api-key',
    generatedKey,
    '--cwd',
    cwd
  ]

  log.info('Starting Open Terminal...', pythonPath, commandArgs.join(' '))

  let spawned: pty.IPty
  try {
    spawned = pty.spawn(pythonPath, commandArgs, {
      name: 'xterm-256color',
      cols: 200,
      rows: 50,
      env: {
        ...process.env,
        ...(configEnvVars ?? {}),
        PYTHONUNBUFFERED: '1',
        ...(process.platform === 'win32' ? { PYTHONIOENCODING: 'utf-8' } : {})
      }
    })
  } catch (error) {
    throw new Error(`Failed to spawn Open Terminal: ${error?.message ?? error}`)
  }

  const spawnedPid = spawned.pid
  logBuffer = []
  ptyProcess = spawned
  pid = spawnedPid
  apiKey = generatedKey
  status = 'starting'

  spawned.onData((data: string) => {
    logBuffer.push(data)
    log.info(`[OpenTerminal:${spawnedPid}] ${data.replace(/[\r\n]+/g, ' ').trim()}`)
  })

  spawned.onExit(({ exitCode, signal }) => {
    log.info(`[OpenTerminal:${spawnedPid}] Exited code=${exitCode} signal=${signal}`)
    ptyProcess = null
    pid = null
    url = null
    apiKey = null
    status = 'stopped'
  })

  const serverUrl = `http://${host}:${availablePort}`
  url = serverUrl
  status = 'started'
  log.info(`Open Terminal started — PID: ${spawnedPid}, URL: ${serverUrl}`)

  return { url: serverUrl, apiKey: generatedKey, pid: spawnedPid }
}

export const stopOpenTerminal = async (): Promise<void> => {
  if (ptyProcess) {
    try {
      ptyProcess.kill()
    } catch (e) {
      log.warn('Failed to kill Open Terminal PTY:', e)
    }
    // Give it a moment to exit
    await new Promise((r) => setTimeout(r, 1000))
    // Force kill if still running
    if (pid) {
      try {
        process.kill(pid, 0) // check alive
        process.kill(pid, 'SIGKILL')
      } catch {
        // already dead
      }
    }
  }
  ptyProcess = null
  pid = null
  url = null
  apiKey = null
  status = null
  logBuffer = []
  lock.release()
}

/**
 * Validate whether the tracked Open Terminal process is still alive.
 */
export const validateOpenTerminalProcess = (): boolean => {
  if (!pid) return false
  if (isProcessAlive(pid)) return true
  pid = null
  status = null
  lock.release()
  return false
}
