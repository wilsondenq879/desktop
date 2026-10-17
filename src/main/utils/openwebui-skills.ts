import fs from 'fs'
import os from 'os'
import path from 'path'
import crypto from 'crypto'
import { execFile } from 'child_process'
import { promisify } from 'util'
import { getInstallDir, getOpenWebUIDataPath, getPythonPath } from './index'

type OpenWebUISkill = {
  id: string
  name: string
  description: string
  content: string
  meta: Record<string, unknown>
  is_active: boolean
  access_grants: unknown[]
}

type ExistingSkill = {
  id: string
  name?: string
  access_grants?: unknown[]
  description?: string
  content?: string
  meta?: Record<string, unknown>
  is_active?: boolean
}

type SyncResult = {
  changed: boolean
  created: number
  updated: number
  skipped: number
}

const skillSyncFingerprints = new Map<string, string>()

const FIREWORKS_SKILL_ID = 'fireworks-tech-graph'
const runFile = promisify(execFile)

const getBundledProfileRoot = (): string => {
  const packaged = path.join(process.resourcesPath || '', 'openwebui-server-profile')
  return fs.existsSync(path.join(packaged, 'profile.json'))
    ? packaged
    : path.join(process.cwd(), 'resources', 'openwebui-server-profile')
}

const profilePythonEnv = (): NodeJS.ProcessEnv => ({
  ...process.env,
  PATH: `${path.dirname(getPythonPath())}${path.delimiter}${process.env.PATH || ''}`,
  PYTHONIOENCODING: 'utf-8'
})

/** Install local files before launching the local backend. No remote writes. */
export const installBundledVisualAssets = async (): Promise<void> => {
  const bundle = getBundledProfileRoot()
  const helper = path.join(bundle, 'install-assets.py')
  if (!fs.existsSync(helper)) return
  await runFile(getPythonPath(), ['-m', 'uv', 'run', 'python', helper, '--bundle', bundle,
    '--data-dir', getOpenWebUIDataPath()], { env: profilePythonEnv(), timeout: 120000 })
  // Fresh Windows installations may have no Cairo/GTK DLL. Use a pinned
  // binary wheel instead of requiring users to install graphics toolchains.
  try {
    await runFile(getPythonPath(), ['-c',
      "import importlib.metadata; assert importlib.metadata.version('resvg-py') == '0.5.0'"],
    { env: profilePythonEnv(), timeout: 15000 })
  } catch {
    await runFile(getPythonPath(), ['-m', 'uv', 'pip', 'install', '--python', getPythonPath(),
      '--only-binary', ':all:', 'resvg-py==0.5.0'],
    { env: profilePythonEnv(), timeout: 120000 })
  }
}

/** Update only Desktop's loopback server, as its signed-in administrator.
 * A remote server is not ours to reconfigure merely because the user connected.
 * The helper snapshots old values and imports only the reviewed prompt keys.
 */
export const syncBundledVisualProfile = async (baseUrl: string, token: string): Promise<void> => {
  const url = new URL(baseUrl)
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.username || url.password) return
  const bundle = getBundledProfileRoot()
  const helper = path.join(bundle, 'restore-profile.py')
  if (!fs.existsSync(helper) || !fs.existsSync(getPythonPath())) return
  await runFile(getPythonPath(), ['-m', 'uv', 'run', 'python', helper, '--bundle', bundle,
    '--base', baseUrl, '--apply', '--settings', '--backup-dir',
    path.join(getOpenWebUIDataPath(), 'visual-profile', 'restore-backups')], {
    env: { ...profilePythonEnv(), OPENWEBUI_PROFILE_TOKEN: token }, timeout: 180000
  })
}

