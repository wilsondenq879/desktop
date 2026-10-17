// @ts-nocheck

import crypto from 'crypto'
import { spawn } from 'child_process'
import fs from 'fs'
import log from 'electron-log'
import os from 'os'
import path from 'path'
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
// Some macOS/Linux environments reject node-pty's posix_spawnp even though a
// regular child process can start normally. The HTTP tool server does not
// require a pseudo-terminal, so keep a pipe-based fallback for that case.
let childProcess: import('child_process').ChildProcess | null = null
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

const getDefaultProjectFolders = (config: Awaited<ReturnType<typeof getConfig>>) =>
  config.openTerminal?.defaultProjectFolders ?? {}

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
 * Return the one-shot project selected before a chat exists. It is claimed by
 * the next newly created chat and then cleared, so later chats cannot inherit
 * it accidentally.
 */
export const getOpenTerminalDefaultProjectFolder = async (
  connectionId: string
): Promise<string | null> => {
  if (!connectionId) return null
  const config = await getConfig()
  return getDefaultProjectFolders(config)[connectionId] ?? null
}

export const setOpenTerminalDefaultProjectFolder = async (
  connectionId: string,
  folderPath: string
): Promise<string> => {
  if (!connectionId) throw new Error('No Open WebUI connection is active.')

  const stat = await fs.promises.stat(folderPath).catch(() => null)
  if (!stat?.isDirectory()) throw new Error('The selected project folder is not available.')

  const config = await getConfig()
  const defaultProjectFolders = {
    ...getDefaultProjectFolders(config),
    [connectionId]: folderPath
  }
  await setConfig({
    openTerminal: {
      ...config.openTerminal,
      enabled: true,
      cwd: folderPath,
      defaultProjectFolders
    }
  })
  return folderPath
}

export const clearOpenTerminalDefaultProjectFolder = async (
  connectionId: string
): Promise<void> => {
  if (!connectionId) return

  const config = await getConfig()
  const defaultProjectFolders = { ...getDefaultProjectFolders(config) }
  delete defaultProjectFolders[connectionId]
  await setConfig({
    openTerminal: {
      ...config.openTerminal,
      defaultProjectFolders
    }
  })
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
  return rememberOpenTerminalProjectFolder(connectionId, chatId, resolvedPath)
}

/**
 * Persist a chat's project mapping even when the optional Open Terminal
 * service is temporarily unavailable. Other desktop capabilities, such as
 * Draw Things, can still use the selected workspace and Open Terminal will
 * re-apply this path the next time it starts successfully.
 */
