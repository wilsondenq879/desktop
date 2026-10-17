import SwiftUI
import WebKit

struct OpenWebUIWebView: UIViewRepresentable {
    let url: URL
    let reloadID: UUID
    @Binding var isLoading: Bool
    @Binding var errorMessage: String?

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.userContentController.addUserScript(
            WKUserScript(
                source: ModelCapabilityDecorator.script,
                injectionTime: .atDocumentEnd,
                forMainFrameOnly: true
            )
        )
        configuration.userContentController.addUserScript(
            WKUserScript(
                source: DiagramRendererBootstrap.script,
                injectionTime: .atDocumentEnd,
                forMainFrameOnly: true
            )
        )
        configuration.userContentController.addUserScript(
            WKUserScript(
                source: TerminalConnectionToastDecorator.script,
                injectionTime: .atDocumentEnd,
                forMainFrameOnly: true
            )
        )

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.allowsLinkPreview = true
        webView.backgroundColor = UIColor(TechTheme.ink)
        webView.scrollView.backgroundColor = UIColor(TechTheme.ink)
        context.coordinator.load(url, in: webView, reloadID: reloadID)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.load(url, in: webView, reloadID: reloadID)
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        private var parent: OpenWebUIWebView
        private var loadedURL: URL?
        private var lastReloadID: UUID?

        init(_ parent: OpenWebUIWebView) { self.parent = parent }

        func load(_ url: URL, in webView: WKWebView, reloadID: UUID) {
            guard loadedURL != url || lastReloadID != reloadID else { return }
            loadedURL = url
            lastReloadID = reloadID
            parent.errorMessage = nil
            parent.isLoading = true
            var request = URLRequest(
                url: url,
                cachePolicy: .reloadIgnoringLocalAndRemoteCacheData,
                timeoutInterval: 30
            )
            request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
            webView.load(request)
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
            parent.errorMessage = nil
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.errorMessage = error.localizedDescription
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.errorMessage = error.localizedDescription
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            parent.errorMessage = "Open WebUI 的網頁程序被系統中止。請重新整理。"
            parent.isLoading = false
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            if let requestURL = navigationAction.request.url {
                webView.load(URLRequest(url: requestURL))
            }
            return nil
        }
    }
}