const getBundledFireworksRoot = (): string => {
  const profile = path.join(getBundledProfileRoot(), 'runtime', 'skills', FIREWORKS_SKILL_ID)
  if (fs.existsSync(path.join(profile, 'SKILL.md'))) return profile
  const packaged = path.join(
    process.resourcesPath || '',
    'openwebui-skill-runtimes',
    FIREWORKS_SKILL_ID
  )
  if (process.resourcesPath && fs.existsSync(path.join(packaged, 'SKILL.md'))) return packaged
  return path.join(
    process.cwd(),
    'resources',
    'openwebui-managed-skills',
    FIREWORKS_SKILL_ID
  )
}

/**
 * Open WebUI stores only SKILL.md in its database, while Fireworks also needs
 * schemas, templates and renderer scripts. Install that runtime into Desktop's
 * persistent data directory and expose its path to every Open Terminal process.
 */
export const installOpenWebUISkillRuntimes = async (): Promise<string | null> => {
  const source = getBundledFireworksRoot()
  if (!fs.existsSync(path.join(source, 'scripts', 'fireworks.py'))) return null

  const destination = path.join(getInstallDir(), 'skills', FIREWORKS_SKILL_ID)
  // Include the renderer itself: a runtime-only fix (for example a font
  // fallback) must be copied to existing installations even when SKILL.md
  // and package metadata are unchanged.
  const signatureFiles = [
    'package.json',
    'SKILL.md',
    'UPSTREAM.json',
    'scripts/generate-from-template.py',
    'scripts/fireworks.py',
    'scripts/png_export.py',
    'assets/icons/technical/bundle-sha256.txt'
  ]
  const readSignature = async (root: string): Promise<string> =>
    crypto
      .createHash('sha256')
      .update(
        (
          await Promise.all(
            signatureFiles.map((name) =>
              fs.promises.readFile(path.join(root, name), 'utf8').catch(() => '')
            )
          )
        ).join('\n')
      )
      .digest('hex')
  const sourceSignature = await readSignature(source)
  const destinationSignature = await readSignature(destination)
  if (sourceSignature !== destinationSignature) {
    await fs.promises.mkdir(path.dirname(destination), { recursive: true })
    await fs.promises.cp(source, destination, { recursive: true, force: true })
  }

  process.env.OPENWEBUI_FIREWORKS_SKILL_ROOT = destination
  return destination
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value)

// Open WebUI has used both a direct array and envelope shapes such as
// `{ data: { items: [...] } }` for Workspace lists.  Keep the desktop import
// compatible with either shape, otherwise a valid existing list is mistaken
// for an empty one and the mobile picker never receives the synced Skills.
const unwrapCollection = (value: unknown, depth = 0): unknown[] => {
  if (Array.isArray(value)) return value
  if (!isRecord(value) || depth >= 5) return []
  for (const key of ['data', 'items', 'skills']) {
    if (key in value) {
      const items = unwrapCollection(value[key], depth + 1)
      if (items.length || Array.isArray(value[key])) return items
    }
  }
  return []
}

const getBundlePath = (): string => {
  const resourceRoot = process.resourcesPath
  if (resourceRoot && fs.existsSync(path.join(resourceRoot, 'openwebui-skills.json'))) {
    return path.join(resourceRoot, 'openwebui-skills.json')
  }
  return path.join(process.cwd(), 'resources', 'openwebui-skills.json')
}

const stripLmlabPrefix = (value: string): string => {
  const trimmed = value.trim()
  const visible = trimmed.replace(/^lmlab(?:\s*[-_:·|]\s*|\s+)?/i, '').trim()
  return visible || trimmed
}

