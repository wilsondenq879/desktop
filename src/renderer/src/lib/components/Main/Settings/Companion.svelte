<script lang="ts">
  import { onMount } from 'svelte'
  import QRCode from 'qrcode'

  import { config } from '../../../stores'
  import Switch from '../../common/Switch.svelte'

  type CompanionSettings = {
    enabled: boolean
    host: string
    port: number
    apiKey: string
  }

  let settings = $state<CompanionSettings>({
    enabled: true,
    host: '0.0.0.0',
    port: 39280,
    apiKey: ''
  })
  let saving = $state(false)
  let message = $state('')
  let pairingQr = $state('')
  let pairingExpiresAt = $state('')
  let pairingBusy = $state(false)

  onMount(() => {
    const saved = $config?.companion ?? {}
    settings = {
      enabled: saved.enabled ?? true,
      host: saved.host ?? '0.0.0.0',
      port: saved.port ?? 39280,
      apiKey: saved.apiKey ?? ''
    }
  })

  const save = async () => {
    saving = true
    message = ''
    try {
      await window.electronAPI.setConfig({ companion: { ...settings } })
      config.set(await window.electronAPI.getConfig())
      message = '已儲存。手機端重新測試連線即可。'
    } catch (error) {
      message = error instanceof Error ? error.message : String(error)
    } finally {
      saving = false
    }
  }

  const createPairingCode = async () => {
    pairingBusy = true
    message = ''
    try {
      await save()
      const pairing = await window.electronAPI.createDesktopCompanionPairing()
      pairingQr = await QRCode.toDataURL(pairing.pairingUrl, {
        width: 360,
        margin: 2,
        color: { dark: '#06121d', light: '#f4fbff' }
      })
      pairingExpiresAt = new Date(pairing.expiresAt).toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit'
      })
      message = 'QR Code 已建立。請在手機 App 的「遠端桌面」掃描配對。'
    } catch (error) {
      message = error instanceof Error ? error.message : String(error)
    } finally {
      pairingBusy = false
    }
  }
</script>

<div class="flex flex-col divide-y divide-black/[0.05] dark:divide-white/[0.06]">
  <section class="py-4 flex items-center justify-between gap-6">
    <div>
      <div class="text-[13px] opacity-80">手機 Companion API</div>
      <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-lg">
        讓 iPhone 讀取這台電腦的專案進度、檔案變更與成品摘要；不會開放任意檔案系統操作。
      </div>
    </div>
    <Switch
      checked={settings.enabled}
      label="啟用手機 Companion API"
      onchange={(value) => {
        settings.enabled = value
        void save()
      }}
    />
  </section>

  <section class="py-4">
    <div class="text-[13px] opacity-80">連線位址</div>
    <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-lg">
      手機不能填 127.0.0.1。家中 Wi-Fi 使用這台電腦的 LAN IP；遠端使用 Tailscale 或 ZeroTier IP。
    </div>

    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="companion-host" class="block text-[12px] opacity-75 mb-1.5">監聽介面</label>
        <input
          id="companion-host"
          type="text"
          bind:value={settings.host}
          placeholder="0.0.0.0"
          onblur={save}
          class="min-h-11 w-full rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] font-mono text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
        />
      </div>
      <div>
        <label for="companion-port" class="block text-[12px] opacity-75 mb-1.5">連接埠</label>
        <input
          id="companion-port"
          type="number"
          min="1"
          max="65535"
          bind:value={settings.port}
          onblur={save}
          class="min-h-11 w-full rounded-xl border border-black/[0.06] bg-black/[0.04] px-3 text-[12px] text-[#1d1d1f] outline-none transition focus:border-blue-500/40 focus:ring-2 focus:ring-blue-500/10 dark:border-white/[0.08] dark:bg-white/[0.06] dark:text-[#fafafa]"
        />
      </div>
    </div>
  </section>

  <section class="py-4">
    <div class="text-[13px] opacity-80">掃碼配對遠端桌面</div>
    <div class="text-[12px] opacity-60 mt-1 leading-relaxed max-w-lg">
      QR Code 只含五分鐘、一次性的配對碼；不含 Open WebUI 密碼，也不會改變手機 App 的聊天連線。
    </div>
    <div class="mt-3 flex flex-wrap items-start gap-4">
      <button
        type="button"
        disabled={pairingBusy || !settings.enabled}
        onclick={createPairingCode}
        class="min-h-11 shrink-0 rounded-xl border-none bg-cyan-600 px-4 text-[12px] text-white transition hover:bg-cyan-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40 disabled:pointer-events-none disabled:opacity-50"
      >
        {pairingBusy ? '產生中…' : '顯示手機配對 QR Code'}
      </button>
      {#if pairingQr}
        <div class="rounded-2xl bg-white p-3 shadow-sm">
          <img src={pairingQr} alt="掃描以配對 Open WebUI Desktop" width="180" height="180" class="block h-[180px] w-[180px]" />
          <div class="mt-2 text-center text-[11px] text-slate-600">有效至 {pairingExpiresAt}</div>
        </div>
      {/if}
    </div>
  </section>

  <section class="py-4 flex items-center justify-between gap-4">
    <div class="text-[11px] opacity-55 leading-relaxed">
      {#if message}{message}{:else}變更會在儲存後立即套用。Windows 防火牆若跳出提示，請允許私人網路。{/if}
    </div>
    <button
      type="button"
      disabled={saving}
      onclick={save}
      class="min-h-11 shrink-0 rounded-xl border-none bg-blue-600 px-4 text-[12px] text-white transition hover:bg-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:pointer-events-none disabled:opacity-50"
    >
      {saving ? '儲存中…' : '儲存設定'}
    </button>
  </section>
</div>
