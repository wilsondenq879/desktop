<script lang="ts">
  import { onMount } from 'svelte'

  import i18n from '../../../i18n'
  import { config } from '../../../stores'
  import Switch from '../../common/Switch.svelte'

  type Settings = {
    enabled: boolean
    host: string
    sshPort: number
    username: string
    keyPath: string
    knownHostsPath: string
  }

  type Status = {
    ok: boolean
    message: string
    detail?: string
  }

  let settings = $state<Settings>({
    enabled: false,
    host: '',
    sshPort: 22,
    username: 'admin',
    keyPath: '',
    knownHostsPath: ''
  })
  let testing = $state(false)
  let saving = $state(false)
  let status = $state<Status | null>(null)

  onMount(() => {
    const saved = $config?.asuswrtMcp ?? {}
    settings = {
      enabled: saved.enabled ?? false,
      host: saved.host ?? '',
      sshPort: saved.sshPort ?? 22,
      username: saved.username ?? 'admin',
      keyPath: saved.keyPath ?? '',
      knownHostsPath: saved.knownHostsPath ?? ''
    }
  })

  const save = async () => {
    saving = true
    status = null
    try {
      const result = await window.electronAPI.saveAsuswrtMcp(settings)
      config.set(await window.electronAPI.getConfig())
      status = {
        ok: true,
        message: $i18n.t('settings.asuswrtMcp.saved'),
        detail: result?.configPath
      }
    } catch (error) {
      status = {
        ok: false,
        message: $i18n.t('settings.asuswrtMcp.saveFailed'),
        detail: error instanceof Error ? error.message : String(error)
      }
    } finally {
      saving = false
    }
  }

  const testConnection = async () => {
    testing = true
    status = null
    try {
      status = await window.electronAPI.testAsuswrtMcp(settings)
    } catch (error) {
      status = {
        ok: false,
        message: $i18n.t('settings.asuswrtMcp.testFailed'),
        detail: error instanceof Error ? error.message : String(error)
      }
    } finally {
      testing = false
    }
  }

  const chooseFile = async (field: 'keyPath' | 'knownHostsPath', title: string) => {
    const selected = await window.electronAPI.selectFile({ title })
    if (selected) settings[field] = selected
  }
</script>