const frontmatterValue = (content: string, key: string): string => {
  if (!content.startsWith('---\n')) return ''
  const end = content.indexOf('\n---', 4)
  if (end < 0) return ''
  const frontmatter = content.slice(4, end)
  const match = frontmatter.match(new RegExp(`^${key}:\\s*(.*)$`, 'mi'))
  return match?.[1]?.trim().replace(/^['"]|['"]$/g, '') ?? ''
}

const normalizeId = (name: string): string => {
  const normalized = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || `desktop-skill-${Date.now()}`
}

const readSkill = async (skillFile: string, source: string): Promise<OpenWebUISkill | null> => {
  try {
    const content = await fs.promises.readFile(skillFile, 'utf8')
    const directoryName = path.basename(path.dirname(skillFile))
    const id = normalizeId(directoryName)
    const rawName =
      frontmatterValue(content, 'openwebui-name') || frontmatterValue(content, 'name') || directoryName
    const name = stripLmlabPrefix(rawName)
    const description =
      frontmatterValue(content, 'openwebui-description') || frontmatterValue(content, 'description')
    return {
      id,
      name,
      description,
      content,
      meta: { tags: ['desktop', 'local-skill'], source },
      is_active: true,
      access_grants: []
    }
  } catch {
    return null
  }
}

const readSkillRoot = async (root: string, source: string): Promise<OpenWebUISkill[]> => {
  const entries = await fs.promises.readdir(root, { withFileTypes: true }).catch(() => [])
  const skills: OpenWebUISkill[] = []
  for (const entry of entries) {
    if (!entry.isDirectory() && !entry.isSymbolicLink()) continue
    const skillFile = path.join(root, entry.name, 'SKILL.md')
    const skill = await readSkill(skillFile, source)
    if (skill) skills.push(skill)
  }
  return skills
}

const readBundle = async (): Promise<OpenWebUISkill[]> => {
  try {
    const raw = await fs.promises.readFile(getBundlePath(), 'utf8')
    const items: unknown = JSON.parse(raw)
    if (!Array.isArray(items)) return []
    return items
      .filter(
        (item): item is Record<string, unknown> =>
          isRecord(item) && typeof item.id === 'string' && typeof item.content === 'string'
      )
      .map(
        (item): OpenWebUISkill => ({
          ...item,
          id: normalizeId(String(item.id)),
          name: stripLmlabPrefix(String(item.name || item.id)),
          description: String(item.description || ''),
          content: String(item.content),
          meta: { ...(isRecord(item.meta) ? item.meta : {}), source: 'desktop-bundle' },
          is_active: item.is_active !== false,
          access_grants: Array.isArray(item.access_grants) ? item.access_grants : []
        })
      )
  } catch {
    return []
  }
}

export const collectOpenWebUISkills = async (): Promise<OpenWebUISkill[]> => {
  const merged = new Map<string, OpenWebUISkill>()
  for (const skill of await readBundle()) merged.set(skill.id, skill)

  const home = os.homedir()
  const roots: Array<[string, string]> = [
    [path.join(home, '.codex', 'skills'), 'codex'],
    [path.join(home, '.agents', 'skills'), 'agents'],
    [path.join(home, '.claude', 'skills'), 'claude']
  ]
  for (const [root, source] of roots) {
    for (const skill of await readSkillRoot(root, source)) merged.set(skill.id, skill)
  }
  // Managed visual skills must win over stale personal copies with the same ID.
  for (const skill of await readSkillRoot(path.join(getBundledProfileRoot(), 'runtime', 'skills'), 'desktop-managed')) {
    merged.set(skill.id, skill)
  }
  return [...merged.values()].sort((a, b) => a.name.localeCompare(b.name))
}

const parseError = async (response: Response): Promise<string> => {
  try {
    const body = await response.json()
    return body?.detail || body?.message || response.statusText
  } catch {
    return response.statusText
  }
}

const apiRequest = async (
  url: string,
  token: string,
  init: RequestInit = {}
): Promise<Response> => {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  headers.set('Content-Type', 'application/json')
  return fetch(url, { ...init, headers, signal: AbortSignal.timeout(15000) })
}

/**
 * Import the desktop's local skill bundle into Open WebUI Workspace Skills.
 * IDs remain stable (including lmlab-* IDs); only the visible name is cleaned.
 */
export const syncOpenWebUISkills = async (
  connectionUrl: string,
  token: string,
  force = false
): Promise<SyncResult> => {
  await installOpenWebUISkillRuntimes()
  const baseUrl = String(connectionUrl || '').replace(/\/$/, '')
  if (!/^https?:\/\//i.test(baseUrl) || !token) {
    return { changed: false, created: 0, updated: 0, skipped: 0 }
  }

  const skills = await collectOpenWebUISkills()
  if (!skills.length) return { changed: false, created: 0, updated: 0, skipped: 0 }
  const fingerprint = crypto
    .createHash('sha1')
    .update(skills.map((skill) => `${skill.id}:${skill.name}:${skill.content}`).join('|'))
    .digest('hex')
  if (!force && skillSyncFingerprints.get(baseUrl) === fingerprint) {
    return { changed: false, created: 0, updated: 0, skipped: 0 }
  }

  const listResponse = await apiRequest(`${baseUrl}/api/v1/skills/`, token)
  if (!listResponse.ok) throw new Error(`Open WebUI Skills list failed (${listResponse.status})`)
  const existingItems: unknown = await listResponse.json()
  const existing = new Map<string, ExistingSkill>(
    unwrapCollection(existingItems)
      .filter((item): item is ExistingSkill => isRecord(item) && typeof item.id === 'string')
      .map((item): [string, ExistingSkill] => [item.id, item])
  )

  let created = 0
  let updated = 0
  let skipped = 0

  // Existing manually imported LMLab skills may not exist in the local
  // bundle anymore. Clean only their visible names while preserving their
  // original IDs and full content.
  const bundledIds = new Set(skills.map((skill) => skill.id))
  for (const current of existing.values()) {
    if (
      bundledIds.has(current.id) ||
      (!String(current.id).toLowerCase().startsWith('lmlab-') &&
        !/^lmlab(?:\s|[-_:·|])/i.test(String(current.name || '')))
    ) {
      continue
    }
    const visibleName = stripLmlabPrefix(String(current.name || current.id))
    if (!visibleName || visibleName === current.name) continue

    const detailResponse = await apiRequest(
      `${baseUrl}/api/v1/skills/id/${encodeURIComponent(current.id)}`,
      token
    )
    if (!detailResponse.ok) {
      skipped++
      continue
    }
    const detail = await detailResponse.json()
    const response = await apiRequest(
      `${baseUrl}/api/v1/skills/id/${encodeURIComponent(current.id)}/update`,
      token,
      {
        method: 'POST',
        body: JSON.stringify({
          id: current.id,
          name: visibleName,
          description: detail.description || '',
          content: detail.content || '',
          meta: detail.meta || { tags: [] },
          is_active: detail.is_active !== false,
          access_grants: detail.access_grants || []
        })
      }
    )
    if (response.ok) updated++
    else skipped++
  }

  for (const skill of skills) {
    const current = existing.get(skill.id)
    const payload = {
      ...skill,
      access_grants: current?.access_grants ?? skill.access_grants
    }
    const response = current
      ? await apiRequest(
          `${baseUrl}/api/v1/skills/id/${encodeURIComponent(skill.id)}/update`,
          token,
          {
            method: 'POST',
            body: JSON.stringify(payload)
          }
        )
      : await apiRequest(`${baseUrl}/api/v1/skills/create`, token, {
          method: 'POST',
          body: JSON.stringify(payload)
        })

    if (response.ok) {
      current ? updated++ : created++
      continue
    }

    // A user may already own a different skill with the same display name.
    // Keep that skill untouched rather than making the whole sync fail.
    skipped++
    const detail = await parseError(response)
    console.warn(`[OpenWebUI Skills] skipped ${skill.id}: ${detail}`)
  }

  skillSyncFingerprints.set(baseUrl, fingerprint)
  return { changed: created + updated > 0, created, updated, skipped }
}

export const normalizeOpenWebUISkillName = stripLmlabPrefix
