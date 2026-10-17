<script lang="ts">
  import { fade, fly } from 'svelte/transition'
  import i18n from '../../../i18n'

  interface ProjectItem {
    path: string
    name: string
    available: boolean
  }

  interface Props {
    projectFolder: string | null
    projectTemporary: boolean
    projectBusy: boolean
    openTerminalStatus: string | null
    recentProjects: ProjectItem[]
    onChooseProject: () => void
    onUseProject: (project: ProjectItem) => void
    onOpenProject: () => void
    onStart: () => void
    onContinueWithoutProject: () => void
  }

  let {
    projectFolder,
    projectTemporary,
    projectBusy,
    openTerminalStatus,
    recentProjects,
    onChooseProject,
    onUseProject,
    onOpenProject,
    onStart,
    onContinueWithoutProject
  }: Props = $props()

  const projectName = $derived(
    projectTemporary
      ? $i18n.t('projectHome.temporaryWorkspace')
      : (projectFolder?.replace(/\\/g, '/').split('/').filter(Boolean).at(-1) ?? '')
  )
  const terminalReady = $derived(openTerminalStatus === 'started')
</script>

<div
  class="absolute inset-0 z-20 overflow-y-auto bg-[#f5f5f7]/96 p-5 text-[#1d1d1f] backdrop-blur-xl dark:bg-[#0a0a0a]/96 dark:text-[#fafafa]"
  transition:fade={{ duration: 160 }}
