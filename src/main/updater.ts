import { autoUpdater, type UpdateInfo } from 'electron-updater'
import log from 'electron-log'
import { app, BrowserWindow } from 'electron'

let mainWin: BrowserWindow | null = null

const isPortableBuild = (): boolean => Boolean(process.env.PORTABLE_EXECUTABLE_FILE)

const send = (type: string, data?: any): void => {
  mainWin?.webContents.send('main:data', { type, data })
}

export function initUpdater(window: BrowserWindow): void {
  mainWin = window

  // electron-builder's portable target runs from a temporary extraction directory.
  // Installing an NSIS update from there would replace the portable build with the
  // upstream installed app, so portable releases are updated by replacing the EXE.
  if (isPortableBuild()) {
    log.info('Auto update disabled for portable build')
    return
  }

  autoUpdater.logger = log
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('checking-for-update', () => {
    send('update:checking')
  })

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    send('update:available', {
      version: info.version,
      releaseDate: info.releaseDate
    })
  })

  autoUpdater.on('update-not-available', (_info: UpdateInfo) => {
    send('update:not-available')
  })

  autoUpdater.on('download-progress', (progress) => {
    send('update:download-progress', {
      percent: progress.percent,
      bytesPerSecond: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total
    })
  })

  autoUpdater.on('update-downloaded', (_info: UpdateInfo) => {
    send('update:downloaded')
  })

  autoUpdater.on('error', (error: Error) => {
    send('update:error', { message: error?.message ?? 'Update error' })
  })

  // Auto-check on launch (silently, only when packaged)
  if (app.isPackaged) {
    autoUpdater.checkForUpdates().catch((err) => {
      log.warn('Auto update check failed:', err)
    })
  }
}

export async function checkForUpdates(): Promise<void> {
  if (!app.isPackaged || isPortableBuild()) {
    log.info('Skipping update check — app is not packaged or is a portable build')
    send('update:not-available')
    return
  }
  await autoUpdater.checkForUpdates()
}

export async function downloadUpdate(): Promise<void> {
  if (isPortableBuild()) return
  await autoUpdater.downloadUpdate()
}

export function installUpdate(): void {
  if (isPortableBuild()) return
  autoUpdater.quitAndInstall(false, true)
}
