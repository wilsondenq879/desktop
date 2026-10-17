import { createHash, randomUUID } from 'crypto'
import fs from 'fs'
import path from 'path'

import { getUserDataPath } from './index'

const MAX_FILES = 5000
const MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024
const MAX_RESTORABLE_FILE_BYTES = 8 * 1024 * 1024
const MAX_PREVIEW_BYTES = 5 * 1024 * 1024
const MAX_CHECKPOINTS = 12
const TEMP_WORKSPACE_DIRECTORY = 'temporary-workspaces'

const EXCLUDED_DIRECTORIES = new Set([
  '.git',
  '.hg',
  '.svn',
  '.next',
  '.nuxt',
  '.svelte-kit',
  '.venv',
  'venv',
  'node_modules',
  'dist',
  'build',
  'coverage',
  '__pycache__',
  '.cache'
])

const TEXT_EXTENSIONS = new Set([
  '.txt',
  '.md',
  '.markdown',
  '.html',
  '.htm',
  '.css',
  '.js',
  '.jsx',
  '.ts',
  '.tsx',
  '.svelte',
  '.vue',
  '.json',
  '.jsonl',
  '.yaml',
  '.yml',
  '.toml',
  '.xml',
  '.csv',
  '.tsv',
  '.py',
  '.rb',
  '.php',
  '.java',
  '.kt',
  '.kts',
  '.go',
  '.rs',
  '.c',
  '.h',
  '.cpp',
  '.hpp',
  '.cs',
  '.sh',
  '.zsh',
  '.bash',
  '.ps1',
  '.sql',
  '.ini',
  '.env',
  '.gitignore'
])

const ARTIFACT_EXTENSIONS = new Set([
  '.md',
  '.markdown',
  '.txt',
  '.html',
  '.htm',
  '.pdf',
  '.docx',
  '.xlsx',
  '.pptx',
  '.csv',
  '.tsv',
  '.json',
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.gif',
  '.svg'
])

type ActivityStatus = 'running' | 'complete' | 'failed'
type CheckpointStatus = 'capturing' | 'running' | 'complete' | 'failed' | 'restored'
type ChangeKind = 'created' | 'modified' | 'deleted'

interface SnapshotEntry {
  path: string
  size: number
  mtimeMs: number
  hash: string
  restorable: boolean
  snapshotPath?: string
}

export interface WorkspaceActivity {
  id: string
  label: string
  detail?: string
  status: ActivityStatus
  time: string
}

export interface WorkspaceChange {
  path: string
  kind: ChangeKind
  restorable: boolean
  beforeSize: number
  afterSize: number
  previewable: boolean
}

export interface WorkspaceArtifact {
  path: string
  name: string
  extension: string
  size: number
  kind: ChangeKind
  previewKind: 'image' | 'pdf' | 'html' | 'text' | 'office' | 'unsupported'
}

export interface WorkspaceCheckpoint {
  id: string
  connectionId: string
  chatId: string
  projectPath: string
  status: CheckpointStatus
  startedAt: string
  completedAt?: string
  restoredAt?: string
  activities: WorkspaceActivity[]
  entries: Record<string, SnapshotEntry>
  changes: WorkspaceChange[]
  artifacts: WorkspaceArtifact[]
  limits: {
    files: number
    snapshotBytes: number
    skippedFiles: number
    truncated: boolean
  }
  error?: string
}

const checkpoints = new Map<string, WorkspaceCheckpoint>()

const checkpointsRoot = (): string => path.join(getUserDataPath(), 'workspace-checkpoints')
const temporaryWorkspacesRoot = (): string => path.join(getUserDataPath(), TEMP_WORKSPACE_DIRECTORY)
const checkpointRoot = (checkpointId: string): string => path.join(checkpointsRoot(), checkpointId)
const metadataPath = (checkpointId: string): string =>
  path.join(checkpointRoot(checkpointId), 'checkpoint.json')

const normalizeRelativePath = (value: string): string => value.split(path.sep).join('/')

export interface TemporaryWorkspaceMigration {
  sourcePath: string
  targetPath: string
  movedFiles: number
  renamedConflicts: Array<{ from: string; to: string }>
  skippedEntries: string[]
}

