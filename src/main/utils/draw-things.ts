import { spawn } from 'child_process'
import { randomBytes, randomUUID } from 'crypto'
import fs from 'fs'
import http, { type IncomingMessage, type ServerResponse } from 'http'
import path from 'path'

import log from 'electron-log'

import { getUserDataPath } from './index'

type DrawThingsContext = {
  projectPath: string
  apiUrl: string
  connectionUrl: string
  authToken: string
  autoLaunch: boolean
}

type DrawThingsGenerateRequest = {
  prompt?: unknown
  negative_prompt?: unknown
  width?: unknown
  height?: unknown
  steps?: unknown
  guidance_scale?: unknown
  seed?: unknown
}

export type DrawThingsBridgeRegistration = {
  url: string
  key: string
  openapi: Record<string, any>
}

export type DrawThingsConnectionStatus = {
  ok: boolean
  message: string
  detail?: string
}

const HOST = '127.0.0.1'
const DEFAULT_BRIDGE_PORT = 7861
const MAX_BODY_BYTES = 128 * 1024
const MAX_CONTEXTS = 128
const GENERATION_TIMEOUT_MS = 10 * 60 * 1000

let bridgeServer: http.Server | null = null
let bridgePort = 0
let bridgeKey = ''
let startPromise: Promise<void> | null = null

const contexts = new Map<string, DrawThingsContext>()
const chatContexts = new Map<string, DrawThingsContext>()
let latestContext: DrawThingsContext | null = null

const trimUrl = (value: string): string => value.trim().replace(/\/+$/, '')

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Session-Id',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Private-Network': 'true'
}

const sendJson = (res: ServerResponse, status: number, body: unknown): void => {
  res.writeHead(status, {
    ...corsHeaders,
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  })
  res.end(JSON.stringify(body))
}

const sendError = (res: ServerResponse, status: number, message: string): void => {
  sendJson(res, status, { error: message })
}

const isAuthorized = (req: IncomingMessage): boolean => {
  const authorization = req.headers.authorization ?? ''
  return authorization === `Bearer ${bridgeKey}`
}

const readJsonBody = async (req: IncomingMessage): Promise<DrawThingsGenerateRequest> => {
  const chunks: Buffer[] = []
  let total = 0

  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    total += buffer.length
    if (total > MAX_BODY_BYTES) throw new Error('Request body is too large.')
    chunks.push(buffer)
  }

  if (!chunks.length) return {}
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw new Error('Request body must be valid JSON.')
  }
}

const asFiniteNumber = (value: unknown, fallback: number): number => {
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

const clamp = (value: unknown, fallback: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, Math.round(asFiniteNumber(value, fallback))))

const clampDimension = (value: unknown, fallback: number): number => {
  const dimension = clamp(value, fallback, 256, 2048)
  return Math.max(256, Math.round(dimension / 64) * 64)
}

const safePromptSlug = (prompt: string): string => {
  const slug = prompt
    .normalize('NFKD')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
  return slug || 'image'
}

const detectImageType = (buffer: Buffer): { extension: string; mimeType: string } => {
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return { extension: 'jpg', mimeType: 'image/jpeg' }
  }
  if (
    buffer.length >= 12 &&
    buffer.toString('ascii', 0, 4) === 'RIFF' &&
    buffer.toString('ascii', 8, 12) === 'WEBP'
  ) {
    return { extension: 'webp', mimeType: 'image/webp' }
  }
  return { extension: 'png', mimeType: 'image/png' }
}

const drawThingsOptionsUrl = (apiUrl: string): string => `${trimUrl(apiUrl)}/sdapi/v1/options`

export const testDrawThingsConnection = async (
  apiUrl: string
): Promise<DrawThingsConnectionStatus> => {
  const normalized = trimUrl(apiUrl)
  if (!/^https?:\/\//i.test(normalized)) {
    return {
      ok: false,
      message: 'Draw Things 位址必須以 http:// 或 https:// 開頭。'
    }
  }

  try {
    const response = await fetch(drawThingsOptionsUrl(normalized), {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(5000)
    })
    if (!response.ok) {
      return {
        ok: false,
        message: `Draw Things API 回傳 HTTP ${response.status}。`,
        detail: '請確認 API Server 已啟用，Protocol 為 HTTP。'
      }
    }
    return { ok: true, message: '已連上 Draw Things API。' }
  } catch (error) {
    return {
      ok: false,
      message: '無法連上 Draw Things API。',
      detail:
        error instanceof Error
          ? error.message
          : '請在 Draw Things 的 Settings → Advanced 啟用 API Server。'
    }
  }
}

