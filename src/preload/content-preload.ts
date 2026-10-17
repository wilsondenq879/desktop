import { ipcRenderer, contextBridge, webFrame } from 'electron'
import { modelCapabilityDecoratorScript } from './model-capability-decorator'

// ─── Desktop ↔ Open WebUI Generic Protocol ──────────────
// This preload is a dumb relay. It passes typed {type, data}
// messages between the embedder (desktop renderer) and the Open WebUI page.

type EventCallback = (data: any) => void
type ApprovalMode = 'ask' | 'auto'

const eventCallbacks: EventCallback[] = []
const APPROVAL_MODE_KEY = 'open-webui-desktop-approval-mode'
const APPROVAL_CONTROL_ID = 'open-webui-desktop-approval-control'
const APPROVAL_MENU_ID = 'open-webui-desktop-approval-menu'
const APPROVAL_STYLE_ID = 'open-webui-desktop-approval-style'
const RESPONSE_ACTIVITY_STYLE_ID = 'open-webui-desktop-response-activity-style'
const RESPONSE_ACTIVITY_CLASS = 'open-webui-desktop-response-activity'

let approvalMenu: HTMLDivElement | null = null
let approvalAnchor: HTMLButtonElement | null = null
let approvalBridgeReady = false
let approvalBridgeLoading = false
let approvalMountQueued = false
let lastRelayedAuthToken: string | null = null

type ResponseActivityState = {
  indicator: HTMLDivElement
  caretHost: HTMLElement
  startedAt: number
  timer: number
}

const responseActivityStates = new Map<HTMLElement, ResponseActivityState>()
let responseActivityScanQueued = false

const relayAuthToken = (): void => {
  let token = ''
  try {
    token = localStorage.getItem('token') ?? ''
  } catch {
    // Some remote pages can temporarily deny storage access while navigating.
  }

  if (token === lastRelayedAuthToken) return
  lastRelayedAuthToken = token
  ipcRenderer.sendToHost('webview:send', { type: 'token:update', token })
}

// The embedded WebUI owns the model picker. Decorate that existing picker
// instead of adding a second Desktop-only selector, so capabilities stay
// visible in the same place on macOS and in the mobile companion.
const installModelCapabilityDecorator = (): void => {
  void webFrame.executeJavaScript(modelCapabilityDecoratorScript).catch(() => {
    // A navigation can replace the guest document between preload and execution.
    // The next document load gets its own preload and retries safely.
  })
}

// Open WebUI does not guarantee that it will notify the Desktop shell when its
// login token changes. Relay it from the trusted guest preload instead, both at
// page load and after SPA sign-in/sign-out changes.
window.addEventListener('DOMContentLoaded', relayAuthToken, { once: true })
window.addEventListener('focus', relayAuthToken)
window.addEventListener('storage', relayAuthToken)
window.setInterval(relayAuthToken, 1500)
window.addEventListener('DOMContentLoaded', installModelCapabilityDecorator, { once: true })
relayAuthToken()

const approvalLabel = (mode: ApprovalMode): string => (mode === 'auto' ? '代我核准' : '要求核准')

const approvalDescription = (mode: ApprovalMode): string =>
  mode === 'auto' ? '在已選專案範圍內，直接執行必要操作。' : '會改變專案前，先要求你的明確核准。'

const getApprovalMode = (): ApprovalMode => {
  try {
    return localStorage.getItem(APPROVAL_MODE_KEY) === 'auto' ? 'auto' : 'ask'
  } catch {
    return 'ask'
  }
}

const getApprovalInstruction = (mode: ApprovalMode): string =>
  mode === 'auto'
    ? 'Desktop approval mode: the user chose Approve automatically. Within the selected project folder, use the tools actually available to you to complete necessary file changes and commands without pausing for approval. Do not substitute suggestions, code snippets, or instructions for real work when tools are available. At the end, report the files actually changed and validation actually run. Never claim a tool action that you did not perform.'
    : 'Desktop approval mode: the user chose Require approval. You may inspect files and perform read-only analysis. Before any write, delete, rename, dependency change, command with side effects, or other operation that changes the selected project, clearly state the exact change and wait for the user to explicitly approve it. Do not treat the original request as approval for a destructive or modifying action.'

/**
 * Approval is separate from Open WebUI Skills. The policy is added only to
 * Chat Completions requests, preserving native Skills and slash behaviour.
 */
