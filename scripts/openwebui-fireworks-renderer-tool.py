"""
title: Fireworks 技術圖表與統計樣板 Renderer
description: 以 Fireworks 產生技術架構圖；以可重用 SVG 樣板產生比較、趨勢、組成、分佈及時程統計成品。
version: 6.2.0
requirements: resvg-py==0.5.0
"""

from __future__ import annotations

import asyncio
import csv
from datetime import date, timedelta
import html
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from functools import lru_cache


class Tools:
    """Native-mode renderer: it exposes progress as statuses and returns only a finished artifact."""

    _SAFE_ID = re.compile(r"[^a-zA-Z0-9_-]+")
    _STYLE_BY_FAMILY = {
        "network": 3,
        "rdma": 3,
        "cloud": 6,
        "workflow": 6,
        "api": 6,
        "software": 6,
        "hardware": 3,
        "clean": 4,
    }
    _TONE_COLORS = {
        "default": ("#10283A", "#94A3B8"),
        "network": ("#0A4B78", "#38BDF8"),
        "active": ("#123B2B", "#22C55E"),
        "remote": ("#3D2B12", "#F59E0B"),
        "blocked": ("#401820", "#FB7185"),
    }
    _LINE_COLORS = {"default": "#A0ACBA", "network": "#3478F6", "active": "#19B5A5", "remote": "#E8B760", "blocked": "#F07178"}
    _SWITCH_ICONS = {"switch", "rdma-switch", "aggregation-switch"}

    @classmethod
    def _icon_catalog(cls) -> dict:
        paths = [Path(__file__).resolve().parents[1] / "resources/architecture-icon-pack/manifest.json"]
        try:
            paths.append(cls._runtime_root() / "assets/icons/technical/manifest.json")
        except RuntimeError:
            pass
        for path in paths:
            if path.is_file():
                catalog = dict(cls._read_icon_file(str(path), path.stat().st_mtime_ns))
                for extra in (path.parent/'hardware.json', path.parent/'extended/catalog.json'):
                    if extra.is_file():
                        catalog.update(cls._read_icon_file(str(extra), extra.stat().st_mtime_ns))
                return catalog
        raise RuntimeError("架構圖示庫尚未安裝")

    @staticmethod
    @lru_cache(maxsize=12)
    def _read_icon_file(path, modified):
        return {item['id']:item for item in json.loads(Path(path).read_text())["icons"]}

    @staticmethod
    def _brand_icon(raw, catalog):
        text = " ".join(str(raw.get(k) or "") for k in ("brand", "label", "detail")).lower()
        brands = {'open webui':'openwebui','openwebui':'openwebui','nvidia':'nvidia','intel':'intel','asus':'asus','amd':'amd',
            'ollama':'ollama','qwen':'qwen','deepseek':'deepseek','gemini':'gemini','openai':'openai','claude':'claude',
            'tailscale':'tailscale','zerotier':'zerotier','docker':'docker','kubernetes':'kubernetes','proxmox':'proxmox','truenas':'truenas','synology':'synology'}
        for alias, slug in brands.items():
            if re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z])', text):
                for provider in ('lobe','simple','dashboard'):
                    for suffix in ('-color',''):
                        key=provider+':'+slug+suffix
                        if key in catalog:
                            return key
        return ''

    @classmethod
    def _pick_icon(cls, raw: dict, catalog: dict) -> str:
        explicit = str(raw.get("icon") or raw.get("icon_id") or "").lower()
        if explicit in catalog:
            return explicit
        label=str(raw.get('label') or '').lower()
        # The equipment's name outranks a component mentioned in its detail.
        # "SFP28 Switch" is not an SFP cage; "GPU Node / RDMA NIC" is a host.
        if re.search(r'switch|交換[器機]',label):
            return 'hardware:rdma-switch' if re.search(r'rdma|25g|50g|100g',label) else 'hardware:desktop-switch'
        if re.search(r'workstation|工作站|gpu[ _-]*(?:node|host)|運算節點|計算節點',label):
            return 'hardware:ai-workstation'
        text = " ".join(str(raw.get(k) or "") for k in ("label", "detail", "type")).lower()
        matches = []
        for icon_id, item in catalog.items():
            # Thousands of provider glyphs are searchable/explicit, not
            # thousands of ambiguous regexes in every node's auto-matcher.
            if item.get('provider') in {'lucide','lobe','simple','dashboard'}:
                continue
            for alias in [icon_id, *item.get("aliases", [])]:
                alias = alias.lower()
                pattern = re.escape(alias) if re.search(r"[^\x00-\x7f]", alias) else r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
                if re.search(pattern, text):
                    matches.append((len(alias)+(100 if icon_id.startswith('hardware:') else 0), icon_id))
        physical = max(matches)[1] if matches else ''
        if physical and (physical.startswith('hardware:') or physical in {'router','switch','rdma-switch','aggregation-switch','nas','gpu','network-card','mini-pc','workstation','desktop','server','access-point','memory','ssd','disk'}):
            return physical
        return cls._brand_icon(raw,catalog) or physical or "app"

    @staticmethod
    def _glyph(item, color='#F4F6F8', prefix='glyph'):
        """Only our pre-sanitized local catalog supplies vectors; no model SVG."""
        defaults=item.get('defaults') or {'fill':'none','stroke':'currentColor','stroke-width':'1.8','stroke-linecap':'round','stroke-linejoin':'round'}
        root=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg" viewBox="'+item.get('viewBox','0 0 48 48')+'">'+item['body']+'</svg>')
        root.set('color',color)
        for key,value in defaults.items():
            root.set(key,value.replace('currentColor',color))
        if item.get('provider')=='lucide' or item['id'].startswith('hardware:'):
            root.set('stroke-width',str(float(item.get('viewBox','0 0 48 48').split()[2])/48*1.8))
        for child in root.iter():
            for key,value in list(child.attrib.items()):
                if key=='id':
                    child.set(key,prefix+'-'+value)
                elif key.rsplit('}',1)[-1]=='href' and value.startswith('#'):
                    child.set(key,'#'+prefix+'-'+value[1:])
                else:
                    child.set(key,re.sub(r'url\(#([^)]+)\)',lambda m:'url(#'+prefix+'-'+m[1]+')',value).replace('currentColor',color))
        return root

    @staticmethod
    def _brand_palette(item):
        # Preserve upstream colors; white-only dark variants need a dark
        # plate, not white-on-white. Other marks use a neutral light plate.
        source=item['body']+' '+json.dumps(item.get('defaults',{}))
        colors=re.findall(r'#[0-9a-fA-F]{3,8}\b',source)
        rgb=[]
        paints=re.findall(r'(?:fill|stroke|stop-color)=["\']([^"\']+)',item['body'])+list(item.get('defaults',{}).values())
        for paint in paints:
            if paint.lower() in {'white','whitesmoke','ivory'}: rgb.append([1,1,1])
            if paint.lower()=='black': rgb.append([0,0,0])
        for color in colors:
            value=color[1:]
            if len(value)==3: value=''.join(c*2 for c in value)
            if len(value) not in {6,8}: continue
            rgb.append([int(value[i:i+2],16)/255 for i in (0,2,4)])
        bright=rgb and all(.2126*r+.7152*g+.0722*b>.78 for r,g,b in rgb)
        return ('#172235','#F8FAFC') if bright else ('#F8FAFC','#172235')

    async def search_diagram_assets(self, query: str, limit: int = 8) -> str:
        """搜尋伺服器本機圖庫與構圖模板。query 可用中文設備類別、品牌英文或命名空間，例如 NAS、GPU、ollama、qwen、lucide:router、hardware:pcie-nic。只回傳可傳給 nodes[].icon 的 ID、來源與授權，不回 SVG 程式碼。四套圖庫為 lucide/lobe/dashboard/simple；網通硬體用 hardware 命名空間。layout 模板有 layered/star/dual_compute/rack/dataflow/ecosystem；關係與埠數不得為排版而編造。"""
        query=self._clean(query,120).lower()
        limit=max(1,min(20,int(limit)))
        catalog=self._icon_catalog()
        terms=query.split()
        ranked=[]
        for id,item in catalog.items():
            hay=' '.join([id,item['label'],*item.get('aliases',[])]).lower()
            if id==query:
                score=1000
            elif query and query in hay:
                score=150-len(id)/100
            elif terms and all(t in hay for t in terms):
                score=50-len(id)/100
            else:
                continue
            ranked.append((score,id,item))
        ranked.sort(key=lambda item:(-item[0],item[1]))
        matches=[{'id':id,'label':item['label'],'provider':item.get('provider','local'),
            'license':item.get('license','MIT'),'source':item.get('source','Original local generic equipment')} for _,id,item in ranked[:limit]]
        return json.dumps({'matches':matches,'total_matches':len(ranked),'catalog_size':len(catalog),
            'layouts':['layered','star','dual_compute','rack','dataflow','ecosystem'],
            'note':'品牌標誌僅識別用途；不代表背書或硬體規格。'},ensure_ascii=False)

    @staticmethod
    def _wrap(text: str, units: float) -> list[str]:
        lines, line, width = [], "", 0.0
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*|[^\x00-\xff]|\s+|.", text)
        pieces = []
        for token in tokens:
            pieces.extend(list(token) if sum(Tools._char_units(c) for c in token)>units else [token])
        for char in pieces:
            step = sum(Tools._char_units(c) for c in char)
            if line and width + step > units:
                lines.append(line.strip())
                line, width = "", 0.0
            line += char
            width += step
        if line.strip():
            lines.append(line.strip())
        return lines

    @staticmethod
    def _char_units(char):
        return 1.0 if ord(char)>255 or char in 'MW@#%&' else .32 if char.isspace() or char in '.,:;!|il' else .72 if char.isupper() else .6

    @classmethod
    def _port_geometry(cls,node):
        ports=node.get('port_groups') or []
        if not ports:return 0,0,0,[]
        total=sum(p['count'] for p in ports)
        columns=min(total,max(1,int((node['width']-35)/15)))
        rows=math.ceil(total/columns)
        summary=' · '.join(str(p['count'])+' x '+p['label'] for p in ports)
        lines=cls._wrap(summary,(node['width']-32)/13)
        return 20*rows+17*len(lines)+14,columns,rows,lines

    @classmethod
    def _node_height(cls,node):
        available=node['width']-(132 if node.get('brand_icon') and node['brand_icon']!=node['icon'] else 102)
        height=38+23*len(cls._wrap(node['label'],available/18))+19*len(cls._wrap(node['sublabel'],available/13.5))
        return math.ceil(max(112,height+cls._port_geometry(node)[0])/36)*36

    @classmethod
    def _decorate_svg(cls, source: str, diagram: dict) -> str:
        """Add trusted vector glyphs, panels and semantic line styles to Fireworks geometry."""
        ns = "http://www.w3.org/2000/svg"
        ET.register_namespace("", ns)
        root = ET.fromstring(source)
        catalog = cls._icon_catalog()
        tag = lambda name: "{" + ns + "}" + name
        def element(parent, name, **attrs):
            return ET.SubElement(parent, tag(name), {k.replace("_", "-"): str(v) for k, v in attrs.items()})
        def text(parent, x, y, value, size=17, color="#F4F6F8", weight=500):
            item = element(parent, "text", x=x, y=y, fill=color, font_size=size, font_weight=weight)
            item.text = value
            return item
        defs = root.find(tag("defs"))
        for tone, color in cls._LINE_COLORS.items():
            marker = element(defs, "marker", id="tech-arrow-" + tone, viewBox="0 0 10 10", refX=9, refY=5, markerWidth=6, markerHeight=6, orient="auto-start-reverse")
            element(marker, "path", d="M1 1L9 5L1 9Z", fill=color)
        stylesheet = root.find(".//" + tag("style"))
        stylesheet.text = (stylesheet.text or "") + "\n.title{fill:#F4F6F8;font-size:30px}.subtitle{font-size:14.5px}.subtitle,.footnote{fill:#99A7B5}.section{fill:#CED7E0}.arrow-label{fill:#E4E9EF}\n"
        used={n['icon'] for n in diagram['nodes']}|{n['brand_icon'] for n in diagram['nodes'] if n.get('brand_icon') and catalog[n['icon']].get('category')!='brand'}
        metadata=element(root,'desc',id='icon-provenance')
        metadata.text=json.dumps([{'id':id,'provider':catalog[id].get('provider','local'),
            'source':catalog[id].get('source','Original local generic equipment'),'license':catalog[id].get('license','MIT'),
            'sha256':catalog[id].get('sha256','')} for id in sorted(used)],ensure_ascii=False)
        # Keep required copyright/permission notices in the editable SVG.
        for provider in {catalog[id].get('provider') for id in used}-{None}:
            for base in (Path(__file__).resolve().parents[1]/'resources/architecture-icon-pack',cls._runtime_root()/'assets/icons/technical'):
                folder=base/'extended/licenses'/provider
                if folder.is_dir():
                    notice=element(root,'desc',id='license-'+provider)
                    notice.text='\n\n'.join(p.read_text() for p in sorted(folder.iterdir()) if p.is_file())
                    break
        title_lines = cls._wrap(diagram["title"], (diagram["width"]-88)/30)
        subtitle_lines = cls._wrap(diagram["subtitle"], (diagram["width"]-88)/14.5)
        for item in root.findall('.//' + tag("text")):
            if item.get("class") in {"title", "subtitle"}:
                is_title = item.get("class") == "title"
                start_y = 62 if is_title else 64+len(title_lines)*34
                item.set("x", str(diagram["width"]/2))
                item.set("y", str(start_y))
                item.set("text-anchor", "middle")
                item.text = None
                for child in list(item): item.remove(child)
                for index, line in enumerate(title_lines if is_title else subtitle_lines):
                    element(item, "tspan", x=diagram["width"]/2, y=start_y+index*(34 if is_title else 22)).text = line
        for line in root.findall(tag("line")):
            if line.get("y1") == line.get("y2") and float(line.get("y1", "999")) < 130:
                root.remove(line)
        for background in root.findall('.//*[@data-graph-role="background"]'):
            background.set("fill", "#0E1012")
        for label in root.findall('.//*[@data-graph-role="label"]'):
            for rect in label.findall('.//' + tag("rect")):
                rect.set("fill", "#142733")
                rect.set("stroke", "#29495F")
            for item in label.findall('.//' + tag("text")):
                item.set("fill", "#E4E9EF")
        edge_map = {e["id"]: e for e in diagram["arrows"]}
        for path in root.findall('.//*[@data-graph-role="edge"]'):
            edge = edge_map.get(path.get("data-edge-id"), {})
            tone = edge.get("tone", "network")
            path.set("stroke", cls._LINE_COLORS[tone])
            path.set("stroke-width", "3")
            path.attrib.pop("marker-start", None)
            path.attrib.pop("marker-end", None)
            path.attrib.pop("stroke-dasharray", None)
            if edge.get("dashed"):
                path.set("stroke-dasharray", "8 6")
            if edge.get("direction") in {"forward", "both"}:
                path.set("marker-end", f"url(#tech-arrow-{tone})")
            if edge.get("direction") == "both":
                path.set("marker-start", f"url(#tech-arrow-{tone})")
        node_map = {n["id"]: n for n in diagram["nodes"]}
        for group in root.findall('.//*[@data-graph-role="node"]'):
            node = node_map[group.get("data-node-id")]
            for child in list(group):
                group.remove(child)
            x, y, w, h = (node[k] for k in ("x", "y", "width", "height"))
            group.set("data-icon-id", node["icon"])
            group.set('data-origin-node-id',node.get('origin_id',node['id']))
            group.set('data-logical-group',node.get('group',''))
            group.set("data-icon-pack", catalog[node['icon']].get('provider','local-architecture-v2'))
            element(group, "rect", x=x, y=y, width=w, height=h, rx=11, fill="#14191F", stroke="#3A4652", stroke_width=1.4)
            item=catalog[node['icon']]
            brand=item.get('category')=='brand'
            plate,ink=cls._brand_palette(item) if brand else ('','#F4F6F8')
            if brand:
                plate_shape=element(group,'rect',x=x+16,y=y+20,width=56,height=56,rx=9,fill=plate,stroke='none')
            glyph = cls._glyph(item, ink, 'node-'+node['id'])
            glyph.set('x',str(x+20));glyph.set('y',str(y+24))
            glyph.set('width','48');glyph.set('height','48')
            glyph.set("data-graph-role", "decoration")
            group.append(glyph)
            badge=node.get('brand_icon') if not brand else ''
            if badge and badge!=node['icon']:
                badge_plate,badge_ink=cls._brand_palette(catalog[badge])
                element(group,'rect',x=x+w-40,y=y+10,width=28,height=28,rx=6,fill=badge_plate,stroke='none')
                brand_glyph=cls._glyph(catalog[badge],badge_ink,'badge-'+node['id'])
                brand_glyph.attrib.update(x=str(x+w-36),y=str(y+14),width='20',height='20')
                brand_glyph.set('data-graph-role','decoration')
                group.append(brand_glyph)
            available=w-(132 if badge and badge!=node['icon'] else 102)
            title_lines = cls._wrap(node["label"], available/18)
            detail_lines = cls._wrap(node["sublabel"], available/13.5)
            panel_height,columns,port_rows,summary_lines=cls._port_geometry(node)
            content_height=h-panel_height
            if content_height < 38+len(title_lines)*23+len(detail_lines)*19:
                raise ValueError('Final wrapped text does not fit its node')
            glyph.set('y',str(y+(content_height-48)/2))
            if brand:
                plate_shape.set('y',str(y+(content_height-48)/2-4))
            cursor = y+(content_height-len(title_lines)*23-len(detail_lines)*19)/2+18
            for line in title_lines:
                text(group, x+84, cursor, line, 18, weight=600)
                cursor += 23
            for line in detail_lines:
                text(group, x+84, cursor+1, line, 13.5, "#A5B2BF")
                cursor += 19
            if node["port_groups"]:
                ports = node["port_groups"]
                total = sum(p["count"] for p in ports)
                pw=min(20,(w-40-(columns-1)*5)/columns)
                py=y+content_height+8
                index=0
                for port in ports:
                    for _ in range(port["count"]):
                        col=index%columns;row=index//columns
                        count=min(columns,total-row*columns)
                        px=x+(w-(count*pw+(count-1)*5))/2+col*(pw+5)
                        element(group, "rect", x=round(px,2),y=py+row*20,width=round(pw,2),height=13,rx=2,fill=cls._LINE_COLORS[port['tone']])
                        index+=1
                for index,line in enumerate(summary_lines):
                    t=text(group,x+w/2,py+port_rows*20+14+index*17,line,13,'#A5B2BF');t.set('text-anchor','middle')
        if diagram.get('layout')=='rack':
            slots=[n for n in diagram['nodes'] if n['group']=='rack']
            rail=element(root,'g',data_graph_role='decoration')
            top=min(n['y'] for n in slots);bottom=max(n['y']+n['height'] for n in slots)
            for x in (min(n['x'] for n in slots)-12,max(n['x']+n['width'] for n in slots)+7):
                element(rail,'rect',x=x,y=top,width=5,height=bottom-top,rx=2,fill='#475569')
                for y in range(int(top+12),int(bottom-10),36):
                    element(rail,'circle',cx=x+2.5,cy=y,r=1.3,fill='#0B0F17')
        return ET.tostring(root, encoding="unicode")

    @staticmethod
    def _clean(value: Any, limit: int = 90) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]

    @classmethod
    def _id(cls, value: Any, index: int) -> str:
        raw=cls._clean(value,48)
        candidate=cls._SAFE_ID.sub('-',raw).strip('-')
        # A CJK ID must resolve identically from nodes and edges, regardless
        # of their list positions. Also avoid "a b"/"a-b" collisions.
        if raw and candidate!=raw:
            return (candidate or 'node')+'-'+hashlib.sha256(raw.encode()).hexdigest()[:10]
        return candidate or f'node-{index+1}'

    @staticmethod
    async def _status(emitter, description: str, done: bool = False, hidden: bool = False) -> None:
        if emitter:
            try:await emitter({"type": "status", "data": {"description": description, "done": done, "hidden": hidden}})
            except Exception:pass  # A disconnected UI does not invalidate a real artifact.

    @staticmethod
    def _runtime_root() -> Path:
        candidates = [
            os.environ.get("OPENWEBUI_FIREWORKS_SKILL_ROOT", ""),
            str(Path.home() / "Library/Application Support/OpenWebUIRuntime/skills/fireworks-tech-graph"),
            str(Path.home() / "Library/Application Support/Open WebUI/skills/fireworks-tech-graph"),
        ]
        try:
            from open_webui.env import DATA_DIR
            candidates[1:1]=[str(Path(DATA_DIR)/'skills/fireworks-tech-graph'),str(Path(DATA_DIR).parent/'skills/fireworks-tech-graph')]
        except ImportError:
            pass
        if os.environ.get("APPDATA"):
            candidates.append(str(Path(os.environ["APPDATA"]) / "Open WebUI/skills/fireworks-tech-graph"))
        if os.environ.get("LOCALAPPDATA"):
            candidates.append(str(Path(os.environ["LOCALAPPDATA"]) / "OpenWebUIRuntime/skills/fireworks-tech-graph"))
        for candidate in candidates:
            root = Path(candidate).expanduser()
            if (root / "scripts/fireworks.py").is_file():
                return root
        raise RuntimeError("找不到 Fireworks Tech Graph runtime")

    @staticmethod
    def _static_output_dir() -> Path:
        configured = os.environ.get("OPENWEBUI_FIREWORKS_OUTPUT_DIR")
        if configured:
            output = Path(configured).expanduser()
        else:
            import open_webui

            output = Path(open_webui.__file__).resolve().parent / "static/openwebui-generated/fireworks"
        output.mkdir(parents=True, exist_ok=True)
        return output

    @classmethod
    def _layout(cls, title: str, subtitle: str, nodes: list[dict], edges: list[dict], groups: list[dict], style: int, layout: str = 'layered') -> dict:
        if len(nodes) < 2:
            raise ValueError("架構圖至少需要兩個節點")
        if len(nodes) > 14 or len(edges) > 22:
            raise ValueError("圖表過於複雜；請控制在 14 個節點與 22 條連線內")

        normalized_nodes: list[dict] = []
        catalog = cls._icon_catalog()
        ids: set[str] = set()
        for index, raw in enumerate(nodes):
            node_id = cls._id(raw.get("id") or raw.get("label"), index)
            if node_id in ids:
                raise ValueError('節點 id 重複，無法判定連線；請使用唯一 id')
            ids.add(node_id)
            tone = str(raw.get("tone") or "default").lower()
            if tone not in cls._TONE_COLORS:
                tone = "default"
            normalized_nodes.append({
                "id": node_id,
                "label": cls._clean(raw.get("label"), 42) or f"節點 {index + 1}",
                "sublabel": cls._clean(raw.get("detail") or raw.get("sublabel"), 56),
                "group": cls._clean(raw.get("group"), 42),
                "level": max(0, min(5, int(raw.get("level", 0) or 0))),
                "tone": tone,
                "kind": "rect",
                "icon": cls._pick_icon(raw, catalog),
                "brand_icon": cls._brand_icon(raw,catalog),
                "port_groups": [],
            })
            for port in raw.get("port_groups") or []:
                count = int(port.get("count", 0))
                if not 1 <= count <= 24 or len(normalized_nodes[-1]["port_groups"]) >= 4:
                    raise ValueError("連接埠群組須有 1–24 個埠，最多四組")
                normalized_nodes[-1]["port_groups"].append({"count":count, "label":cls._clean(port.get("label"), 16), "tone":port.get("tone") if port.get("tone") in cls._LINE_COLORS else "network"})
            if sum(p["count"] for p in normalized_nodes[-1]["port_groups"]) > 48:
                raise ValueError("單一設備連接埠示意上限為 48")

        by_level: dict[int, list[dict]] = {}
        for node in normalized_nodes:
            by_level.setdefault(node["level"], []).append(node)
        levels = sorted(by_level)
        width = max(1080, 120 + max(len(row) for row in by_level.values()) * 360)
        y = math.ceil(max(160, 90+len(cls._wrap(title, (width-88)/30))*34+len(cls._wrap(subtitle, (width-88)/14.5))*22)/36)*36
        for row_index, level in enumerate(levels):
            row = by_level[level]
            gap = (width - 120) / len(row)
            for column, node in enumerate(row):
                node_width = 720 if len(row) == 1 and node["icon"] in cls._SWITCH_ICONS else 288
                available=node_width-(132 if node.get('brand_icon') and node['brand_icon']!=node['icon'] else 102)
                title_lines = cls._wrap(node["label"], available/18)
                detail_lines = cls._wrap(node["sublabel"], available/13.5)
                node['width']=node_width
                node_height=cls._node_height(node)
                # A shared routing grid prevents 3–9px jogs when endpoint
                # groups have different port counts. Keep node boundaries,
                # row heights and clearance corridors on the same grid.
                center = round((60 + gap*(column+.5))/36)*36
                node["x"] = center-node_width/2
                node["y"] = y
                node["width"] = node_width
                node["height"] = math.ceil(node_height/36)*36
                fill, stroke = cls._TONE_COLORS[node["tone"]]
                node["fill"] = fill
                node["stroke"] = stroke
                node["flat"] = node["kind"] != "double_rect"
            row_height = max(node["height"] for node in row)
            for node in row:
                node["height"] = row_height
            y += row_height + 144
        height = max(560, y-20)
        layout=cls._choose_layout(title,normalized_nodes,edges,layout)
        hub=None
        geometric_edges=[{'from':cls._id(e.get('from') or e.get('source'),i),
            'to':cls._id(e.get('to') or e.get('target'),i+1)} for i,e in enumerate(edges)]
        if layout!='layered':
            width,height,hub=cls._arrange(normalized_nodes,geometric_edges,layout)
            # Templates may change a wide switch into a narrower hub. Size
            # the *final* wrapped labels, then reflow rather than clipping.
            for node in normalized_nodes:
                node['height']=max(node['height'],cls._node_height(node))
            width,height,hub=cls._arrange(normalized_nodes,geometric_edges,layout)

        node_map = {node["id"]: node for node in normalized_nodes}
        normalized_edges: list[dict] = []
        hub_pitch=max((n['height'] for n in normalized_nodes if n['id']!=hub),default=144)+144
        for index, raw in enumerate(edges):
            source = cls._id(raw.get("from") or raw.get("source"), index)
            target = cls._id(raw.get("to") or raw.get("target"), index + 1)
            if source not in ids or target not in ids or source == target:
                raise ValueError(f"連線 {index + 1} 端點無效：{source} → {target}；from/to 必須是 nodes 的 id")
            tone = str(raw.get("tone") or "network").lower()
            flow = {"active": "data", "remote": "async", "blocked": "feedback", "network": "read"}.get(tone, "control")
            a, b = node_map[source], node_map[target]
            if layout!='layered':
                ax,ay=a['x']+a['width']/2,a['y']+a['height']/2
                bx,by=b['x']+b['width']/2,b['y']+b['height']/2
                if layout=='rack' and a['group']==b['group']=='rack':
                    # Cables run beside rack slots instead of passing through
                    # intervening equipment or taking a full chassis detour.
                    intervening=any(n['group']=='rack' and min(ay,by)<n['y']+n['height']/2<max(ay,by) for n in normalized_nodes if n not in (a,b))
                    source_port=target_port='left' if intervening else 'right'
                elif (hub and hub in {source,target}) or abs(bx-ax)>=abs(by-ay):
                    source_port,target_port=('right','left') if ax<bx else ('left','right')
                else:
                    source_port,target_port=('bottom','top') if ay<by else ('top','bottom')
            elif a["level"] == b["level"]:
                reverse_pair = any(e.get("from",e.get("source")) == target and e.get("to",e.get("target")) == source for e in edges)
                if raw.get("label") or reverse_pair:
                    source_port = target_port = "bottom" if a["x"] < b["x"] else "top"
                else:
                    source_port, target_port = ("right", "left") if a["x"] < b["x"] else ("left", "right")
            elif a["level"] < b["level"]:
                source_port, target_port = "bottom", "top"
            else:
                source_port, target_port = "top", "bottom"
            normalized_edges.append({
                "id": f"edge-{index + 1}", "source": source, "target": target,
                "source_port": source_port, "target_port": target_port, "flow": flow,
                "routing_padding":36,"port_clearance":36,
                "port_spacing":hub_pitch if hub in {source,target} and layout in {'star','ecosystem'} else 36,
                "min_segment_length":16,"max_route_bends":4,
                "label": cls._clean(raw.get("label"), 42),
                "dashed": bool(raw.get("dashed")),
                "tone": tone if tone in cls._LINE_COLORS else "network",
                "direction": raw.get("direction") if raw.get("direction") in {"forward", "both", "none"} else ("none" if style == 3 else "forward"),
            })

        if not normalized_edges:
            raise ValueError("架構圖缺少連線；edges 至少需要一個有效的 from/to 節點關係")

        containers: list[dict] = []
        known_groups = {item["id"]: item for item in groups if isinstance(item, dict) and item.get("id")}
        for group_name in sorted({node["group"] for node in normalized_nodes if node["group"]}):
            members = [node for node in normalized_nodes if node["group"] == group_name]
            definition = known_groups.get(group_name, {})
            def bounds(items):
                return (min(n['x'] for n in items)-24,min(n['y'] for n in items)-42,
                    max(n['x']+n['width'] for n in items)+24,max(n['y']+n['height'] for n in items)+22)
            left,top,right,bottom=bounds(members)
            # A logical group can be physically distributed. A single large
            # rectangle used to enclose an unrelated hub and fail the gutter
            # check. Preserve group identity with same-labelled regions.
            overlaps=any(n not in members and n['x']<right and n['x']+n['width']>left and n['y']<bottom and n['y']+n['height']>top for n in normalized_nodes)
            for part in ([[n] for n in members] if overlaps else [members]):
                left,top,right,bottom=bounds(part)
                containers.append({
                    'id':f'group-{cls._id(group_name,len(containers))}-{len(containers)}','x':left,'y':top,
                    'width':right-left,'height':bottom-top,
                    'label':cls._clean(definition.get('label') or ('機櫃配置示意；安裝相容性待核實' if layout=='rack' and group_name=='rack' else group_name),36)})

        return {
            "schema_version": 1, "mode": "architecture", "template_type": "architecture",
            # Keep showcase clearance/crossing rules and at most two bends
            # per edge; the total budget scales with actual graph size.
            # A skip-level edge can legitimately need four turns to go around
            # an intervening switch. Keep zero crossings and >=16px segments;
            # don't reject a valid branch just for bypassing a middle layer.
            "style": style, "quality_profile": {"profile":"showcase", "max_bends_per_edge":4,"max_total_bends":max(8, 4*len(normalized_edges)),"max_route_stretch":1.8}, "text_policy": "strict",
            "width": width, "height": height, "title": title, "subtitle": subtitle,"layout":layout,"hub":hub,
            "containers": containers, "nodes": normalized_nodes, "arrows": normalized_edges,
            "footer": "實線：實體或資料連線 · 虛線：依本圖標示之控制／遠端關係 · 設備圖示為類別示意",
            "footer_x": 44, "footer_y": height - 28,
        }

    @staticmethod
    def _choose_layout(title,nodes,edges,requested):
        allowed={'layered','star','dual_compute','rack','dataflow','ecosystem'}
        if requested not in allowed|{'auto'}:
            raise ValueError('layout 須為 auto/layered/star/dual_compute/rack/dataflow/ecosystem')
        if requested!='auto':
            if requested=='rack' and not any(n['group']=='rack' for n in nodes):
                raise ValueError('rack 配置須明確以 group=rack 指定示意架內設備；不推測安裝相容性')
            return requested
        if re.search(r'機櫃|mini.?rack',title,re.I) and any(n['group']=='rack' for n in nodes):
            return 'rack'
        if re.search(r'雙機|雙工作站|dual.compute',title,re.I):
            return 'dual_compute'
        if re.search(r'資料流|流程|pipeline|data.?flow',title,re.I):
            return 'dataflow'
        if re.search(r'星狀|star',title,re.I):
            return 'star'
        if re.search(r'生態圈|ecosystem',title,re.I):
            return 'ecosystem'
        return 'layered'

    @staticmethod
    def _arrange(nodes,edges,layout):
        """Geometry templates never invent nodes, edges, specs or mount compatibility."""
        top=max(180,min(n['y'] for n in nodes))
        hub=None
        if layout in {'star','ecosystem'}:
            degrees={n['id']:0 for n in nodes}
            for edge in edges:
                for key in ('from','to'):
                    if edge.get(key) in degrees:
                        degrees[edge[key]]+=1
            center=max(nodes,key=lambda n:degrees[n['id']])
            hub=center['id'];leaves=[n for n in nodes if n is not center]
            # Keep connected downstream subgraphs together on one side;
            # blindly alternating every leaf creates diagonal crossings.
            remaining={n['id'] for n in leaves};components=[]
            while remaining:
                first=next(n['id'] for n in leaves if n['id'] in remaining)
                component={first};pending=[first];remaining.remove(first)
                while pending:
                    current=pending.pop()
                    for edge in edges:
                        a,b=edge.get('from'),edge.get('to')
                        other=b if a==current else a if b==current else None
                        if other in remaining:
                            remaining.remove(other);component.add(other);pending.append(other)
                components.append([n for n in leaves if n['id'] in component])
            columns=[[],[]]
            for component in components:
                columns[0 if len(columns[0])<=len(columns[1]) else 1].extend(component)
            rows=max(map(len,columns))
            leaf_height=max(n['height'] for n in leaves)
            step=leaf_height+144
            # One horizontal lane per leaf. The old 36px hub port pitch did
            # not match 288px leaf rows and forced overlaps on ordinary fans.
            center.update(x=576,y=top,width=360 if layout=='star' else 432)
            center['height']=max(center['height'],(rows-1)*step+leaf_height)
            for col,column in enumerate(columns):
                for row,node in enumerate(column):
                    node.update(x=72 if col==0 else 1188,y=top+row*step,width=288,height=leaf_height)
            width=1584
        elif layout=='dual_compute':
            group_names=list(dict.fromkeys(n['group'] for n in nodes if n['group']))
            columns=[[],[]]
            for i,node in enumerate(nodes):
                column=group_names.index(node['group']) if len(group_names)==2 and node['group'] else i%2
                columns[column].append(node)
            for col,column in enumerate(columns):
                cursor=top
                for node in sorted(column,key=lambda n:n['level']):
                    node.update(x=144+col*648,y=cursor,width=360)
                    cursor+=node['height']+144
            width=1296
        elif layout=='rack':
            inside=[n for n in nodes if n['group']=='rack'];outside=[n for n in nodes if n['group']!='rack']
            cursor=top
            for node in inside:
                node.update(x=144,y=cursor,width=576)
                cursor+=node['height']+108
            for i,node in enumerate(outside):
                node.update(x=1116,y=top+sum(n['height']+144 for n in outside[:i]),width=288)
            width=1512
        else:  # dataflow: preserve explicit levels, rotate left-to-right.
            levels=sorted({n['level'] for n in nodes})
            for col,level in enumerate(levels):
                cursor=top
                for node in (n for n in nodes if n['level']==level):
                    node.update(x=108+col*468,y=cursor,width=288)
                    cursor+=node['height']+144
            width=max(1080,108+len(levels)*468)
        height=math.ceil((max(n['y']+n['height'] for n in nodes)+144)/36)*36
        return width,height,hub

    @classmethod
    def _connection_views(cls,original):
        """Exact focused views when one global routing cannot pass quality.

        This is not a guessed replacement topology. Every original edge gets
        one independently routable panel; repeated devices keep canonical IDs.
        Thus even a non-planar graph can be shown without deleting a link,
        relaxing the crossing gate or turning crossing lines into junctions.
        """
        by_id={n['id']:n for n in original['nodes']}
        numbers={n['id']:i+1 for i,n in enumerate(original['nodes'])}
        result={**original,'layout':'connection_views','width':1320,'nodes':[],'arrows':[],'containers':[]}
        result['_canonical']=original
        y=max(240,min(n['y'] for n in original['nodes']))
        connected=set()
        for index,edge in enumerate(original['arrows']):
            pair=[]
            for side,node_id in enumerate([edge['source'],edge['target']]):
                connected.add(node_id);node=dict(by_id[node_id])
                node.update(id=f'view-{index}-{side}',origin_id=node_id,width=360)
                node['label']=f"N{numbers[node_id]} · "+node['label']
                if node['group']:node['sublabel']+=' · 群組：'+node['group']
                node['height']=cls._node_height(node);pair.append(node)
            h=max(n['height'] for n in pair)
            for side,node in enumerate(pair):
                node.update(x=96+side*768,y=y+56+(h-node['height'])/2)
            result['nodes']+=pair
            result['containers'].append({'id':f'view-panel-{index}','x':64,'y':y,
                'width':1192,'height':h+88,'label':f"L{index+1} · "+(edge['label'] or '設備連線')})
            result['arrows'].append({**edge,'source':pair[0]['id'],'target':pair[1]['id'],
                'source_port':'right','target_port':'left','label':f'L{index+1}',
                'canonical_source':edge['source'],'canonical_target':edge['target']})
            y+=h+128
        for node_id,node in by_id.items():
            if node_id in connected:continue
            node={**node,'origin_id':node_id,'width':360,'x':480,'y':y+56}
            node['height']=cls._node_height(node);result['nodes'].append(node)
            result['containers'].append({'id':'isolated-'+node_id,'x':448,'y':y,'width':424,
                'height':node['height']+88,'label':'獨立節點：原資料未提供連線'})
            y+=node['height']+128
        result.update(height=y+64,footer_y=y+36,
            footer='連線分解檢視 · 相同 N 編號是同一設備；L 為原始連線；設備、方向、規格均保留')
        return result

    @staticmethod
    def _semantic_graph(diagram):
        original=diagram.get('_canonical',diagram)
        return {'nodes':[{k:n.get(k,'') for k in ['id','label','sublabel','group','icon']} for n in original['nodes']],
            'edges':[{k:e.get(k,'') for k in ['id','source','target','label','direction','dashed','tone']} for e in original['arrows']]}

    @classmethod
    def _final_svg(cls,source,diagram):
        font=os.environ.get('OPENWEBUI_DIAGRAM_FONT') or ('PingFang TC' if sys.platform=='darwin' else
            'Microsoft JhengHei' if sys.platform=='win32' else 'Noto Sans CJK TC')
        source=re.sub(r'font-family:[^;}]+',f"font-family: '{font}'",source)
        source=source.replace('</style>','.node-title { fill: #F8FAFC; } .node-sub { fill: #CBD5E1; }</style>')
        tree=ET.fromstring(cls._decorate_svg(source,diagram))
        if len(tree.findall('.//*[@data-graph-role="node"]'))!=len(diagram['nodes']) or len(tree.findall('.//*[@data-graph-role="edge"]'))!=len(diagram['arrows']):
            raise ValueError('Rendered graph lost nodes or edges')
        ET.SubElement(tree,'{http://www.w3.org/2000/svg}desc',{'id':'architecture-semantic-graph'}).text=json.dumps(cls._semantic_graph(diagram),ensure_ascii=False)
        tree.set('data-layout',diagram['layout']);tree.set('data-text-complete','true')
        return ET.tostring(tree,encoding='unicode')

    async def render_technical_architecture(
        self,
        title: str,
        nodes: list[dict],
        edges: list[dict],
        subtitle: str = "",
        groups: list[dict] | None = None,
        visual_family: str = "network",
        layout: str = "auto",
        __event_emitter__=None,
        __request__=None,
    ) -> str:
        """產生有設備圖示／品牌標誌的 PNG、SVG、互動 HTML。layout=auto/layered(分層)/star(中心拓撲)/dual_compute(雙欄主機)/rack(機櫃示意)/dataflow(橫向流程)/ecosystem(生態圈)。rack 必須以 nodes[].group='rack' 明確指定架內設備，不宣稱尺寸或固定方式相容。nodes 必須有 id,label,level；可有 detail,group,tone,icon,brand,port_groups。icon 支援本機四圖庫 lucide/lobe/dashboard/simple 命名空間（例 lobe:ollama、simple:asus、lucide:router），或 hardware:mini-ai-pc/pcie-nic/ai-workstation/desktop-switch/mini-rack 及 nas/router/vpn 等原有 ID。不知道 ID 時先 search_diagram_assets，也可省略讓伺服器自動選圖；不傳 SVG。品牌識別自動加小徽章，硬體不因品牌變成商標卡。port_groups=[{label:'25G',count:4,tone:'active'}] 僅填已知埠數，禁止猜規格。edges 須有 from,to，可有 label,tone,dashed,direction(none/forward/both)。tone=network藍/active青綠/remote琥珀/default灰/blocked紅；實體連線用 none。保留所有真實設備、分支及邏輯流，不以構圖模板編造關係。"""
        await self._status(__event_emitter__, "正在繪製技術架構圖…")
        diagram = None
        try:
            family = self._clean(visual_family, 20).lower()
            style = self._STYLE_BY_FAMILY.get(family, 3)
            diagram = self._layout(
                self._clean(title, 72) or "技術架構圖",
                self._clean(subtitle, 132),
                nodes if isinstance(nodes, list) else [],
                edges if isinstance(edges, list) else [],
                groups if isinstance(groups, list) else [],
                style, layout,
            )
            runtime = self._runtime_root()
            output_dir = self._static_output_dir()
            token = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
            source = output_dir / f"{token}.json"
            svg = output_dir / f"{token}.svg"
            png = output_dir / f"{token}.png"
            preview = output_dir / f"{token}.html"
            command = [sys.executable, str(runtime / "scripts/fireworks.py"), "render", "architecture", str(source), str(svg)]
            original=diagram;attempts=[];deadline=time.monotonic()+24
            layouts=list(dict.fromkeys([diagram['layout'],'star','layered','dataflow']))
            choices=[*layouts,'connection_views']
            for candidate in choices:
                if candidate!='connection_views' and attempts and time.monotonic()>=deadline:continue
                if attempts:await self._status(__event_emitter__,'正在重新安排連線，保留全部設備與關係…')
                diagram=self._connection_views(original) if candidate=='connection_views' else (
                    original if candidate==original['layout'] else self._layout(self._clean(title,72) or '技術架構圖',
                        self._clean(subtitle,132),nodes,edges,groups or [],style,candidate))
                # Fireworks' temporary node boxes are replaced below by our
                # fully wrapped cards. Audit final card text, not the
                # intermediate generator's single-line placeholder text.
                intermediate={k:v for k,v in diagram.items() if not k.startswith('_')}
                intermediate['text_policy']='report'
                source.write_text(json.dumps(intermediate,ensure_ascii=False),encoding='utf-8')
                started=time.monotonic()
                try:
                    result=await asyncio.to_thread(subprocess.run,command,capture_output=True,text=True,
                        timeout=10 if candidate=='connection_views' else min(8,max(1,deadline-time.monotonic())))
                    failure=(result.stderr or result.stdout or 'Geometry renderer failed') if result.returncode else ''
                    if not failure and svg.is_file():
                        svg.write_text(self._final_svg(svg.read_text(encoding='utf-8'),diagram),encoding='utf-8')
                        # The generator routes edges in sequence: a later
                        # route can invalidate an earlier label's clearance.
                        # Check the complete decorated SVG, not only its draft.
                        checked=await asyncio.to_thread(subprocess.run,
                            [sys.executable,str(runtime/'scripts/fireworks.py'),'check',str(svg)],
                            capture_output=True,text=True,timeout=8)
                        if checked.returncode:failure=checked.stderr or checked.stdout or 'Final SVG validation failed'
                except subprocess.TimeoutExpired:
                    failure='Geometry attempt exceeded its time budget'
                except ValueError as error:
                    failure=str(error)
                attempts.append({'layout':candidate,'error':failure[:1500],'seconds':round(time.monotonic()-started,3)})
                if not failure and svg.is_file():break
            else:raise RuntimeError('Geometry recovery failed: '+attempts[-1]['error'])
            fallback=diagram['layout']!=original['layout']
            source.unlink(missing_ok=True)
            semantic=self._semantic_graph(diagram)
            # Mobile WebViews and a few Open WebUI markdown renderers do not
            # display SVG image URLs reliably even though the server returns
            # 200.  Keep the editable SVG, but make the conversation use a
            # raster PNG as the primary image so the finished diagram is
            # visible on desktop, browser and phone clients alike.
            png_command = [
                sys.executable,
                str(runtime / "scripts/fireworks.py"),
                "export-png",
                str(svg),
                str(png),
                "--width",
                "1920",
            ]
            png_result = await asyncio.to_thread(
                subprocess.run, png_command, capture_output=True, text=True, timeout=60
            )
            if png_result.returncode != 0 or not png.is_file():
                raise RuntimeError((png_result.stderr or png_result.stdout or "PNG export failed").strip()[:500])
            url = f"/static/openwebui-generated/fireworks/{png.name}"
            svg_url = f"/static/openwebui-generated/fireworks/{svg.name}"
            html_result = await asyncio.to_thread(subprocess.run,
                [sys.executable, str(runtime / "scripts/fireworks.py"), "export-html", str(svg), str(preview)],
                capture_output=True, text=True, timeout=30)
            preview_url = f"/static/openwebui-generated/fireworks/{preview.name}" if html_result.returncode == 0 and preview.is_file() else ""
            alt=re.sub(r'[\[\]\\]','',self._clean(title,72)) or '技術架構圖'
            artifact = f"![{alt}]({url})\n\n[下載 PNG]({url}) · [下載可編輯 SVG]({svg_url})"
            if preview_url:
                artifact += f" · [放大互動預覽]({preview_url})"
            artifact += ' · [圖示來源／授權](/static/architecture-icons/v2/NOTICE.html)'
            if fallback:
                artifact += ('\n\n此圖採連線分解檢視；相同 N 編號代表同一設備，全部原始連線與方向均保留。' if diagram['layout']=='connection_views'
                    else '\n\n已依連線自動調整構圖；原有設備、群組與連線均保留。')
            try:
                (output_dir/(token+'.report.json')).write_text(json.dumps({'layout':diagram['layout'],
                    'nodes':len(semantic['nodes']),'edges':len(semantic['edges']),
                    'attempts':[{**a,'error':bool(a['error'])} for a in attempts],
                    'text_complete':True,'png_bytes':png.stat().st_size},ensure_ascii=False),encoding='utf-8')
            except OSError:pass  # An optional diagnostic is not a rendering dependency.
            if __request__ is not None:
                state = getattr(__request__.state, "fireworks_diagram", None)
                if state is not None:
                    state["artifact"] = artifact
                    state.setdefault("architecture_artifacts", []).append(artifact)
            await self._status(__event_emitter__, "架構圖完成", done=True, hidden=True)
            if __event_emitter__:
                try:
                    await __event_emitter__({'type':'files','data':{'files':[
                        {'type':'file','name':alt+'.png','url':url},{'type':'file','name':alt+'.svg','url':svg_url}]}})
                except Exception:pass
            return artifact
        except Exception as error:
            # Keep bounded normalized geometry privately for a reproducible
            # failure, not in the public static directory or model context.
            if diagram is not None and os.environ.get('DATA_DIR'):
                try:
                    folder=Path(os.environ['DATA_DIR'])/'visual-profile/render-failures'
                    folder.mkdir(parents=True,exist_ok=True)
                    (folder/(str(time.time_ns())+'.json')).write_text(json.dumps({
                        'error':str(error)[:2000],'diagram':diagram},ensure_ascii=False),encoding='utf-8')
                except OSError:pass  # Diagnostics must not hide the real error.
            await self._status(__event_emitter__, "架構圖產生失敗", done=True)
            return f"Fireworks 架構圖未能產生：{self._clean(error, 280)}。請改以簡短文字說明，勿輸出繪圖程式碼。"

    @classmethod
    def _chart_options(cls, kind, value):
        if value is None:
            return {}
        allowed = {"gauge":{"min", "max", "target"}, "radar":{"max"},
            "scatter":{"x_unit", "y_unit"}, "bubble":{"x_unit", "y_unit", "size_unit"},
            "waterfall":{"roles"}, "treemap":{"parents"}, "gantt":{"tasks", "progress"}}
        if not isinstance(value, dict) or set(value)-allowed.get(kind, set()):
            raise ValueError("options 包含此圖型不支援的欄位")
        if len(json.dumps(value, ensure_ascii=False)) > 16000:
            raise ValueError("options 過大")
        result = dict(value)
        for key in ("min", "max", "target"):
            if key in result and (isinstance(result[key], bool) or not isinstance(result[key], (int, float)) or not math.isfinite(result[key]) or abs(result[key]) > 1e15):
                raise ValueError(key+" 必須是有限數字")
        for key in ("x_unit", "y_unit", "size_unit"):
            if key in result:
                result[key] = cls._clean(result[key], 32)
                if not result[key]:
                    raise ValueError(key+" 不可空白")
        return result

    @classmethod
    def _gantt_dates(cls, labels, series, options):
        tasks = options["tasks"]
        if series != [] or not isinstance(tasks, list) or len(tasks) != len(labels):
            raise ValueError("日期甘特圖提供 series=[]，options.tasks 與 labels 等長")
        planned = any(isinstance(t, dict) and ("planned_start" in t or "planned_end" in t) for t in tasks)
        keys = ["start", "end"] + (["planned_start", "planned_end"] if planned else [])
        parsed, progress = [], []
        for task in tasks:
            if not isinstance(task, dict) or set(task)-set(keys+["progress"]):
                raise ValueError("甘特 tasks 只支援 start/end/planned_start/planned_end/progress")
            try:
                parsed.append([date.fromisoformat(task[k]) for k in keys])
            except (KeyError, TypeError, ValueError):
                raise ValueError("每項任務日期須完整，使用 YYYY-MM-DD") from None
            progress.append(task.get("progress"))
        origin = min(d for row in parsed for d in row)
        if max(d for row in parsed for d in row)-origin > timedelta(days=36500):
            raise ValueError("甘特圖日期範圍不可超過 100 年")
        normalized = [{"name":name, "values":[(row[i]-origin).days for row in parsed]} for i, name in enumerate(["開始", "結束", "計畫開始", "計畫結束"][:len(keys)])]
        if "progress" in options:
            raise ValueError("日期任務的進度放在每個 tasks.progress，不要同時傳 options.progress")
        options = {"time_origin":origin.isoformat(), "progress":progress,
            "tasks":[{k:row[i].isoformat() for i,k in enumerate(keys)} for row in parsed]}
        return normalized, options

    @classmethod
    def _validate_chart_template(cls, kind, labels, series, options):
        values = [v for s in series for v in s["values"]]
        single = {"gauge", "waterfall", "pie", "doughnut", "treemap", "funnel"}
        if kind in single and len(series) != 1:
            raise ValueError("此圖型須恰有一組數值")
        if kind in {"pie", "doughnut", "treemap", "funnel", "area", "radar", "stacked_column", "percent_stacked_column", "tornado"} and min(values) < 0:
            raise ValueError("此圖型不可有負值；請用長條／折線圖表示負數")
        if kind in {"pie", "doughnut", "treemap", "funnel"} and sum(values) <= 0:
            raise ValueError("組成／漏斗圖的合計必須大於零")
        if kind in {"pie", "doughnut"} and len(labels) > 7:
            raise ValueError("圓餅／環形最多 7 類，較多項請用橫條或樹狀圖")
        if kind == "tornado" and len(series) != 2:
            raise ValueError("旋風／蝴蝶圖須恰有兩組非負值，左右共用尺度")
        if kind == "radar":
            maximum = options.get("max", 100)
            if not 3 <= len(labels) <= 8 or len(series) > 3 or maximum <= 0 or max(values) > maximum:
                raise ValueError("雷達圖需 3–8 軸、最多 3 組、同量尺 0 至 options.max（預設 100）")
        if kind == "gauge":
            low, high = options.get("min", 0), options.get("max", 100)
            if len(labels) != 1 or high <= low or not low <= values[0] <= high or not low <= options.get("target", high) <= high:
                raise ValueError("儀表盤須恰一數值且 min < max；數值與 target 均須在量尺內")
        if kind in {"scatter", "bubble"}:
            expected = 3 if kind == "bubble" else 2
            if len(series) != expected or not options.get("x_unit") or not options.get("y_unit"):
                raise ValueError("散點須 X/Y 兩組；氣泡須 X/Y/大小三組，並設定 options.x_unit/y_unit")
            if kind == "bubble" and (not options.get("size_unit") or min(series[2]["values"]) <= 0):
                raise ValueError("氣泡大小須大於零且設定 size_unit；面積與數值成正比")
        if kind == "percent_stacked_column" and any(sum(s["values"][i] for s in series) <= 0 for i in range(len(labels))):
            raise ValueError("百分比堆積每類別合計須大於零，不能把零合計當 100%")
        if kind == "funnel" and any(b > a for a,b in zip(values, values[1:])):
            raise ValueError("轉換漏斗階段值須單調不增，增加或不同母體請改長條圖")
        if kind == "waterfall":
            roles = options.setdefault("roles", ["total"]+["change"]*(len(labels)-1))
            if not isinstance(roles, list) or len(roles) != len(labels) or roles[0] != "total" or any(r not in {"total", "change"} for r in roles):
                raise ValueError("瀑布 roles 與 labels 等長，首項為 total，其餘 total/change")
            total = values[0]
            for value, role in zip(values[1:], roles[1:]):
                if role == "total":
                    if not math.isclose(total, value, rel_tol=1e-9, abs_tol=1e-9):
                        raise ValueError("瀑布圖總額與前面累計不符，不自動改動資料")
                else:
                    total += value
        if kind == "treemap" and "parents" in options:
            parents = options["parents"]
            if not isinstance(parents, list) or len(parents) != len(labels) or any(not isinstance(v, str) or len(v) > 100 or len(v.split('/')) > 4 for v in parents):
                raise ValueError("parents 與 labels 等長，父層路徑最多 4 層，以 / 分隔")
            options["parents"] = [cls._clean(v, 100) for v in parents]
        if kind == "gantt":
            if len(series) not in {2, 4} or min(values) < 0:
                raise ValueError("甘特圖須開始／結束兩組，可再加計畫開始／計畫結束；相對時間不可為負")
            if any(series[i+1]["values"][j] < series[i]["values"][j] for i in range(0,len(series),2) for j in range(len(labels))):
                raise ValueError("任務結束不可早於開始")
            progress = options.setdefault("progress", [None]*len(labels))
            if not isinstance(progress, list) or len(progress) != len(labels) or any(p is not None and (isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0 <= p <= 100) for p in progress):
                raise ValueError("甘特 progress 與任務等長，範圍 0–100")

    @classmethod
    def _chart_data(cls, title, labels, series, unit, chart_type, data_kind, sources, note, better, options=None):
        kinds = {"measured":"實測資料", "reported":"引用資料", "estimated":"估算資料", "illustrative":"示意資料", "user_provided":"使用者提供"}
        if data_kind not in kinds:
            raise ValueError("data_kind 必須明確區分 measured/reported/estimated/illustrative/user_provided")
        aliases = {"column":"bar", "butterfly":"tornado", "donut":"doughnut", "stacked":"stacked_column", "stacked100":"percent_stacked_column"}
        chart_type = aliases.get(chart_type, chart_type)
        supported = {"auto", "bar", "horizontal_bar", "line", "quadrant", "tornado", "radar", "gauge", "area", "waterfall", "pie", "doughnut", "stacked_column", "percent_stacked_column", "treemap", "scatter", "bubble", "gantt", "funnel"}
        if chart_type not in supported:
            raise ValueError("不支援的 chart_type，請使用已安裝統計圖表樣板")
        options = cls._chart_options(chart_type, options)
        maximum = 48 if chart_type in {"scatter", "bubble"} else 24 if chart_type in {"line", "area", "treemap"} else 12
        minimum = 1 if chart_type in {"gauge", "gantt", "treemap", "scatter", "bubble"} else 2
        if not isinstance(labels, list) or not minimum <= len(labels) <= maximum:
            raise ValueError(f"此圖須有 {minimum}–{maximum} 個類別／資料點")
        labels = [cls._clean(label, 48) for label in labels]
        if any(not label for label in labels) or len(set(labels)) != len(labels):
            raise ValueError("類別名稱不可空白或重複")
        if chart_type == "gantt" and options.get("tasks"):
            series, options = cls._gantt_dates(labels, series, options)
        if not isinstance(series, list) or not 1 <= len(series) <= 4:
            raise ValueError("series 必須包含 1–4 組同單位數值")
        normalized = []
        for item in series:
            if not isinstance(item, dict) or not isinstance(item.get("values"), list) or len(item["values"]) != len(labels):
                raise ValueError("每組 values 數量必須與 labels 完全一致，缺失值不得填 0")
            values = item["values"]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e15 or (v != 0 and abs(v) < 1e-12) for v in values):
                raise ValueError("values 必須是有限數值；不得以字串、未知值或布林值冒充")
            normalized.append({"name":cls._clean(item.get("name"), 36) or "數值", "values":values})
        if len({item["name"] for item in normalized}) != len(normalized):
            raise ValueError("不同系列須有不同名稱，避免圖例無法辨識")
        if chart_type == "quadrant" and (len(normalized) != 2 or any(not 0 <= value <= 1 for item in normalized for value in item["values"])):
            raise ValueError("定位圖須恰有 X、Y 兩組 0–1 相對座標，不代表百分比或市佔率")
        cls._validate_chart_template(chart_type, labels, normalized, options)
        if sources is not None and not isinstance(sources, list):
            raise ValueError("sources 必須是出處清單，不能以單一字串替代")
        sources = [cls._clean(s, 220) for s in (sources or []) if isinstance(s, str) and s.strip()][:5]
        if data_kind in {"measured", "reported"} and not sources:
            raise ValueError("實測或引用資料必須提供 sources，包含出處或測試條件")
        if data_kind in {"estimated", "illustrative"} and not str(note).strip():
            raise ValueError("估算或示意資料必須用 note 說明假設或非實測性質")
        title, unit = cls._clean(title, 80), cls._clean(unit, 32)
        if not title or not unit:
            raise ValueError("必須提供圖表標題與單位，無因次資料請填倍數或指數等")
        if chart_type == "auto":
            chart_type = "horizontal_bar" if len(labels) > 4 or max(map(len, labels)) > 14 else "bar"
        return {"title":title, "labels":labels, "series":normalized, "unit":unit,
            "chart_type":chart_type, "data_kind":data_kind, "kind_label":kinds[data_kind],
            "sources":sources, "note":cls._clean(note, 600), "options":options, "better":better if better in {"higher", "lower"} else "neutral"}

    @staticmethod
    def _chart_number(value):
        if value and abs(value) < .001:
            return f"{value:.3g}"
        return f"{value:,.3f}".rstrip("0").rstrip(".") if value != int(value) else f"{int(value):,}"

    @classmethod
    def _template_chart_svg(cls, data):
        """Trusted deterministic SVG templates. Only validated data enters this path."""
        kind, labels, series, opt = (data[k] for k in ("chart_type", "labels", "series", "options"))
        colors = ["#60A5FA", "#2DD4BF", "#FBBF24", "#C4B5FD", "#FB7185", "#A3E635", "#FDBA74"]
        width, left, right = 960, 136, 890
        legend_rows = math.ceil(len(series)/2) if kind in {"radar", "area", "tornado", "stacked_column", "percent_stacked_column"} else 0
        top = 162 + legend_rows*48
        bottom = top + (max(340, len(labels)*52) if kind in {"gantt", "tornado", "funnel"} else 370)
        if kind in {'pie','doughnut'}: bottom=top+max(370,len(labels)*68)
        if kind in {'tornado','funnel'}:
            bottom=top+max(340,len(labels)*max(52,22*max(len(cls._wrap(label,12)) for label in labels)+16))
        if kind=='gantt':
            bottom=top+max(340,len(labels)*max(64,23*max(len(cls._wrap(label,13)) for label in labels)+20))
        foot = bottom+115
        notes = ([data["note"]] if data["note"] else []) + ["來源："+s for s in data["sources"]]
        if kind in {"pie", "doughnut", "treemap"}:
            notes.insert(0, "比例以本圖所列項目合計為分母；未列出的項目不在此分母內。零值僅保留於資料表。")
        if kind == "percent_stacked_column":
            notes.insert(0, "每柱獨立正規化至 100%；原始數值保留於資料表，柱高不代表總量。")
        if kind == "bubble":
            notes.insert(0, "氣泡面積（非半徑）與第三項數值成正比；圖中編號對應下方資料表。")
        if kind in {"scatter", "bubble"}:
            notes.append("散點關係不代表因果；不自動推論相關性或統計顯著性。")
        if kind == "radar":
            notes.insert(0, "各軸必須使用共同量尺；不同單位需先依公開方法正規化，面積不是總體分數。")
        if kind == "gantt":
            notes.insert(0, "細灰條為計畫（如有）；藍條為執行區間，內部青綠表示已提供的完成率；同日為里程碑。")
        note_lines = [line for note in notes for line in cls._wrap(note, 62)]
        # Point keys make dense scatter plots readable without overlapping text.
        if kind in {"scatter", "bubble"}:
            keys = [f'{i+1}. {label}' for i,label in enumerate(labels)]
            note_lines = [line for key in keys for line in cls._wrap(key, 62)]+note_lines
        height = foot + len(note_lines)*25+32
        esc, number = html.escape, cls._chart_number
        font = os.environ.get("OPENWEBUI_DIAGRAM_FONT") or ("PingFang TC" if sys.platform == "darwin" else "Microsoft JhengHei" if sys.platform == "win32" else "Noto Sans CJK TC")
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc" data-chart-type="{kind}" data-template-version="1">',
            '<title id="chart-title">'+esc(data["title"])+'</title><desc id="chart-desc">'+esc(data["kind_label"]+'；'+data['note'])+'</desc>',
            f'<rect width="{width}" height="{height}" rx="20" fill="#0B0F17"/>',
            '<style>text{font-family:"'+esc(font)+'"}g:focus{outline:2px solid #F8FAFC}</style>']
        def text(x,y,value,color="#F8FAFC",size=18,anchor="start"):
            parts.append(f'<text x="{x:g}" y="{y:g}" fill="{color}" font-size="{size}" text-anchor="{anchor}">{esc(str(value))}</text>')
        def lines(x,y,value,limit=36,color="#F8FAFC",size=18,anchor="start",maximum=4):
            wrapped=cls._wrap(value,limit)
            visible=wrapped[:maximum]
            if len(wrapped)>maximum:visible[-1]=visible[-1].rstrip()+'…'
            for i,line in enumerate(visible):
                text(x,y+i*(size+5),line,color,size,anchor)
        def rect(x,y,w,h,fill,stroke="none",radius=0):
            parts.append(f'<rect x="{x:g}" y="{y:g}" width="{max(0,w):g}" height="{max(0,h):g}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')
        def path(d,stroke="#334155",fill="none",thickness=1,dash=""):
            parts.append(f'<path d="{d}" stroke="{stroke}" fill="{fill}" stroke-width="{thickness}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
        def point(x,y,r,color):
            parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{color}" stroke="#0B0F17" stroke-width="2"/>')
        def begin(label):
            label=esc(str(label))
            parts.append(f'<g tabindex="0" role="img" aria-label="{label}"><title>{label}</title>')
        def end(): parts.append('</g>')
        def nice_range(values,zero=True):
            lo,hi=min(values),max(values)
            if zero: lo,hi=min(0,lo),max(0,hi)
            if lo==hi:
                margin=max(abs(lo)*.1,1)
                lo,hi=(0,margin) if lo==0 else (lo-margin,hi+margin)
            raw=(hi-lo)/5
            power=10**math.floor(math.log10(raw))
            step=next(v for v in (1,2,2.5,5,10) if v*power>=raw)*power
            return math.floor(lo/step)*step,math.ceil(hi/step)*step,step
        def y_axis(values,percent=False):
            lo,hi,step=(0,100,20) if percent else nice_range(values)
            scale=lambda v:bottom-(v-lo)/(hi-lo)*(bottom-top)
            for i in range(round((hi-lo)/step)+1):
                v=lo+i*step; y=scale(v)
                path(f'M{left} {y:g}H{right}',dash="3 5")
                text(left-14,y+6,number(v)+('%' if percent else ''),'#94A3B8',16,'end')
            return scale
        def categories():
            band=(right-left)/len(labels)
            for i,label in enumerate(labels):
                if len(labels)>10 and i%math.ceil(len(labels)/8) and i!=len(labels)-1: continue
                lines(left+band*(i+.5),bottom+30,label,max(4,band/16),'#CBD5E1',16,'middle',3)
            return band
        lines(36,44,data['title'],42,size=25,maximum=2)
        text(36,112,data['kind_label']+' · '+('X/Y 單位分別標示' if kind in {'scatter','bubble'} else '單位：'+data['unit']),'#94A3B8',17)
        if legend_rows:
            for i,s in enumerate(series):
                x,y=36+(i%2)*450,150+(i//2)*48
                rect(x,y-12,12,12,colors[i],radius=3)
                lines(x+22,y,s['name'],24,'#CBD5E1',16,maximum=2)

        if kind in {'pie','doughnut'}:
            vals=series[0]['values']; total=sum(vals); cx,cy,r=270,(top+bottom)/2,155
            angle=-math.pi/2
            for i,(label,v) in enumerate(zip(labels,vals)):
                fraction=v/total; nxt=angle+2*math.pi*fraction
                begin(f'{label}：{number(v)} {data["unit"]}；{fraction*100:.1f}%')
                if v:
                    if kind=='doughnut':
                        # Circle stroke lengths preserve exact angular shares, including a 100% segment.
                        circumference=2*math.pi*(r-26)
                        parts.append(f'<circle cx="{cx}" cy="{cy:g}" r="{r-26}" fill="none" stroke="{colors[i]}" stroke-width="52" stroke-dasharray="{fraction*circumference:g} {circumference:g}" transform="rotate({angle*180/math.pi:g} {cx} {cy:g})"/>')
                    elif fraction>=1:
                        point(cx,cy,r,colors[i])
                    else:
                        x1,y1=cx+r*math.cos(angle),cy+r*math.sin(angle)
                        x2,y2=cx+r*math.cos(nxt),cy+r*math.sin(nxt)
                        path(f'M{cx} {cy:g}L{x1:g} {y1:g}A{r} {r} 0 {int(fraction>.5)} 1 {x2:g} {y2:g}Z', '#0B0F17', colors[i],2)
                end(); angle=nxt
                y=top+i*68
                rect(500,y,12,12,colors[i],radius=3)
                lines(522,y+11,label,24,size=16,maximum=2)
                text(522,y+57,f'{number(v)} {data["unit"]} · {fraction*100:.1f}%','#CBD5E1',16)
            text(cx,cy+6,'合計' if kind=='doughnut' else '',size=20,anchor='middle')
            if kind=='doughnut': text(cx,cy+38,number(total),'#CBD5E1',23,'middle')

        elif kind=='gauge':
            low,high=opt.get('min',0),opt.get('max',100); v=series[0]['values'][0]
            cx,cy,r=480,bottom-70,220
            path(f'M{cx-r} {cy}A{r} {r} 0 0 1 {cx+r} {cy}', '#253044',thickness=36)
            def on_arc(value):
                a=math.pi+(value-low)/(high-low)*math.pi
                return cx+r*math.cos(a),cy+r*math.sin(a)
            if v>low:
                x,y=on_arc(v); path(f'M{cx-r} {cy}A{r} {r} 0 0 1 {x:g} {y:g}',colors[0],thickness=36)
            if 'target' in opt:
                tx,ty=on_arc(opt['target']); dx,dy=(tx-cx)/r,(ty-cy)/r
                path(f'M{tx-24*dx:g} {ty-24*dy:g}L{tx+24*dx:g} {ty+24*dy:g}',colors[2],thickness=4)
                text(cx,bottom+32,'目標：'+number(opt['target'])+' '+data['unit'],colors[2],19,'middle')
            text(cx,cy-54,number(v)+' '+data['unit'],size=34,anchor='middle')
            lines(cx,cy-15,labels[0],25,'#CBD5E1',20,'middle')
            text(cx-r,cy+48,number(low),'#94A3B8',18,'middle');text(cx+r,cy+48,number(high),'#94A3B8',18,'middle')

        elif kind=='radar':
            cx,cy,r=480,(top+bottom)/2,148; maximum=opt.get('max',100); n=len(labels)
            def polar(i,value):
                a=-math.pi/2+2*math.pi*i/n
                return cx+r*value/maximum*math.cos(a),cy+r*value/maximum*math.sin(a)
            for ring in range(1,5):
                coords=[polar(i,maximum*ring/4) for i in range(n)]
                path('M'+'L'.join(f'{x:g} {y:g}' for x,y in coords)+'Z')
                text(cx+8,cy-r*ring/4+5,number(maximum*ring/4),'#94A3B8',13)
            for i,label in enumerate(labels):
                x,y=polar(i,maximum); path(f'M{cx} {cy:g}L{x:g} {y:g}')
                x,y=polar(i,maximum*1.25)
                lines(x,y,label,14,'#CBD5E1',17,'middle',2)
            for si,s in enumerate(series):
                points=[polar(i,v) for i,v in enumerate(s['values'])]
                coords=' '.join(f'{x:g},{y:g}' for x,y in points)
                parts.append(f'<polygon points="{coords}" fill="{colors[si]}" fill-opacity="0.13" stroke="{colors[si]}" stroke-width="3"'+(' stroke-dasharray="7 4"' if si%2 else '')+'/>')
                for i,(x,y) in enumerate(points):
                    begin(f'{s["name"]} · {labels[i]}：{number(s["values"][i])} / {number(maximum)}');point(x,y,5,colors[si]);end()

        elif kind in {'stacked_column','percent_stacked_column','area'}:
            percent=kind=='percent_stacked_column'
            totals=[sum(s['values'][i] for s in series) for i in range(len(labels))]
            scale=y_axis(totals if kind!='area' else [v for s in series for v in s['values']],percent)
            band=categories()
            for si,s in enumerate(series):
                if kind=='area':
                    points=[(left+band*(i+.5),scale(v)) for i,v in enumerate(s['values'])]
                    d=f'M{points[0][0]:g} {scale(0):g}L'+'L'.join(f'{x:g} {y:g}' for x,y in points)+f'L{points[-1][0]:g} {scale(0):g}Z'
                    parts.append(f'<path d="{d}" fill="{colors[si]}" fill-opacity="0.16"/>')
                    path('M'+'L'.join(f'{x:g} {y:g}' for x,y in points),colors[si],thickness=3,dash='7 4' if si%2 else '')
                    for i,(x,y) in enumerate(points):
                        begin(f'{labels[i]} · {s["name"]}：{number(s["values"][i])} {data["unit"]}');point(x,y,4,colors[si]);end()
                    continue
                for i,v in enumerate(s['values']):
                    prior=sum(t['values'][i] for t in series[:si]);factor=100/totals[i] if percent else 1
                    y1,y2=scale((prior+v)*factor),scale(prior*factor)
                    begin(f'{labels[i]} · {s["name"]}：{number(v)} {data["unit"]}'+(f'；{v*factor:.1f}%' if percent else ''))
                    rect(left+band*(i+.18),y1,band*.64,y2-y1,colors[si])
                    if y2-y1>=28 and band>75:
                        text(left+band*(i+.5),(y1+y2)/2+6,f'{v*factor:.1f}%' if percent else number(v),'#0B0F17',16,'middle')
                    end()
            if kind=='stacked_column':
                for i,total in enumerate(totals): text(left+band*(i+.5),scale(total)-13,number(total),size=17,anchor='middle')

        elif kind=='tornado':
            maxval=max(1,max(v for s in series for v in s['values'])); half=270; center=520
            band=(bottom-top)/len(labels)
            for i,label in enumerate(labels):
                y=top+band*(i+.5)
                lines(36,y-6,label,12,'#CBD5E1',16,maximum=4)
                for si,s in enumerate(series):
                    v=s['values'][i];w=v/maxval*half
                    begin(f'{label} · {s["name"]}：{number(v)} {data["unit"]}')
                    rect(center-w if si==0 else center,y-13,w,26,colors[si])
                    text(center-w-9 if si==0 else center+w+9,y+6,number(v),size=17,anchor='end' if si==0 else 'start');end()
            path(f'M{center} {top-12}V{bottom+6}','#94A3B8')
            for direction in (-1,1):
                for fraction in (0.5,1): text(center+direction*half*fraction,bottom+34,number(maxval*fraction),'#94A3B8',16,'middle')
            text(center,bottom+34,'0','#94A3B8',16,'middle')

        elif kind=='waterfall':
            entries=[]; total=0
            for label,v,role in zip(labels,series[0]['values'],opt['roles']):
                start=0 if role=='total' else total
                total=v if role=='total' else total+v
                entries.append((label,start,total,role,v))
            if opt['roles'][-1]!='total': entries.append(('合計',0,total,'total',total))
            scale=y_axis([v for entry in entries for v in entry[1:3]])
            band=(right-left)/len(entries)
            for i,(label,start,endvalue,role,v) in enumerate(entries):
                x=left+band*(i+.18);y1,y2=scale(start),scale(endvalue)
                color=colors[0] if role=='total' else '#2DD4BF' if v>=0 else '#FB7185'
                begin(f'{label}：{number(v)}；累計 {number(endvalue)} {data["unit"]}')
                rect(x,min(y1,y2),band*.64,abs(y2-y1),color)
                text(x+band*.32,min(y1,y2)-13,number(v) if role=='total' else f'{v:+g}',color,17,'middle');end()
                if i<len(entries)-1: path(f'M{x+band*.64:g} {y2:g}H{left+band*(i+1.18):g}', '#94A3B8',dash='4 4')
                lines(left+band*(i+.5),bottom+30,label,max(4,band/16),'#CBD5E1',16,'middle',3)
            text(36,bottom+96,'藍：總額 · 青綠：增加 · 紅：減少（僅表示正負，不代表好壞）','#94A3B8',16)

        elif kind in {'scatter','bubble'}:
            xs,ys=[s['values'] for s in series[:2]]
            xmin,xmax,xstep=nice_range(xs,False);ymin,ymax,ystep=nice_range(ys,False)
            # Padding reserves enough space for the largest bubble at a boundary.
            x0,x1=left+42,right-42;y0,y1=top+42,bottom-42
            sx=lambda v:x0+(v-xmin)/(xmax-xmin)*(x1-x0)
            sy=lambda v:y1-(v-ymin)/(ymax-ymin)*(y1-y0)
            for i in range(round((xmax-xmin)/xstep)+1):
                v=xmin+i*xstep;x=sx(v);path(f'M{x:g} {y0}V{y1}',dash='3 5');text(x,bottom+16,number(v),'#94A3B8',15,'middle')
            for i in range(round((ymax-ymin)/ystep)+1):
                v=ymin+i*ystep;y=sy(v);path(f'M{x0} {y:g}H{x1}',dash='3 5');text(left-10,y+5,number(v),'#94A3B8',15,'end')
            lines((left+right)/2,bottom+54,series[0]['name']+' ('+opt['x_unit']+')',48,'#CBD5E1',17,'middle',2)
            lines(36,top-16,series[1]['name']+' ('+opt['y_unit']+')',48,'#CBD5E1',17,maximum=1)
            used=[]
            # Largest first so a small bubble at the same location stays visible.
            order=sorted(range(len(labels)),key=lambda i:-series[2]['values'][i]) if kind=='bubble' else range(len(labels))
            for i in order:
                x,y=sx(xs[i]),sy(ys[i]);r=36*math.sqrt(series[2]['values'][i]/max(series[2]['values'])) if kind=='bubble' else 7
                tooltip=f'{i+1}. {labels[i]}：X={number(xs[i])} {opt["x_unit"]}，Y={number(ys[i])} {opt["y_unit"]}'
                if kind=='bubble':tooltip+=f'，大小={number(series[2]["values"][i])} {opt["size_unit"]}'
                begin(tooltip)
                parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{colors[0]}" fill-opacity="0.55" stroke="#93C5FD" stroke-width="2"/>');end()
                offset=next((d for d in (0,20,-20,40,-40,60) if all(abs(x-a)>22 or abs(y-r-10+d-b)>16 for a,b in used)),80)
                label_y=max(top+4,min(bottom,y-r-10+offset));used.append((x,label_y))
                text(x,label_y,i+1,size=16,anchor='middle')
            if kind=='bubble':text(36,bottom+92,'面積：'+series[2]['name']+' ('+opt['size_unit']+')','#CBD5E1',17)

        elif kind=='funnel':
            vals=series[0]['values']; peak=vals[0];band=(bottom-top)/len(labels)
            for i,(label,v) in enumerate(zip(labels,vals)):
                # Stage rectangle width is linear to count; no invented trapezoid areas.
                w=v/peak*460;y=top+i*band
                begin(f'{label}：{number(v)} {data["unit"]}；首階段保留 {v/peak*100:.1f}%')
                rect(260+(460-w)/2,y+5,w,band-10,colors[i%len(colors)],radius=4);end()
                lines(36,y+band/2-5,label,12,'#CBD5E1',17,maximum=4)
                text(750,y+band/2,number(v)+' '+data['unit'],size=18)
                rate='首階段 100%' if i==0 else ('上階轉換 —' if vals[i-1]==0 else f'上階轉換 {v/vals[i-1]*100:.1f}%')
                text(750,y+band/2+23,rate,'#94A3B8',15)

        elif kind=='gantt':
            vals=[v for s in series for v in s['values']];lo,hi=min(vals),max(vals)
            if hi==lo:hi=lo+1
            left=270
            sx=lambda v:left+(v-lo)/(hi-lo)*(right-left)
            ticks=sorted(set(round(lo+(hi-lo)*i/4) for i in range(5))) if opt.get('time_origin') else [lo+(hi-lo)*i/4 for i in range(5)]
            for v in ticks:
                x=sx(v);path(f'M{x:g} {top}V{bottom}',dash='3 5')
                value=(date.fromisoformat(opt['time_origin'])+timedelta(days=v)).isoformat() if opt.get('time_origin') else number(v)
                text(x,bottom+28,value,'#94A3B8',14,'middle')
            band=(bottom-top)/len(labels)
            for i,label in enumerate(labels):
                y=top+band*(i+.5)
                lines(36,y-6,label,13,'#CBD5E1',17,maximum=4)
                if len(series)==4:
                    a,b=(s['values'][i] for s in series[2:]);rect(sx(a),y-18,sx(b)-sx(a),6,'#94A3B8')
                a,b=(s['values'][i] for s in series[:2]);progress=opt['progress'][i]
                begin(f'{label}：{number(a)}–{number(b)} {data["unit"]}'+(f'；{progress:g}%' if progress is not None else '；未提供進度'))
                if a==b:
                    x=sx(a);path(f'M{x:g} {y-7}l7 7l-7 7l-7 -7Z',colors[0],colors[0])
                else:
                    rect(sx(a),y-8,sx(b)-sx(a),18,colors[0],radius=3)
                    if progress is not None:rect(sx(a),y-8,(sx(b)-sx(a))*progress/100,18,colors[1],radius=3)
                end()
                if progress is not None:text(min(right-28,sx(b)),y+30,f'{progress:g}%','#CBD5E1',14,'middle')

        elif kind=='treemap':
            vals=series[0]['values'];total=sum(vals);parents=opt.get('parents',['']*len(labels))
            tree={}
            for i,(parent,v) in enumerate(zip(parents,vals)):
                if not v:continue
                node=tree
                for name in filter(None,parent.split('/')):node=node.setdefault(name,{})
                node['\0'+str(i)]=v
            def weight(node):return sum(weight(v) if isinstance(v,dict) else v for v in node.values())
            def tiles(items,x,y,w,h):
                if len(items)==1:return [(items[0],x,y,w,h)]
                acc=0;half=sum(v[2] for v in items)/2;split=1
                for j,item in enumerate(items[:-1],1):
                    acc+=item[2]
                    if acc>=half:split=j;break
                    split=j
                # Pick the partition closest to half, not the number of nodes.
                split=min(range(1,len(items)),key=lambda j:abs(sum(v[2] for v in items[:j])-half))
                fraction=sum(v[2] for v in items[:split])/(half*2)
                if w>=h:return tiles(items[:split],x,y,w*fraction,h)+tiles(items[split:],x+w*fraction,y,w*(1-fraction),h)
                return tiles(items[:split],x,y,w,h*fraction)+tiles(items[split:],x,y+h*fraction,w,h*(1-fraction))
            def draw(node,x,y,w,h,depth=0,group=''):
                items=sorted([(key,value,weight(value) if isinstance(value,dict) else value) for key,value in node.items()],key=lambda v:-v[2])
                for (key,value,amount),tx,ty,tw,th in tiles(items,x,y,w,h):
                    if isinstance(value,dict):
                        draw(value,tx,ty,tw,th,depth+1,key)
                        rect(tx,ty,tw,th,'none','#CBD5E1')
                    else:
                        i=int(key[1:]);color=colors[i%len(colors)]
                        begin((parents[i]+' / ' if parents[i] else '')+labels[i]+f'：{number(amount)} {data["unit"]}；{amount/total*100:.1f}%')
                        rect(tx,ty,tw,th,color,'#0B0F17')
                        if tw>94 and th>75:
                            maxchars=max(4,int((tw-20)/19))
                            if group:text(tx+12,ty+22,group[:maxchars],'#0B0F17',14)
                            lines(tx+12,ty+(46 if group else 28),labels[i],maxchars,'#0B0F17',18,maximum=1)
                            if th>100:text(tx+12,ty+(74 if group else 58),f'{number(amount)} · {amount/total*100:.1f}%','#0B0F17',16)
                        end()
            draw(tree,36,top,888,bottom-top)

        for i,line in enumerate(note_lines):text(36,foot+i*25,line,'#94A3B8',16)
        parts.append('</svg>')
        return '\n'.join(parts)

    @classmethod
    def _chart_svg(cls, data):
        if data["chart_type"] == "quadrant":
            return cls._quadrant_svg(data)
        if data["chart_type"] not in {"bar", "horizontal_bar", "line"}:
            return cls._template_chart_svg(data)
        esc = html.escape
        horizontal = data["chart_type"] == "horizontal_bar"
        line = data["chart_type"] == "line"
        width = 960
        labels, series = data["labels"], data["series"]
        count, groups = len(labels), len(series)
        longest_label = max(len(cls._wrap(label, 14)) for label in labels)
        plot_height = max(360, count * max(groups*32+24, longest_label*22+12)) if horizontal else 360
        left, top, right = (260 if horizontal else 105), 148, 65
        bottom = top + plot_height
        plot_width = width-left-right
        all_values = [v for item in series for v in item["values"]]
        # Zero is always included; truncated bar axes exaggerate differences.
        low, high = min(0, min(all_values)), max(0, max(all_values))
        if low == high:
            high = low + 1
        step_raw = (high-low) / 5
        power = 10 ** math.floor(math.log10(step_raw))
        step = next(v for v in (1, 2, 2.5, 5, 10) if v*power >= step_raw) * power
        low, high = math.floor(low/step)*step, math.ceil(high/step)*step
        def scale(v):
            ratio = (v-low)/(high-low)
            return left + ratio*plot_width if horizontal else bottom-ratio*plot_height
        footnotes = [data["note"]] if data["note"] else []
        footnotes.extend("來源："+s for s in data["sources"])
        foot_lines = [part for note in footnotes for part in cls._wrap(note, 64)]
        delta = None
        if len(series) == 1 and count == 2:
            a, b = series[0]["values"]
            if a > 0 and b >= 0:
                delta = (b-a)/a*100
        label_rows = max(len(cls._wrap(label, max(5, plot_width/count/18))) for label in labels)
        footer_y = bottom + (65 if horizontal else 65+label_rows*21)
        height = footer_y + (60 if delta is not None else 0) + 28*len(foot_lines) + 40 + (100 if groups > 1 else 0)
        font = os.environ.get("OPENWEBUI_DIAGRAM_FONT") or ("PingFang TC" if sys.platform == "darwin" else "Microsoft JhengHei" if sys.platform == "win32" else "Noto Sans CJK TC")
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc" data-chart-type="{data["chart_type"]}">',
            f'<title id="chart-title">{esc(data["title"])}</title><desc id="chart-desc">{esc(data["kind_label"]+"；單位："+data["unit"])}</desc>',
            f'<rect width="{width}" height="{height}" rx="20" fill="#0B0F17"/>',
            f'<style>text {{ font-family: "{esc(font)}"; }}</style><g fill="#F8FAFC">']
        def text(x, y, content, color="#F8FAFC", size=16, anchor="start", **attrs):
            extra = " ".join(f'{key.replace("_", "-")}="{esc(str(value))}"' for key, value in attrs.items())
            parts.append(f'<text x="{x:g}" y="{y:g}" fill="{color}" font-size="{size}" text-anchor="{anchor}" {extra}>{esc(str(content))}</text>')
        title_lines = cls._wrap(data["title"], 44)
        for i, title in enumerate(title_lines[:2]):
            text(36, 40+i*29, title, size=24, font_weight=600)
        text(36, 112, data["kind_label"]+" · 單位："+data["unit"], "#94A3B8")
        colors = ["#3478F6", "#19B5A5", "#E8B760", "#B39DF3"]
        if groups > 1:
            for index, item in enumerate(series):
                x, y = 36+(index%2)*450, height-80+(index//2)*40
                parts.append(f'<rect x="{x}" y="{y}" width="12" height="12" rx="3" fill="{colors[index]}"/>')
                for row, content in enumerate(cls._wrap(item["name"], 28)):
                    text(x+19, y+11+row*18, content, "#CBD5E1", 14)
        tick = low
        for _ in range(12):
            if tick > high+step/100:
                break
            at = scale(tick)
            if horizontal:
                parts.append(f'<path d="M {at:g} {top} V {bottom}" stroke="#253044" stroke-dasharray="3 5"/>')
                text(at, bottom+30, cls._chart_number(tick), "#94A3B8", 14, "middle")
            else:
                parts.append(f'<path d="M {left} {at:g} H {width-right}" stroke="#253044" stroke-dasharray="3 5"/>')
                text(left-14, at+5, cls._chart_number(tick), "#94A3B8", 14, "end")
            tick += step
        if not line:
            origin = scale(0)
            parts.append(f'<path d="M {origin:g} {top} V {bottom}" stroke="#64748B"/>' if horizontal else f'<path d="M {left} {origin:g} H {width-right}" stroke="#64748B"/>')
        band = (plot_height if horizontal else plot_width)/count
        for index, label in enumerate(labels):
            if horizontal:
                for row, content in enumerate(cls._wrap(label, 14)):
                    text(left-20, top+band*(index+.5)-10+row*21, content, "#CBD5E1", 16, "end")
            else:
                if line and index % max(1, math.ceil(count/6)) and index != count-1:
                    continue
                for row, content in enumerate(cls._wrap(label, max(5, band/18))):
                    text(left+band*(index+.5), bottom+30+row*21, content, "#CBD5E1", 15, "middle")
        for si, item in enumerate(series):
            points = []
            bar_size = min(104, band*.66/groups)
            for index, value in enumerate(item["values"]):
                center = (top if horizontal else left)+band*(index+.5)
                offset = (si-(groups-1)/2)*bar_size
                at = scale(value)
                label = cls._chart_number(value)
                tooltip = esc(f'{labels[index]} · {item["name"]}：{label} {data["unit"]}')
                parts.append(f'<g tabindex="0" role="img" aria-label="{tooltip}"><title>{tooltip}</title>')
                if line:
                    points.append((center, at))
                    parts.append(f'<circle cx="{center:g}" cy="{at:g}" r="5" fill="{colors[si]}" stroke="#0B0F17" stroke-width="2"/>')
                    if count <= 8 and groups <= 2:
                        text(center, at-15-si*7, label, colors[si], 15, "middle")
                elif horizontal:
                    origin = scale(0)
                    parts.append(f'<rect x="{min(origin,at):g}" y="{center+offset-bar_size*.42:g}" width="{abs(at-origin):g}" height="{bar_size*.84:g}" rx="5" fill="{colors[si]}"/>')
                    # Keep negative labels out of the category-label gutter.
                    inside = value < 0 and at-left < 70
                    text(at+9 if value >= 0 or inside else at-9, center+offset+5, label, size=15, anchor="start" if value >= 0 or inside else "end")
                else:
                    origin = scale(0)
                    parts.append(f'<rect x="{center+offset-bar_size*.42:g}" y="{min(origin,at):g}" width="{bar_size*.84:g}" height="{abs(at-origin):g}" rx="7" fill="{colors[si]}"/>')
                    text(center+offset, at-12 if value >= 0 or bottom-at < 30 else at+22, label, size=15, anchor="middle")
                parts.append('</g>')
            if line:
                coords = " ".join(f'{x:g},{y:g}' for x,y in points)
                dash = ' stroke-dasharray="8 5"' if si % 2 else ''
                parts.append(f'<polyline points="{coords}" fill="none" stroke="{colors[si]}" stroke-width="3"{dash}/>')
                text(points[-1][0], points[-1][1]-28-si*20, item["name"], colors[si], 13, "end")
        if delta is not None:
            direction = "增加" if delta >= 0 else "減少"
            good = (delta >= 0 and data["better"] == "higher") or (delta <= 0 and data["better"] == "lower")
            color = "#22C55E" if good and delta else "#F59E0B" if data["better"] != "neutral" and delta else "#38BDF8"
            text(36, footer_y, f'{delta:+.1f}%', color, 27, font_weight=600)
            # Neutral wording: a larger number need not be an improvement.
            text(195, footer_y, f'第二項相對第一項{direction}（同一系列）', "#CBD5E1", 16)
            footer_y += 54
        for row, content in enumerate(foot_lines):
            text(36, footer_y+row*28, content, "#94A3B8", 15)
        parts.append('</g></svg>')
        return "\n".join(parts)

    @classmethod
    def _quadrant_svg(cls, data):
        """Relative positioning, not a market-share chart; numbered keys avoid label collisions."""
        esc = html.escape
        foot_lines = [line for note in [data["note"], *["來源："+s for s in data["sources"]]] for line in cls._wrap(note, 88)]
        width, height = 1120, max(860, 810+len(foot_lines)*22)
        font = os.environ.get("OPENWEBUI_DIAGRAM_FONT") or ("PingFang TC" if sys.platform == "darwin" else "Microsoft JhengHei" if sys.platform == "win32" else "Noto Sans CJK TC")
        left, top, size = 100, 155, 520
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc" data-chart-type="quadrant">',
            '<title id="chart-title">'+esc(data["title"])+'</title>',
            '<desc id="chart-desc">'+esc(data["kind_label"]+'；'+data["note"])+'</desc>',
            f'<rect width="{width}" height="{height}" rx="22" fill="#0B0F17"/>',
            '<style>text{font-family:"'+esc(font)+'"}</style>']
        def text(x, y, value, color="#F8FAFC", font=18, anchor="start"):
            parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{font}" text-anchor="{anchor}">'+esc(str(value).replace('→','至'))+'</text>')
        text(36, 48, data["title"], font=27)
        text(36, 82, data["kind_label"]+' · 非市佔率；相對座標不等於客觀評分', '#F59E0B', 17)
        for dx, dy, fill in [(0,0,"#122A30"),(260,0,"#172D45"),(0,260,"#172235"),(260,260,"#292639")]:
            parts.append(f'<rect x="{left+dx}" y="{top+dy}" width="260" height="260" fill="{fill}"/>')
        for index in range(5):
            x, y = left+index*size/4, top+index*size/4
            parts.append(f'<path d="M{x} {top}V{top+size} M{left} {y}H{left+size}" stroke="#334155" stroke-width="1"/>')
        for i,line in enumerate([data["series"][0]["name"][j:j+26] for j in range(0,len(data["series"][0]["name"]),26)]):
            text(left+size/2, top+size+52+i*23, line, '#CBD5E1', 18, 'middle')
        parts.append(f'<text transform="translate(38 {top+size/2}) rotate(-90)" fill="#CBD5E1" font-size="16" text-anchor="middle">'+esc(data["series"][1]["name"].replace('→','至'))+'</text>')
        text(left, top+size+23, '低', '#94A3B8', 14)
        text(left+size, top+size+23, '高', '#94A3B8', 14, 'end')
        text(left-12, top+7, '高', '#94A3B8', 14, 'end')
        text(left-12, top+size, '低', '#94A3B8', 14, 'end')
        text(685, 150, '品牌／方案', font=21)
        used = []
        for i, label in enumerate(data["labels"]):
            xvalue, yvalue = (s["values"][i] for s in data["series"])
            x, y = left+xvalue*size, top+(1-yvalue)*size
            # Offset overlapping badge labels, not the actual data points.
            bx, by = x, y
            for _ in range(18):
                if all(math.hypot(bx-a, by-b) >= 35 for a,b in used):
                    break
                by += 36 if by < top+size-44 else -72
            used.append((bx,by))
            color = '#22C55E' if re.search(r'ASUS', label, re.I) else '#38BDF8'
            parts.append('<g tabindex="0"><title>'+esc(f'{label}：X={xvalue:g}，Y={yvalue:g}；'+data["kind_label"])+'</title>')
            if (bx,by) != (x,y):
                parts.append(f'<path d="M{x} {y}L{bx} {by}" stroke="{color}"/><circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
            parts.append(f'<circle cx="{bx}" cy="{by}" r="16" fill="#0B0F17" stroke="{color}" stroke-width="2"/>')
            text(bx, by+5, i+1, color, 15, 'middle')
            parts.append('</g>')
            text(685, 191+i*39, str(i+1).zfill(2), color, 16)
            # Wrap long names; preserve the full label in the accessible table.
            chunks = [label[j:j+21] for j in range(0,len(label),21)]
            for j, chunk in enumerate(chunks[:2]):
                text(724, 191+i*39+j*17, chunk, '#F8FAFC', 16 if len(chunks)>1 else 18)
        for i, line in enumerate(foot_lines):
            text(36, 790+i*22, line, '#94A3B8', 15)
        parts.append('</svg>')
        return ''.join(parts)

    @classmethod
    def _chart_rows(cls, data):
        kind,opt=data['chart_type'],data.get('options',{})
        units=[data['unit']]*len(data['series'])
        if kind in {'scatter','bubble'}:
            units=[opt['x_unit'],opt['y_unit']]+([opt['size_unit']] if kind=='bubble' else [])
        headers=['類別']+[s['name']+' ('+units[i]+')' for i,s in enumerate(data['series'])]
        rows=[[label,*[s['values'][i] for s in data['series']]] for i,label in enumerate(data['labels'])]
        extras=[]
        if kind=='waterfall':
            total=0;starts=[];ends=[]
            for v,role in zip(data['series'][0]['values'],opt['roles']):
                starts.append(0 if role=='total' else total)
                total=v if role=='total' else total+v
                ends.append(total)
            extras=[('角色',opt['roles']),('起點',starts),('累計',ends)]
        if kind=='treemap' and 'parents' in opt: extras=[('父層',opt['parents'])]
        if kind=='gantt':
            if opt.get('tasks'):
                for j,key in enumerate(['start','end','planned_start','planned_end'][:len(data['series'])]):
                    headers[j+1]=data['series'][j]['name']+' (日期)'
                    for i,row in enumerate(rows): row[j+1]=opt['tasks'][i][key]
            extras=[('完成率 (%)',[p if p is not None else '未提供' for p in opt['progress']])]
        if kind in {'pie','doughnut','treemap'}:
            total=sum(data['series'][0]['values'])
            extras.append(('佔所列合計 (%)',[v/total*100 for v in data['series'][0]['values']]))
        if kind=='percent_stacked_column':
            for s in data['series']:
                extras.append((s['name']+' (%)',[s['values'][i]/sum(t['values'][i] for t in data['series'])*100 for i in range(len(rows))]))
        if kind=='gauge':
            extras=[('量尺下限',[opt.get('min',0)]),('量尺上限',[opt.get('max',100)])]
            if 'target' in opt:extras.append(('目標',[opt['target']]))
        for header,values in extras:
            headers.append(header)
            for row,value in zip(rows,values):row.append(value)
        return [headers,*rows]

    async def render_data_chart(self, title: str, labels: list[str], series: list[dict], unit: str,
        data_kind: str, chart_type: str = "auto", sources: list[str] | None = None,
        note: str = "", better: str = "neutral", options: dict | None = None, __event_emitter__=None, __request__=None) -> str:
        """套用本機統計圖表樣板產生 PNG/SVG/HTML/CSV，不必生成程式碼。chart_type=auto/bar/horizontal_bar/line/area/tornado/radar/gauge/waterfall/pie/doughnut/stacked_column/percent_stacked_column/treemap/scatter/bubble/gantt/funnel/quadrant。labels 與 series=[{name,values}] 等長，數值有限，unit 必填。
        一般 series 同單位；tornado 恰兩組非負值；radar 3–8 軸最多3組同量尺 options={max:100}；gauge 一個label一組數值 options={min:0,max:100,target:80}；waterfall 單組首值為總額，其餘為增減，可 options={roles:['total','change','total']}，工具驗證合計。pie/doughnut 單組非負，最多7類；stacked_column 非負分量，percent_stacked_column 逐柱計算100%；treemap 單組非負葉節點，可 options={parents:['硬體/算力','硬體/網路']}。scatter 恰 X/Y 兩組，bubble 恰 X/Y/面積三組，options={x_unit:'W',y_unit:'tokens/s',size_unit:'元'}；散點與氣泡容許不同軸單位，size_unit 只用於bubble。gantt：labels為任務，series=[]，options={tasks:[{start:'2026-10-01',end:'2026-10-05',progress:40}]}，可全數附 planned_start/planned_end；或數字型開始/結束兩組，options={progress:[40,70]}。funnel 單組非負遞減、同母體。quadrant 恰 X/Y 兩組 0–1 相對座標，定性定位須 illustrative，非市佔。
        data_kind=measured/reported/estimated/illustrative/user_provided；引用/實測要sources，估算/示意要note。不可編造或補零；better=higher/lower/neutral。先簡短文字後呼叫工具，回傳真實成品連結，不展示繪圖代碼。"""
        # quadrant: labels are brands; exactly two series name X/Y axes and
        # contain normalized relative positions. Qualitative maps must use
        # illustrative + an explicit non-survey note, never market-share %.
        await self._status(__event_emitter__, "正在整理數據並繪製比較圖…")
        try:
            data = self._chart_data(title, labels, series, unit, chart_type, data_kind, sources, note, better, options)
            output = self._static_output_dir()
            token = f"chart-{int(time.time())}-{uuid.uuid4().hex[:8]}"
            svg, png, preview, csv_path = [output / (token+suffix) for suffix in (".svg", ".png", ".html", ".csv")]
            svg_text = self._chart_svg(data)
            svg.write_text(svg_text, encoding="utf-8")
            # Use the same installed CJK-aware export path as architecture diagrams.
            result = await asyncio.to_thread(subprocess.run,
                [sys.executable, str(self._runtime_root()/"scripts/fireworks.py"), "export-png", str(svg), str(png), "--width", "1600"],
                capture_output=True, text=True, timeout=60)
            if result.returncode or not png.is_file():
                raise RuntimeError("PNG 匯出失敗，請檢查伺服器字型與繪圖環境")
            def safe_cell(value):
                # Spreadsheet formula injection applies to textual cells only.
                return "'"+value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
            rows = self._chart_rows(data)
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerows([[safe_cell(cell) for cell in row] for row in rows])
                writer.writerow(["資料性質", data["kind_label"]])
                writer.writerow(["說明", safe_cell(data["note"])])
                writer.writerows([["來源", safe_cell(s)] for s in data["sources"]])
            table = "<thead><tr>"+"".join("<th scope='col'>"+html.escape(str(c))+"</th>" for c in rows[0])+"</tr></thead><tbody>"
            table += "".join("<tr>"+"".join("<td>"+html.escape(str(c))+"</td>" for c in row)+"</tr>" for row in rows[1:])+"</tbody>"
            preview.write_text('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                +'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'">'
                +'<title>'+html.escape(data["title"])+'</title><style>body{margin:0;background:#0B0F17;color:#F8FAFC;font:16px/1.5 system-ui}main{max-width:1100px;margin:auto;padding:16px}.chart,.table{overflow:auto}.chart svg{display:block;width:100%;min-width:640px;height:auto}table{border-collapse:collapse;width:100%;margin-top:24px}th,td{padding:12px;text-align:left;border-bottom:1px solid #334155;min-width:90px;overflow-wrap:anywhere}a{color:#38BDF8;display:inline-flex;align-items:center;min-height:44px;padding:0 12px;margin:4px}a:focus-visible{outline:2px solid #F8FAFC}svg g:focus{outline:2px solid #38BDF8}caption{text-align:left}.note{overflow-wrap:anywhere}</style><main><p>可橫向捲動放大檢視；圖下方提供完整數據。</p><div class="chart" tabindex="0" role="region" aria-label="圖表，可左右捲動">'
                +svg_text+'</div><a href="'+csv_path.name+'" download>下載 CSV</a><a href="'+svg.name+'" download>下載 SVG</a><p class="note">'+html.escape(data['note'])+'</p>'
                +''.join('<p class="note">來源：'+html.escape(s)+'</p>' for s in data['sources'])+'<div class="table" tabindex="0" role="region" aria-label="完整資料表，可左右捲動"><table><caption>'+html.escape(data["kind_label"])+" · "+html.escape(data["unit"])+'</caption>'+table+'</table></div></main></html>', encoding="utf-8")
            prefix = "/static/openwebui-generated/fireworks/"
            alt = re.sub(r"[\[\]\\]", "", data["title"])
            artifact = f'![{alt}]({prefix}{png.name})\n\n[放大／資料表]({prefix}{preview.name}) · [SVG]({prefix}{svg.name}) · [CSV]({prefix}{csv_path.name})'
            if __request__ is not None:
                state = getattr(__request__.state, "fireworks_diagram", None)
                if state is not None:
                    state.setdefault("chart_artifacts", []).append(artifact)
            await self._status(__event_emitter__, "比較圖完成", done=True, hidden=True)
            return artifact
        except Exception as error:
            await self._status(__event_emitter__, "圖表未完成", done=True)
            return "數值圖表未產生："+self._clean(error, 240)+"。請保留文字分析並說明缺少哪些資料，不要編造數值或輸出繪圖代碼。"
