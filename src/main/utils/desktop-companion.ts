import http, { type IncomingMessage, type ServerResponse } from 'http'
import { randomBytes, timingSafeEqual } from 'crypto'

import log from 'electron-log'

import {
  listWorkspaceStates,
  readWorkspaceFile,
  rollbackWorkspaceCheckpoint,
  type WorkspaceCheckpoint
} from './workspace'

export interface DesktopCompanionConfig {
  enabled: boolean
  host: string
  port: number
  apiKey: string
}

let companionServer: http.Server | null = null
let companionConfig: DesktopCompanionConfig | null = null
const pairingCodes = new Map<string, number>()
const PAIRING_TTL_MS = 5 * 60 * 1000

const prunePairingCodes = (): void => {
  const now = Date.now()
  for (const [code, expiresAt] of pairingCodes) {
    if (expiresAt <= now) pairingCodes.delete(code)
  }
}

/**
 * Creates a short-lived, single-use code for a phone to exchange for the
 * desktop Companion credential. The raw credential never appears in the QR.
 */
export const createDesktopCompanionPairing = (): { code: string; expiresAt: string } => {
  if (!companionServer || !companionConfig?.enabled || !companionConfig.apiKey) {
    throw new Error('請先啟用手機 Companion API。')
  }
  prunePairingCodes()
  const code = randomBytes(24).toString('base64url')
  const expiresAt = Date.now() + PAIRING_TTL_MS
  pairingCodes.set(code, expiresAt)
  return { code, expiresAt: new Date(expiresAt).toISOString() }
}

const json = (res: ServerResponse, statusCode: number, body: unknown): void => {
  res.statusCode = statusCode
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(body))
}

const setCors = (res: ServerResponse): void => {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
}

const isAuthorized = (req: IncomingMessage): boolean => {
  const configuredKey = companionConfig?.apiKey ?? ''
  if (!configuredKey) return false
  const header = req.headers.authorization ?? ''
  const supplied = header.startsWith('Bearer ') ? header.slice(7).trim() : ''
  if (!supplied) return false
  const expected = Buffer.from(configuredKey)
  const actual = Buffer.from(supplied)
  return expected.length === actual.length && timingSafeEqual(expected, actual)
}

const publicCheckpoint = (checkpoint: WorkspaceCheckpoint) => ({
  id: checkpoint.id,
  connectionId: checkpoint.connectionId,
  chatId: checkpoint.chatId,
  projectPath: checkpoint.projectPath,
  status: checkpoint.status,
  startedAt: checkpoint.startedAt,
  completedAt: checkpoint.completedAt,
  restoredAt: checkpoint.restoredAt,
  activities: checkpoint.activities,
  changes: checkpoint.changes,
  artifacts: checkpoint.artifacts,
  limits: checkpoint.limits,
  error: checkpoint.error
})

const route = async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
  setCors(res)
  if (req.method === 'OPTIONS') {
    res.statusCode = 204
    res.end()
    return
  }

  const requestUrl = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = requestUrl.pathname.replace(/\/$/, '') || '/'

  const pairingMatch = pathname.match(/^\/api\/desktop\/pair\/([^/]+)$/)
  if (req.method === 'POST' && pairingMatch) {
    prunePairingCodes()
    const code = decodeURIComponent(pairingMatch[1])
    const expiresAt = pairingCodes.get(code)
    if (!expiresAt) {
      json(res, 410, { error: '此配對碼已失效，請回到桌面端重新產生 QR Code。' })
      return
    }
    pairingCodes.delete(code)
    json(res, 200, {
      version: 1,
      apiKey: companionConfig?.apiKey,
      expiresAt: new Date(expiresAt).toISOString(),
      service: 'open-webui-desktop-companion'
    })
    return
  }

  if (pathname === '/health') {
    if (!isAuthorized(req)) {
      json(res, 401, { ok: false, error: 'Companion API key required.' })
      return
    }
    json(res, 200, { ok: true, service: 'open-webui-desktop-companion', version: 1 })
    return
  }

  if (!isAuthorized(req)) {
    json(res, 401, { error: 'Companion API key required.' })
    return
  }

  try {
    if (req.method === 'GET' && pathname === '/api/desktop/workspaces') {
      const states = await listWorkspaceStates()
      json(res, 200, { workspaces: states.slice(0, 24).map(publicCheckpoint) })
      return
    }

    const fileMatch = pathname.match(/^\/api\/desktop\/workspaces\/([^/]+)\/file$/)
    if (req.method === 'GET' && fileMatch) {
      const relativePath = requestUrl.searchParams.get('path') ?? ''
      if (!relativePath) {
        json(res, 400, { error: 'Missing path query parameter.' })
        return
      }
      const version = requestUrl.searchParams.get('version')
      const preview = await readWorkspaceFile({
        checkpointId: decodeURIComponent(fileMatch[1]),
        relativePath,
        version: version === 'before' ? 'before' : 'after'
      })
      json(res, 200, preview)
      return
    }

    const rollbackMatch = pathname.match(/^\/api\/desktop\/workspaces\/([^/]+)\/rollback$/)
    if (req.method === 'POST' && rollbackMatch) {
      const checkpoint = await rollbackWorkspaceCheckpoint(decodeURIComponent(rollbackMatch[1]))
      json(res, 200, { workspace: publicCheckpoint(checkpoint) })
      return
    }

    json(res, 404, { error: 'Not found.' })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    log.warn('Desktop Companion request failed:', message)
    json(res, 400, { error: message })
  }
}

export const startDesktopCompanion = async (config: DesktopCompanionConfig): Promise<void> => {
  if (!config.enabled) {
    await stopDesktopCompanion()
    return
  }

  if (
    companionServer &&
    companionConfig?.host === config.host &&
    companionConfig?.port === config.port &&
    companionConfig?.apiKey === config.apiKey
  ) {
    return
  }

  await stopDesktopCompanion()
  companionConfig = { ...config }
  companionServer = http.createServer((req, res) => {
    route(req, res).catch((error) => {
      log.error('Desktop Companion route error:', error)
      if (!res.headersSent) json(res, 500, { error: 'Internal Companion API error.' })
      else res.end()
    })
  })

  await new Promise<void>((resolve, reject) => {
    const server = companionServer!
    const onError = (error: Error): void => {
      server.off('listening', onListening)
      companionServer = null
      companionConfig = null
      reject(error)
    }
    const onListening = (): void => {
      server.off('error', onError)
      log.info(`Desktop Companion API listening on http://${config.host}:${config.port}`)
      resolve()
    }
    server.once('error', onError)
    server.once('listening', onListening)
    server.listen(config.port, config.host)
  })
}

export const stopDesktopCompanion = async (): Promise<void> => {
  const server = companionServer
  companionServer = null
  companionConfig = null
  pairingCodes.clear()
  if (!server) return
  await new Promise<void>((resolve) => {
    server.close(() => resolve())
  })
}
