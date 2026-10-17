/**
 * Runs in Open WebUI's page context. It labels rows in the model picker with
 * compact capability icons without changing the selected model or the server's
 * own model data. Server-provided capability metadata wins; conservative name
 * detection fills in useful local-model defaults when metadata is absent.
 */
export const modelCapabilityDecoratorScript = String.raw`
(() => {
  const bridgeKey = '__openWebUIModelCapabilityDecoratorV2'
  if (window[bridgeKey]) return
  window[bridgeKey] = true

  const styleId = 'open-webui-model-capability-style'
  const state = { models: [], attempts: 0, scheduled: false, pickerTrigger: null, pickerOpenUntil: 0 }
  const labels = {
    chat: '文字對話',
    reasoning: '推理',
    vision: '視覺',
    code: '程式',
    tools: 'Tools',
    image: '圖像生成'
  }
  const icons = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 18.75 3.75 21v-4.5A8.25 8.25 0 1 1 12 20.25a8.2 8.2 0 0 1-4.5-1.5Z"/></svg>',
    reasoning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 4.5a3 3 0 0 1 4.5 0 3 3 0 0 1 3 3 3 3 0 0 1 0 5.25 3 3 0 0 1-1.5 5.25 3 3 0 0 1-4.5 0 3 3 0 0 1-4.5-2.625 3 3 0 0 1 0-5.25 3 3 0 0 1 3-5.25Z"/><path stroke-linecap="round" d="M9 9.25h.01M15 9.25h.01M10 14.5c.6.5 1.25.75 2 .75s1.4-.25 2-.75"/></svg>',
    vision: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12S5.75 6.75 12 6.75 21.75 12 21.75 12 18.25 17.25 12 17.25 2.25 12 2.25 12Z"/><circle cx="12" cy="12" r="2.25"/></svg>',
    code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 8.25-3.75 3.75 3.75 3.75M15.75 8.25l3.75 3.75-3.75 3.75M13.5 5.25l-3 13.5"/></svg>',
    tools: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M14.7 6.3a4.25 4.25 0 0 0-5.64 5.64L3.75 17.25a2.12 2.12 0 1 0 3 3l5.31-5.31a4.25 4.25 0 0 0 5.64-5.64l-2.48 2.48-3.08-.62-.62-3.08 2.48-2.48Z"/></svg>',
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3.75" y="4.5" width="16.5" height="15" rx="2.25"/><path stroke-linecap="round" stroke-linejoin="round" d="m5.25 16.5 4.25-4.25 3 3 2-2 4.25 4.25M15.75 9h.01"/></svg>'
  }

  const normalize = (value) => String(value || '').trim().toLowerCase()
  const visible = (element) => {
    const style = window.getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }

  const ensureStyles = () => {
    if (document.getElementById(styleId)) return
    const style = document.createElement('style')
    style.id = styleId
    style.textContent =
      '.open-webui-model-capability-row{position:relative!important;min-width:0!important;padding-right:82px!important;}' +
      '.open-webui-model-capabilities{position:absolute;right:8px;top:50%;transform:translateY(-50%);display:inline-flex;align-items:center;justify-content:flex-end;gap:2px;max-width:74px;margin:0;z-index:2;pointer-events:none;}' +
      '.open-webui-model-capability{display:inline-flex;flex:0 0 16px;width:16px;height:16px;align-items:center;justify-content:center;border:1px solid color-mix(in srgb,currentColor 16%,transparent);border-radius:5px;background:color-mix(in srgb,#38bdf8 10%,#111827 72%);color:color-mix(in srgb,#38bdf8 80%,currentColor);box-sizing:border-box;}' +
      '.open-webui-model-capability svg{width:10px;height:10px;display:block;}' +
      '@media (max-width:520px){.open-webui-model-capability-row{padding-right:78px!important}.open-webui-model-capabilities{right:7px;max-width:70px}.open-webui-model-capability{flex-basis:15px;width:15px;height:15px;border-radius:4px}.open-webui-model-capability svg{width:9px;height:9px}}' +
      '@media (prefers-reduced-motion:reduce){.open-webui-model-capability{transition:none!important}}'
    document.head.appendChild(style)
  }

  const modelList = (payload) => {
    const raw = Array.isArray(payload) ? payload : (payload && (payload.data || payload.models || payload.items))
    if (!Array.isArray(raw)) return []
    return raw
      .filter((model) => model && (model.id || model.name))
      .map((model) => ({
        raw: model,
        id: String(model.id || ''),
        name: String(model.name || model.id || '')
      }))
  }

  const capabilitySources = (model) => {
    const raw = model.raw || {}
    return [
      raw.capabilities,
      raw.meta && raw.meta.capabilities,
      raw.info && raw.info.capabilities,
      raw.info && raw.info.meta && raw.info.meta.capabilities,
      raw.details && raw.details.capabilities
    ].filter(Boolean)
  }

  const hasCapability = (model, keys) => capabilitySources(model).some((source) => {
    if (Array.isArray(source)) return source.some((value) => keys.includes(normalize(value)))
    if (!source || typeof source !== 'object') return false
    return keys.some((key) => source[key] === true || source[key] === 'true' || source[key] === 1)
  })

  const capabilitiesFor = (model) => {
    const identity = normalize(model.id + ' ' + model.name)
    const has = (keys) => hasCapability(model, keys)
    const result = []
    const reasoning = has(['reasoning', 'thinking', 'reason']) || /(?:deepseek-r1|reasoner|thinking|nemotron|qwen3|gpt-oss)/.test(identity)
    const vision = has(['vision', 'image_input', 'image-input', 'multimodal']) || /(?:\bvl\b|vision|llava|pixtral|moondream|gemma[-: ]?3|qwen[-.: ]?vl)/.test(identity)
    const code = has(['code', 'coding']) || /(?:coder|code|qwen|gpt-oss|starcoder|codestral)/.test(identity)
    const tools = has(['tools', 'tool_calling', 'function_calling', 'function-calling'])
    const image = has(['image_generation', 'image-generation']) || /(?:flux|stable[- ]?diffusion|sdxl|sd[-_:])/i.test(identity)
    if (reasoning) result.push('reasoning')
    if (vision) result.push('vision')
    if (code) result.push('code')
    if (tools) result.push('tools')
    if (image) result.push('image')
    return result.length ? result.slice(0, 4) : ['chat']
  }

  const matchingModel = (element) => {
    const text = normalize(element.textContent)
    if (!text) return null
    const ranked = state.models
      .map((model) => ({ model, keys: [model.name, model.id].map(normalize).filter((key) => key.length > 2) }))
      .sort((a, b) => Math.max(...b.keys.map((key) => key.length), 0) - Math.max(...a.keys.map((key) => key.length), 0))
    return ranked.find(({ keys }) => keys.some((key) => text.includes(key)))?.model || null
  }

  const findRows = () => {
    const rows = []
    document.querySelectorAll('button,[role="option"],[role="menuitem"]').forEach((element) => {
      if (!visible(element)) return
      if (element.querySelector('.open-webui-model-capabilities')) return
      const model = matchingModel(element)
      if (model) rows.push({ element, model })
    })
    return rows
  }

  const decorateRow = ({ element, model }) => {
    const features = capabilitiesFor(model)
    const strip = document.createElement('span')
    strip.className = 'open-webui-model-capabilities'
    strip.setAttribute('aria-label', '模型能力：' + features.map((feature) => labels[feature]).join('、'))
    features.forEach((feature) => {
      const badge = document.createElement('span')
      badge.className = 'open-webui-model-capability'
      badge.title = labels[feature]
      badge.setAttribute('role', 'img')
      badge.setAttribute('aria-label', labels[feature])
      badge.innerHTML = icons[feature]
      strip.appendChild(badge)
    })
    // Keep the capability rail outside the model-name span. The previous
    // implementation appended it to the nearest text wrapper, which caused
    // the icons to overlap truncated names on narrow phone pickers.
    element.classList.add('open-webui-model-capability-row')
    element.appendChild(strip)
  }

  const decorate = () => {
    state.scheduled = false
    if (!state.models.length) return
    // Model names also appear in the compact composer selector. Only add
    // badges during the short window immediately after that selector opens.
    // This prevents the selected-model button from being mistaken for a row.
    if (Date.now() > state.pickerOpenUntil || !state.pickerTrigger || !state.pickerTrigger.isConnected) return
    ensureStyles()
    const rows = findRows().filter(({ element }) =>
      element !== state.pickerTrigger &&
      !state.pickerTrigger.contains(element) &&
      !element.contains(state.pickerTrigger)
    )
    // A single matching button is normally the compact composer selector.
    // Only decorate a menu/list where at least two model options are visible.
    if (new Set(rows.map(({ model }) => model.id || model.name)).size < 2) return
    rows.forEach(decorateRow)
  }

  const schedule = () => {
    if (state.scheduled) return
    state.scheduled = true
    window.requestAnimationFrame(decorate)
  }

  const refreshModels = async () => {
    try {
      const response = await window.fetch(new URL('/api/models', window.location.origin).toString(), { credentials: 'same-origin' })
      if (!response.ok) throw new Error('model list unavailable')
      const models = modelList(await response.json())
      if (models.length) {
        state.models = models
        schedule()
        return
      }
    } catch {
      // The WebUI session may not be authenticated yet. Retry briefly after login.
    }
    state.attempts += 1
    if (state.attempts < 8) window.setTimeout(refreshModels, 1600)
  }

  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true })
  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target.closest('button,[role="button"],[role="combobox"]') : null
    if (!target || target.closest('.open-webui-model-capabilities') || !matchingModel(target)) return
    state.pickerTrigger = target
    state.pickerOpenUntil = Date.now() + 2200
    window.setTimeout(schedule, 70)
    window.setTimeout(schedule, 260)
  }, true)
  ensureStyles()
  void refreshModels()
})()
`
