/* Open WebUI React + SVG architecture renderer. Model output is inert JSON. */
(() => {
  const bridgeKey = '__openWebUIReactSvgDiagramRendererV2'
  let bootAttempts = 0
  const boot = () => {
    if (window[bridgeKey]) return
    const React = window.React
    const ReactDOM = window.ReactDOM
    if (!React || !ReactDOM?.createRoot) {
      bootAttempts += 1
      if (bootAttempts < 80) window.setTimeout(boot, 125)
      return
    }
    window[bridgeKey] = true

    const h = React.createElement
    const MAX_NODES = 12
    const MAX_EDGES = 18
    const MAX_GROUPS = 6
    const NODE_TYPES = new Set(['client', 'switch', 'router', 'firewall', 'server', 'gpu', 'nic', 'storage', 'cloud', 'service', 'database', 'default'])
    const P = { canvas: '#0B0F17', text: '#F8FAFC', muted: '#94A3B8', faint: '#64748B', network: '#38BDF8', active: '#22C55E', remote: '#F59E0B', blocked: '#EF4444', border: '#334155' }
    const tones = {
      default: { line: P.muted, fill: '#182334', label: '一般元件' },
      network: { line: P.network, fill: '#10283A', label: '網路／資訊' },
      active: { line: P.active, fill: '#123126', label: '啟用資料流' },
      remote: { line: P.remote, fill: '#36270F', label: '遠端／警示' },
      blocked: { line: P.blocked, fill: '#351519', label: '安全邊界' }
    }
    const clean = (value, max = 72) => String(value || '').replace(/[\u0000-\u001F\u007F]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max)
    const safeTone = (tone) => tones[tone] ? tone : 'default'
    const safeType = (type) => NODE_TYPES.has(type) ? type : 'default'
    const makeId = (value, index = 0) => clean(value, 36).replace(/[^a-zA-Z0-9_-]/g, '-') || `node-${index + 1}`

    const normalizeDiagram = (raw) => {
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
      const sourceNodes = Array.isArray(raw.nodes) ? raw.nodes.slice(0, MAX_NODES) : []
      if (sourceNodes.length < 2) return null
      const used = new Set()
      const nodes = sourceNodes.map((node, index) => {
        let id = makeId(node?.id || node?.label, index)
        while (used.has(id)) id = `${id}-${index + 1}`
        used.add(id)
        return {
          id, label: clean(node?.label, 34) || `節點 ${index + 1}`,
          detail: clean(node?.detail || node?.caption, 52),
          level: Math.max(0, Math.min(8, Number.isFinite(Number(node?.level)) ? Math.round(Number(node.level)) : index)),
          tone: safeTone(node?.tone), type: safeType(node?.type), group: makeId(node?.group || '', index)
        }
      })
      const ids = new Set(nodes.map((node) => node.id))
      const groups = (Array.isArray(raw.groups) ? raw.groups : []).slice(0, MAX_GROUPS).flatMap((group, index) => {
        const id = makeId(group?.id || group?.label, index)
        const nodeIds = [...new Set([...(Array.isArray(group?.nodeIds) ? group.nodeIds.map((value) => makeId(value)) : []), ...nodes.filter((node) => node.group === id).map((node) => node.id)])].filter((nodeId) => ids.has(nodeId))
        return nodeIds.length ? [{ id, label: clean(group?.label, 30) || '架構區域', tone: safeTone(group?.tone), nodeIds }] : []
      })
      const groupIds = new Set(groups.map((group) => group.id))
      nodes.forEach((node) => { if (!groupIds.has(node.group)) node.group = '' })
      const edges = (Array.isArray(raw.edges) ? raw.edges : []).slice(0, MAX_EDGES).flatMap((edge, index) => {
        const from = makeId(edge?.from, index)
        const to = makeId(edge?.to, index + 1)
        if (!ids.has(from) || !ids.has(to) || from === to) return []
        return [{ id: `${from}-${to}-${index}`, from, to, label: clean(edge?.label, 36), tone: safeTone(edge?.tone || 'network'), dashed: edge?.dashed === true, bidirectional: edge?.bidirectional === true }]
      })
      return {
        title: clean(raw.title, 56) || '技術架構圖', subtitle: clean(raw.subtitle || raw.summary, 110),
        kind: ['topology', 'flow', 'layers', 'comparison'].includes(raw.kind) ? raw.kind : 'topology',
        direction: raw.direction === 'LR' ? 'LR' : 'TB', nodes, edges, groups
      }
    }

    const wrap = (value, maxChars, maxLines = 2) => {
      const text = clean(value, 110)
      if (!text) return []
      const lines = []
      let current = ''
      for (const glyph of text) {
        current += glyph
        if (current.length >= maxChars) { lines.push(current); current = '' }
      }
      if (current) lines.push(current)
      if (lines.length <= maxLines) return lines
      const clipped = lines.slice(0, maxLines)
      clipped[maxLines - 1] = `${clipped[maxLines - 1].slice(0, Math.max(1, maxChars - 1))}…`
      return clipped
    }
    const textLines = (key, x, y, lines, attributes = {}) => h('text', { key, x, y, ...attributes }, lines.map((line, index) => h('tspan', { key: `${key}-${index}`, x, dy: index === 0 ? 0 : '1.24em' }, line)))
    const chunks = (items, size) => { const result = []; for (let i = 0; i < items.length; i += size) result.push(items.slice(i, i + size)); return result }

    const createLayout = (diagram, compact) => {
      const levels = [...new Set(diagram.nodes.map((node) => node.level))].sort((a, b) => a - b)
      const byLevel = new Map(levels.map((level) => [level, diagram.nodes.filter((node) => node.level === level)]))
      const positions = new Map()
      const guides = []
      const nodeHeight = compact ? 94 : 90
      if (compact) {
        const width = 360
        const nodeWidth = 286
        let y = 78
        levels.forEach((level, levelIndex) => {
          const levelNodes = byLevel.get(level) || []
          guides.push({ axis: 'horizontal', value: y - 50, label: `LAYER ${levelIndex + 1}` })
          levelNodes.forEach((node, rowIndex) => positions.set(node.id, { x: width / 2, y: y + rowIndex * 116 }))
          y += Math.max(1, levelNodes.length) * 116 + 48
        })
        return { width, height: Math.max(250, y - 42), nodeWidth, nodeHeight, positions, levels, guides, direction: 'TB', compact }
      }
      if (diagram.direction === 'LR') {
        const nodeWidth = 198
        const columnGap = 246
        const width = Math.max(960, 190 + Math.max(0, levels.length - 1) * columnGap + 190)
        const maxRows = Math.max(...[...byLevel.values()].map((nodes) => nodes.length))
        const height = Math.max(390, 160 + Math.max(0, maxRows - 1) * 124)
        levels.forEach((level, levelIndex) => {
          const levelNodes = byLevel.get(level) || []
          const x = 140 + levelIndex * columnGap
          const startY = height / 2 - Math.max(0, levelNodes.length - 1) * 62
          levelNodes.forEach((node, rowIndex) => positions.set(node.id, { x, y: startY + rowIndex * 124 }))
          guides.push({ axis: 'vertical', value: x, label: `LAYER ${levelIndex + 1}` })
        })
        return { width, height, nodeWidth, nodeHeight, positions, levels, guides, direction: 'LR', compact }
      }
      const width = 960
      const nodeWidth = 220
      let y = 90
      levels.forEach((level, levelIndex) => {
        const rows = chunks(byLevel.get(level) || [], 3)
        guides.push({ axis: 'horizontal', value: y - 58, label: `LAYER ${levelIndex + 1}` })
        rows.forEach((row, rowIndex) => {
          const gap = width / (row.length + 1)
          row.forEach((node, columnIndex) => positions.set(node.id, { x: gap * (columnIndex + 1), y: y + rowIndex * 118 }))
        })
        y += Math.max(1, rows.length) * 118 + 54
      })
      return { width, height: Math.max(390, y - 12), nodeWidth, nodeHeight, positions, levels, guides, direction: 'TB', compact }
    }

    const DeviceIcon = ({ type, x, y, color }) => {
      const a = { fill: 'none', stroke: color, strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }
      const p = []
      if (type === 'switch' || type === 'nic') {
        p.push(h('rect', { key: 'b', x: 2, y: 7, width: 28, height: 18, rx: 4, ...a }))
        ;[7, 13, 19, 25].forEach((cx) => p.push(h('circle', { key: `p${cx}`, cx, cy: 16, r: 1.35, fill: color })))
        if (type === 'nic') p.push(h('path', { key: 'bus', d: 'M8 25v4m5-4v4m5-4v4', ...a }))
      } else if (type === 'router') {
        p.push(h('circle', { key: 'b', cx: 16, cy: 16, r: 13, ...a }), h('path', { key: 'a', d: 'M8 13h15m0 0-4-4m4 4-4 4M24 20H9m0 0 4-4m-4 4 4 4', ...a }))
      } else if (type === 'firewall') {
        p.push(h('path', { key: 's', d: 'M16 3 27 7v8c0 7-4.8 11.8-11 14-6.2-2.2-11-7-11-14V7l11-4Z', ...a }), h('path', { key: 'w', d: 'M8 12h16M8 17h16M12 8v4m8-4v4m-5 0v5m7-5v5m-11 0v5m8-5v5', ...a }))
      } else if (type === 'server') {
        p.push(h('rect', { key: 'b', x: 5, y: 3, width: 22, height: 26, rx: 3, ...a }), h('path', { key: 'r', d: 'M5 11h22M5 20h22', ...a }), h('circle', { key: 'l1', cx: 22, cy: 7, r: 1.2, fill: color }), h('circle', { key: 'l2', cx: 22, cy: 16, r: 1.2, fill: color }), h('circle', { key: 'l3', cx: 22, cy: 25, r: 1.2, fill: color }))
      } else if (type === 'gpu') {
        p.push(h('rect', { key: 'b', x: 3, y: 6, width: 26, height: 20, rx: 3, ...a }), h('circle', { key: 'f1', cx: 11, cy: 16, r: 5, ...a }), h('circle', { key: 'f2', cx: 22, cy: 16, r: 4, ...a }), h('path', { key: 'bus', d: 'M9 26v3m5-3v3m5-3v3', ...a }))
      } else if (type === 'storage' || type === 'database') {
        p.push(h('ellipse', { key: 't', cx: 16, cy: 7, rx: 11, ry: 4, ...a }), h('path', { key: 'b', d: 'M5 7v18c0 2.2 4.9 4 11 4s11-1.8 11-4V7M5 16c0 2.2 4.9 4 11 4s11-1.8 11-4', ...a }))
      } else if (type === 'cloud') {
        p.push(h('path', { key: 'c', d: 'M9 26h15a6 6 0 0 0 1-11.9A9.5 9.5 0 0 0 7 12.5 6.8 6.8 0 0 0 9 26Z', ...a }))
      } else if (type === 'client') {
        p.push(h('rect', { key: 's', x: 3, y: 4, width: 26, height: 19, rx: 3, ...a }), h('path', { key: 'st', d: 'M16 23v5m-7 0h14', ...a }))
      } else if (type === 'service') {
        p.push(h('circle', { key: 'c', cx: 16, cy: 16, r: 5, ...a }), h('path', { key: 'g', d: 'M16 3v5m0 16v5M3 16h5m16 0h5M7 7l3.5 3.5m11 11L25 25M25 7l-3.5 3.5m-11 11L7 25', ...a }))
      } else {
        p.push(h('rect', { key: 'b', x: 4, y: 4, width: 24, height: 24, rx: 6, ...a }), h('path', { key: 'n', d: 'M10 12h12M10 17h12M10 22h7', ...a }))
      }
      return h('g', { transform: `translate(${x} ${y})`, 'aria-hidden': 'true' }, p)
    }

    const groupBounds = (group, layout) => {
      const points = group.nodeIds.map((id) => layout.positions.get(id)).filter(Boolean)
      if (!points.length) return null
      const left = Math.min(...points.map((point) => point.x - layout.nodeWidth / 2)) - 16
      const right = Math.max(...points.map((point) => point.x + layout.nodeWidth / 2)) + 16
      const top = Math.min(...points.map((point) => point.y - layout.nodeHeight / 2)) - 34
      const bottom = Math.max(...points.map((point) => point.y + layout.nodeHeight / 2)) + 16
      return { x: left, y: top, width: right - left, height: bottom - top }
    }

    const Connector = ({ edge, from, to, nodeWidth, nodeHeight, markerPrefix }) => {
      const tone = tones[edge.tone]
      const dx = to.x - from.x
      const dy = to.y - from.y
      const horizontal = Math.abs(dx) > Math.abs(dy) * 1.15
      let startX, startY, endX, endY, path
      if (horizontal) {
        const d = dx >= 0 ? 1 : -1
        startX = from.x + d * nodeWidth / 2; startY = from.y; endX = to.x - d * nodeWidth / 2; endY = to.y
        const mid = (startX + endX) / 2
        path = `M ${startX} ${startY} H ${mid} V ${endY} H ${endX}`
      } else {
        const d = dy >= 0 ? 1 : -1
        startX = from.x; startY = from.y + d * nodeHeight / 2; endX = to.x; endY = to.y - d * nodeHeight / 2
        const mid = (startY + endY) / 2
        path = `M ${startX} ${startY} V ${mid} H ${endX} V ${endY}`
      }
      const labelX = (startX + endX) / 2
      const labelY = (startY + endY) / 2
      const labelWidth = Math.min(184, Math.max(62, edge.label.length * 8 + 20))
      return h('g', { key: edge.id }, [
        h('path', { key: 'line', d: path, fill: 'none', stroke: tone.line, strokeWidth: 2.5, strokeDasharray: edge.dashed ? '8 7' : undefined, markerStart: edge.bidirectional ? `url(#${markerPrefix}-arrow-${edge.tone})` : undefined, markerEnd: `url(#${markerPrefix}-arrow-${edge.tone})`, opacity: 0.95 }),
        edge.label ? h('g', { key: 'label' }, [h('rect', { key: 'back', x: labelX - labelWidth / 2, y: labelY - 13, width: labelWidth, height: 25, rx: 8, fill: P.canvas, stroke: `${tone.line}77` }), h('text', { key: 'text', x: labelX, y: labelY + 4, fill: P.text, fontSize: 11.5, textAnchor: 'middle', fontWeight: 650 }, edge.label)]) : null
      ])
    }

    const NodeCard = ({ node, position, nodeWidth, nodeHeight }) => {
      const tone = tones[node.tone]
      const title = wrap(node.label, nodeWidth > 230 ? 20 : 15, 2)
      const detail = wrap(node.detail, nodeWidth > 230 ? 28 : 19, 1)
      const x = position.x - nodeWidth / 2
      const y = position.y - nodeHeight / 2
      return h('g', { key: node.id, transform: `translate(${x}, ${y})` }, [
        h('rect', { key: 'shadow', x: 3, y: 5, width: nodeWidth, height: nodeHeight, rx: 15, fill: '#020617', opacity: 0.42 }),
        h('rect', { key: 'body', width: nodeWidth, height: nodeHeight, rx: 15, fill: tone.fill, stroke: tone.line, strokeWidth: 1.5 }),
        h('rect', { key: 'accent', x: 0, y: 13, width: 4, height: nodeHeight - 26, rx: 2, fill: tone.line }),
        h('circle', { key: 'icon-bg', cx: 34, cy: nodeHeight / 2, r: 22, fill: P.canvas, stroke: `${tone.line}66` }),
        h(DeviceIcon, { key: 'icon', type: node.type, x: 18, y: nodeHeight / 2 - 16, color: tone.line }),
        textLines('title', 65, title.length > 1 ? 29 : 36, title, { fill: P.text, fontSize: 14.5, fontWeight: 740 }),
        detail.length ? textLines('detail', 65, title.length > 1 ? 68 : 63, detail, { fill: P.muted, fontSize: 11.5, fontWeight: 530 }) : null
      ])
    }

    const useCompact = () => {
      const query = '(max-width: 620px)'
      const [compact, setCompact] = React.useState(() => window.matchMedia?.(query).matches ?? false)
      React.useEffect(() => {
        const media = window.matchMedia?.(query)
        if (!media) return undefined
        const update = () => setCompact(media.matches)
        media.addEventListener?.('change', update)
        return () => media.removeEventListener?.('change', update)
      }, [])
      return compact
    }

    const SvgDiagram = ({ diagram, zoom, compact }) => {
      const layout = createLayout(diagram, compact)
      const markerPrefix = React.useId().replace(/[^a-zA-Z0-9_-]/g, '') || 'owui'
      const indexedNodes = new Map(diagram.nodes.map((node) => [node.id, node]))
      return h('svg', { viewBox: `0 0 ${layout.width} ${layout.height}`, role: 'img', 'aria-label': diagram.title, style: { width: `${zoom}%`, minWidth: `${zoom}%`, height: 'auto', display: 'block', transformOrigin: 'top left' } }, [
        h('defs', { key: 'defs' }, Object.entries(tones).map(([name, tone]) => h('marker', { key: name, id: `${markerPrefix}-arrow-${name}`, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' }, h('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: tone.line })))),
        h('rect', { key: 'canvas', width: layout.width, height: layout.height, rx: 24, fill: P.canvas }),
        ...diagram.groups.map((group) => {
          const bounds = groupBounds(group, layout)
          if (!bounds) return null
          const tone = tones[group.tone]
          return h('g', { key: `group-${group.id}` }, [
            h('rect', { key: 'zone', ...bounds, rx: 20, fill: `${tone.line}0D`, stroke: `${tone.line}66`, strokeWidth: 1.2, strokeDasharray: group.tone === 'blocked' ? '7 6' : undefined }),
            h('rect', { key: 'label-bg', x: bounds.x + 14, y: bounds.y - 1, width: Math.max(76, group.label.length * 12 + 24), height: 24, rx: 8, fill: P.canvas }),
            h('text', { key: 'label', x: bounds.x + 25, y: bounds.y + 16, fill: tone.line, fontSize: 11, fontWeight: 760, letterSpacing: 0.5 }, group.label)
          ])
        }),
        ...layout.guides.map((guide, index) => guide.axis === 'vertical'
          ? h('g', { key: `guide-${index}` }, [h('line', { key: 'line', x1: guide.value, y1: 35, x2: guide.value, y2: layout.height - 28, stroke: P.border, strokeWidth: 1, strokeDasharray: '3 9', opacity: 0.48 }), h('text', { key: 'caption', x: guide.value, y: 24, fill: P.faint, fontSize: 10, fontWeight: 760, textAnchor: 'middle', letterSpacing: 1.2 }, guide.label)])
          : h('g', { key: `guide-${index}` }, [h('line', { key: 'line', x1: 24, y1: guide.value, x2: layout.width - 24, y2: guide.value, stroke: P.border, strokeWidth: 1, strokeDasharray: '3 9', opacity: 0.42 }), h('text', { key: 'caption', x: 30, y: guide.value + 14, fill: P.faint, fontSize: 10, fontWeight: 760, letterSpacing: 1.2 }, guide.label)])),
        ...diagram.edges.map((edge) => {
          const fromNode = indexedNodes.get(edge.from)
          const toNode = indexedNodes.get(edge.to)
          if (!fromNode || !toNode) return null
          return h(Connector, { key: edge.id, edge, from: layout.positions.get(fromNode.id), to: layout.positions.get(toNode.id), nodeWidth: layout.nodeWidth, nodeHeight: layout.nodeHeight, markerPrefix })
        }),
        ...diagram.nodes.map((node) => h(NodeCard, { key: node.id, node, position: layout.positions.get(node.id), nodeWidth: layout.nodeWidth, nodeHeight: layout.nodeHeight }))
      ])
    }

    const DiagramCard = ({ diagram }) => {
      const compact = useCompact()
      const [zoom, setZoom] = React.useState(100)
      React.useEffect(() => setZoom(100), [compact])
      const legend = ['network', 'active', 'remote', 'blocked'].filter((tone) => diagram.edges.some((edge) => edge.tone === tone) || diagram.nodes.some((node) => node.tone === tone) || diagram.groups.some((group) => group.tone === tone))
      return h('section', { className: 'owui-svg-diagram', 'data-kind': diagram.kind }, [
        h('header', { key: 'header', className: 'owui-svg-diagram__header' }, [
          h('div', { key: 'headings' }, [h('p', { key: 'eyebrow', className: 'owui-svg-diagram__eyebrow' }, 'VISUAL ARCHITECTURE'), h('h3', { key: 'title', className: 'owui-svg-diagram__title' }, diagram.title), diagram.subtitle ? h('p', { key: 'subtitle', className: 'owui-svg-diagram__subtitle' }, diagram.subtitle) : null]),
          h('div', { key: 'controls', className: 'owui-svg-diagram__controls', role: 'group', 'aria-label': '圖表縮放' }, [h('button', { key: 'out', type: 'button', title: '縮小圖表', disabled: zoom <= 80, onClick: () => setZoom((value) => Math.max(80, value - 10)) }, '−'), h('span', { key: 'value' }, `${zoom}%`), h('button', { key: 'in', type: 'button', title: '放大圖表', disabled: zoom >= 140, onClick: () => setZoom((value) => Math.min(140, value + 10)) }, '+')])
        ]),
        h('div', { key: 'viewport', className: 'owui-svg-diagram__viewport' }, h(SvgDiagram, { diagram, zoom, compact })),
        legend.length ? h('footer', { key: 'legend', className: 'owui-svg-diagram__legend' }, legend.map((tone) => h('span', { key: tone }, [h('i', { key: 'dot', style: { backgroundColor: tones[tone].line } }), tones[tone].label]))) : null
      ])
    }

    const css = `
      .owui-svg-diagram{box-sizing:border-box;width:100%;margin:18px 0 22px;overflow:hidden;border:1px solid #334155;border-radius:20px;background:#0B0F17;color:#F8FAFC;box-shadow:0 16px 38px rgba(2,6,23,.32);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.owui-svg-diagram *{box-sizing:border-box}.owui-svg-diagram__header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:19px 20px 15px;border-bottom:1px solid rgba(148,163,184,.18);background:#111827}.owui-svg-diagram__eyebrow{margin:0 0 6px;color:#38BDF8;font-size:10px;font-weight:800;letter-spacing:.16em}.owui-svg-diagram__title{margin:0;color:#F8FAFC;font-size:clamp(17px,3vw,22px);font-weight:750;line-height:1.25}.owui-svg-diagram__subtitle{margin:7px 0 0;color:#94A3B8;font-size:13px;line-height:1.5}.owui-svg-diagram__controls{display:flex;align-items:center;gap:6px;flex:none;padding:3px;border:1px solid rgba(148,163,184,.22);border-radius:11px;background:#0B0F17}.owui-svg-diagram__controls button{width:30px;height:30px;border:0;border-radius:8px;background:transparent;color:#E2E8F0;font-size:20px;cursor:pointer}.owui-svg-diagram__controls button:hover:not(:disabled){background:#334155}.owui-svg-diagram__controls button:disabled{opacity:.35}.owui-svg-diagram__controls span{min-width:37px;color:#94A3B8;font-size:11px;font-weight:700;text-align:center}.owui-svg-diagram__viewport{overflow:auto;padding:16px;background:#0B0F17}.owui-svg-diagram__viewport::-webkit-scrollbar{width:7px;height:7px}.owui-svg-diagram__viewport::-webkit-scrollbar-thumb{border-radius:99px;background:#334155}.owui-svg-diagram__legend{display:flex;flex-wrap:wrap;gap:10px 14px;padding:13px 20px 15px;border-top:1px solid rgba(148,163,184,.15);color:#CBD5E1;font-size:11px;font-weight:650}.owui-svg-diagram__legend span{display:inline-flex;align-items:center;gap:6px}.owui-svg-diagram__legend i{width:8px;height:8px;border-radius:50%}@media(max-width:620px){.owui-svg-diagram{margin:14px 0 18px;border-radius:16px}.owui-svg-diagram__header{padding:15px;gap:9px}.owui-svg-diagram__viewport{padding:8px 6px 10px}.owui-svg-diagram__subtitle{font-size:12px}.owui-svg-diagram__legend{padding:11px 15px 13px}.owui-svg-diagram__controls{gap:2px}.owui-svg-diagram__controls button{width:28px;height:28px}.owui-svg-diagram__controls span{display:none}}@media(prefers-reduced-motion:reduce){.owui-svg-diagram *{transition:none!important}}
    `

    const attach = (source, diagram) => {
      const host = document.createElement('div')
      host.className = 'openwebui-react-svg-diagram-host'
      host.setAttribute('data-openwebui-diagram', 'rendered')
      const shadow = host.attachShadow({ mode: 'open' })
      const style = document.createElement('style')
      style.textContent = css
      shadow.appendChild(style)
      const root = document.createElement('div')
      shadow.appendChild(root)
      ReactDOM.createRoot(root).render(h(DiagramCard, { diagram }))
      source.before(host)
      source.hidden = true
      source.dataset.openwebuiDiagramRendered = 'true'
    }
    const parseDiagramCandidate = (candidate) => {
      let payload = String(candidate.textContent || '').trim().replace(/^\s*(?:openwebui-diagram|owui-diagram)\s*/i, '')
      if (!payload.startsWith('{') || !payload.endsWith('}')) return null
      const raw = JSON.parse(payload)
      if (!raw || typeof raw !== 'object' || Array.isArray(raw) || !Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) return null
      return normalizeDiagram(raw)
    }
    const findLanguageShell = (element) => {
      let current = element
      while (current && current !== document.body) {
        if (current.tagName === 'DIV' && [...current.classList].some((name) => name.startsWith('language-'))) return current
        current = current.parentElement
      }
      return null
    }
    const scan = () => {
      document.querySelectorAll('pre:not([data-openwebui-diagram-rendered])').forEach((pre) => {
        if (pre.closest('[data-openwebui-diagram-rendered]')) return
        const candidate = pre.querySelector('code') || pre
        try { const diagram = parseDiagramCandidate(candidate); if (diagram) attach(findLanguageShell(candidate)?.parentElement || pre, diagram) } catch {}
      })
      document.querySelectorAll('.cm-content').forEach((editor) => {
        if (editor.closest('[data-openwebui-diagram-rendered]')) return
        try { const diagram = parseDiagramCandidate(editor); if (!diagram) return; const shell = findLanguageShell(editor); const source = shell?.parentElement || shell || editor.parentElement; if (source) attach(source, diagram) } catch {}
      })
    }
    let queued = false
    const schedule = () => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; scan() }) }
    const start = () => { scan(); new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true, characterData: true }) }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true }); else start()
  }
  boot()
})()