<div class="flex flex-col divide-y divide-black/[0.05] dark:divide-white/[0.06]">
  <section class="py-4 flex items-center justify-between gap-6">
    <div>
      <div class="text-[13px] opacity-80">{$i18n.t('settings.asuswrtMcp.enabled')}</div>
      <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-lg">
        {$i18n.t('settings.asuswrtMcp.enabledDesc')}
      </div>
    </div>
    <Switch
      checked={settings.enabled}
      label={$i18n.t('settings.asuswrtMcp.toggleEnabled')}
      onchange={(value) => (settings.enabled = value)}
    />
  </section>

  <section class="py-4">
    <div class="text-[13px] opacity-80">{$i18n.t('settings.asuswrtMcp.connectionTitle')}</div>
    <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-lg">
      {$i18n.t('settings.asuswrtMcp.connectionDesc')}
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="asuswrt-host" class="block text-[12px] opacity-75 mb-1.5">
          {$i18n.t('settings.asuswrtMcp.host')}
        </label>
        <input
          id="asuswrt-host"
          type="text"
          bind:value={settings.host}
          placeholder="192.168.50.1"
          autocomplete="off"
          class="min-h-11 w-full rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
          aria-describedby="asuswrt-host-help"
        />
        <p id="asuswrt-host-help" class="mt-1.5 text-[11px] opacity-55">
          {$i18n.t('settings.asuswrtMcp.hostHint')}
        </p>
      </div>

      <div>
        <label for="asuswrt-port" class="block text-[12px] opacity-75 mb-1.5">
          {$i18n.t('settings.asuswrtMcp.sshPort')}
        </label>
        <input
          id="asuswrt-port"
          type="number"
          min="1"
          max="65535"
          bind:value={settings.sshPort}
          class="min-h-11 w-full rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
        />
      </div>

      <div>
        <label for="asuswrt-user" class="block text-[12px] opacity-75 mb-1.5">
          {$i18n.t('settings.asuswrtMcp.username')}
        </label>
        <input
          id="asuswrt-user"
          type="text"
          bind:value={settings.username}
          autocomplete="username"
          class="min-h-11 w-full rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
        />
      </div>

      <div class="md:col-span-2">
        <label for="asuswrt-key" class="block text-[12px] opacity-75 mb-1.5">
          {$i18n.t('settings.asuswrtMcp.keyPath')}
        </label>
        <div class="flex items-center gap-2">
          <input
            id="asuswrt-key"
            type="text"
            bind:value={settings.keyPath}
            placeholder="C:\\Users\\you\\.ssh\\asuswrt_ed25519"
            autocomplete="off"
            class="min-h-11 min-w-0 flex-1 rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] font-mono text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
            aria-describedby="asuswrt-key-help"
          />
          <button
            type="button"
            onclick={() => chooseFile('keyPath', $i18n.t('settings.asuswrtMcp.chooseKey'))}
            class="min-h-11 shrink-0 rounded-xl border-none bg-black/[0.06] px-3 text-[12px] text-[#1d1d1f] transition hover:bg-black/[0.10] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:bg-white/[0.08] dark:text-[#fafafa] dark:hover:bg-white/[0.12]"
          >
            {$i18n.t('settings.asuswrtMcp.browse')}
          </button>
        </div>
        <p id="asuswrt-key-help" class="mt-1.5 text-[11px] opacity-55">
          {$i18n.t('settings.asuswrtMcp.keyHint')}
        </p>
      </div>

      <div class="md:col-span-2">
        <label for="asuswrt-known-hosts" class="block text-[12px] opacity-75 mb-1.5">
          {$i18n.t('settings.asuswrtMcp.knownHostsPath')}
        </label>
        <div class="flex items-center gap-2">
          <input
            id="asuswrt-known-hosts"
            type="text"
            bind:value={settings.knownHostsPath}
            placeholder="C:\\Users\\you\\.ssh\\known_hosts"
            autocomplete="off"
            class="min-h-11 min-w-0 flex-1 rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] font-mono text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
          />
          <button
            type="button"
            onclick={() => chooseFile('knownHostsPath', $i18n.t('settings.asuswrtMcp.chooseKnownHosts'))}
            class="min-h-11 shrink-0 rounded-xl border-none bg-black/[0.06] px-3 text-[12px] text-[#1d1d1f] transition hover:bg-black/[0.10] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:bg-white/[0.08] dark:text-[#fafafa] dark:hover:bg-white/[0.12]"
          >
            {$i18n.t('settings.asuswrtMcp.browse')}
          </button>
        </div>
        <p class="mt-1.5 text-[11px] opacity-55">{$i18n.t('settings.asuswrtMcp.knownHostsHint')}</p>
      </div>
    </div>

    <div class="mt-5 flex flex-wrap items-center justify-end gap-2">
      <button
        type="button"
        disabled={testing || saving || !settings.host.trim()}
        onclick={testConnection}
        class="min-h-11 rounded-xl border border-black/[0.08] bg-transparent px-4 text-[12px] text-[#1d1d1f] transition hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:pointer-events-none disabled:opacity-35 dark:border-white/[0.12] dark:text-[#fafafa] dark:hover:bg-white/[0.06]"
      >
        {#if testing}
          <span class="flex items-center gap-2">
            <span class="size-3 rounded-full border-[1.5px] border-current border-t-transparent animate-spin motion-reduce:animate-none" aria-hidden="true"></span>
            {$i18n.t('settings.asuswrtMcp.testing')}
          </span>
        {:else}
          {$i18n.t('settings.asuswrtMcp.test')}
        {/if}
      </button>
      <button
        type="button"
        disabled={testing || saving}
        onclick={save}
        class="min-h-11 rounded-xl border-none bg-blue-600 px-4 text-[12px] font-medium text-white transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:pointer-events-none disabled:opacity-35"
      >
        {#if saving}
          {$i18n.t('settings.asuswrtMcp.saving')}
        {:else}
          {$i18n.t('settings.asuswrtMcp.save')}
        {/if}
      </button>
    </div>

    {#if status}
      <div
        class="mt-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-[12px] {status.ok
          ? 'bg-emerald-500/[0.08] text-emerald-700 dark:text-emerald-300'
          : 'bg-red-500/[0.08] text-red-700 dark:text-red-300'}"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <span class="mt-1 size-1.5 shrink-0 rounded-full {status.ok ? 'bg-emerald-500' : 'bg-red-500'}" aria-hidden="true"></span>
        <span>
          <span class="block font-medium">{status.message}</span>
          {#if status.detail}<span class="mt-0.5 block opacity-70 break-all">{status.detail}</span>{/if}
        </span>
      </div>
    {/if}
  </section>

  <section class="py-4">
    <div class="rounded-2xl border border-black/[0.05] bg-black/[0.025] p-4 dark:border-white/[0.07] dark:bg-white/[0.035]">
      <div class="text-[13px] font-medium opacity-80">{$i18n.t('settings.asuswrtMcp.securityTitle')}</div>
      <ul class="mt-2 list-disc space-y-1.5 pl-4 text-[12px] leading-relaxed opacity-65">
        <li>{$i18n.t('settings.asuswrtMcp.securityStep1')}</li>
        <li>{$i18n.t('settings.asuswrtMcp.securityStep2')}</li>
        <li>{$i18n.t('settings.asuswrtMcp.securityStep3')}</li>
      </ul>
    </div>
  </section>
</div>
