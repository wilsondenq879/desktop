<script lang="ts">
  import { fade } from 'svelte/transition'
  import i18n from '../../../i18n'
  import { tooltip } from '../../../actions/tooltip'
  import { appInfo } from '../../../stores'
  import trayIcon from '../../../../../../../resources/tray.png'

  interface Props {
    serverStatus: string | undefined
    serverReachable: boolean | undefined
    openTerminalStatus: string | null
    llamaCppStatus: string | null
    openWebuiInstalled: boolean
    openTerminalInstalled: boolean
    llamaCppInstalled: boolean
    activeLog: string | null
    projectControlsVisible: boolean
    activeChatId: string
    projectFolder: string | null
    projectBusy: boolean
    projectMessage: string
    projectError: string
    onSelectLog: (log: string) => void
    onStartServer: () => void
    onToggleOpenTerminal: () => void
    onToggleLlamaCpp: () => void
    onChooseProjectFolder: () => void
    onClearProjectFolder: () => void
    onOpenProjectFolder: () => void
  }

  let {
    serverStatus,
    serverReachable,
    openTerminalStatus,
    llamaCppStatus,
    openWebuiInstalled,
    openTerminalInstalled,
    llamaCppInstalled,
    activeLog,
    projectControlsVisible,
    activeChatId,
    projectFolder,
    projectBusy,
    projectMessage,
    projectError,
    onSelectLog,
    onStartServer,
    onToggleOpenTerminal,
    onToggleLlamaCpp,
    onChooseProjectFolder,
    onClearProjectFolder,
    onOpenProjectFolder
  }: Props = $props()

  // Derived server state
  const serverRunning = $derived(serverStatus === 'started' && serverReachable)
  const serverStarting = $derived(
    serverStatus === 'starting' || (serverStatus === 'started' && !serverReachable)
  )

  const otRunning = $derived(openTerminalStatus === 'started')
  const otStarting = $derived(
    openTerminalStatus === 'starting' || openTerminalStatus === 'stopping'
  )
  const otFailed = $derived(openTerminalStatus === 'failed')

  const lsRunning = $derived(llamaCppStatus === 'started')
  const lsStarting = $derived(
    llamaCppStatus === 'starting' ||
      llamaCppStatus === 'setting-up' ||
      llamaCppStatus === 'stopping'
  )
  const lsFailed = $derived(llamaCppStatus === 'failed')

  // Derived visibility — show each section only when installed or active
  const showServer = $derived(openWebuiInstalled || !!serverStatus)
  const showTerminal = $derived(openTerminalInstalled || !!openTerminalStatus)
  const showLlama = $derived(llamaCppInstalled || !!llamaCppStatus)
  const projectFolderName = $derived(
    projectFolder?.replace(/\\/g, '/').split('/').filter(Boolean).at(-1) ?? ''
  )
</script>

<div
  class="shrink-0 flex items-center gap-1 px-3 h-7 border-t border-black/[0.08] dark:border-white/[0.08] bg-[#ebebed] dark:bg-[#111111]"
  in:fade={{ duration: 150 }}