export const isTemporaryWorkspacePath = (folderPath?: string | null): boolean => {
  if (!folderPath) return false
  const root = path.resolve(temporaryWorkspacesRoot())
  const candidate = path.resolve(folderPath)
  const relative = path.relative(root, candidate)
  return Boolean(relative && !relative.startsWith('..') && !path.isAbsolute(relative))
}

export const createTemporaryWorkspace = async (): Promise<string> => {
  const root = temporaryWorkspacesRoot()
  await fs.promises.mkdir(root, { recursive: true })
  const folderPath = path.join(root, `chat-${Date.now()}-${randomUUID().slice(0, 8)}`)
  await fs.promises.mkdir(folderPath, { recursive: false })
  return folderPath
}

export const ensureTemporaryWorkspaceRoot = async (): Promise<string> => {
  const root = temporaryWorkspacesRoot()
  await fs.promises.mkdir(root, { recursive: true })
  return root
}

const conflictDestination = async (targetPath: string): Promise<string> => {
  const extension = path.extname(targetPath)
  const stem = extension ? targetPath.slice(0, -extension.length) : targetPath
  for (let index = 1; index <= 1000; index += 1) {
    const suffix = index === 1 ? ' (Open WebUI tmp)' : ` (Open WebUI tmp ${index})`
    const candidate = `${stem}${suffix}${extension}`
    if (!(await fs.promises.lstat(candidate).catch(() => null))) return candidate
  }
  throw new Error(`Could not find a safe name for ${path.basename(targetPath)}.`)
}

export const migrateTemporaryWorkspace = async (
  sourcePath: string | null | undefined,
  targetPath: string
): Promise<TemporaryWorkspaceMigration | null> => {
  if (!sourcePath || !isTemporaryWorkspacePath(sourcePath)) return null

  const source = path.resolve(sourcePath)
  const target = path.resolve(targetPath)
  if (source === target) return null
  const targetInsideSource = path.relative(source, target)
  if (
    targetInsideSource &&
    !targetInsideSource.startsWith('..') &&
    !path.isAbsolute(targetInsideSource)
  ) {
    throw new Error('The destination cannot be inside the temporary workspace.')
  }

  const sourceStats = await fs.promises.stat(source).catch(() => null)
  const targetStats = await fs.promises.stat(target).catch(() => null)
  if (!sourceStats?.isDirectory()) return null
  if (!targetStats?.isDirectory()) throw new Error('The selected project folder is not available.')

  const result: TemporaryWorkspaceMigration = {
    sourcePath: source,
    targetPath: target,
    movedFiles: 0,
    renamedConflicts: [],
    skippedEntries: []
  }

  const moveEntry = async (sourceEntry: string, targetEntry: string): Promise<void> => {
    const stats = await fs.promises.lstat(sourceEntry).catch(() => null)
    if (!stats) return
    const relativePath = normalizeRelativePath(path.relative(source, sourceEntry))

    if (stats.isSymbolicLink()) {
      result.skippedEntries.push(relativePath)
      return
    }

    if (stats.isDirectory()) {
      let directoryTarget = targetEntry
      const existingTarget = await fs.promises.lstat(directoryTarget).catch(() => null)
      if (existingTarget && !existingTarget.isDirectory()) {
        directoryTarget = await conflictDestination(directoryTarget)
        result.renamedConflicts.push({
          from: relativePath,
          to: normalizeRelativePath(path.relative(target, directoryTarget))
        })
      }
      await fs.promises.mkdir(directoryTarget, { recursive: true })
      const children = await fs.promises.readdir(sourceEntry)
      for (const child of children) {
        await moveEntry(path.join(sourceEntry, child), path.join(directoryTarget, child))
      }
      await fs.promises.rmdir(sourceEntry).catch(() => undefined)
      return
    }

    if (!stats.isFile()) {
      result.skippedEntries.push(relativePath)
      return
    }

    let destination = targetEntry
    if (await fs.promises.lstat(destination).catch(() => null)) {
      destination = await conflictDestination(destination)
      result.renamedConflicts.push({
        from: relativePath,
        to: normalizeRelativePath(path.relative(target, destination))
      })
    }

    await fs.promises.mkdir(path.dirname(destination), { recursive: true })
    await fs.promises
      .rename(sourceEntry, destination)
      .catch(async (error: NodeJS.ErrnoException) => {
        if (error.code !== 'EXDEV') throw error
        await fs.promises.copyFile(sourceEntry, destination, fs.constants.COPYFILE_EXCL)
        await fs.promises.unlink(sourceEntry)
      })
    result.movedFiles += 1
  }

  for (const child of await fs.promises.readdir(source)) {
    await moveEntry(path.join(source, child), path.join(target, child))
  }
  await fs.promises.rmdir(source).catch(() => undefined)
  return result
}

