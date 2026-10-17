<script lang="ts">
  import { onMount } from 'svelte'
  import { fade, fly } from 'svelte/transition'
  import i18n from '../../../i18n'

  type WorkspaceTab = 'activity' | 'changes' | 'artifacts'

  interface WorkspaceActivity {
    id: string
    label: string
    detail?: string
    status: 'running' | 'complete' | 'failed'
    time: string
  }

  interface WorkspaceChange {
    path: string
    kind: 'created' | 'modified' | 'deleted'
    restorable: boolean
    beforeSize: number
    afterSize: number
    previewable: boolean
  }

  interface WorkspaceArtifact {
    path: string
    name: string
    extension: string
    size: number
    kind: 'created' | 'modified' | 'deleted'
    previewKind: 'image' | 'pdf' | 'html' | 'text' | 'office' | 'unsupported'
  }

  interface WorkspaceState {
    id: string
    connectionId: string
    chatId: string
    projectPath: string
    status: 'capturing' | 'running' | 'complete' | 'failed' | 'restored'
    startedAt: string
    completedAt?: string
    restoredAt?: string
    activities: WorkspaceActivity[]
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

  interface PreviewData {
    path: string
    name: string
    mime: string
    previewKind: WorkspaceArtifact['previewKind']
    encoding: 'utf8' | 'base64'
    data: string
    size: number
  }

  interface Props {
    connectionId: string
    chatId: string
    projectFolder: string | null
    projectTemporary: boolean
    onClose: () => void
  }

  let { connectionId, chatId, projectFolder, projectTemporary, onClose }: Props = $props()

  let activeTab: WorkspaceTab = $state('activity')
  let workspace: WorkspaceState | null = $state(null)
  let loading = $state(false)
  let rollbackBusy = $state(false)
  let message = $state('')
  let error = $state('')
  let canvasOpen = $state(false)
  let canvasTitle = $state('')
  let canvasPath = $state('')
  let canvasMode: 'artifact' | 'diff' = $state('artifact')
  let preview: PreviewData | null = $state(null)
  let beforePreview: PreviewData | null = $state(null)
  let afterPreview: PreviewData | null = $state(null)
  let previewLoading = $state(false)
  let previewError = $state('')
  let autoPreviewedCheckpointId = $state('')

  const projectName = $derived(
    projectTemporary
      ? $i18n.t('workspace.temporaryWorkspace')
      : (projectFolder?.replace(/\\/g, '/').split('/').filter(Boolean).at(-1) ?? '')
  )
  const canRollback = $derived(
    Boolean(
      workspace &&
      workspace.status !== 'running' &&
      workspace.status !== 'capturing' &&
      workspace.status !== 'restored' &&
      workspace.changes.some((change) => change.restorable)
    )
  )

  const refresh = async (quiet = false) => {
    if (!connectionId) {
      workspace = null
      return
    }
    if (!quiet) loading = true
    try {
      workspace = await window.electronAPI.getWorkspaceState({
        connectionId,
        chatId: chatId || undefined,
        projectPath: projectFolder
      })
      error = ''
    } catch (refreshError: any) {
      error = refreshError?.message ?? $i18n.t('workspace.loadError')
    } finally {
      if (!quiet) loading = false
    }
  }

  onMount(() => {
    void refresh()
    const interval = window.setInterval(() => void refresh(true), 1800)
    const unsubscribe = window.electronAPI.onData((data: any) => {
      if (data.type === 'workspace:changed' && data.data?.connectionId === connectionId) {
        void refresh(true)
      }
    })
    return () => {
      window.clearInterval(interval)
      unsubscribe?.()
    }
  })

  $effect(() => {
    connectionId
    chatId
    projectFolder
    void refresh(true)
  })

  const formatBytes = (bytes: number): string => {
    if (!bytes) return '0 B'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatTime = (value: string): string =>
    new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(
      new Date(value)
    )

  const kindLabel = (kind: WorkspaceChange['kind']): string =>
    kind === 'created'
      ? $i18n.t('workspace.created')
      : kind === 'deleted'
        ? $i18n.t('workspace.deleted')
        : $i18n.t('workspace.modified')

  const loadFile = async (
    relativePath: string,
    version: 'before' | 'after'
  ): Promise<PreviewData | null> => {
    if (!workspace?.id) return null
    try {
      return await window.electronAPI.readWorkspaceFile({
        checkpointId: workspace.id,
        relativePath,
        version
      })
    } catch {
      return null
    }
  }

  const openArtifactCanvas = async (artifact: WorkspaceArtifact) => {
    if (!workspace) return
    canvasOpen = true
    canvasMode = 'artifact'
    canvasTitle = artifact.name
    canvasPath = artifact.path
    preview = null
    beforePreview = null
    afterPreview = null
    previewError = ''
    previewLoading = true
    try {
      preview = await window.electronAPI.readWorkspaceFile({
        checkpointId: workspace.id,
        relativePath: artifact.path,
        version: 'after'
      })
    } catch (previewFailure: any) {
      previewError = previewFailure?.message ?? $i18n.t('workspace.previewUnavailable')
    } finally {
      previewLoading = false
    }
  }

  const openChangeCanvas = async (change: WorkspaceChange) => {
    if (!workspace) return
    canvasOpen = true
    canvasMode = 'diff'
    canvasTitle = change.path.split('/').at(-1) ?? change.path
    canvasPath = change.path
    preview = null
    beforePreview = null
    afterPreview = null
    previewError = ''
    previewLoading = false
    if (!change.previewable) {
      previewError = $i18n.t('workspace.previewUnavailable')
      return
    }
    previewLoading = true
    const [before, after] = await Promise.all([
      change.kind === 'created' ? Promise.resolve(null) : loadFile(change.path, 'before'),
      change.kind === 'deleted' ? Promise.resolve(null) : loadFile(change.path, 'after')
    ])
    beforePreview = before
    afterPreview = after
    if (!before && !after) previewError = $i18n.t('workspace.previewUnavailable')
    previewLoading = false
  }

  const openInDefaultApp = async (relativePath: string) => {
    if (!workspace) return
    await window.electronAPI.openWorkspaceFile({
      checkpointId: workspace.id,
      relativePath
    })
  }

  const revealInFolder = async (relativePath: string) => {
    if (!workspace) return
    await window.electronAPI.revealWorkspaceFile({
      checkpointId: workspace.id,
      relativePath
    })
  }

  const rollback = async () => {
    if (!workspace || !canRollback || rollbackBusy) return
    rollbackBusy = true
    error = ''
    message = ''
    try {
      workspace = await window.electronAPI.rollbackWorkspaceCheckpoint(workspace.id)
      message = $i18n.t('workspace.rollbackComplete')
    } catch (rollbackError: any) {
      error = rollbackError?.message ?? $i18n.t('workspace.rollbackError')
    } finally {
      rollbackBusy = false
    }
  }

  const closeCanvas = () => {
    canvasOpen = false
    preview = null
    beforePreview = null
    afterPreview = null
    previewError = ''
  }

  const dataUrl = (item: PreviewData): string => `data:${item.mime};base64,${item.data}`

  // Match Codex-style delivery: once a task finishes with a previewable
  // artifact, open the Canvas automatically instead of making the user hunt
  // through the project folder or click through several tabs.
  $effect(() => {
    const current = workspace
    const artifact = current?.artifacts?.[0]
    if (
      !current ||
      current.status !== 'complete' ||
      !artifact ||
      autoPreviewedCheckpointId === current.id
    ) {
      return
    }

    autoPreviewedCheckpointId = current.id
    activeTab = 'artifacts'
    window.setTimeout(() => {
      if (workspace?.id === current.id) void openArtifactCanvas(artifact)
    }, 0)
  })
</script>

<svelte:window
  onkeydown={(event) => {
    if (canvasOpen && event.key === 'Escape') closeCanvas()
  }}
/>

<aside
  class="workspace-panel relative z-10 flex h-full w-[390px] min-w-[320px] max-w-[42vw] shrink-0 flex-col border-l border-black/[0.09] bg-[#f7f7f8] text-[#1d1d1f] dark:border-white/[0.09] dark:bg-[#111] dark:text-[#fafafa]"
  aria-label={$i18n.t('workspace.title')}
  transition:fly={{ x: 18, duration: 180 }}
>
  <header
    class="flex h-12 shrink-0 items-center gap-3 border-b border-black/[0.08] px-3 dark:border-white/[0.08]"
  >
    <div class="min-w-0 flex-1">
      <div class="truncate text-[13px] font-semibold">{$i18n.t('workspace.title')}</div>
      <div class="truncate text-[10px] opacity-45">
        {projectName || $i18n.t('workspace.noProject')}
      </div>
    </div>
    <button
      class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border-none bg-transparent opacity-50 transition hover:bg-black/[0.06] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-blue-500 dark:hover:bg-white/[0.07]"
      onclick={onClose}
      aria-label={$i18n.t('workspace.close')}
    >
      <svg
        class="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        aria-hidden="true"
      >
        <path stroke-linecap="round" d="m7 7 10 10M17 7 7 17" />
      </svg>
    </button>
  </header>

  <div
    class="grid shrink-0 grid-cols-3 gap-1 border-b border-black/[0.08] p-1.5 dark:border-white/[0.08]"
    role="tablist"
  >
    {#each [['activity', $i18n.t('workspace.activity'), workspace?.activities.length ?? 0], ['changes', $i18n.t('workspace.changes'), workspace?.changes.length ?? 0], ['artifacts', $i18n.t('workspace.artifacts'), workspace?.artifacts.length ?? 0]] as tab}
      <button
        class="flex min-h-8 cursor-pointer items-center justify-center gap-1.5 rounded-lg border-none text-[11px] font-medium transition focus-visible:outline-2 focus-visible:outline-blue-500 {activeTab ===
        tab[0]
          ? 'bg-white text-black shadow-sm dark:bg-white/[0.11] dark:text-white'
          : 'bg-transparent opacity-50 hover:bg-black/[0.04] hover:opacity-80 dark:hover:bg-white/[0.05]'}"
        role="tab"
        aria-selected={activeTab === tab[0]}
        onclick={() => (activeTab = tab[0] as WorkspaceTab)}
      >
        <span>{tab[1]}</span>
        {#if Number(tab[2]) > 0}
          <span
            class="min-w-4 rounded-full bg-black/[0.07] px-1 text-[9px] tabular-nums dark:bg-white/[0.09]"
            >{tab[2]}</span
          >
        {/if}
      </button>
    {/each}
  </div>

  <div class="min-h-0 flex-1 overflow-y-auto p-3" role="tabpanel">
    {#if loading}
      <div class="flex h-28 items-center justify-center" aria-label={$i18n.t('common.loading')}>
        <div
          class="h-5 w-5 animate-spin rounded-full border-2 border-black/10 border-t-black/50 dark:border-white/15 dark:border-t-white/60"
        ></div>
      </div>
    {:else if !projectFolder}
      <div
        class="rounded-xl border border-dashed border-black/15 p-5 text-center dark:border-white/15"
      >
        <div class="text-[12px] font-medium">{$i18n.t('workspace.chooseProjectTitle')}</div>
        <div class="mt-1 text-[11px] leading-relaxed opacity-45">
          {$i18n.t('workspace.chooseProjectDescription')}
        </div>
      </div>
    {:else if !workspace}
      <div
        class="rounded-xl border border-dashed border-black/15 p-5 text-center dark:border-white/15"
      >
        <div class="text-[12px] font-medium">{$i18n.t('workspace.readyTitle')}</div>
        <div class="mt-1 text-[11px] leading-relaxed opacity-45">
          {$i18n.t('workspace.readyDescription')}
        </div>
      </div>
    {:else if activeTab === 'activity'}
      <div
        class="mb-3 flex items-center justify-between rounded-xl bg-black/[0.035] px-3 py-2.5 dark:bg-white/[0.045]"
      >
        <div>
          <div class="text-[11px] font-semibold">
            {$i18n.t(`workspace.status.${workspace.status}`)}
          </div>
          <div class="mt-0.5 text-[10px] opacity-45">{formatTime(workspace.startedAt)}</div>
        </div>
        {#if workspace.status === 'running' || workspace.status === 'capturing'}
          <div
            class="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-blue-500/25 border-t-blue-500"
          ></div>
        {:else if workspace.status === 'failed'}
          <span class="text-[11px] font-medium text-red-500">{$i18n.t('common.failed')}</span>
        {:else}
          <span class="text-[11px] font-medium text-emerald-600 dark:text-emerald-400"
            >{$i18n.t('common.ready')}</span
          >
        {/if}
      </div>

      <ol class="space-y-1.5">
        {#each workspace.activities as activity, index (activity.id)}
          <li class="grid grid-cols-[18px_minmax(0,1fr)] gap-2 rounded-lg px-1 py-1.5">
            <div class="relative flex justify-center pt-1">
              <span
                class="relative z-10 h-2.5 w-2.5 rounded-full border-2 {activity.status ===
                'complete'
                  ? 'border-emerald-500 bg-emerald-500'
                  : activity.status === 'failed'
                    ? 'border-red-500 bg-red-500'
                    : 'animate-pulse border-blue-500 bg-transparent'}"
              ></span>
              {#if index < workspace.activities.length - 1}
                <span class="absolute bottom-[-11px] top-3 w-px bg-black/10 dark:bg-white/10"
                ></span>
              {/if}
            </div>
            <div class="min-w-0">
              <div class="text-[11px] font-medium leading-5">{activity.label}</div>
              {#if activity.detail}
                <div class="text-[10px] leading-relaxed opacity-45">{activity.detail}</div>
              {/if}
            </div>
          </li>
        {/each}
      </ol>

      {#if workspace.limits.skippedFiles > 0 || workspace.limits.truncated}
        <div
          class="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-[10px] leading-relaxed text-amber-800 dark:text-amber-200"
        >
          {$i18n.t('workspace.snapshotLimit', { count: workspace.limits.skippedFiles })}
        </div>
      {/if}
    {:else if activeTab === 'changes'}
      {#if workspace.changes.length === 0}
        <div class="py-12 text-center text-[11px] opacity-40">{$i18n.t('workspace.noChanges')}</div>
      {:else}
        <div class="space-y-1.5">
          {#each workspace.changes as change (change.path)}
            <button
              class="group flex w-full cursor-pointer items-center gap-2 rounded-xl border border-transparent bg-black/[0.025] px-3 py-2.5 text-left text-inherit transition hover:border-black/10 hover:bg-black/[0.05] focus-visible:outline-2 focus-visible:outline-blue-500 dark:bg-white/[0.035] dark:hover:border-white/10 dark:hover:bg-white/[0.07]"
              onclick={() => void openChangeCanvas(change)}
            >
              <span
                class="w-12 shrink-0 rounded-md px-1.5 py-0.5 text-center text-[9px] font-semibold {change.kind ===
                'created'
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  : change.kind === 'deleted'
                    ? 'bg-red-500/10 text-red-700 dark:text-red-300'
                    : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'}"
                >{kindLabel(change.kind)}</span
              >
              <span class="min-w-0 flex-1">
                <span class="block truncate text-[11px] font-medium"
                  >{change.path.split('/').at(-1)}</span
                >
                <span class="block truncate text-[9px] opacity-40">{change.path}</span>
              </span>
              {#if !change.restorable}
                <span class="text-[9px] text-amber-600 dark:text-amber-300"
                  >{$i18n.t('workspace.notRestorable')}</span
                >
              {/if}
              <svg
                class="h-3.5 w-3.5 shrink-0 opacity-30 transition group-hover:opacity-60"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
                aria-hidden="true"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="m9 6 6 6-6 6" />
              </svg>
            </button>
          {/each}
        </div>
      {/if}
    {:else if workspace.artifacts.length === 0}
      <div class="py-12 text-center text-[11px] opacity-40">{$i18n.t('workspace.noArtifacts')}</div>
    {:else}
      <div class="grid grid-cols-2 gap-2">
        {#each workspace.artifacts as artifact (artifact.path)}
          <button
            class="group min-h-28 cursor-pointer rounded-xl border border-black/[0.08] bg-white p-3 text-left text-inherit transition hover:border-blue-500/30 hover:bg-blue-500/[0.025] focus-visible:outline-2 focus-visible:outline-blue-500 dark:border-white/[0.09] dark:bg-white/[0.035] dark:hover:border-blue-400/35 dark:hover:bg-blue-400/[0.05]"
            onclick={() => void openArtifactCanvas(artifact)}
          >
            <div class="mb-5 flex items-center justify-between">
              <div
                class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10 text-[10px] font-bold uppercase text-blue-700 dark:text-blue-300"
              >
                {artifact.extension.replace('.', '').slice(0, 4)}
              </div>
              <svg
                class="h-4 w-4 opacity-25 transition group-hover:opacity-60"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M14 3h7v7m0-7L10 14M5 7v12h12v-5"
                />
              </svg>
            </div>
            <div class="truncate text-[11px] font-semibold">{artifact.name}</div>
            <div class="mt-0.5 truncate text-[9px] opacity-40">{formatBytes(artifact.size)}</div>
          </button>
        {/each}
      </div>
    {/if}

    {#if error}
      <div
        class="mt-3 rounded-lg bg-red-500/[0.08] px-3 py-2 text-[10px] text-red-700 dark:text-red-300"
        role="status"
      >
        {error}
      </div>
    {/if}
    {#if message}
      <div
        class="mt-3 rounded-lg bg-emerald-500/[0.08] px-3 py-2 text-[10px] text-emerald-700 dark:text-emerald-300"
        role="status"
      >
        {message}
      </div>
    {/if}
  </div>

  {#if workspace?.changes.length}
    <footer class="shrink-0 border-t border-black/[0.08] p-3 dark:border-white/[0.08]">
      <button
        class="flex min-h-9 w-full items-center justify-center gap-2 rounded-xl border border-black/10 bg-white text-[11px] font-semibold text-black transition hover:bg-black/[0.035] focus-visible:outline-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-35 dark:border-white/10 dark:bg-white/[0.07] dark:text-white dark:hover:bg-white/[0.11]"
        disabled={!canRollback || rollbackBusy}
        onclick={() => void rollback()}
      >
        <svg
          class="h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 7H4v-5M4 7a9 9 0 1 1-1 8" />
        </svg>
        {rollbackBusy ? $i18n.t('workspace.restoring') : $i18n.t('workspace.rollback')}
      </button>
      <div class="mt-1.5 text-center text-[9px] leading-relaxed opacity-35">
        {$i18n.t('workspace.rollbackHint')}
      </div>
    </footer>
  {/if}
</aside>

{#if canvasOpen}
  <div
    class="fixed inset-0 z-[1000] flex items-center justify-center bg-black/55 p-5 backdrop-blur-sm"
    transition:fade={{ duration: 150 }}
    role="presentation"
  >
    <div
      class="flex h-[min(84vh,900px)] w-[min(1180px,92vw)] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#f6f6f7] text-[#1d1d1f] shadow-2xl dark:bg-[#111] dark:text-[#fafafa]"
      aria-label={$i18n.t('workspace.canvas')}
      aria-modal="true"
      role="dialog"
      transition:fly={{ y: 12, duration: 180 }}
    >
      <header
        class="flex h-13 shrink-0 items-center gap-3 border-b border-black/[0.08] px-4 dark:border-white/[0.08]"
      >
        <div class="min-w-0 flex-1">
          <div class="truncate text-[13px] font-semibold">{canvasTitle}</div>
          <div class="truncate text-[10px] opacity-45">{canvasPath}</div>
        </div>
        {#if workspace && canvasMode === 'artifact'}
          <button
            class="h-8 cursor-pointer rounded-lg border border-black/10 bg-white px-3 text-[11px] font-medium text-inherit transition hover:bg-black/[0.04] focus-visible:outline-2 focus-visible:outline-blue-500 dark:border-white/10 dark:bg-white/[0.07] dark:hover:bg-white/[0.11]"
            onclick={() => void revealInFolder(canvasPath)}>{$i18n.t('workspace.reveal')}</button
          >
          <button
            class="h-8 cursor-pointer rounded-lg border border-black/10 bg-white px-3 text-[11px] font-medium text-inherit transition hover:bg-black/[0.04] focus-visible:outline-2 focus-visible:outline-blue-500 dark:border-white/10 dark:bg-white/[0.07] dark:hover:bg-white/[0.11]"
            onclick={() => void openInDefaultApp(canvasPath)}>{$i18n.t('workspace.open')}</button
          >
        {/if}
        <button
          class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg border-none bg-transparent opacity-55 transition hover:bg-black/[0.06] hover:opacity-100 focus-visible:outline-2 focus-visible:outline-blue-500 dark:hover:bg-white/[0.08]"
          onclick={closeCanvas}
          aria-label={$i18n.t('common.close')}
        >
          <svg
            class="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
            aria-hidden="true"><path stroke-linecap="round" d="m7 7 10 10M17 7 7 17" /></svg
          >
        </button>
      </header>

      <div class="min-h-0 flex-1 overflow-auto bg-[#ededee] p-4 dark:bg-[#0a0a0a]">
        {#if previewLoading}
          <div class="flex h-full items-center justify-center">
            <div
              class="h-6 w-6 animate-spin rounded-full border-2 border-black/10 border-t-black/50 dark:border-white/15 dark:border-t-white/60"
            ></div>
          </div>
        {:else if previewError}
          <div class="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div class="text-[13px] font-medium">{$i18n.t('workspace.previewUnavailable')}</div>
            <div class="max-w-md text-[11px] leading-relaxed opacity-45">{previewError}</div>
            {#if canvasMode === 'artifact'}
              <button
                class="rounded-lg bg-black px-4 py-2 text-[11px] font-medium text-white dark:bg-white dark:text-black"
                onclick={() => void openInDefaultApp(canvasPath)}
                >{$i18n.t('workspace.open')}</button
              >
            {/if}
          </div>
        {:else if canvasMode === 'diff'}
          <div class="grid min-h-full grid-cols-2 gap-3">
            <article
              class="min-w-0 overflow-hidden rounded-xl border border-red-500/15 bg-white dark:bg-[#151515]"
            >
              <div
                class="border-b border-black/[0.07] px-3 py-2 text-[10px] font-semibold text-red-700 dark:border-white/[0.08] dark:text-red-300"
              >
                {$i18n.t('workspace.before')}
              </div>
              <pre
                class="h-[calc(100%-33px)] overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-relaxed">{beforePreview?.data ??
                  $i18n.t('workspace.emptyFile')}</pre>
            </article>
            <article
              class="min-w-0 overflow-hidden rounded-xl border border-emerald-500/15 bg-white dark:bg-[#151515]"
            >
              <div
                class="border-b border-black/[0.07] px-3 py-2 text-[10px] font-semibold text-emerald-700 dark:border-white/[0.08] dark:text-emerald-300"
              >
                {$i18n.t('workspace.after')}
              </div>
              <pre
                class="h-[calc(100%-33px)] overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-relaxed">{afterPreview?.data ??
                  $i18n.t('workspace.emptyFile')}</pre>
            </article>
          </div>
        {:else if preview}
          {#if preview.previewKind === 'image'}
            <div class="flex min-h-full items-center justify-center">
              <img
                src={dataUrl(preview)}
                alt={preview.name}
                class="max-h-full max-w-full rounded-lg object-contain shadow-sm"
              />
            </div>
          {:else if preview.previewKind === 'pdf'}
            <object
              data={dataUrl(preview)}
              type="application/pdf"
              aria-label={preview.name}
              class="h-full min-h-[520px] w-full rounded-lg bg-white"
              ><p>{$i18n.t('workspace.previewUnavailable')}</p></object
            >
          {:else if preview.previewKind === 'html'}
            <iframe
              title={preview.name}
              srcdoc={preview.data}
              sandbox="allow-scripts"
              class="h-full min-h-[520px] w-full rounded-lg border-none bg-white"
            ></iframe>
          {:else if preview.previewKind === 'text'}
            <pre
              class="min-h-full whitespace-pre-wrap break-words rounded-xl border border-black/[0.08] bg-white p-5 font-mono text-[12px] leading-relaxed dark:border-white/[0.08] dark:bg-[#151515]">{preview.data}</pre>
          {:else}
            <div class="flex h-full flex-col items-center justify-center gap-3 text-center">
              <div class="text-[13px] font-medium">{$i18n.t('workspace.officePreview')}</div>
              <button
                class="rounded-lg bg-black px-4 py-2 text-[11px] font-medium text-white dark:bg-white dark:text-black"
                onclick={() => void openInDefaultApp(canvasPath)}
                >{$i18n.t('workspace.open')}</button
              >
            </div>
          {/if}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .workspace-panel :global(button) {
    touch-action: manipulation;
  }

  @media (max-width: 920px) {
    .workspace-panel {
      position: absolute;
      inset: 0 0 0 auto;
      width: min(390px, 92vw);
      max-width: 92vw;
      box-shadow: -20px 0 50px rgba(0, 0, 0, 0.25);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .workspace-panel :global(*) {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