>
  <!-- Open WebUI logo mark -->
  <img src={trayIcon} alt="" class="w-3.5 opacity-30 mx-0.5 shrink-0 invert dark:invert-0" />

  {#if showServer}
    <!-- Open WebUI status -->
    <button
      class="flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] transition-all bg-transparent border-none cursor-pointer text-[#1d1d1f] dark:text-[#fafafa] {activeLog ===
      'server'
        ? 'bg-black/[0.08] dark:bg-white/[0.1] opacity-90'
        : 'opacity-50 hover:opacity-80 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]'}"
      onclick={() => {
        if (!serverRunning && !serverStarting) {
          onStartServer()
        }
        onSelectLog('server')
      }}
      use:tooltip={serverRunning
        ? $i18n.t('statusBar.serverRunning')
        : serverStarting
          ? $i18n.t('common.starting')
          : $i18n.t('statusBar.serverStopped')}
    >
      <div
        class="w-[7px] h-[7px] shrink-0 rounded-full {serverRunning
          ? 'bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.6)]'
          : serverStarting
            ? 'bg-amber-400 animate-pulse'
            : 'bg-black/15 dark:bg-white/20'}"
      ></div>
      <span>{$i18n.t('statusBar.server')}</span>
    </button>
  {/if}

  {#if showTerminal}
    {#if showServer}
      <div class="w-px h-3 bg-black/[0.08] dark:bg-white/[0.08] mx-0.5"></div>
    {/if}

    <!-- Open Terminal status -->
    <button
      class="flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] transition-all bg-transparent border-none cursor-pointer text-[#1d1d1f] dark:text-[#fafafa] {activeLog ===
      'open-terminal'
        ? 'bg-black/[0.08] dark:bg-white/[0.1] opacity-90'
        : 'opacity-50 hover:opacity-80 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]'}"
      onclick={() => {
        if (!otRunning && !otStarting) {
          onToggleOpenTerminal()
        }
        onSelectLog('open-terminal')
      }}
      oncontextmenu={(e) => {
        e.preventDefault()
        if (otRunning) onToggleOpenTerminal()
      }}
      use:tooltip={otRunning
        ? activeLog === 'open-terminal'
          ? $i18n.t('sidebar.tooltip.hideLogs')
          : $i18n.t('sidebar.tooltip.viewLogs')
        : otStarting
          ? $i18n.t('common.starting')
          : otFailed
            ? $i18n.t('sidebar.tooltip.clickToRetry')
            : $i18n.t('sidebar.tooltip.startTerminalServer')}
    >
      <div
        class="w-[7px] h-[7px] shrink-0 rounded-full {otRunning
          ? 'bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.6)]'
          : otStarting
            ? 'bg-amber-400 animate-pulse'
            : otFailed
              ? 'bg-red-400'
              : 'bg-black/15 dark:bg-white/20'}"
      ></div>
      <span>{$i18n.t('sidebar.openTerminal')}</span>
    </button>
  {/if}

  {#if showLlama}
    {#if showServer || showTerminal}
      <div class="w-px h-3 bg-black/[0.08] dark:bg-white/[0.08] mx-0.5"></div>
    {/if}

    <!-- llama.cpp status -->
    <button
      class="flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] transition-all bg-transparent border-none cursor-pointer text-[#1d1d1f] dark:text-[#fafafa] {activeLog ===
      'llama-server'
        ? 'bg-black/[0.08] dark:bg-white/[0.1] opacity-90'
        : 'opacity-50 hover:opacity-80 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]'}"
      onclick={() => {
        if (!lsRunning && !lsStarting) {
          onToggleLlamaCpp()
        }
        onSelectLog('llama-server')
      }}
      oncontextmenu={(e) => {
        e.preventDefault()
        if (lsRunning) onToggleLlamaCpp()
      }}
      use:tooltip={lsRunning
        ? activeLog === 'llama-server'
          ? $i18n.t('sidebar.tooltip.hideLogs')
          : $i18n.t('sidebar.tooltip.viewLogs')
        : lsStarting
          ? $i18n.t('common.starting')
          : lsFailed
            ? $i18n.t('sidebar.tooltip.clickToRetry')
            : $i18n.t('sidebar.tooltip.startLlamaServer')}
    >
      <div
        class="w-[7px] h-[7px] shrink-0 rounded-full {lsRunning
          ? 'bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.6)]'
          : lsStarting
            ? 'bg-amber-400 animate-pulse'
            : lsFailed
              ? 'bg-red-400'
              : 'bg-black/15 dark:bg-white/20'}"
      ></div>
      <span>{$i18n.t('sidebar.llamaCpp')}</span>
    </button>
  {/if}

  {#if projectControlsVisible}
    {#if showServer || showTerminal || showLlama}
      <div class="w-px h-3 bg-black/[0.08] dark:bg-white/[0.08] mx-0.5"></div>
    {/if}

    <div class="flex items-center min-w-0" aria-busy={projectBusy}>
      <button
        class="group flex min-w-0 items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] transition-all border-none text-[#1d1d1f] dark:text-[#fafafa] {activeChatId
          ? 'cursor-pointer bg-black/[0.035] hover:bg-black/[0.07] dark:bg-white/[0.045] dark:hover:bg-white/[0.09] opacity-70 hover:opacity-100'
          : 'cursor-default bg-transparent opacity-30'}"
        disabled={!activeChatId || projectBusy}
        onclick={onChooseProjectFolder}
        aria-label={projectFolder
          ? $i18n.t('statusBar.changeProjectFolder', { folder: projectFolderName })
          : $i18n.t('statusBar.chooseProjectFolder')}
        use:tooltip={!activeChatId
          ? $i18n.t('statusBar.openChatForProject')
          : projectFolder || $i18n.t('statusBar.chooseProjectFolder')}
      >
        {#if projectBusy}
          <div
            class="w-3 h-3 shrink-0 rounded-full border-[1.5px] border-black/25 dark:border-white/35 border-t-transparent animate-spin"
          ></div>
        {:else}
          <svg
            class="w-3 h-3 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3.75 6.75A2.25 2.25 0 016 4.5h3.879c.398 0 .779.158 1.06.44l1.122 1.12c.281.282.663.44 1.061.44H18A2.25 2.25 0 0120.25 8.75v7.5A2.25 2.25 0 0118 18.5H6a2.25 2.25 0 01-2.25-2.25v-9.5z"
            />
          </svg>
        {/if}
        <span class="max-w-[160px] truncate">
          {#if !activeChatId}
            {$i18n.t('statusBar.project')}
          {:else if projectFolder}
            {projectFolderName}
          {:else}
            {$i18n.t('statusBar.chooseProject')}
          {/if}
        </span>
      </button>

      {#if projectFolder && activeChatId && !projectBusy}
        <button
          class="ml-0.5 flex items-center justify-center w-6 h-6 rounded-md bg-transparent border-none cursor-pointer opacity-35 hover:opacity-80 hover:bg-black/[0.05] dark:hover:bg-white/[0.06] text-[#1d1d1f] dark:text-[#fafafa] transition"
          onclick={onOpenProjectFolder}
          aria-label={$i18n.t('statusBar.openProjectFolder')}
          use:tooltip={$i18n.t('statusBar.openProjectFolder')}
        >
          <svg
            class="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M13.5 6H18m0 0v4.5M18 6l-7.5 7.5M6 8.25v9.75h9.75"
            />
          </svg>
        </button>
        <button
          class="flex items-center justify-center w-6 h-6 rounded-md bg-transparent border-none cursor-pointer opacity-30 hover:opacity-75 hover:bg-black/[0.05] dark:hover:bg-white/[0.06] text-[#1d1d1f] dark:text-[#fafafa] transition"
          onclick={onClearProjectFolder}
          aria-label={$i18n.t('statusBar.clearProjectFolder')}
          use:tooltip={$i18n.t('statusBar.clearProjectFolder')}
        >
          <svg
            class="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
            aria-hidden="true"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      {/if}
    </div>

    {#if projectError}
      <span
        class="max-w-[220px] truncate text-[10px] text-red-500/80 dark:text-red-400/80"
        role="status"
        use:tooltip={projectError}
      >
        {projectError}
      </span>
    {/if}
  {/if}

  <span class="sr-only" aria-live="polite">
    {projectError || projectMessage}
  </span>

  <!-- Version (right-aligned) -->
  <span class="ml-auto text-[10px] opacity-25 select-none">v{$appInfo?.version ?? ''}</span>
</div>