const assertProjectDirectory = async (projectPath: string): Promise<string> => {
  const resolved = await fs.promises.realpath(projectPath)
  const stats = await fs.promises.stat(resolved)
  if (!stats.isDirectory()) throw new Error('The selected project path is not a folder.')
  return resolved
}

const resolveInsideProject = (projectPath: string, relativePath: string): string => {
  const resolved = path.resolve(projectPath, relativePath)
  const relative = path.relative(projectPath, resolved)
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    if (!relative) return resolved
    throw new Error('The requested file is outside the selected project.')
  }
  return resolved
}

const sha256 = async (filePath: string): Promise<string> => {
  const hash = createHash('sha256')
  const stream = fs.createReadStream(filePath)
  for await (const chunk of stream) hash.update(chunk)
  return hash.digest('hex')
}

const pushActivity = (
  checkpoint: WorkspaceCheckpoint,
  label: string,
  status: ActivityStatus,
  detail?: string
): void => {
  checkpoint.activities.push({
    id: randomUUID(),
    label,
    detail,
    status,
    time: new Date().toISOString()
  })
}

const persistCheckpoint = async (checkpoint: WorkspaceCheckpoint): Promise<void> => {
  const root = checkpointRoot(checkpoint.id)
  await fs.promises.mkdir(root, { recursive: true })
  await fs.promises.writeFile(metadataPath(checkpoint.id), JSON.stringify(checkpoint, null, 2))
  checkpoints.set(checkpoint.id, checkpoint)
}

const loadCheckpoint = async (checkpointId: string): Promise<WorkspaceCheckpoint> => {
  const memory = checkpoints.get(checkpointId)
  if (memory) return memory
  const parsed = JSON.parse(await fs.promises.readFile(metadataPath(checkpointId), 'utf8'))
  checkpoints.set(checkpointId, parsed)
  return parsed
}

/**
 * Return the recent workspace checkpoints for the Desktop Companion API.
 *
 * The in-memory map is intentionally supplemented from disk so a phone can
 * reconnect after the desktop app has restarted.  Entries contain the full
 * file snapshot and are kept private; callers only receive metadata through
 * the companion layer.
 */
export const listWorkspaceStates = async (): Promise<WorkspaceCheckpoint[]> => {
  const root = checkpointsRoot()
  const children = await fs.promises.readdir(root, { withFileTypes: true }).catch(() => [])
  const states: WorkspaceCheckpoint[] = []
  for (const child of children) {
    if (!child.isDirectory()) continue
    try {
      states.push(await loadCheckpoint(child.name))
    } catch {
      // Ignore a partially written checkpoint left by a crashed task.
    }
  }
  return states.sort((a, b) => {
    return new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
  })
}

const walkProject = async (
  projectPath: string,
  options: { snapshotRoot?: string } = {}
): Promise<{
  entries: Record<string, SnapshotEntry>
  files: number
  snapshotBytes: number
  skippedFiles: number
  truncated: boolean
}> => {
  const entries: Record<string, SnapshotEntry> = {}
  let files = 0
  let snapshotBytes = 0
  let skippedFiles = 0
  let truncated = false

  const visit = async (directory: string): Promise<void> => {
    if (truncated) return
    const children = await fs.promises.readdir(directory, { withFileTypes: true }).catch(() => [])
    for (const child of children) {
      if (files >= MAX_FILES) {
        truncated = true
        break
      }
      if (child.isSymbolicLink()) continue
      if (child.isDirectory() && EXCLUDED_DIRECTORIES.has(child.name)) continue

      const absolutePath = path.join(directory, child.name)
      if (child.isDirectory()) {
        await visit(absolutePath)
        continue
      }
      if (!child.isFile()) continue

      const relativePath = normalizeRelativePath(path.relative(projectPath, absolutePath))
      const stats = await fs.promises.stat(absolutePath).catch(() => null)
      if (!stats) continue
      files += 1

      const withinFileLimit = stats.size <= MAX_RESTORABLE_FILE_BYTES
      const withinTotalLimit = snapshotBytes + stats.size <= MAX_SNAPSHOT_BYTES
      const restorable = withinFileLimit && withinTotalLimit
      let hash = ''
      try {
        hash = await sha256(absolutePath)
      } catch {
        skippedFiles += 1
      }

      const entry: SnapshotEntry = {
        path: relativePath,
        size: stats.size,
        mtimeMs: stats.mtimeMs,
        hash,
        restorable: Boolean(options.snapshotRoot && restorable && hash)
      }

      if (options.snapshotRoot && entry.restorable) {
        const target = path.join(options.snapshotRoot, relativePath)
        await fs.promises.mkdir(path.dirname(target), { recursive: true })
        await fs.promises.copyFile(absolutePath, target)
        entry.snapshotPath = normalizeRelativePath(path.relative(checkpointsRoot(), target))
        snapshotBytes += stats.size
      } else if (options.snapshotRoot) {
        skippedFiles += 1
      }

      entries[relativePath] = entry
    }
  }

  await visit(projectPath)
  return { entries, files, snapshotBytes, skippedFiles, truncated }
}