const maybeLaunchDrawThings = async (context: DrawThingsContext): Promise<void> => {
  if (!context.autoLaunch || process.platform !== 'darwin') return

  let hostname = ''
  try {
    hostname = new URL(context.apiUrl).hostname
  } catch {
    return
  }
  if (!['127.0.0.1', 'localhost', '::1'].includes(hostname)) return

  const child = spawn('open', ['-a', 'Draw Things'], {
    detached: true,
    stdio: 'ignore'
  })
  child.unref()

  for (let attempt = 0; attempt < 12; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    const status = await testDrawThingsConnection(context.apiUrl)
    if (status.ok) return
  }
}

const ensureDrawThingsReady = async (context: DrawThingsContext): Promise<void> => {
  let status = await testDrawThingsConnection(context.apiUrl)
  if (!status.ok) {
    await maybeLaunchDrawThings(context)
    status = await testDrawThingsConnection(context.apiUrl)
  }
  if (!status.ok) {
    throw new Error(
      `${status.message} ${status.detail ?? ''} 請在 Draw Things → Settings → Advanced 開啟 API Server，Protocol 選 HTTP，並確認連接埠。`.trim()
    )
  }
}

const uploadToOpenWebUI = async (
  context: DrawThingsContext,
  bytes: Buffer,
  filename: string,
  mimeType: string
): Promise<string | null> => {
  const baseUrl = trimUrl(context.connectionUrl)
  if (!baseUrl || !context.authToken) return null

  try {
    const form = new FormData()
    form.append('file', new Blob([Uint8Array.from(bytes)], { type: mimeType }), filename)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    let response: Response
    try {
      response = await fetch(`${baseUrl}/api/v1/files/?process=false`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${context.authToken}`,
          Accept: 'application/json'
        },
        body: form,
        signal: controller.signal
      })
    } finally {
      clearTimeout(timeout)
    }
    if (!response.ok) {
      log.warn(`Could not upload Draw Things image to Open WebUI (HTTP ${response.status})`)
      return null
    }
    const result = (await response.json()) as { id?: string; url?: string }
    if (result.id) return `/api/v1/files/${encodeURIComponent(result.id)}/content`
    if (typeof result.url === 'string' && result.url) return result.url
  } catch (error) {
    log.warn('Could not upload Draw Things image to Open WebUI:', error)
  }
  return null
}

const generateImage = async (
  context: DrawThingsContext,
  request: DrawThingsGenerateRequest
): Promise<Record<string, unknown>> => {
  const prompt = typeof request.prompt === 'string' ? request.prompt.trim() : ''
  if (!prompt) throw new Error('prompt is required.')

  await ensureDrawThingsReady(context)

  const payload = {
    prompt,
    negative_prompt:
      typeof request.negative_prompt === 'string' ? request.negative_prompt.trim() : '',
    seed: clamp(request.seed, -1, -1, 2147483647),
    steps: clamp(request.steps, 20, 1, 100),
    guidance_scale: Math.min(30, Math.max(0, asFiniteNumber(request.guidance_scale, 4))),
    batch_count: 1,
    width: clampDimension(request.width, 1024),
    height: clampDimension(request.height, 1024)
  }

  const response = await fetch(`${trimUrl(context.apiUrl)}/sdapi/v1/txt2img`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(GENERATION_TIMEOUT_MS)
  })

  if (!response.ok) {
    const detail = (await response.text()).slice(0, 1000)
    throw new Error(`Draw Things 產圖失敗（HTTP ${response.status}）：${detail}`)
  }

  const result = (await response.json()) as { images?: unknown[]; info?: unknown }
  const firstImage = result.images?.find((image) => typeof image === 'string')
  if (typeof firstImage !== 'string' || !firstImage) {
    throw new Error('Draw Things 沒有回傳圖片。')
  }

  const encoded = firstImage.includes(',')
    ? firstImage.slice(firstImage.indexOf(',') + 1)
    : firstImage
  const bytes = Buffer.from(encoded, 'base64')
  if (!bytes.length) throw new Error('Draw Things 回傳了空白圖片。')

  const { extension, mimeType } = detectImageType(bytes)
  const timestamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')
    .replace('T', '_')
    .replace('Z', '')
  const filename = `${timestamp}-${safePromptSlug(prompt)}.${extension}`
  const generatedDir = path.join(context.projectPath, 'generated-images')
  await fs.promises.mkdir(generatedDir, { recursive: true })
  const projectFilePath = path.join(generatedDir, filename)
  await fs.promises.writeFile(projectFilePath, bytes)

  const artifactDir = path.join(getUserDataPath(), 'draw-things-artifacts')
  await fs.promises.mkdir(artifactDir, { recursive: true })
  const artifactName = `${randomUUID()}.${extension}`
  await fs.promises.writeFile(path.join(artifactDir, artifactName), bytes)

  const uploadedUrl = await uploadToOpenWebUI(context, bytes, filename, mimeType)
  const localUrl = `http://${HOST}:${bridgePort}/artifacts/${artifactName}`
  const imageUrl = uploadedUrl ?? localUrl
  const markdown = `![Draw Things 產生的圖片](${imageUrl})`

  return {
    success: true,
    prompt,
    path: projectFilePath,
    name: filename,
    content_type: mimeType,
    mime_type: mimeType,
    image_url: imageUrl,
    markdown,
    synced_to_open_webui: Boolean(uploadedUrl),
    instruction:
      '圖片已完成。請在最終回答中逐字貼上 markdown 欄位，讓圖片直接顯示在對談；並告知使用者檔案已儲存到 path。不要只描述圖片。'
  }
}

const serveArtifact = async (artifactName: string, res: ServerResponse): Promise<void> => {
  if (!/^[0-9a-f-]+\.(png|jpg|webp)$/i.test(artifactName)) {
    sendError(res, 404, 'Image not found.')
    return
  }

  const artifactPath = path.join(getUserDataPath(), 'draw-things-artifacts', artifactName)
  const stats = await fs.promises.stat(artifactPath).catch(() => null)
  if (!stats?.isFile()) {
    sendError(res, 404, 'Image not found.')
    return
  }

  const extension = path.extname(artifactName).toLowerCase()
  const mimeType =
    extension === '.jpg' ? 'image/jpeg' : extension === '.webp' ? 'image/webp' : 'image/png'
  res.writeHead(200, {
    ...corsHeaders,
    'Content-Type': mimeType,
    'Content-Length': stats.size,
    'Cache-Control': 'public, max-age=31536000, immutable'
  })
  fs.createReadStream(artifactPath).pipe(res)
}

const handleRequest = async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders)
    res.end()
    return
  }

  const requestUrl = new URL(req.url ?? '/', `http://${HOST}:${bridgePort || DEFAULT_BRIDGE_PORT}`)
  const artifactMatch = requestUrl.pathname.match(/^\/artifacts\/([^/]+)$/)
  if (req.method === 'GET' && artifactMatch) {
    await serveArtifact(artifactMatch[1], res)
    return
  }

  if (!isAuthorized(req)) {
    sendError(res, 401, 'Unauthorized.')
    return
  }

  if (req.method === 'GET' && requestUrl.pathname === '/health') {
    sendJson(res, 200, { ok: true })
    return
  }

  if (req.method === 'GET' && requestUrl.pathname === '/openapi.json') {
    sendJson(res, 200, createOpenApi())
    return
  }

  if (req.method === 'POST' && requestUrl.pathname === '/generate-image') {
    const sessionId = Array.isArray(req.headers['x-session-id'])
      ? req.headers['x-session-id'][0]
      : req.headers['x-session-id']
    const context = (sessionId ? chatContexts.get(sessionId) : null) ?? latestContext
    if (!context) {
      sendError(res, 404, 'This chat image context is not ready. Send the request again.')
      return
    }
    const body = await readJsonBody(req)
    const result = await generateImage(context, body)
    sendJson(res, 200, result)
    return
  }

  sendError(res, 404, 'Not found.')
}