export const rememberOpenTerminalProjectFolder = async (
  connectionId: string,
  chatId: string,
  folderPath: string
): Promise<OpenTerminalProjectFolder> => {
  if (!connectionId) throw new Error('No Open WebUI connection is active.')
  if (!chatId) throw new Error('A chat must be open before selecting a project folder.')

  const stat = await fs.promises.stat(folderPath).catch(() => null)
  if (!stat?.isDirectory()) throw new Error('The selected project folder is not available.')

  const config = await getConfig()
  const projectFolders = structuredClone(getProjectFolders(config))
  projectFolders[connectionId] = {
    ...(projectFolders[connectionId] ?? {}),
    [chatId]: folderPath
  }

  await setConfig({
    openTerminal: {
      ...config.openTerminal,
      projectFolders
    }
  })

  return { connectionId, chatId, path: folderPath }
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
  const fireworksSkillRoot = path.join(getInstallDir(), 'skills', 'fireworks-tech-graph')

  // Run the installed CLI directly when available. Calling `python -m uv run`
  // adds a dependency on uv's cache and its shell environment, which is
  // fragile inside Electron (and especially on Windows). Keep the uv route as
  // a fallback for older installs that do not expose the console script.
  const pythonBinDir = path.dirname(pythonPath)
  const directExecutable = path.join(
    pythonBinDir,
    process.platform === 'win32' ? 'open-terminal.exe' : 'open-terminal'
  )
  const useDirectExecutable = fs.existsSync(directExecutable)
  const executable = useDirectExecutable ? directExecutable : pythonPath
  const commandArgs = useDirectExecutable
    ? [
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
    : [
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

  log.info('Starting Open Terminal...', executable, commandArgs.join(' '))

  let spawned: pty.IPty | null = null
  let fallbackProcess: import('child_process').ChildProcess | null = null
  try {
    spawned = pty.spawn(executable, commandArgs, {
      name: 'xterm-256color',
      cols: 200,
      rows: 50,
      env: {
        ...process.env,
        ...(configEnvVars ?? {}),
        ...(fs.existsSync(path.join(fireworksSkillRoot, 'scripts', 'fireworks.py'))
          ? {
              OPENWEBUI_FIREWORKS_SKILL_ROOT: fireworksSkillRoot,
              OPENWEBUI_FIREWORKS_PYTHON: pythonPath
            }
          : {}),
        PYTHONUNBUFFERED: '1',
        ...(process.platform === 'win32' ? { PYTHONIOENCODING: 'utf-8' } : {})
      }
    })
  } catch (error) {
    log.warn('node-pty could not start Open Terminal; using pipe fallback:', error)
    try {
      fallbackProcess = spawn(executable, commandArgs, {
        cwd,
        env: {
          ...process.env,
          ...(configEnvVars ?? {}),
          ...(fs.existsSync(path.join(fireworksSkillRoot, 'scripts', 'fireworks.py'))
            ? {
                OPENWEBUI_FIREWORKS_SKILL_ROOT: fireworksSkillRoot,
                OPENWEBUI_FIREWORKS_PYTHON: pythonPath
              }
            : {}),
          PYTHONUNBUFFERED: '1',
          ...(process.platform === 'win32' ? { PYTHONIOENCODING: 'utf-8' } : {})
        },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true
      })
    } catch (fallbackError) {
      throw new Error(`Failed to spawn Open Terminal: ${fallbackError?.message ?? fallbackError}`)
    }
  }

  const spawnedPid = spawned?.pid ?? fallbackProcess?.pid ?? null
  if (!spawnedPid) throw new Error('Open Terminal started without a process id.')
  logBuffer = []
  ptyProcess = spawned
  childProcess = fallbackProcess
  pid = spawnedPid
  apiKey = generatedKey
  status = 'starting'

  const recordOutput = (data: string): void => {
    logBuffer.push(data)
    log.info(`[OpenTerminal:${spawnedPid}] ${data.replace(/[\r\n]+/g, ' ').trim()}`)
  }
  const markExited = (exitCode: number | null, signal: string | null): void => {
    log.info(`[OpenTerminal:${spawnedPid}] Exited code=${exitCode} signal=${signal}`)
    ptyProcess = null
    childProcess = null
    pid = null
    url = null
    apiKey = null
    status = 'stopped'
  }

  if (spawned) {
    spawned.onData(recordOutput)
    spawned.onExit(({ exitCode, signal }) => markExited(exitCode, signal))
  } else if (fallbackProcess) {
    fallbackProcess.stdout?.on('data', (data) => recordOutput(String(data)))
    fallbackProcess.stderr?.on('data', (data) => recordOutput(String(data)))
    fallbackProcess.once('error', (error) => recordOutput(`Open Terminal process error: ${error.message}\n`))
    fallbackProcess.once('exit', (exitCode, signal) => markExited(exitCode, signal))
  }

  const serverUrl = `http://${host}:${availablePort}`
  url = serverUrl
  status = 'starting'

  // The process can be alive a moment before its HTTP server is ready. Folder
  // selection and the first chat request both depend on the API immediately,
  // so do not advertise a usable terminal until the OpenAPI endpoint responds.
  let ready = false
  let lastReadyError: unknown = null
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const response = await fetch(`${serverUrl}/openapi.json`, {
        headers: { Authorization: `Bearer ${generatedKey}` },
        signal: AbortSignal.timeout(1000)
      })
      if (response.ok) {
        ready = true
        break
      }
      lastReadyError = new Error(`HTTP ${response.status}`)
    } catch (error) {
      lastReadyError = error
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }

  if (!ready) {
    await stopOpenTerminal()
    throw new Error(
      `Open Terminal started but its local API did not become ready. (${lastReadyError?.message ?? lastReadyError ?? 'timeout'})`
    )
  }

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
  if (childProcess) {
    try {
      childProcess.kill()
    } catch (e) {
      log.warn('Failed to kill Open Terminal child process:', e)
    }
    await new Promise((r) => setTimeout(r, 250))
    if (pid) {
      try {
        process.kill(pid, 0)
        process.kill(pid, 'SIGKILL')
      } catch {
        // already dead
      }
    }
  }
  ptyProcess = null
  childProcess = null
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