const installApprovalRequestBridge = (): void => {
  if (approvalBridgeReady || approvalBridgeLoading) return
  approvalBridgeLoading = true
  const initialMode = JSON.stringify(getApprovalMode())
  const askInstruction = JSON.stringify(getApprovalInstruction('ask'))
  const autoInstruction = JSON.stringify(getApprovalInstruction('auto'))

  void webFrame
    .executeJavaScript(
      `
    (() => {
      const bridgeKey = '__openWebuiDesktopApprovalBridgeV2'
      if (window[bridgeKey]) return

      let mode = ${initialMode}
      const instructions = { ask: ${askInstruction}, auto: ${autoInstruction} }
      const nativeFetch = window.fetch.bind(window)

      const isChatCompletion = (input) => {
        try {
          const url = typeof input === 'string' ? input : input?.url
          return new URL(url, window.location.href).pathname.endsWith('/api/chat/completions')
        } catch {
          return false
        }
      }

      const prepareProject = async (chatId) => {
        if (!window.electronAPI?.send) return null
        try {
          const response = await Promise.race([
            window.electronAPI.send({ type: 'desktop-project:prepare', chatId: chatId || '' }),
            new Promise((resolve) => setTimeout(() => resolve(null), 30000))
          ])
          if (response?.error) {
            console.warn('[Open WebUI Desktop] Project preparation failed:', response.error)
            return null
          }
          return response
        } catch (error) {
          console.warn('[Open WebUI Desktop] Project preparation failed:', error)
          return null
        }
      }

      const startWorkspaceTask = async (chatId) => {
        if (!window.electronAPI?.send) return null
        try {
          const response = await Promise.race([
            window.electronAPI.send({ type: 'desktop-workspace:task-start', chatId: chatId || '' }),
            new Promise((resolve) => setTimeout(() => resolve(null), 45000))
          ])
          return response?.error ? null : response
        } catch (error) {
          console.warn('[Open WebUI Desktop] Workspace checkpoint failed:', error)
          return null
        }
      }

      const finishWorkspaceTask = (checkpointId, error) => {
        if (!checkpointId || !window.electronAPI?.send) return
        void window.electronAPI.send({
          type: 'desktop-workspace:task-finish',
          checkpointId,
          error: error ? String(error) : undefined
        }).catch((finishError) => {
          console.warn('[Open WebUI Desktop] Workspace finalization failed:', finishError)
        })
      }

      const getLastUserText = (messages) => {
        if (!Array.isArray(messages)) return ''
        for (let index = messages.length - 1; index >= 0; index -= 1) {
          const message = messages[index]
          if (message?.role !== 'user') continue
          if (typeof message.content === 'string') return message.content
          if (Array.isArray(message.content)) {
            return message.content
              .filter((part) => part?.type === 'text' && typeof part.text === 'string')
              .map((part) => part.text)
              .join(' ')
          }
        }
        return ''
      }

      const isArtifactRequest = (text) => {
        const normalized = String(text || '').toLowerCase()
        return /建立|創建|創作|製作|做一個|做個|產出|生成|寫入|新增|修改|編輯|修復|重構|實作|開發|建立檔案|網頁|網站|遊戲|程式|html|css|javascript|typescript|python|文件|報告|簡報|試算表|create|build|make|write|edit|fix|implement|develop|generate|save|file|website|web app|game|html|javascript|typescript|python|document|spreadsheet|presentation/.test(normalized)
      }

      const responseContainsToolCall = (text) =>
        /function_call|function_call_output|tool_calls|write_file|replace_file_content|execute:tool/.test(
          String(text || '')
        )

      const addDesktopInstructions = async (body) => {
        if (typeof body !== 'string') return null
        try {
          const payload = JSON.parse(body)
          if (!Array.isArray(payload?.messages)) return null

          const chatId = typeof payload.chat_id === 'string' ? payload.chat_id : ''
          const userText = getLastUserText(payload.messages)
          const artifactIntent = isArtifactRequest(userText)
          const project = await prepareProject(chatId)
          payload.messages = payload.messages.filter(
            (message) =>
              message?.name !== 'open-webui-desktop-approval-policy' &&
              message?.name !== 'open-webui-desktop-project-policy' &&
              message?.name !== 'open-webui-desktop-draw-things-policy'
          )
          payload.messages.unshift({
            role: 'system',
            name: 'open-webui-desktop-approval-policy',
            content: instructions[mode] || instructions.ask
          })

          payload.params = {
            ...(payload.params && typeof payload.params === 'object' ? payload.params : {}),
            tool_approval_mode: mode === 'auto' ? 'full' : 'ask'
          }

          if (project?.path && project?.toolServer) {
            const normalizeUrl = (value) => {
              const url = String(value || '')
              return url.endsWith('/') ? url.slice(0, -1) : url
            }
            const normalizedUrl = normalizeUrl(project.toolServer.url)
            const toolServers = Array.isArray(payload.tool_servers)
              ? payload.tool_servers.filter(
                  (server) => normalizeUrl(server?.url) !== normalizedUrl
                )
              : []
            payload.tool_servers = [
              ...toolServers,
              { ...project.toolServer, is_terminal: true }
            ]
            payload.messages.unshift({
              role: 'system',
              name: 'open-webui-desktop-project-policy',
              content:
                'Open WebUI Desktop project policy: A local working folder is ready: ' +
                JSON.stringify(project.path) +
                (project.temporary
                  ? '. This is an isolated Desktop-managed temporary workspace for this chat because the user has not selected a permanent project folder. Create requested files here without asking for another destination. If the user selects a project later, Desktop will safely migrate these files. '
                  : '. This is the permanent project folder selected for this chat. ') +
                'Treat it as the current working directory and the default destination for every generated file. ' +
                'Use the local file and terminal tools attached to this request to perform the work directly. ' +
                'When the user asks for a document, presentation, spreadsheet, code change, download, or other artifact, actually create it inside this folder (or an appropriate subfolder), verify that it exists, and report the resulting path. ' +
                'Do not ask where to save it unless the user explicitly requests a different destination. ' +
                'Do not replace execution with suggestions, sample scripts, or instructions when the attached tools can complete the task. ' +
                'Do not claim that browser security prevents local filesystem access: this request comes from Desktop and includes authorized local tools. ' +
                'If a tool genuinely fails, report the concrete tool error and retry safely instead of giving a generic browser limitation.'
            })

            // Models which support native function calling sometimes still answer
            // with prose for an artifact request. Requiring one tool call here
            // prevents a false "完成了" response when Desktop has a real file
            // server attached. Legacy function-calling models keep their normal
            // Open WebUI compatibility path.
            const supportsNativeTools = payload.params?.function_calling !== 'legacy'
            const hasWriteTool = Array.isArray(project.toolServer.specs) &&
              project.toolServer.specs.some((spec) =>
                ['write_file', 'replace_file_content', 'create_file'].includes(spec?.name)
              )
            if (artifactIntent && supportsNativeTools && hasWriteTool && !payload.tool_choice) {
              payload.tool_choice = 'required'
            }
          } else if (project?.path && artifactIntent) {
            payload.messages.unshift({
              role: 'system',
              name: 'open-webui-desktop-project-tool-error',
              content:
                'Open WebUI Desktop could not attach its local file tool for this request. ' +
                'Do not claim that the requested file, web page, game, or other artifact was created. ' +
                'State that the local tool is unavailable and include the concrete error from the Desktop connection.'
            })
          }

          if (project?.drawThingsToolServer) {
            const normalizeUrl = (value) => {
              const url = String(value || '')
              return url.endsWith('/') ? url.slice(0, -1) : url
            }
            const normalizedUrl = normalizeUrl(project.drawThingsToolServer.url)
            const toolServers = Array.isArray(payload.tool_servers)
              ? payload.tool_servers.filter(
                  (server) => normalizeUrl(server?.url) !== normalizedUrl
                )
              : []
            payload.tool_servers = [...toolServers, project.drawThingsToolServer]
            payload.messages.unshift({
              role: 'system',
              name: 'open-webui-desktop-draw-things-policy',
              content:
                'Open WebUI Desktop local image policy: Draw Things on the user’s computer is connected through the draw_image tool. ' +
                'When the user asks you to draw, generate, render, paint, illustrate, or create an image, call draw_image immediately with a detailed prompt that preserves the user’s intent. ' +
                'Do not say that you cannot access Draw Things, cannot create images, or can only provide a prompt while this tool is available. ' +
                'After draw_image succeeds, include the returned markdown field verbatim and exactly once in the final answer so the generated image is visible in this conversation. ' +
                'Also briefly report the returned saved path. Do not replace the image with a prose description. ' +
                'If the tool returns a concrete connection or API error, explain that exact setup error instead of inventing a browser limitation.'
            })
          }
          return { body: JSON.stringify(payload), chatId, project, artifactIntent }
        } catch {
          return null
        }
      }

      const fetchWithWorkspace = async (input, init, prepared) => {
        const checkpoint = prepared?.project?.path
          ? await startWorkspaceTask(prepared.chatId)
          : null
        try {
          const response = await nativeFetch(input, init)
          if (checkpoint?.id) {
            response.clone().text().then(
              (body) => {
                const missingTool = prepared.artifactIntent && !responseContainsToolCall(body)
                finishWorkspaceTask(
                  checkpoint.id,
                  missingTool
                    ? '模型沒有實際呼叫檔案工具，因此未建立成品。請改用支援工具呼叫的模型，或重新送出。'
                    : undefined
                )
              },
              (error) => finishWorkspaceTask(checkpoint.id, error)
            )
          }
          return response
        } catch (error) {
          finishWorkspaceTask(checkpoint?.id, error)
          throw error
        }
      }

      window.fetch = async function (input, init) {
        if (!isChatCompletion(input)) return nativeFetch(input, init)

        if (init && typeof init.body === 'string') {
          const prepared = await addDesktopInstructions(init.body)
          return prepared
            ? fetchWithWorkspace(input, { ...init, body: prepared.body }, prepared)
            : nativeFetch(input, init)
        }

        if (!init && input instanceof Request) {
          try {
            const prepared = await addDesktopInstructions(await input.clone().text())
            if (prepared) {
              const headers = new Headers(input.headers)
              headers.delete('content-length')
              return fetchWithWorkspace(
                new Request(input, { headers, body: prepared.body }),
                undefined,
                prepared
              )
            }
          } catch {
            // Requests without a readable body are passed through unchanged.
          }
        }

        return nativeFetch(input, init)
      }

      window[bridgeKey] = {
        setMode: (nextMode) => {
          mode = nextMode === 'auto' ? 'auto' : 'ask'
        }
      }
    })()
  `
    )
    .then(() => {
      approvalBridgeReady = true
    })
    .catch(() => {
      // A page can navigate while its preload loads; mounting retries this.
    })
    .finally(() => {
      approvalBridgeLoading = false
    })
}