const listen = async (preferredPort: number): Promise<void> => {
  bridgeServer = http.createServer((req, res) => {
    void handleRequest(req, res).catch((error) => {
      log.error('Draw Things bridge request failed:', error)
      if (!res.headersSent) {
        sendError(res, 500, error instanceof Error ? error.message : String(error))
      } else {
        res.end()
      }
    })
  })

  const bind = (port: number): Promise<void> =>
    new Promise((resolve, reject) => {
      const onError = (error: NodeJS.ErrnoException): void => {
        bridgeServer?.off('listening', onListening)
        reject(error)
      }
      const onListening = (): void => {
        bridgeServer?.off('error', onError)
        const address = bridgeServer?.address()
        bridgePort = typeof address === 'object' && address ? address.port : port
        resolve()
      }
      bridgeServer?.once('error', onError)
      bridgeServer?.once('listening', onListening)
      bridgeServer?.listen(port, HOST)
    })

  try {
    await bind(preferredPort)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EADDRINUSE') throw error
    bridgeServer.removeAllListeners()
    bridgeServer = null
    await listen(0)
  }
}

export const startDrawThingsBridge = async (preferredPort = DEFAULT_BRIDGE_PORT): Promise<void> => {
  if (bridgeServer?.listening) return
  if (startPromise) return startPromise

  startPromise = (async () => {
    bridgeKey = randomBytes(32).toString('hex')
    await listen(preferredPort)
    log.info(`Draw Things bridge listening on http://${HOST}:${bridgePort}`)
  })()

  try {
    await startPromise
  } finally {
    startPromise = null
  }
}