const previewKindFor = (relativePath: string): WorkspaceArtifact['previewKind'] => {
  const extension = path.extname(relativePath).toLowerCase()
  if (['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'].includes(extension)) return 'image'
  if (extension === '.pdf') return 'pdf'
  if (['.html', '.htm'].includes(extension)) return 'html'
  if (TEXT_EXTENSIONS.has(extension)) return 'text'
  if (['.docx', '.xlsx', '.pptx'].includes(extension)) return 'office'
  return 'unsupported'
}

const pruneCheckpoints = async (): Promise<void> => {
  const root = checkpointsRoot()
  const children = await fs.promises.readdir(root, { withFileTypes: true }).catch(() => [])
  const candidates: Array<{ id: string; time: number }> = []
  for (const child of children) {
    if (!child.isDirectory()) continue
    const stats = await fs.promises.stat(path.join(root, child.name)).catch(() => null)
    if (stats) candidates.push({ id: child.name, time: stats.mtimeMs })
  }
  candidates.sort((a, b) => b.time - a.time)
  for (const stale of candidates.slice(MAX_CHECKPOINTS)) {
    checkpoints.delete(stale.id)
    await fs.promises.rm(path.join(root, stale.id), { recursive: true, force: true })
  }
}

export const startWorkspaceTask = async (options: {
  connectionId: string
  chatId?: string
  projectPath: string
}): Promise<WorkspaceCheckpoint> => {
  const projectPath = await assertProjectDirectory(options.projectPath)
  const id = `${Date.now()}-${randomUUID()}`
  const checkpoint: WorkspaceCheckpoint = {
    id,
    connectionId: options.connectionId,
    chatId: options.chatId?.trim() ?? '',
    projectPath,
    status: 'capturing',
    startedAt: new Date().toISOString(),
    activities: [],
    entries: {},
    changes: [],
    artifacts: [],
    limits: { files: 0, snapshotBytes: 0, skippedFiles: 0, truncated: false }
  }

  pushActivity(checkpoint, '建立安全檢查點', 'running', '正在記錄專案修改前的狀態')
  await persistCheckpoint(checkpoint)

  try {
    const snapshotRoot = path.join(checkpointRoot(id), 'baseline')
    await fs.promises.mkdir(snapshotRoot, { recursive: true })
    const scan = await walkProject(projectPath, { snapshotRoot })
    checkpoint.entries = scan.entries
    checkpoint.limits = {
      files: scan.files,
      snapshotBytes: scan.snapshotBytes,
      skippedFiles: scan.skippedFiles,
      truncated: scan.truncated
    }
    checkpoint.activities[0].status = 'complete'
    checkpoint.activities[0].detail = `已保護 ${Object.values(scan.entries).filter((entry) => entry.restorable).length} 個檔案`
    checkpoint.status = 'running'
    pushActivity(checkpoint, '模型正在處理工作', 'running', '等待工具操作與回應完成')
    await persistCheckpoint(checkpoint)
    await pruneCheckpoints()
    return checkpoint
  } catch (error) {
    checkpoint.status = 'failed'
    checkpoint.error = error instanceof Error ? error.message : String(error)
    checkpoint.activities[0].status = 'failed'
    pushActivity(checkpoint, '無法建立檢查點', 'failed', checkpoint.error)
    await persistCheckpoint(checkpoint)
    throw error
  }
}