/// Loads the same React + SVG renderer used by the web client. The native
/// bootstrap runs even when WKWebView restored an older cached Open WebUI shell.
private enum DiagramRendererBootstrap {
    static let script = #"""
    (() => {
      const key = '__openWebUIDiagramBootstrapV6';
      if (window[key]) return;
      window[key] = true;

      const load = (src, ready) => new Promise((resolve, reject) => {
        if (ready()) return resolve();
        const existing = [...document.scripts].find((script) => script.src.includes(src.split('?')[0]));
        if (existing) {
          existing.addEventListener('load', resolve, { once: true });
          existing.addEventListener('error', reject, { once: true });
          return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.async = false;
        script.addEventListener('load', resolve, { once: true });
        script.addEventListener('error', reject, { once: true });
        document.head.appendChild(script);
      });

      load('/static/openwebui-react-18.min.js?v=18.3.1', () => Boolean(window.React))
        .then(() => load('/static/openwebui-react-dom-18.min.js?v=18.3.1', () => Boolean(window.ReactDOM?.createRoot)))
        .then(() => load('/static/openwebui-react-svg-diagram-renderer.js?v=20261017-6', () => Boolean(window.__openWebUIReactSvgDiagramRendererV2)))
        .catch((error) => console.error('[Open WebUI Diagram] bootstrap failed', error));
    })();
    """#
}

/// Open WebUI presents unreachable desktop-only terminal endpoints as a full-width
/// red error toast. On a phone this is especially distracting: an endpoint such
/// as 127.0.0.1 is intentionally unavailable from iOS and does not stop chat
/// from working. Keep the message and its dismiss control, but present it as a
/// compact, non-blocking status chip instead.
private enum TerminalConnectionToastDecorator {
    static let script = #"""
    (() => {
      const key = '__openWebUITerminalToastDecoratorV1';
      if (window[key]) return;
      window[key] = true;

      const failure = /(?:無法連線至終端機伺服器|無法連線.*終端機|unable to connect to (?:the )?terminal server|could not connect to (?:the )?terminal server|failed to connect.*terminal)/i;
      const styleID = 'open-webui-terminal-toast-compact-style';

      const installStyle = () => {
        if (document.getElementById(styleID)) return;
        const style = document.createElement('style');
        style.id = styleID;
        style.textContent = `
          .open-webui-terminal-toast-compact {
            position: fixed !important;
            top: calc(env(safe-area-inset-top, 0px) + 8px) !important;
            right: 10px !important;
            left: auto !important;
            z-index: 2147483646 !important;
            width: auto !important;
            max-width: min(80vw, 320px) !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 8px 10px !important;
            border: 1px solid rgba(251, 113, 133, .34) !important;
            border-radius: 10px !important;
            background: rgba(69, 10, 18, .90) !important;
            box-shadow: 0 6px 18px rgba(0, 0, 0, .24) !important;
            color: rgba(255, 228, 230, .96) !important;
            font-size: 12px !important;
            line-height: 1.35 !important;
            letter-spacing: 0 !important;
            transform: none !important;
            animation-duration: 140ms !important;
          }
          .open-webui-terminal-toast-compact svg {
            width: 15px !important;
            height: 15px !important;
            flex: 0 0 15px !important;
          }
          .open-webui-terminal-toast-compact button {
            min-width: 28px !important;
            min-height: 28px !important;
            margin: -4px -5px -4px 2px !important;
          }
          /* Some Open WebUI versions use a fixed toast stack. Compact each
             card in that stack too, instead of leaving a wide red child. */
          .open-webui-terminal-toast-compact > [data-sonner-toast],
          .open-webui-terminal-toast-compact > [role="alert"] {
            width: auto !important;
            max-width: min(80vw, 320px) !important;
            min-height: 0 !important;
            padding: 8px 10px !important;
            border-radius: 10px !important;
            background: rgba(69, 10, 18, .90) !important;
            font-size: 12px !important;
            line-height: 1.35 !important;
          }
          @media (prefers-reduced-motion: reduce) {
            .open-webui-terminal-toast-compact { animation: none !important; }
          }
        `;
        document.head.appendChild(style);
      };

      const visible = (element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      };

      const chooseToast = (element) => {
        const semanticToast = element.closest('[role="alert"], [data-sonner-toast], [data-toast], [data-type="error"]');
        if (semanticToast instanceof HTMLElement && visible(semanticToast)) return semanticToast;
        let current = element;
        for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
          const text = (current.innerText || current.textContent || '').trim();
          const positioned = ['fixed', 'absolute'].includes(getComputedStyle(current).position);
          const matchesToast = current.getAttribute('role') === 'alert' || /toast|notification|sonner/i.test(String(current.className || ''));
          if (text && failure.test(text) && (positioned || matchesToast) && visible(current)) return current;
        }
        return null;
      };

      const decorate = () => {
        document.querySelectorAll('body *').forEach((element) => {
          if (!(element instanceof HTMLElement) || element.classList.contains('open-webui-terminal-toast-compact')) return;
          const ownText = (element.innerText || element.textContent || '').trim();
          if (!ownText || !failure.test(ownText)) return;
          const toast = chooseToast(element);
          if (toast) toast.classList.add('open-webui-terminal-toast-compact');
        });
      };

      installStyle();
      const queue = () => requestAnimationFrame(decorate);
      new MutationObserver(queue).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
      queue();
    })();
    """#
}

/// Open WebUI supplies the model picker. This same-origin script decorates
/// its existing picker after it loads, so models remain server-defined while
/// users can scan their likely strengths through the same compact icon system
/// used by the Desktop wrapper.
private enum ModelCapabilityDecorator {
    static let script = #"""
    (() => {
      const key = '__openWebUIModelCapabilityDecoratorV2';
      if (window[key]) return;
      window[key] = true;
      const state = { models: [], attempts: 0, queued: false, pickerTrigger: null, pickerOpenUntil: 0 };
      const labels = { chat: '文字對話', reasoning: '推理', vision: '視覺', code: '程式', tools: 'Tools', image: '圖像生成' };
      const icons = {
        chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 18.75 3.75 21v-4.5A8.25 8.25 0 1 1 12 20.25a8.2 8.2 0 0 1-4.5-1.5Z"/></svg>',
        reasoning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 4.5a3 3 0 0 1 4.5 0 3 3 0 0 1 3 3 3 3 0 0 1 0 5.25 3 3 0 0 1-1.5 5.25 3 3 0 0 1-4.5 0 3 3 0 0 1-4.5-2.625 3 3 0 0 1 0-5.25 3 3 0 0 1 3-5.25Z"/><path stroke-linecap="round" d="M9 9.25h.01M15 9.25h.01M10 14.5c.6.5 1.25.75 2 .75s1.4-.25 2-.75"/></svg>',
        vision: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12S5.75 6.75 12 6.75 21.75 12 21.75 12 18.25 17.25 12 17.25 2.25 12 2.25 12Z"/><circle cx="12" cy="12" r="2.25"/></svg>',
        code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 8.25-3.75 3.75 3.75 3.75M15.75 8.25l3.75 3.75-3.75 3.75M13.5 5.25l-3 13.5"/></svg>',
        tools: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M14.7 6.3a4.25 4.25 0 0 0-5.64 5.64L3.75 17.25a2.12 2.12 0 1 0 3 3l5.31-5.31a4.25 4.25 0 0 0 5.64-5.64l-2.48 2.48-3.08-.62-.62-3.08 2.48-2.48Z"/></svg>',
        image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3.75" y="4.5" width="16.5" height="15" rx="2.25"/><path stroke-linecap="round" stroke-linejoin="round" d="m5.25 16.5 4.25-4.25 3 3 2-2 4.25 4.25M15.75 9h.01"/></svg>'
      };
      const norm = (value) => String(value || '').trim().toLowerCase();
      const isVisible = (element) => { const style = getComputedStyle(element); const box = element.getBoundingClientRect(); return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0; };
      const addStyle = () => {
        if (document.getElementById('open-webui-model-capability-style')) return;
        const style = document.createElement('style');
        style.id = 'open-webui-model-capability-style';
        style.textContent = '.open-webui-model-capability-row{position:relative!important;min-width:0!important;padding-right:78px!important}.open-webui-model-capabilities{position:absolute;right:7px;top:50%;transform:translateY(-50%);display:inline-flex;align-items:center;justify-content:flex-end;gap:2px;max-width:70px;margin:0;z-index:2;pointer-events:none}.open-webui-model-capability{display:inline-flex;flex:0 0 15px;width:15px;height:15px;align-items:center;justify-content:center;border:1px solid color-mix(in srgb,currentColor 16%,transparent);border-radius:4px;background:color-mix(in srgb,#38bdf8 10%,#111827 72%);color:color-mix(in srgb,#38bdf8 80%,currentColor);box-sizing:border-box}.open-webui-model-capability svg{width:9px;height:9px;display:block}@media(min-width:521px){.open-webui-model-capability-row{padding-right:82px!important}.open-webui-model-capabilities{right:8px;max-width:74px}.open-webui-model-capability{flex-basis:16px;width:16px;height:16px;border-radius:5px}.open-webui-model-capability svg{width:10px;height:10px}}';
        document.head.appendChild(style);
      };
      const has = (model, names) => {
        const raw = model.raw || {};
        const sources = [raw.capabilities, raw.meta && raw.meta.capabilities, raw.info && raw.info.capabilities, raw.info && raw.info.meta && raw.info.meta.capabilities, raw.details && raw.details.capabilities].filter(Boolean);
        return sources.some((source) => Array.isArray(source) ? source.some((item) => names.includes(norm(item))) : source && typeof source === 'object' && names.some((name) => source[name] === true || source[name] === 'true' || source[name] === 1));
      };
      const features = (model) => {
        const value = norm(model.id + ' ' + model.name); const result = [];
        if (has(model, ['reasoning','thinking','reason']) || /(?:deepseek-r1|reasoner|thinking|nemotron|qwen3|gpt-oss)/.test(value)) result.push('reasoning');
        if (has(model, ['vision','image_input','image-input','multimodal']) || /(?:\\bvl\\b|vision|llava|pixtral|moondream|gemma[-: ]?3|qwen[-.: ]?vl)/.test(value)) result.push('vision');
        if (has(model, ['code','coding']) || /(?:coder|code|qwen|gpt-oss|starcoder|codestral)/.test(value)) result.push('code');
        if (has(model, ['tools','tool_calling','function_calling','function-calling'])) result.push('tools');
        if (has(model, ['image_generation','image-generation']) || /(?:flux|stable[- ]?diffusion|sdxl|sd[-_:])/.test(value)) result.push('image');
        return result.length ? result.slice(0, 4) : ['chat'];
      };
      const matching = (element) => {
        const text = norm(element.textContent); if (!text) return null;
        const choices = state.models.map((model) => ({ model, keys: [model.name, model.id].map(norm).filter((entry) => entry.length > 2) })).sort((a, b) => Math.max(...b.keys.map((entry) => entry.length), 0) - Math.max(...a.keys.map((entry) => entry.length), 0));
        const found = choices.find((choice) => choice.keys.some((entry) => text.includes(entry)));
        return found ? found.model : null;
      };
      const paint = () => {
        state.queued = false; if (!state.models.length) return;
        if (Date.now() > state.pickerOpenUntil || !state.pickerTrigger || !state.pickerTrigger.isConnected) return;
        addStyle();
        const rows = [];
        document.querySelectorAll('button,[role="option"],[role="menuitem"]').forEach((element) => { if (!isVisible(element) || element.querySelector('.open-webui-model-capabilities')) return; const model = matching(element); if (model) rows.push({ element, model }); });
        const menuRows = rows.filter(({ element }) => element !== state.pickerTrigger && !state.pickerTrigger.contains(element) && !element.contains(state.pickerTrigger));
        if (new Set(menuRows.map((row) => row.model.id || row.model.name)).size < 2) return;
        menuRows.forEach(({ element, model }) => {
          const values = features(model); const strip = document.createElement('span'); strip.className = 'open-webui-model-capabilities'; strip.setAttribute('aria-label', '模型能力：' + values.map((value) => labels[value]).join('、'));
          values.forEach((value) => { const badge = document.createElement('span'); badge.className = 'open-webui-model-capability'; badge.title = labels[value]; badge.setAttribute('role', 'img'); badge.setAttribute('aria-label', labels[value]); badge.innerHTML = icons[value]; strip.appendChild(badge); });
          // Keep the capability rail outside the model-name span. Appending it
          // to the text wrapper makes the icons overlap truncated names on iPhone.
          element.classList.add('open-webui-model-capability-row');
          element.appendChild(strip);
        });
      };
      const queue = () => { if (state.queued) return; state.queued = true; requestAnimationFrame(paint); };
      const load = async () => {
        try { const response = await fetch(new URL('/api/models', location.origin).toString(), { credentials: 'same-origin' }); const data = await response.json(); const raw = Array.isArray(data) ? data : (data && (data.data || data.models || data.items)); if (Array.isArray(raw) && raw.length) { state.models = raw.filter((model) => model && (model.id || model.name)).map((model) => ({ raw: model, id: String(model.id || ''), name: String(model.name || model.id || '') })); queue(); return; } } catch (_) {}
        state.attempts += 1; if (state.attempts < 8) setTimeout(load, 1600);
      };
      new MutationObserver(queue).observe(document.documentElement, { childList: true, subtree: true });
      document.addEventListener('click', (event) => {
        const target = event.target instanceof Element ? event.target.closest('button,[role="button"],[role="combobox"]') : null;
        if (!target || target.closest('.open-webui-model-capabilities') || !matching(target)) return;
        state.pickerTrigger = target; state.pickerOpenUntil = Date.now() + 2200;
        setTimeout(queue, 70); setTimeout(queue, 260);
      }, true); addStyle(); void load();
    })();
    """#
}