const syncApprovalModeToRequestBridge = (): void => {
  if (!approvalBridgeReady) return
  const mode = JSON.stringify(getApprovalMode())
  void webFrame
    .executeJavaScript(
      `
    window.__openWebuiDesktopApprovalBridgeV2?.setMode(${mode})
  `
    )
    .catch(() => {
      // The next mount installs the bridge again.
    })
}

const setApprovalMode = (mode: ApprovalMode): void => {
  try {
    localStorage.setItem(APPROVAL_MODE_KEY, mode)
  } catch {
    // Storage can be unavailable for a remote connection.
  }
  syncApprovalModeToRequestBridge()
  window.dispatchEvent(
    new CustomEvent('open-webui-desktop:approval-mode-change', { detail: { mode } })
  )
}

const icon = (paths: string): string => `
  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
    ${paths}
  </svg>
`

const approvalIcon = (mode: ApprovalMode): string =>
  mode === 'auto'
    ? icon('<path d="M20 6 9 17l-5-5"/><path d="M14.5 6H20v5.5"/>')
    : icon(
        '<path d="M12 3 4.5 6v5.4c0 4.7 3.2 7.7 7.5 9.6 4.3-1.9 7.5-4.9 7.5-9.6V6L12 3Z"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
      )

const chevronIcon = (): string => icon('<path d="m7 10 5 5 5-5"/>')

