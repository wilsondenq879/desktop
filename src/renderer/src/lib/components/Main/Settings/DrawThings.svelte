<script lang="ts">
  import { onMount } from 'svelte'

  import i18n from '../../../i18n'
  import { config } from '../../../stores'
  import Switch from '../../common/Switch.svelte'

  type ConnectionStatus = {
    ok: boolean
    message: string
    detail?: string
  }

  let apiUrl = $state('http://127.0.0.1:7860')
  let testing = $state(false)
  let status = $state<ConnectionStatus | null>(null)
  let platform = $state('')

  onMount(async () => {
    apiUrl = $config?.drawThings?.apiUrl ?? 'http://127.0.0.1:7860'
    platform = (await window.electronAPI.getAppInfo())?.platform ?? ''
  })

  const updateDrawThingsConfig = async (changes: Record<string, unknown>) => {
    const current = $config ?? {}
    const drawThings = { ...(current.drawThings ?? {}), ...changes }
    await window.electronAPI.setConfig({ drawThings })
    config.set(await window.electronAPI.getConfig())
  }

  const saveApiUrl = async () => {
    const normalized = apiUrl.trim().replace(/\/+$/, '') || 'http://127.0.0.1:7860'
    apiUrl = normalized
    status = null
    await updateDrawThingsConfig({ apiUrl: normalized })
  }

  const testConnection = async () => {
    testing = true
    status = null
    try {
      await saveApiUrl()
      status = await window.electronAPI.testDrawThingsConnection(apiUrl)
    } catch (error) {
      status = {
        ok: false,
        message: $i18n.t('settings.drawThings.testFailed'),
        detail: error instanceof Error ? error.message : String(error)
      }
    } finally {
      testing = false
    }
  }
</script>

<div class="flex flex-col divide-y divide-black/[0.05] dark:divide-white/[0.06]">
  <section class="py-4 flex items-center justify-between gap-6">
    <div>
      <div class="text-[13px] opacity-80">{$i18n.t('settings.drawThings.enabled')}</div>
      <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-md">
        {$i18n.t('settings.drawThings.enabledDesc')}
      </div>
    </div>
    <Switch
      checked={$config?.drawThings?.enabled ?? true}
      label={$i18n.t('settings.drawThings.toggleEnabled')}
      onchange={(value) => updateDrawThingsConfig({ enabled: value })}
    />
  </section>

  <section class="py-4">
    <label for="draw-things-api-url" class="block text-[13px] opacity-80">
      {$i18n.t('settings.drawThings.apiUrl')}
    </label>
    <div class="text-[12px] opacity-60 mt-1 leading-relaxed">
      {$i18n.t('settings.drawThings.apiUrlDesc')}
    </div>
    <div class="mt-3 flex items-center gap-2">
      <input
        id="draw-things-api-url"
        type="url"
        bind:value={apiUrl}
        disabled={!($config?.drawThings?.enabled ?? true) || testing}
        onkeydown={(event) => {
          if (event.key === 'Enter') void testConnection()
        }}
        onblur={saveApiUrl}
        class="min-h-11 flex-1 rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 disabled:opacity-35 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
        aria-describedby="draw-things-api-help"
      />
      <button
        type="button"
        disabled={!($config?.drawThings?.enabled ?? true) || testing}
        onclick={testConnection}
        class="min-h-11 shrink-0 rounded-xl border-none bg-black/[0.06] px-4 text-[12px] text-[#1d1d1f] transition hover:bg-black/[0.10] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:pointer-events-none disabled:opacity-35 dark:bg-white/[0.08] dark:text-[#fafafa] dark:hover:bg-white/[0.12]"
      >
        <span class="flex items-center gap-2">
          {#if testing}
            <span
              class="size-3 rounded-full border-[1.5px] border-current border-t-transparent animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            ></span>
            {$i18n.t('settings.drawThings.testing')}
          {:else}
            {$i18n.t('settings.drawThings.test')}
          {/if}
        </span>
      </button>
    </div>
    <p id="draw-things-api-help" class="mt-2 text-[11px] opacity-60 leading-relaxed">
      {$i18n.t('settings.drawThings.networkHint')}
    </p>

    {#if status}
      <div
        class="mt-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-[12px] {status.ok
          ? 'bg-emerald-500/[0.08] text-emerald-700 dark:text-emerald-300'
          : 'bg-red-500/[0.08] text-red-700 dark:text-red-300'}"
        role="status"
        aria-atomic="true"
      >
        <span
          class="mt-1 size-1.5 shrink-0 rounded-full {status.ok ? 'bg-emerald-500' : 'bg-red-500'}"
          aria-hidden="true"
        ></span>
        <span>
          <span class="block font-medium">{status.message}</span>
          {#if status.detail}
            <span class="mt-0.5 block opacity-70">{status.detail}</span>
          {/if}
        </span>
      </div>
    {/if}
  </section>

  {#if platform === 'darwin'}
    <section class="py-4 flex items-center justify-between gap-6">
      <div>
        <div class="text-[13px] opacity-80">{$i18n.t('settings.drawThings.autoLaunch')}</div>
        <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-md">
          {$i18n.t('settings.drawThings.autoLaunchDesc')}
        </div>
      </div>
      <Switch
        checked={$config?.drawThings?.autoLaunch ?? true}
        label={$i18n.t('settings.drawThings.toggleAutoLaunch')}
        onchange={(value) => updateDrawThingsConfig({ autoLaunch: value })}
      />
    </section>
  {/if}

  <section class="py-4">
    <div
      class="rounded-2xl border border-black/[0.05] bg-black/[0.025] p-4 dark:border-white/[0.07] dark:bg-white/[0.035]"
    >
      <div class="text-[13px] font-medium opacity-80">
        {$i18n.t('settings.drawThings.setupTitle')}
      </div>
      <ol class="mt-2 list-decimal space-y-1.5 pl-4 text-[12px] leading-relaxed opacity-65">
        <li>{$i18n.t('settings.drawThings.setupStep1')}</li>
        <li>{$i18n.t('settings.drawThings.setupStep2')}</li>
        <li>{$i18n.t('settings.drawThings.setupStep3')}</li>
      </ol>
      <p class="mt-3 text-[12px] leading-relaxed opacity-60">
        {$i18n.t('settings.drawThings.resultHint')}
      </p>
    </div>
  </section>
</div>