>
  <main
    class="mx-auto flex min-h-full w-full max-w-[920px] items-center justify-center py-6"
    aria-labelledby="project-launcher-title"
  >
    <div
      class="grid w-full gap-4 lg:grid-cols-[minmax(0,1fr)_300px]"
      transition:fly={{ y: 10, duration: 190 }}
    >
      <section
        class="rounded-3xl border border-black/[0.08] bg-white p-7 shadow-[0_16px_50px_rgba(0,0,0,0.06)] dark:border-white/[0.09] dark:bg-[#121212] dark:shadow-black/30"
      >
        <div
          class="mb-5 flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-700 dark:text-blue-300"
        >
          <svg
            class="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3.75 6.75A2.25 2.25 0 0 1 6 4.5h3.879c.398 0 .779.158 1.06.44l1.122 1.12c.281.282.663.44 1.061.44H18a2.25 2.25 0 0 1 2.25 2.25v7.5A2.25 2.25 0 0 1 18 18.5H6a2.25 2.25 0 0 1-2.25-2.25v-9.5Z"
            />
          </svg>
        </div>

        <h1 id="project-launcher-title" class="text-[24px] font-semibold tracking-[-0.025em]">
          {$i18n.t('projectHome.title')}
        </h1>
        <p class="mt-2 max-w-xl text-[13px] leading-6 opacity-55">
          {$i18n.t('projectHome.description')}
        </p>

        <div class="mt-6">
          <div class="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] opacity-35">
            {$i18n.t('projectHome.selectedProject')}
          </div>

          {#if projectFolder}
            <div
              class="flex min-h-20 items-center gap-3 rounded-2xl border border-blue-500/20 bg-blue-500/[0.055] p-4"
            >
              <div
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/12 text-blue-700 dark:text-blue-300"
              >
                <svg
                  class="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M3.75 6.75A2.25 2.25 0 0 1 6 4.5h3.879c.398 0 .779.158 1.06.44l1.122 1.12c.281.282.663.44 1.061.44H18a2.25 2.25 0 0 1 2.25 2.25v7.5A2.25 2.25 0 0 1 18 18.5H6a2.25 2.25 0 0 1-2.25-2.25v-9.5Z"
                  />
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate text-[13px] font-semibold">{projectName}</div>
                <div class="mt-0.5 truncate text-[10px] opacity-45">
                  {projectTemporary ? $i18n.t('projectHome.temporaryHint') : projectFolder}
                </div>
              </div>
              <button
                class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border-none bg-transparent opacity-45 transition hover:bg-black/[0.06] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-blue-500 dark:hover:bg-white/[0.08]"
                onclick={onOpenProject}
                aria-label={$i18n.t('projectHome.openFolder')}
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M13.5 6H18m0 0v4.5M18 6l-7.5 7.5M6 8.25V18h9.75"
                  />
                </svg>
              </button>
            </div>
          {:else}
            <button
              class="flex min-h-20 w-full cursor-pointer items-center gap-3 rounded-2xl border border-dashed border-black/20 bg-transparent p-4 text-left text-inherit transition hover:border-blue-500/45 hover:bg-blue-500/[0.035] focus-visible:outline-2 focus-visible:outline-blue-500 dark:border-white/20"
              disabled={projectBusy}
              onclick={onChooseProject}
            >
              <div
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-black/[0.045] dark:bg-white/[0.06]"
              >
                <svg
                  class="h-5 w-5 opacity-55"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  aria-hidden="true"
                >
                  <path stroke-linecap="round" d="M12 5v14M5 12h14" />
                </svg>
              </div>
              <div>
                <div class="text-[12px] font-semibold">{$i18n.t('projectHome.choose')}</div>
                <div class="mt-0.5 text-[10px] opacity-45">
                  {$i18n.t('projectHome.chooseHint')}
                </div>
              </div>
            </button>
          {/if}
        </div>

        <div class="mt-5 flex flex-wrap items-center gap-2">
          <button
            class="min-h-10 cursor-pointer rounded-xl bg-[#1d1d1f] px-5 text-[12px] font-semibold text-white transition hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-white/90"
            disabled={projectBusy}
            onclick={projectFolder ? onStart : onContinueWithoutProject}
          >
            {projectBusy
              ? $i18n.t('projectHome.preparing')
              : projectFolder
                ? $i18n.t('projectHome.start')
                : $i18n.t('projectHome.startTemporary')}
          </button>
          <button
            class="min-h-10 cursor-pointer rounded-xl border border-black/10 bg-transparent px-4 text-[12px] font-medium text-inherit transition hover:bg-black/[0.045] focus-visible:outline-2 focus-visible:outline-blue-500 dark:border-white/10 dark:hover:bg-white/[0.06]"
            disabled={projectBusy}
            onclick={onChooseProject}
          >
            {projectFolder ? $i18n.t('projectHome.change') : $i18n.t('projectHome.choose')}
          </button>
        </div>
      </section>

      <aside class="space-y-4">
        <section
          class="rounded-3xl border border-black/[0.08] bg-white p-5 dark:border-white/[0.09] dark:bg-[#121212]"
        >
          <div class="text-[11px] font-semibold">{$i18n.t('projectHome.workspaceReady')}</div>
          <div class="mt-4 space-y-3">
            {#each [[terminalReady, terminalReady ? $i18n.t('projectHome.terminalReady') : $i18n.t('projectHome.terminalStarting')], [true, $i18n.t('projectHome.checkpointReady')], [true, $i18n.t('projectHome.canvasReady')]] as readiness}
              <div class="flex items-center gap-2.5 text-[11px]">
                <span
                  class="flex h-5 w-5 items-center justify-center rounded-full {readiness[0]
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300'
                    : 'bg-amber-500/10 text-amber-600 dark:text-amber-300'}"
                >
                  {#if readiness[0]}
                    <svg
                      class="h-3 w-3"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      aria-hidden="true"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" d="m5 12 4 4L19 6" />
                    </svg>
                  {:else}
                    <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-current"></span>
                  {/if}
                </span>
                <span class="opacity-65">{readiness[1]}</span>
              </div>
            {/each}
          </div>
        </section>

        {#if recentProjects.length > 0}
          <section
            class="rounded-3xl border border-black/[0.08] bg-white p-3 dark:border-white/[0.09] dark:bg-[#121212]"
          >
            <div
              class="px-2 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] opacity-35"
            >
              {$i18n.t('projectHome.recent')}
            </div>
            <div class="space-y-1">
              {#each recentProjects.slice(0, 5) as project (project.path)}
                <button
                  class="flex w-full cursor-pointer items-center gap-2 rounded-xl border-none bg-transparent px-2 py-2.5 text-left text-inherit transition hover:bg-black/[0.045] focus-visible:outline-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-35 dark:hover:bg-white/[0.06]"
                  disabled={!project.available || projectBusy}
                  onclick={() => onUseProject(project)}
                >
                  <svg
                    class="h-4 w-4 shrink-0 opacity-35"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.6"
                    aria-hidden="true"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M3.75 6.75A2.25 2.25 0 0 1 6 4.5h3.879c.398 0 .779.158 1.06.44l1.122 1.12c.281.282.663.44 1.061.44H18a2.25 2.25 0 0 1 2.25 2.25v7.5A2.25 2.25 0 0 1 18 18.5H6a2.25 2.25 0 0 1-2.25-2.25v-9.5Z"
                    />
                  </svg>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-[11px] font-medium">{project.name}</span>
                    <span class="block truncate text-[9px] opacity-35">{project.path}</span>
                  </span>
                  {#if !project.available}
                    <span class="text-[9px] text-amber-600 dark:text-amber-300">
                      {$i18n.t('projectHome.unavailable')}
                    </span>
                  {/if}
                </button>
              {/each}
            </div>
          </section>
        {/if}
      </aside>
    </div>
  </main>
</div>

<style>
  @media (prefers-reduced-motion: reduce) {
    :global(*) {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
    }
  }
</style>