export const finishWorkspaceTask = async (
  checkpointId: string,
  failedMessage?: string
): Promise<WorkspaceCheckpoint> => {
  const checkpoint = await loadCheckpoint(checkpointId)
  const running = [...checkpoint.activities]
    .reverse()
    .find((activity) => activity.status === 'running')
  if (running) running.status = failedMessage ? 'failed' : 'complete'

  pushActivity(checkpoint, '比對專案變更', 'running', '正在整理修改與成品')
  try {
    const current = await walkProject(checkpoint.projectPath)
    const changes: WorkspaceChange[] = []
    const allPaths = new Set([...Object.keys(checkpoint.entries), ...Object.keys(current.entries)])

    for (const relativePath of [...allPaths].sort((a, b) => a.localeCompare(b))) {
      const before = checkpoint.entries[relativePath]
      const after = current.entries[relativePath]
      let kind: ChangeKind | null = null
      if (!before && after) kind = 'created'
      else if (before && !after) kind = 'deleted'
      else if (before && after && before.hash !== after.hash) kind = 'modified'
      if (!kind) continue

      changes.push({
        path: relativePath,
        kind,
        restorable: kind === 'created' || Boolean(before?.restorable),
        beforeSize: before?.size ?? 0,
        afterSize: after?.size ?? 0,
        previewable: TEXT_EXTENSIONS.has(path.extname(relativePath).toLowerCase())
      })
    }

    checkpoint.changes = changes
    checkpoint.artifacts = changes
      .filter((change) => change.kind !== 'deleted')
      .filter((change) => ARTIFACT_EXTENSIONS.has(path.extname(change.path).toLowerCase()))
      .map((change) => ({
        path: change.path,
        name: path.basename(change.path),
        extension: path.extname(change.path).toLowerCase(),
        size: change.afterSize,
        kind: change.kind,
        previewKind: previewKindFor(change.path)
      }))

    const scanActivity = checkpoint.activities.at(-1)
    if (scanActivity) {
      scanActivity.status = 'complete'
      scanActivity.detail = changes.length
        ? `找到 ${changes.length} 項變更與 ${checkpoint.artifacts.length} 個成品`
        : '沒有偵測到檔案變更'
    }
    checkpoint.status = failedMessage ? 'failed' : 'complete'
    checkpoint.completedAt = new Date().toISOString()
    if (failedMessage) checkpoint.error = failedMessage
    pushActivity(
      checkpoint,
      failedMessage ? '工作未完成' : '工作已完成',
      failedMessage ? 'failed' : 'complete',
      failedMessage || (changes.length ? '可以檢閱變更或開啟成品' : '模型已完成回應')
    )
    await persistCheckpoint(checkpoint)
    return checkpoint
  } catch (error) {
    checkpoint.status = 'failed'
    checkpoint.error = error instanceof Error ? error.message : String(error)
    const scanActivity = checkpoint.activities.at(-1)
    if (scanActivity) scanActivity.status = 'failed'
    pushActivity(checkpoint, '變更掃描失敗', 'failed', checkpoint.error)
    await persistCheckpoint(checkpoint)
    return checkpoint
  }
}

export const getLatestWorkspaceState = async (options: {
  connectionId: string
  chatId?: string
  projectPath?: string | null
}): Promise<WorkspaceCheckpoint | null> => {
  const root = checkpointsRoot()
  const children = await fs.promises.readdir(root, { withFileTypes: true }).catch(() => [])
  const candidates: WorkspaceCheckpoint[] = []

  for (const checkpoint of checkpoints.values()) {
    if (checkpoint.connectionId === options.connectionId) candidates.push(checkpoint)
  }
  for (const child of children) {
    if (!child.isDirectory() || checkpoints.has(child.name)) continue
    try {
      const checkpoint = await loadCheckpoint(child.name)
      if (checkpoint.connectionId === options.connectionId) candidates.push(checkpoint)
    } catch {
      // Ignore incomplete checkpoint metadata left by an interrupted process.
    }
  }

  const normalizedProject = options.projectPath ? path.resolve(options.projectPath) : ''
  const matching = candidates.filter((checkpoint) => {
    if (options.chatId && checkpoint.chatId === options.chatId) return true
    if (normalizedProject && path.resolve(checkpoint.projectPath) === normalizedProject) return true
    return !options.chatId && !normalizedProject
  })
  return matching.sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0] ?? null
}