const isVisible = (element: HTMLElement): boolean => {
  const style = window.getComputedStyle(element)
  const rect = element.getBoundingClientRect()
  return (
    style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  )
}

const ensureApprovalStyles = (): void => {
  if (document.getElementById(APPROVAL_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = APPROVAL_STYLE_ID
  style.textContent = `
    #${APPROVAL_CONTROL_ID} {
      display: inline-flex;
      flex: 0 0 auto;
      align-items: center;
      margin-left: 2px;
      position: relative;
      z-index: 2;
    }
    .open-webui-desktop-approval-trigger {
      display: inline-flex;
      min-height: 32px;
      align-items: center;
      gap: 5px;
      padding: 0 8px;
      border: 1px solid color-mix(in srgb, currentColor 14%, transparent);
      border-radius: 8px;
      background: color-mix(in srgb, Canvas 92%, transparent);
      color: CanvasText;
      cursor: pointer;
      font: 500 12px/1 ui-sans-serif, system-ui, sans-serif;
      white-space: nowrap;
      transition: background .14s ease, border-color .14s ease;
    }
    .open-webui-desktop-approval-trigger:hover,
    .open-webui-desktop-approval-trigger[aria-expanded="true"] {
      border-color: color-mix(in srgb, #2563eb 45%, transparent);
      background: color-mix(in srgb, #2563eb 12%, Canvas);
    }
    .open-webui-desktop-approval-trigger:focus-visible,
    .open-webui-desktop-approval-option:focus-visible {
      outline: 2px solid #2563eb;
      outline-offset: 2px;
    }
    .open-webui-desktop-approval-trigger svg {
      width: 15px;
      height: 15px;
      flex: 0 0 auto;
    }
    #${APPROVAL_MENU_ID} {
      position: fixed;
      z-index: 2147483647;
      display: grid;
      gap: 4px;
      min-width: 250px;
      padding: 6px;
      border: 1px solid color-mix(in srgb, currentColor 16%, transparent);
      border-radius: 11px;
      background: color-mix(in srgb, Canvas 96%, transparent);
      color: CanvasText;
      box-shadow: 0 14px 36px rgba(0, 0, 0, .24);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      font-family: ui-sans-serif, system-ui, sans-serif;
    }
    .open-webui-desktop-approval-heading {
      padding: 5px 7px 6px;
      color: color-mix(in srgb, CanvasText 68%, transparent);
      font-size: 11px;
      font-weight: 600;
    }
    .open-webui-desktop-approval-option {
      display: grid;
      grid-template-columns: 20px minmax(0, 1fr) 16px;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 8px;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }
    .open-webui-desktop-approval-option:hover,
    .open-webui-desktop-approval-option[aria-checked="true"] {
      background: color-mix(in srgb, #2563eb 12%, transparent);
    }
    .open-webui-desktop-approval-option svg {
      width: 17px;
      height: 17px;
    }
    .open-webui-desktop-approval-option-title {
      display: block;
      font-size: 12px;
      font-weight: 600;
      line-height: 1.25;
    }
    .open-webui-desktop-approval-option-description {
      display: block;
      margin-top: 2px;
      color: color-mix(in srgb, CanvasText 67%, transparent);
      font-size: 11px;
      line-height: 1.3;
    }
    .open-webui-desktop-approval-check {
      color: #2563eb;
      font-size: 14px;
      font-weight: 700;
      text-align: center;
    }
  `
  document.head.appendChild(style)
}

const closeApprovalMenu = (): void => {
  approvalMenu?.remove()
  approvalMenu = null
  const trigger = document.querySelector<HTMLButtonElement>('#' + APPROVAL_CONTROL_ID + ' button')
  trigger?.setAttribute('aria-expanded', 'false')
}

const positionApprovalMenu = (): void => {
  if (!approvalMenu) return
  const trigger = document.querySelector<HTMLButtonElement>('#' + APPROVAL_CONTROL_ID + ' button')
  if (!trigger) return closeApprovalMenu()

  const rect = trigger.getBoundingClientRect()
  const width = approvalMenu.offsetWidth
  const height = approvalMenu.offsetHeight
  const left = Math.min(Math.max(12, rect.left), window.innerWidth - width - 12)
  const above = rect.top - height - 8
  const top = above >= 12 ? above : Math.min(window.innerHeight - height - 12, rect.bottom + 8)
  approvalMenu.style.left = `${left}px`
  approvalMenu.style.top = `${Math.max(12, top)}px`
}

const openApprovalMenu = (): void => {
  closeApprovalMenu()
  ensureApprovalStyles()
  const selectedMode = getApprovalMode()
  const menu = document.createElement('div')
  menu.id = APPROVAL_MENU_ID
  menu.setAttribute('role', 'menu')
  menu.setAttribute('aria-label', '選擇操作核准方式')

  const heading = document.createElement('div')
  heading.className = 'open-webui-desktop-approval-heading'
  heading.textContent = '工具操作的核准方式'
  menu.appendChild(heading)
  ;(['ask', 'auto'] as ApprovalMode[]).forEach((mode) => {
    const option = document.createElement('button')
    option.type = 'button'
    option.className = 'open-webui-desktop-approval-option'
    option.setAttribute('role', 'menuitemradio')
    option.setAttribute('aria-checked', String(mode === selectedMode))
    option.innerHTML = `
      <span>${approvalIcon(mode)}</span>
      <span>
        <span class="open-webui-desktop-approval-option-title">${approvalLabel(mode)}</span>
        <span class="open-webui-desktop-approval-option-description">${approvalDescription(mode)}</span>
      </span>
      <span class="open-webui-desktop-approval-check">${mode === selectedMode ? '✓' : ''}</span>
    `
    option.addEventListener('click', () => {
      setApprovalMode(mode)
      mountApprovalControl()
      closeApprovalMenu()
    })
    menu.appendChild(option)
  })

  menu.addEventListener('pointerdown', (event) => event.stopPropagation())
  document.body.appendChild(menu)
  approvalMenu = menu
  document
    .querySelector<HTMLButtonElement>('#' + APPROVAL_CONTROL_ID + ' button')
    ?.setAttribute('aria-expanded', 'true')
  positionApprovalMenu()
  menu.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus()
}

const getComposerAnchor = (): HTMLButtonElement | null => {
  const editors = [...document.querySelectorAll<HTMLElement>('[contenteditable="true"], textarea')]
    .filter((editor) => {
      if (!isVisible(editor)) return false
      const rect = editor.getBoundingClientRect()
      return rect.width >= 180 && rect.bottom >= window.innerHeight * 0.45
    })
    .sort((a, b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom)

  for (const editor of editors) {
    const editorRect = editor.getBoundingClientRect()
    let container: HTMLElement | null = editor

    for (let depth = 0; container && depth < 8; depth += 1, container = container.parentElement) {
      const candidates = [...container.querySelectorAll<HTMLButtonElement>('button')]
        .filter((button) => button.id !== APPROVAL_CONTROL_ID && isVisible(button))
        .map((button) => ({ button, rect: button.getBoundingClientRect() }))
        .filter(
          ({ rect }) =>
            rect.width >= 20 &&
            rect.width <= 64 &&
            rect.height >= 20 &&
            rect.height <= 64 &&
            rect.left >= editorRect.left - 24 &&
            rect.left <= editorRect.left + 96 &&
            rect.top >= editorRect.bottom - 30 &&
            rect.top <= editorRect.bottom + 96
        )
        .sort((a, b) => a.rect.left - b.rect.left || a.rect.top - b.rect.top)

      if (candidates.length > 0) return candidates[0].button
    }
  }

  return null
}

const mountApprovalControl = (): void => {
  installApprovalRequestBridge()
  syncApprovalModeToRequestBridge()
  ensureApprovalStyles()

  const anchor = getComposerAnchor()
  const existing = document.getElementById(APPROVAL_CONTROL_ID)
  if (!anchor) {
    existing?.remove()
    closeApprovalMenu()
    approvalAnchor = null
    return
  }

  if (existing && approvalAnchor === anchor && existing.previousElementSibling === anchor) {
    const label = existing.querySelector<HTMLElement>('[data-approval-label]')
    if (label) label.textContent = approvalLabel(getApprovalMode())
    return
  }

  existing?.remove()
  closeApprovalMenu()
  approvalAnchor = anchor

  const root = document.createElement('span')
  root.id = APPROVAL_CONTROL_ID
  const trigger = document.createElement('button')
  trigger.type = 'button'
  trigger.className = 'open-webui-desktop-approval-trigger'
  trigger.setAttribute('aria-haspopup', 'menu')
  trigger.setAttribute('aria-expanded', 'false')
  trigger.setAttribute('aria-controls', APPROVAL_MENU_ID)
  trigger.title = '選擇是否在工具改動前要求核准'
  trigger.innerHTML = `${approvalIcon(getApprovalMode())}<span data-approval-label>${approvalLabel(getApprovalMode())}</span>${chevronIcon()}`
  trigger.addEventListener('click', (event) => {
    event.stopPropagation()
    if (approvalMenu) closeApprovalMenu()
    else openApprovalMenu()
  })
  root.appendChild(trigger)
  anchor.insertAdjacentElement('afterend', root)
}

const scheduleApprovalMount = (): void => {
  if (approvalMountQueued) return
  approvalMountQueued = true
  window.requestAnimationFrame(() => {
    approvalMountQueued = false
    mountApprovalControl()
  })
}

const responseActivityCopy = (): {
  waiting: string
  working: string
  elapsed: string
  longer: string
} => {
  const language = (document.documentElement.lang || navigator.language || 'en').toLowerCase()

  if (language.startsWith('zh-tw') || language.startsWith('zh-hk') || language.includes('hant')) {
    return {
      waiting: '已送出，正在等待模型回應…',
      working: '模型仍在處理中…',
      elapsed: '已等待',
      longer: '較長的回應可能需要多一點時間。'
    }
  }

  if (language.startsWith('zh')) {
    return {
      waiting: '已发送，正在等待模型响应…',
      working: '模型仍在处理中…',
      elapsed: '已等待',
      longer: '较长的响应可能需要更多时间。'
    }
  }

  return {
    waiting: 'Request sent. Waiting for the model…',
    working: 'The model is still working…',
    elapsed: 'Elapsed',
    longer: 'Longer responses can take a little more time.'
  }
}

const formatResponseElapsed = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

const ensureResponseActivityStyles = (): void => {
  if (document.getElementById(RESPONSE_ACTIVITY_STYLE_ID)) return

  const style = document.createElement('style')
  style.id = RESPONSE_ACTIVITY_STYLE_ID
  style.textContent = `
    .${RESPONSE_ACTIVITY_CLASS} {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      width: fit-content;
      max-width: 100%;
      margin-top: 6px;
      padding: 8px 12px;
      border: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
      border-radius: 12px;
      background: color-mix(in srgb, Canvas 88%, transparent);
      color: CanvasText;
      font-family: ui-sans-serif, system-ui, sans-serif;
      box-sizing: border-box;
    }
    .open-webui-desktop-response-activity-indicator {
      position: relative;
      display: inline-flex;
      flex: 0 0 auto;
      width: 16px;
      height: 16px;
      margin-top: 2px;
      align-items: center;
      justify-content: center;
      color: color-mix(in srgb, CanvasText 58%, transparent);
    }
    .open-webui-desktop-response-activity-ring {
      position: absolute;
      inset: 0;
      border: 2px solid currentColor;
      border-right-color: transparent;
      border-radius: 9999px;
      animation: open-webui-desktop-response-spin 1.1s linear infinite;
    }
    .open-webui-desktop-response-activity-core {
      width: 4px;
      height: 4px;
      border-radius: 9999px;
      background: currentColor;
      animation: open-webui-desktop-response-pulse 1.1s ease-in-out infinite;
    }
    .open-webui-desktop-response-activity-body {
      min-width: 0;
    }
    .open-webui-desktop-response-activity-line {
      display: flex;
      min-width: 0;
      flex-wrap: wrap;
      align-items: center;
      column-gap: 8px;
      row-gap: 2px;
      font-size: 14px;
      line-height: 20px;
    }
    .open-webui-desktop-response-activity-label {
      color: color-mix(in srgb, CanvasText 82%, transparent);
      font-weight: 500;
    }
    .open-webui-desktop-response-activity-elapsed {
      color: color-mix(in srgb, CanvasText 48%, transparent);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .open-webui-desktop-response-activity-longer {
      display: none;
      margin: 2px 0 0;
      color: color-mix(in srgb, CanvasText 48%, transparent);
      font-size: 12px;
      line-height: 16px;
    }
    @keyframes open-webui-desktop-response-spin {
      to { transform: rotate(360deg); }
    }
    @keyframes open-webui-desktop-response-pulse {
      50% { transform: scale(.65); opacity: .45; }
    }
    @media (prefers-reduced-motion: reduce) {
      .open-webui-desktop-response-activity-ring,
      .open-webui-desktop-response-activity-core {
        animation: none;
      }
      .open-webui-desktop-response-activity-ring {
        border-right-color: currentColor;
        opacity: .55;
      }
    }
  `
  document.head.appendChild(style)
}

const updateResponseActivity = (state: ResponseActivityState): void => {
  const elapsedSeconds = Math.floor((Date.now() - state.startedAt) / 1000)
  const copy = responseActivityCopy()
  const label = state.indicator.querySelector<HTMLElement>(
    '.open-webui-desktop-response-activity-label'
  )
  const elapsed = state.indicator.querySelector<HTMLElement>(
    '.open-webui-desktop-response-activity-elapsed'
  )
  const longer = state.indicator.querySelector<HTMLElement>(
    '.open-webui-desktop-response-activity-longer'
  )

  if (label) label.textContent = elapsedSeconds < 8 ? copy.waiting : copy.working
  if (elapsed) elapsed.textContent = `${copy.elapsed} ${formatResponseElapsed(elapsedSeconds)}`
  if (longer) {
    longer.textContent = copy.longer
    longer.style.display = elapsedSeconds >= 15 ? 'block' : 'none'
  }
}

const removeResponseActivity = (container: HTMLElement): void => {
  const state = responseActivityStates.get(container)
  if (!state) return

  window.clearInterval(state.timer)
  state.indicator.remove()
  state.caretHost.style.removeProperty('display')
  container.removeAttribute('aria-busy')
  responseActivityStates.delete(container)
}

const mountResponseActivity = (container: HTMLElement, caretHost: HTMLElement): void => {
  ensureResponseActivityStyles()

  const indicator = document.createElement('div')
  indicator.className = RESPONSE_ACTIVITY_CLASS
  indicator.setAttribute('role', 'status')
  indicator.setAttribute('aria-live', 'polite')
  indicator.innerHTML = `
    <span class="open-webui-desktop-response-activity-indicator" aria-hidden="true">
      <span class="open-webui-desktop-response-activity-ring"></span>
      <span class="open-webui-desktop-response-activity-core"></span>
    </span>
    <span class="open-webui-desktop-response-activity-body">
      <span class="open-webui-desktop-response-activity-line">
        <span class="open-webui-desktop-response-activity-label"></span>
        <span class="open-webui-desktop-response-activity-elapsed" aria-hidden="true"></span>
      </span>
      <span class="open-webui-desktop-response-activity-longer"></span>
    </span>
  `

  caretHost.style.display = 'none'
  caretHost.insertAdjacentElement('beforebegin', indicator)
  container.setAttribute('aria-busy', 'true')

  const state: ResponseActivityState = {
    indicator,
    caretHost,
    startedAt: Date.now(),
    timer: 0
  }
  state.timer = window.setInterval(() => updateResponseActivity(state), 1000)
  responseActivityStates.set(container, state)
  updateResponseActivity(state)
}

const scanResponseActivities = (): void => {
  for (const [container, state] of responseActivityStates) {
    const meaningfulChildren = [...container.children].filter(
      (child) => child !== state.indicator && child !== state.caretHost
    )
    if (!container.isConnected || !state.caretHost.isConnected || meaningfulChildren.length > 0) {
      removeResponseActivity(container)
    }
  }

  document.querySelectorAll<HTMLElement>('#response-content-container').forEach((container) => {
    if (responseActivityStates.has(container)) return

    const message = container.closest<HTMLElement>('[id^="message-"]')
    if (!message?.querySelector('#response-message-model-name')) return

    const caret = container.querySelector<HTMLElement>('span.animate-pulse')
    if (!caret) return

    const caretHost = caret.parentElement ?? caret
    const meaningfulChildren = [...container.children].filter(
      (child) => child !== caretHost && !child.contains(caret)
    )
    if (meaningfulChildren.length > 0) return

    mountResponseActivity(container, caretHost)
  })
}

const scheduleResponseActivityScan = (): void => {
  if (responseActivityScanQueued) return
  responseActivityScanQueued = true
  window.requestAnimationFrame(() => {
    responseActivityScanQueued = false
    scanResponseActivities()
  })
}

const approvalObserver = new MutationObserver(scheduleApprovalMount)
approvalObserver.observe(document.documentElement, { childList: true, subtree: true })
const responseActivityObserver = new MutationObserver(scheduleResponseActivityScan)
responseActivityObserver.observe(document.documentElement, { childList: true, subtree: true })
document.addEventListener('focusin', scheduleApprovalMount, true)
document.addEventListener(
  'pointerdown',
  (event) => {
    const root = document.getElementById(APPROVAL_CONTROL_ID)
    if (root?.contains(event.target as Node) || approvalMenu?.contains(event.target as Node)) return
    closeApprovalMenu()
  },
  true
)
document.addEventListener(
  'keydown',
  (event) => {
    if (event.key === 'Escape' && approvalMenu) {
      event.preventDefault()
      closeApprovalMenu()
    }
  },
  true
)
window.addEventListener('resize', positionApprovalMenu)
window.addEventListener('scroll', positionApprovalMenu, true)
scheduleApprovalMount()
scheduleResponseActivityScan()

// Embedder → Guest (push events from desktop)
ipcRenderer.on('desktop:event', (_event, data) => {
  eventCallbacks.forEach((cb) => cb(data))
})

// ─── Theme Sync: Open WebUI → Desktop ───────────────────
contextBridge.exposeInMainWorld('applyTheme', () => {
  const theme = localStorage.getItem('theme') ?? 'system'
  ipcRenderer.sendToHost('webview:event', { type: 'theme:update', data: { theme } })
})

// Expose to the Open WebUI page via contextBridge (secure, unforgeable)
contextBridge.exposeInMainWorld('electronAPI', {
  onEvent: (callback: EventCallback): void => {
    eventCallbacks.push(callback)
  },
  send: (data: any): Promise<any> => {
    return new Promise((resolve) => {
      const id = Math.random().toString(36).slice(2)
      const handler = (_event: any, response: any) => {
        if (response?._responseId === id) {
          ipcRenderer.removeListener('desktop:response', handler)
          resolve(response.data)
        }
      }
      ipcRenderer.on('desktop:response', handler)
      ipcRenderer.sendToHost('webview:send', { ...data, _requestId: id })
    })
  },
  load: (page: string): void => {
    ipcRenderer.sendToHost('webview:load', page)
  }
})