export const getDrawThingsBridgeConnection = async (
  preferredPort = DEFAULT_BRIDGE_PORT
): Promise<DrawThingsBridgeRegistration> => {
  await startDrawThingsBridge(preferredPort)
  return {
    url: `http://${HOST}:${bridgePort}`,
    key: bridgeKey,
    openapi: createOpenApi()
  }
}

export const stopDrawThingsBridge = async (): Promise<void> => {
  const server = bridgeServer
  bridgeServer = null
  bridgePort = 0
  contexts.clear()
  chatContexts.clear()
  latestContext = null
  if (!server) return
  await new Promise<void>((resolve) => server.close(() => resolve()))
}

const createOpenApi = (): Record<string, any> => ({
  openapi: '3.1.0',
  info: {
    title: 'Desktop Draw Things',
    description:
      'Generate an image with Draw Things running on the user’s computer, save it to the current project, and return it to the chat.',
    version: '1.0.0'
  },
  paths: {
    '/generate-image': {
      post: {
        operationId: 'draw_image',
        summary: 'Use Draw Things on this computer to generate an image',
        description:
          'Call this whenever the user asks to draw, illustrate, render, paint, or generate an image. The result includes Markdown that must be included verbatim in the final answer so the image appears in chat.',
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  prompt: {
                    type: 'string',
                    description:
                      'Detailed positive image prompt. Preserve the user’s requested subject and style.'
                  },
                  negative_prompt: {
                    type: 'string',
                    description: 'Optional things the image should avoid.'
                  },
                  width: {
                    type: 'integer',
                    minimum: 256,
                    maximum: 2048,
                    default: 1024,
                    description: 'Image width in pixels; it will be rounded to a multiple of 64.'
                  },
                  height: {
                    type: 'integer',
                    minimum: 256,
                    maximum: 2048,
                    default: 1024,
                    description: 'Image height in pixels; it will be rounded to a multiple of 64.'
                  },
                  steps: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 100,
                    default: 20
                  },
                  guidance_scale: {
                    type: 'number',
                    minimum: 0,
                    maximum: 30,
                    default: 4
                  },
                  seed: {
                    type: 'integer',
                    minimum: -1,
                    maximum: 2147483647,
                    default: -1,
                    description: '-1 chooses a random seed.'
                  }
                },
                required: ['prompt']
              }
            }
          }
        },
        responses: {
          '200': {
            description: 'Generated image path, URL, and Markdown for inline chat display.'
          }
        }
      }
    }
  }
})

export const registerDrawThingsContext = async (options: {
  projectPath: string
  chatId?: string
  apiUrl: string
  connectionUrl: string
  authToken: string
  autoLaunch: boolean
  bridgePort?: number
}): Promise<DrawThingsBridgeRegistration> => {
  await startDrawThingsBridge(options.bridgePort)

  const contextKey = `${options.connectionUrl}\n${options.chatId || options.projectPath}`
  const context = {
    projectPath: options.projectPath,
    apiUrl: trimUrl(options.apiUrl),
    connectionUrl: trimUrl(options.connectionUrl),
    authToken: options.authToken,
    autoLaunch: options.autoLaunch
  }
  contexts.delete(contextKey)
  contexts.set(contextKey, context)
  if (options.chatId) chatContexts.set(options.chatId, context)
  latestContext = context

  while (contexts.size > MAX_CONTEXTS) {
    const oldestToken = contexts.keys().next().value as string | undefined
    if (!oldestToken) break
    contexts.delete(oldestToken)
    for (const [key, candidate] of chatContexts) {
      if (!Array.from(contexts.values()).includes(candidate)) chatContexts.delete(key)
    }
  }

  return {
    url: `http://${HOST}:${bridgePort}`,
    key: bridgeKey,
    openapi: createOpenApi()
  }
}