const mimeFor = (extension: string): string => {
  const mimes: Record<string, string> = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.pdf': 'application/pdf',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.json': 'application/json',
    '.csv': 'text/csv'
  }
  return mimes[extension] ?? 'text/plain'
}

export const readWorkspaceFile = async (options: {
  checkpointId: string
  relativePath: string
  version?: 'before' | 'after'
}): Promise<{
  path: string
  name: string
  mime: string
  previewKind: WorkspaceArtifact['previewKind']
  encoding: 'utf8' | 'base64'
  data: string
  size: number
}> => {
  const checkpoint = await loadCheckpoint(options.checkpointId)
  const relativePath = normalizeRelativePath(options.relativePath)
  let filePath: string
  if (options.version === 'before') {
    const entry = checkpoint.entries[relativePath]
    if (!entry?.snapshotPath) throw new Error('No restorable version is available for this file.')
    filePath = path.join(checkpointsRoot(), entry.snapshotPath)
  } else {
    filePath = resolveInsideProject(checkpoint.projectPath, relativePath)
  }

  const stats = await fs.promises.stat(filePath)
  if (!stats.isFile()) throw new Error('The requested preview is not a file.')
  if (stats.size > MAX_PREVIEW_BYTES) {
    throw new Error(
      'This file is too large for the built-in Canvas preview. Open it in its default app instead.'
    )
  }

  const extension = path.extname(relativePath).toLowerCase()
  const previewKind = previewKindFor(relativePath)
  const binary = ['image', 'pdf'].includes(previewKind)
  const data = await fs.promises.readFile(filePath, binary ? 'base64' : 'utf8')
  return {
    path: relativePath,
    name: path.basename(relativePath),
    mime: mimeFor(extension),
    previewKind,
    encoding: binary ? 'base64' : 'utf8',
    data,
    size: stats.size
  }
}

export const openWorkspaceFile = async (
  checkpointId: string,
  relativePath: string
): Promise<string> => {
  const checkpoint = await loadCheckpoint(checkpointId)
  return resolveInsideProject(checkpoint.projectPath, normalizeRelativePath(relativePath))
}

export const rollbackWorkspaceCheckpoint = async (
  checkpointId: string
): Promise<WorkspaceCheckpoint> => {
  const checkpoint = await loadCheckpoint(checkpointId)
  if (checkpoint.status === 'running' || checkpoint.status === 'capturing') {
    throw new Error('Wait for the current work to finish before restoring the checkpoint.')
  }

  const rollbackBackup = path.join(checkpointRoot(checkpoint.id), 'before-rollback')
  await fs.promises.mkdir(rollbackBackup, { recursive: true })

  for (const change of checkpoint.changes) {
    if (!change.restorable) continue
    const currentPath = resolveInsideProject(checkpoint.projectPath, change.path)
    const backupPath = path.join(rollbackBackup, change.path)

    if (change.kind === 'created') {
      if (await fs.promises.stat(currentPath).catch(() => null)) {
        await fs.promises.mkdir(path.dirname(backupPath), { recursive: true })
        await fs.promises.rename(currentPath, backupPath).catch(async () => {
          await fs.promises.copyFile(currentPath, backupPath)
          await fs.promises.unlink(currentPath)
        })
      }
      continue
    }

    const entry = checkpoint.entries[change.path]
    if (!entry?.snapshotPath) continue
    const snapshotPath = path.join(checkpointsRoot(), entry.snapshotPath)
    const existing = await fs.promises.stat(currentPath).catch(() => null)
    if (existing?.isFile()) {
      await fs.promises.mkdir(path.dirname(backupPath), { recursive: true })
      await fs.promises.copyFile(currentPath, backupPath)
    }
    await fs.promises.mkdir(path.dirname(currentPath), { recursive: true })
    await fs.promises.copyFile(snapshotPath, currentPath)
  }

  checkpoint.status = 'restored'
  checkpoint.restoredAt = new Date().toISOString()
  pushActivity(checkpoint, '已復原這次修改', 'complete', '復原前的版本仍保留在檢查點資料中')
  await persistCheckpoint(checkpoint)
  return checkpoint
}
