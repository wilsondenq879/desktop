"""
title: Fireworks 技術圖表守門員
description: 伺服器 Renderer、請求隔離的串流緩衝，以及 content/output 一致的成品回覆。
version: 13.0.0
"""

import importlib.util
import asyncio
import copy
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path


class Filter:
    _FIREWORKS_TOOL_ID = "openwebui_fireworks_renderer"
    # This adapter has been observed returning prose/SVG instead of native
    # tool calls. Use data-only planning and let the server own rendering.
    _STRUCTURED_MODELS = {"gemma4:26b-mlx"}

    _REPORT_INSTRUCTION = """[openwebui-mixed-visual-report-v1]
本題需要完整文字報告與圖像，不可只寫摘要或只回傳圖表資料。先立刻給簡短結論，再完成分節分析與需求中的成品。
架構/拓撲/資料路徑用 render_technical_architecture（title,nodes,edges,visual_family,layout）；數值統計圖用 render_data_chart（title,labels,series,unit,data_kind,chart_type,options）。這兩類工具都在伺服器執行，不需要桌面連線或 Open Terminal。兩類可在同一份報告使用，完成其中一張不代表整份報告完成。每個實際需要的圖只畫一次。
架構須具體設備、分支、資料/控制流，避免全串成一條線；未知規格標示待核實。只需語意節點與連線，伺服器負責排版與圖示。
數值比較必須有可靠的同單位/同條件資料；實測與引用提供 sources，估算/示意明標假設。缺乏 RDMA 與 TCP 的可比實測時不要捏造延遲、CPU負載或速度倍數，可用兩條資料路徑的架構圖加定性比較表，明示沒有數值圖的理由。不能把25G埠速當應用實測吞吐。
研究、產品規格與市場結論須查證來源。先研究再繪製依據充分的圖，不把既有示意數字當事實。圖庫按需用 search_diagram_assets，勿載入整庫。
回答使用繁體中文，保留完整報告、分析、限制及真實成品連結。禁止 {{render_data_chart}} 等佔位符、假網址、JSON/React/SVG/Mermaid/ASCII原始碼。只宣稱實際產生成品的項目完成。"""

    @classmethod
    def _visual_intents(cls, text):
        chart=cls._wants_chart(text)
        architecture=cls._wants_diagram(text) and (not chart or bool(re.search(r'架構|拓撲|階層|分層|流程|architecture|topology|data.?path',text,re.I)))
        report=bool(re.search(r'完整.{0,12}(?:報告|評估|分析)|評估報告|研究報告|分析報告|完整報告|full report|assessment report',text,re.I))
        return chart,architecture,report

    _CHART_PLAN_INSTRUCTION = """這是統計圖表的資料整理階段，不是使用者回覆。只回傳一個緊湊 JSON 物件，不要工具、程式碼、Markdown、圖片網址或繪圖幾何。伺服器會套用已完成的樣板，不需要你寫繪圖程式。
欄位：title（繁體中文）、labels、series=[{name,values:[數字]}]、unit、chart_type、data_kind、sources、note、better、options。values 與 labels 等長。不可捏造、補零、假裝有來源。沒有足夠數據只回傳 {"error":"缺少哪些數據"}。
chart_type 依問題選 bar/horizontal_bar/line/area/tornado/radar/gauge/waterfall/pie/doughnut/stacked_column/percent_stacked_column/treemap/scatter/bubble/gantt/funnel/quadrant。比較系列同單位；使用者提供數據用 user_provided；虛構樣式用 illustrative 並 note 說明。真實引用/實測要 sources，無來源不可冒充 reported/measured。better 為 higher/lower/neutral，未指定用 neutral。
radar：labels=3–8個維度，series為各方案數值，共同量尺，options={max:100}。gauge：1個label、1組1值，options={min:0,max:100,target:85}，目標未知省略target。tornado：恰兩組非負。
waterfall：單組首值總額，之後增減，若含最後合計 options.roles=['total','change','total']，長度與 labels 一致。pie/doughnut：單組非負最多7類。stacked_column及percent_stacked_column：輸入原始非負分量，不填自行臆造比例。treemap：單組葉節點權重，可 options.parents=[父層路徑]。
scatter：兩組，先X後Y，options={x_unit:'W',y_unit:'tokens/s'}；bubble：第三組是面積值，另加 options.size_unit。gantt：labels=任務，series=[]，options={tasks:[{start:'2026-10-01',end:'2026-10-05',progress:40}]}，日期必須來自本題，未知進度省略。funnel：單組同母體非負遞減。quadrant：X/Y兩組0–1相對位置，定性示意不是市佔。其他 options={}。"""

    @staticmethod
    def _chart_plan_schema():
        return {'type':'object','properties':{
            'title':{'type':'string'},'labels':{'type':'array','items':{'type':'string'}},
            'series':{'type':'array','items':{'type':'object','properties':{'name':{'type':'string'},'values':{'type':'array','items':{'type':'number'}}},'required':['name','values']}},
            'unit':{'type':'string'},'chart_type':{'type':'string'},'data_kind':{'type':'string'},
            'sources':{'type':'array','items':{'type':'string'}},'note':{'type':'string'},'better':{'type':'string'},
            'options':{'type':'object'},'error':{'type':'string'}},'additionalProperties':False}

    @staticmethod
    def _plan_schema():
        tone = {"type":"string","enum":["default","network","active","remote","blocked"]}
        return {"type":"object","additionalProperties":False,"properties":{
            "title":{"type":"string"}, "subtitle":{"type":"string"},
            "layout":{"type":"string","enum":["auto","layered","star","dual_compute","rack","dataflow","ecosystem"]},
            "nodes":{"type":"array","minItems":2,"maxItems":14,"items":{"type":"object","additionalProperties":False,
                "properties":{"id":{"type":"string"},"label":{"type":"string"},"detail":{"type":"string"},"level":{"type":"integer","minimum":0,"maximum":5},"icon":{"type":"string"},"group":{"type":"string"},"tone":tone},
                "required":["id","label","detail","level","icon","group","tone"]}},
            "edges":{"type":"array","minItems":1,"maxItems":22,"items":{"type":"object","additionalProperties":False,
                "properties":{"from":{"type":"string"},"to":{"type":"string"},"label":{"type":"string"},"tone":tone,"direction":{"type":"string","enum":["none","forward","both"]},"dashed":{"type":"boolean"}},
                "required":["from","to","label","tone","direction","dashed"]}}},
            "required":["title","subtitle","layout","nodes","edges"]}

    _PLAN_INSTRUCTION = """這是架構規劃資料階段，不是給使用者看的回覆。只回傳符合 schema 的一個 JSON 物件（title,subtitle,layout,nodes,edges），伺服器會將它轉為真正 PNG/SVG 成品。
不要工具呼叫、程式碼圍欄、SVG/HTML、Mermaid、ASCII、座標或文字分析。不要聲稱已畫圖。使用緊湊 JSON，不縮排。只列需求明確提到的設備，禁止額外加入未提及的設備。label 最多16字、detail 最多12字；title/label/detail/連線標籤用繁體中文。id 用短英文。
忠實保留使用者點名的設備、平行分支與角色，每個設備各一個節點。level=0–5 由上至下，同層設備用相同 level，不得把所有設備串成直線。edges 的 from/to 必須是實際存在的節點 id。實體連線 direction=none；有明確方向的邏輯資料流才用 forward/both。icon 可用 users,vpn,router,switch,rdma-switch,aggregation-switch,mini-pc,workstation,network-card,nas,gpu,api,mcp,cloud,agent。tone 用 network(資料),active(高速),remote(控制/遠端),default。
規格未知不發明，寫待確認；GX10 和一般 AI 工作站分開表示，不因同列而假定 GX10 可安裝 Intel PCIe 卡。Intel E800 僅畫在有已知擴充介面的工作站側，未知連線能力須標示待確認。"""
    _ASSET_INSTRUCTION = """本機已安裝 Lucide、Lobe Icons、Dashboard Icons、Simple Icons 與網通硬體 SVG。icon 可以省略或空字串讓伺服器自動選圖；已知 ID 可用 hardware:mini-ai-pc、hardware:ai-workstation、hardware:pcie-nic、hardware:desktop-switch、lobe:ollama、lobe:qwen-color、simple:asus、lucide:router。原有 nas/router/vpn 等 ID 仍有效。品牌徽章會自動辨識。原生模式只有找不到圖示時才呼叫 search_diagram_assets，勿把整份圖庫加入上下文。
layout 依本題選 auto/layered(分層)/star(中心)/dual_compute(雙機)/rack(機櫃)/dataflow(橫向資料流)/ecosystem(生態圈)。不確定選 auto。僅在明確要架內設備時 group=rack，其他 group 依本題或空字串。機櫃圖僅概念，尺寸和安裝相容性未確認就明標待核實。構圖與圖示不能改變或編造真實連線、設備、規格。"""
    _PLAN_INSTRUCTION += '\n'+_ASSET_INSTRUCTION

    @staticmethod
    def _needs_host_constraint(text):
        return bool(re.search(r"GX10",text,re.I) and re.search(r"E800",text,re.I) and re.search(r"工作站|workstation",text,re.I) and not re.search(r"假設|hypothetical|已確認.{0,30}GX10",text,re.I))

    @classmethod
    def _enforce_host_constraint(cls, data, text):
        """Enforce the plan's explicit no-unverified-PCIe-installation rule.

        Never add product nodes/specs; only disambiguate the already requested
        GX10, workstation and expansion card. Unverified GX10 access stays a
        clearly dashed proposal, not a claim of RDMA/PCIe compatibility.
        """
        if not cls._needs_host_constraint(text):
            return data
        data = copy.deepcopy(data)
        nodes, edges = data.get("nodes", []), data.get("edges", [])
        gx = next((n for n in nodes if re.search(r"GX10",n.get("label", ""),re.I)),None)
        ws = next((n for n in nodes if re.search(r"工作站|workstation",n.get("label", ""),re.I) and n is not gx),None)
        nic = next((n for n in nodes if re.search(r"E800",n.get("label", ""),re.I)),None)
        access = next((n for n in nodes if re.search(r"10G",n.get("label", ""),re.I) and re.search(r"switch|交換器",n.get("label", ""),re.I)),None)
        fabric = next((n for n in nodes if re.search(r"25G|RDMA",n.get("label", ""),re.I) and re.search(r"switch|交換器",n.get("label", ""),re.I)),None)
        if not (gx and ws and nic and access):
            return data
        gx["icon"], ws["icon"], nic["icon"] = "mini-pc","workstation","network-card"
        for edge in edges:
            pair = {edge.get("from"),edge.get("to")}
            if pair == {gx["id"],nic["id"]}:
                if edge.get("from") == gx["id"]:
                    edge["from"] = ws["id"]
                else:
                    edge["to"] = ws["id"]
                edge.update(label="PCIe（工作站側）",direction="none",dashed=False)
        if any({e.get("from"),e.get("to")} == {nic["id"],ws["id"]} for e in edges) and fabric:
            edges = [e for e in edges if {e.get("from"),e.get("to")} != {fabric["id"],ws["id"]}]
        if fabric and not any({e.get("from"),e.get("to")}=={fabric["id"],nic["id"]} for e in edges):
            edges.append({"from":fabric["id"],"to":nic["id"],"label":"25G RDMA","direction":"none","dashed":False,"tone":"active"})
        for edge in edges:
            if gx["id"] in (edge.get("from"),edge.get("to")):
                if fabric and edge.get("from")==fabric["id"]:
                    edge["from"] = access["id"]
                elif fabric and edge.get("to")==fabric["id"]:
                    edge["to"] = access["id"]
                edge.update(label="網路介面待核實",direction="none",dashed=True,tone="default")
        if not any(gx["id"] in (e.get("from"),e.get("to")) for e in edges):
            edges.append({"from":access["id"],"to":gx["id"],"label":"網路介面待核實","direction":"none","dashed":True,"tone":"default"})
        host_edges = [e for e in edges if {e.get("from"),e.get("to")} == {nic["id"],ws["id"]}]
        if len(host_edges)>1:
            keep = host_edges[0]
            keep.update(label="PCIe（工作站側）",direction="none",dashed=False)
            edges = [e for e in edges if e not in host_edges or e is keep]
        gx["detail"] = "獨立運算節點；網路介面待核實"
        if re.search(r"生態圈|生效圈|架構",gx.get("label", "")):
            gx["label"] = "ASUS GX10"
        if fabric:
            nic["level"] = min(4,int(fabric.get("level",3))+1)
            gx["level"] = ws["level"] = min(5,nic["level"]+1)
        data["edges"] = edges
        return data
    _MARKER = "[openwebui-fireworks-diagram-filter-v7]"
    _INSTRUCTION = """[openwebui-fireworks-diagram-filter-v7]
本題要求完成架構圖。請呼叫工具清單中 render_technical_architecture，傳入依本題設計的 title、nodes、edges、groups 與 visual_family。
請先立刻用 2–3 句繁體中文說明本題的架構設計、分層或主要連線，讓使用者先看到有用的答案，再呼叫繪圖工具。不要只說「我正在畫圖」，不要等圖片完成才開始回答，也不要先寫很長的前言。
這個 Renderer 在 Open WebUI 伺服器執行，不需要手機、桌面或 Open Terminal 連線。不要呼叫 run_command、execute 或把 Skill 名稱當作工具。
節點包含 id、label、detail、level（由上到下從 0 起）、group、tone、icon。請把 label 寫成具體設備／服務，不要只寫「第一層」。
交換器可加 port_groups=[{label:"25G",count:4,tone:"active"}] 畫埠位，只有使用者提供／已核實的埠數與速度才填，否則省略。連線包含 from、to、label、tone、dashed、direction(none/forward/both)。實體連線不要箭頭，邏輯資料流才用方向。tone 可用 network藍、active青綠、remote琥珀、default灰、blocked紅。
忠實保留本題的設備、平行分支與實際關係，區分資料與控制流；不要只把層級名稱全部串成一條直線，也不要為了排版刪掉連線。未知規格須標示為提案。請用繁體中文。工具成功即完成，不要重複繪製。只回傳工具實際產生的圖片與簡短說明，禁止猜測成品網址、placeholder 或貼出繪圖程式碼。"""
    _INSTRUCTION += '\n'+_ASSET_INSTRUCTION
    _CHART_INSTRUCTION = """[openwebui-numeric-chart-v1]
本題涉及數值、組成、關聯或時程。資料足以支持圖型時，主動呼叫 render_data_chart 產生深色成品圖，不要只貼比較表或繪圖代碼。比較或趨勢通常需兩個以上可比較的資料點；單指標 gauge 可一個數值，甘特可一項任務。這是 Open WebUI 伺服器工具，不需要桌面、手機、Open Terminal 或瀏覽器操作。
chart_type：類別／效能比較用 auto 或 bar，長名稱或較多類別用 horizontal_bar，依時間順序的趨勢用 line；多組同單位資料用 series=[{name:系列名,values:[數字,...]},...] 畫分組比較。labels 與每組 values 必須等長，unit 必填。不同單位或不可比的測試條件不得硬畫在同一軸，應分圖或文字說明。
現成樣板也支援 area面積、tornado旋風/蝴蝶（兩組非負共尺度）、radar雷達（3–8軸共同量尺 options.max，預設100，最多3組）、gauge儀表（一個label一組數字，options.min/max/target）、waterfall瀑布（首值總額、其餘正負增減；可options.roles標total/change，由工具驗算）、pie/doughnut圓餅/環形（單組非負，最多7類）、stacked_column總量堆積、percent_stacked_column百分比堆積（不把總量和100%混淆）、treemap矩形樹狀（葉節點單組權重，可options.parents父層路徑）、scatter散點/bubble氣泡（X/Y兩組，氣泡加面積第三組，options.x_unit/y_unit/size_unit分軸標示）、gantt甘特（series=[]，options.tasks=[{start:'2026-10-01',end:'2026-10-05',progress:40}]，labels為任務）、funnel漏斗（同母體遞減階段）。只傳資料選樣板，不用重寫繪圖碼。不強迫所有資料畫長條；依問題關係選圖，沒有支持各維度的資料不可編造雷達評分。甘特日期與統計趨勢是不同語意。
四象限／品牌定位矩陣用 quadrant：labels 為品牌，series 恰有 X/Y 兩組 0–1 相對座標，name 清楚描述低到高的方向；unit=相對位置。主觀定位必須 data_kind=illustrative，note=模型定性示意、非市場調查或市佔率。定位圖不能冒充市佔率；使用者要市佔率但查不到可靠比例時，明確說明無可驗證數據，不能自行改畫定位圖就宣稱已完成市佔研究。禁止 Mermaid quadrantChart，改呼叫 render_data_chart。
data_kind 必填：使用者提供 user_provided、引用 reported、實測 measured、估算 estimated、示意 illustrative。引用／實測必須帶 sources（出處、日期、測試條件），估算／示意必須帶 note 說明假設，不得偷換為實測。未知數字不要編造、不得用 0 補缺值；沒有可靠資料時保留文字分析並明確說明缺少資料，不要為畫圖而捏造數值。IP、型號、版本、埠號不是效能數據。百分比變化由工具計算，better=higher/lower/neutral，不保證數值變大就更好。
用繁體中文回答。先快速輸出1–3句簡短結論與分析，再呼叫樣板工具繪圖，完成後搭配工具回傳的真實圖片連結，再補條件與限制。不要只有圖片、不要猜網址。絕不在對話輸出／串流 JSON、SVG、HTML、React、Mermaid、ASCII 或繪圖程式碼。工具完成即可，不要重複繪製。"""

    @staticmethod
    def _text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(item.get("text", "") for item in value if isinstance(item, dict))
        return ""

    @staticmethod
    def _wants_diagram(text):
        # Ordinary router and coding questions must not become stock diagrams.
        if re.search(r"(?:提供|給我|輸出|顯示).{0,40}(?:原始碼|程式碼|source code)", text, re.I) and not re.search(r"(?:不要|不需|禁止).{0,16}(?:原始碼|程式碼)", text):
            return False
        return bool(re.search(r"(?:繪製|畫出|畫一|畫個|畫張|產生|生成|製作).{0,100}(?:圖|topology|diagram)|(?:draw|render|create|generate).{0,80}(?:diagram|topology)|(?:架構圖|拓撲圖|階層圖|分層圖|流程圖)", text, re.I | re.S))

    @staticmethod
    def _wants_chart(text):
        if re.search(r"(?:提供|給我|輸出|顯示).{0,40}(?:原始碼|程式碼|source code)", text, re.I) and not re.search(r"(?:不要|不需|禁止).{0,16}(?:原始碼|程式碼)", text):
            return False
        if re.search(r"長條圖|柱[狀形]圖|折線圖|趨勢圖|面積圖|旋風圖|蝴蝶圖|雷達圖|儀表[盤板圖]|瀑布圖|圓餅圖|環形圖|堆[積疊].{0,5}圖|矩形樹狀圖|散[點佈]圖|氣泡圖|甘特圖|漏斗圖|數值比較圖|數據圖|圖表|四象限|定位(?:矩陣|圖)|quadrant|positioning map|(?:bar|column|line|area|tornado|butterfly|radar|gauge|waterfall|pie|doughnut|donut|stacked|treemap|scatter|bubble|gantt|funnel) (?:chart|plot)|\btreemap\b|grouped bar", text, re.I):
            return True
        if re.search(r"架構圖|拓撲圖|階層圖|分層圖|流程圖", text):
            return False
        compare = re.search(r"比較|比對|對比|趨勢|成長|改善|效能差|compare|comparison|versus|benchmark|trend|\bvs\b", text, re.I)
        metric = re.search(r"吞吐|延遲|速度|效能|功耗|價格|市佔|銷售|營收|頻寬|數值|數據|比例|佔比|組成|留存|轉換率|預算|進度|tokens?/?s|latency|throughput|watt|revenue|performance|percent|%", text, re.I)
        return bool(compare and (metric or len(re.findall(r"(?<![\w.])\d+(?:\.\d+)?\s*(?:ms|Gbps|Mbps|W|元|%|倍|tokens/s)", text, re.I)) >= 2))

    @staticmethod
    def _state(request):
        if request is None:
            return None
        return getattr(request.state, "fireworks_diagram", None)

    @classmethod
    async def _generate_preface(cls, body, text, request, user):
        """A bounded, small-context text pass before the full tool-enabled pass.

        No tools, skills, model system prompt or long conversation replay. Use
        the selected model with normal access checks, not a different service.
        """
        from open_webui.models.users import Users
        from open_webui.utils.chat import generate_chat_completion
        selected_user = await Users.get_user_by_id(user["id"])
        if selected_user is None:
            return "", None
        snapshot = {key:copy.deepcopy(getattr(request.state, key)) for key in ("bypass_filter", "bypass_system_prompt", "metadata") if hasattr(request.state, key)}
        try:
            model = body.get("model", "")
            chart = cls._wants_chart(text)
            preface_instruction = "你是數據分析助理。根據使用者提供的資料，立刻用兩句繁體中文說明要比較的項目與觀察重點。稍後伺服器會套版產生圖表；此刻不要宣稱已畫完。不要編造數據、結論或來源，缺資料要說明。不要工具、程式碼、JSON、標題或長篇推理。限120中文字。"
            form = {"model":model, "stream":False, "max_tokens":240, "temperature":.2,
                "think":"low" if "gpt-oss" in model.lower() else False,
                "messages":[{"role":"system","content":"你是技術架構助理。根據使用者需求，立刻用兩句繁體中文說明具體架構的分層、設備角色與主要連線。這只是先行設計重點，稍後另一個步驟會完成架構圖。不要工具、程式碼、JSON、ASCII、標題或長篇推理，不要說正在畫圖，不要發明規格。不確定的配置稱為建議。GX10 與一般 AI 工作站分開處理，不能因同列而假定 GX10 可安裝 Intel PCIe 卡，介面能力未知寫待確認。限 120 個中文字。"},
                    {"role":"user","content":text[:2400]}], "metadata":{"task":"architecture_preface"}}
            if chart: form['messages'][0]['content']=preface_instruction
            # The internal OpenAI→Ollama converter reads decoding controls
            # from options, not root-level OpenAI fields. Otherwise the short
            # pass would silently use the model's long-reasoning defaults.
            if (request.app.state.MODELS.get(model) or {}).get("owned_by") == "ollama":
                form["options"] = {"num_predict":320,"temperature":.2,"think":form["think"]}
            else:
                form["reasoning_effort"] = "low"
            response = await generate_chat_completion(request, form, selected_user, bypass_system_prompt=True)
            if not isinstance(response, dict):
                return "", None
            preface = cls._text(((response.get("choices") or [{}])[0].get("message") or {}).get("content")).strip()
            if not chart and cls._needs_host_constraint(text):
                preface = "架構會分開呈現 GX10 與一般 AI 工作站，Intel E800 以工作站擴充介面表示。網路則區分 25G RDMA 骨幹、10G 存取與路由器／VPN 服務層；未核實的 GX10 連線會標示待確認。"
            if not preface or len(preface) > 800 or cls._unsafe_preview(preface):
                return "", response.get("usage")
            return preface+"\n\n", response.get("usage")
        finally:
            for key in ("bypass_filter", "bypass_system_prompt", "metadata"):
                if key in snapshot:
                    setattr(request.state, key, snapshot[key])
                elif hasattr(request.state, key):
                    delattr(request.state, key)

    async def inlet(self, body: dict, __request__=None, __user__=None, __metadata__=None) -> dict:
        if (__metadata__ or {}).get("task"):
            return body
        messages = body.get("messages", [])
        user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        text = self._text(user.get("content"))
        chart,architecture,report = self._visual_intents(text)
        if not chart and not self._wants_diagram(text):
            return body
        if __request__ is not None:
            __request__.state.fireworks_diagram = {"chunks": [], "size": 0, "mode":"chart" if chart else "architecture", "architecture_requested":architecture,"report":report,"mixed":chart and architecture,"intro":"", "pending":"", "preview_blocked":False, "started":time.monotonic(), "model":body.get("model"), "source_text":text}
            if (not chart or body.get('model') in self._STRUCTURED_MODELS) and __user__ and __user__.get("id"):
                try:
                    preface, usage = await asyncio.wait_for(self._generate_preface(body, text, __request__, __user__), timeout=8)
                    state = __request__.state.fireworks_diagram
                    state["intro"], state["prelude"] = preface, preface
                    state["preface_usage"] = usage
                    if not preface:
                        logging.getLogger(__name__).warning("Architecture preface returned no safe visible text")
                except Exception as error:
                    # A slow/missing provider must not prevent the main answer.
                    logging.getLogger(__name__).warning("Architecture preface unavailable (%s)", type(error).__name__)
        # Data-only schema is appropriate for a single visual, never for a
        # full report or architecture+statistics request: it loses half the task.
        structured = body.get("model") in self._STRUCTURED_MODELS and not report and not (chart and architecture)
        if structured:
            # Scope this to explicit architecture requests for the observed
            # incompatible model; ordinary chats/tools are unchanged.
            body["tool_ids"] = []
            schema = self._chart_plan_schema() if chart else self._plan_schema()
            body["response_format"] = {"type":"json_schema","json_schema":{"name":"statistical_chart" if chart else "technical_architecture","strict":not chart,"schema":schema}}
            body["messages"] = [{"role":"system","content":self._CHART_PLAN_INSTRUCTION if chart else self._PLAN_INSTRUCTION}, {"role":"user","content":text}]
            messages = body["messages"]
            if __request__ is not None:
                __request__.state.fireworks_diagram["structured"] = True
        else:
            body["tool_ids"] = sorted(set(body.get("tool_ids") or []) | {self._FIREWORKS_TOOL_ID})
        body.setdefault("params", {})["function_calling"] = "native"
        # Rendering needs no disconnected browser/desktop command RPC.
        body.pop("terminal_id", None)
        mixed = report or (chart and architecture)
        instruction = self._PLAN_INSTRUCTION if structured else self._REPORT_INSTRUCTION if mixed else self._CHART_INSTRUCTION if chart else self._INSTRUCTION
        marker = "[openwebui-mixed-visual-report-v1]" if mixed else "[openwebui-numeric-chart-v1]" if chart else self._MARKER
        if structured:
            return body
        if messages and messages[0].get("role") == "system":
            current = self._text(messages[0].get("content"))
            if marker not in current:
                messages[0]["content"] = instruction + "\n\n" + current
        else:
            messages.insert(0, {"role": "system", "content": instruction})
        return body

    def request(self, body: dict, __request__=None) -> dict:
        state = self._state(__request__) or {}
        if not state.get("structured"):
            return body
        # v0.12.3 adds builtin tools and the skill catalog AFTER inlet. Enforce
        # data-only mode at the final provider boundary as well, otherwise the
        # model receives contradictory shell/tool instructions and ignores it.
        chart=state.get('mode')=='chart'
        body["messages"] = [{"role":"system","content":self._CHART_PLAN_INSTRUCTION if chart else self._PLAN_INSTRUCTION}, {"role":"user","content":state["source_text"]}]
        body["tools"] = []
        body["tool_choice"] = "none"
        body["response_format"] = {"type":"json_schema","json_schema":{"name":"statistical_chart" if chart else "technical_architecture","strict":not chart,"schema":self._chart_plan_schema() if chart else self._plan_schema()}}
        body["max_tokens"] = 3200
        body.setdefault("options", {}).update({"num_predict":3200,"think":False,"temperature":.1})
        return body

    @staticmethod
    def _unsafe_preview(text):
        return bool(re.search(r"```|~~~|[{}]|<(?:svg|html|script|div|path|rect|!doctype)|(?:^|\n)\s*(?:import\s|export\s|const\s|function\s|flowchart\s|graph\s+(?:TD|LR)|[+┌├└│].*[-─|])", text, re.I))

    @classmethod
    def _preview(cls, state, text, flush=False):
        """Release safe complete sentences, not partial source-code tokens.

        A fence/JSON/JS opening disables the remaining pre-tool preview. The
        unmodified source is still buffered for JSON-only recovery at outlet.
        """
        if state.get("preview_blocked") or len(state.get("intro", "")) >= 900:
            return ""
        state["pending"] = state.get("pending", "") + text
        visible = ""
        while state["pending"]:
            pending = state["pending"]
            boundary = re.search(r"[。！？\n]|[.!?](?:\s|$)", pending)
            if boundary:
                end = boundary.end()
            elif flush:
                end = len(pending)
            else:
                break
            segment = pending[:end]
            state["pending"] = pending[end:]
            if cls._unsafe_preview(segment):
                state["preview_blocked"] = True
                state["pending"] = ""
                break
            # Leading indentation from hidden SVG/HTML must not turn ordinary
            # explanatory prose into a Markdown code block.
            visible += re.sub(r"(?m)^ {4,}(?=\S)", "", segment)
            if len(state.get("intro", ""))+len(visible) >= 900:
                state["preview_blocked"] = True
                break
        state["intro"] = state.get("intro", "") + visible
        return visible

    @classmethod
    def _quick_summary(cls, payload):
        """Grounded fallback when the model calls a tool without a preface."""
        nodes = payload.get("nodes") or []
        rows = {}
        for node in nodes:
            if isinstance(node, dict) and node.get("label"):
                try:
                    level = int(node.get("level", 0))
                except (ValueError, TypeError):
                    level = 0
                rows.setdefault(level, []).append(str(node["label"])[:40])
        if not rows:
            return ""
        layers = ["、".join(rows[level][:4]) for level in sorted(rows)[:5]]
        names = {n.get("id"):str(n.get("label", ""))[:40] for n in nodes if isinstance(n, dict)}
        pairs = []
        for edge in payload.get("edges") or []:
            if isinstance(edge, dict) and edge.get("from") in names and edge.get("to") in names:
                pairs.append(names[edge["from"]]+" — "+names[edge["to"]])
        summary = "架構分層包含「"+"」、「".join(layers)+"」。"
        if pairs:
            summary += "主要連線為「"+"」、「".join(pairs[:3])+"」。"
        return summary+"\n\n以下把設備、分支與連線畫成架構圖。\n\n"

    @classmethod
    def _quick_chart_summary(cls, payload):
        labels,series=payload.get('labels'),payload.get('series')
        if not isinstance(labels,list) or not labels or not isinstance(series,list):
            return ''
        clean=lambda value:re.sub(r'[`<>{}\[\]\\\n\r]', '',str(value))[:32]
        kind=payload.get('chart_type','auto')
        if kind=='gantt':
            return f'以下將提供的 {len(labels)} 項任務整理成時程圖，區分時間區間與已知進度。\n\n'
        if kind in {'scatter','bubble'} and len(series)>=2:
            a,b=(clean(s.get('name','')) if isinstance(s,dict) else '' for s in series[:2])
            return f'以下以「{a}」與「{b}」呈現提供資料的分佈；圖形關係本身不代表因果。\n\n'
        names='、'.join(clean(label) for label in labels[:3])
        return f'先對照「{names}」等 {len(labels)} 個項目的提供資料，再用現成圖表樣板呈現；單位為{clean(payload.get("unit","未提供"))}。\n\n'

    def stream(self, event: dict, __request__=None) -> dict:
        state = self._state(__request__)
        if state is None:
            return event
        # Pass early prose through, but keep model source and reasoning hidden.
        # Native tool deltas/finish_reason remain intact.
        for choice in event.get("choices", []):
            delta = choice.get("delta") or {}
            choice["delta"] = delta
            text = delta.get("content")
            if isinstance(text, str) and state["size"] < 200_000:
                state["chunks"].append(text)
                state["size"] += len(text)
            visible = self._preview(state, text if isinstance(text, str) else "", flush=bool(delta.get("tool_calls") or choice.get("finish_reason")))
            if state.get("prelude") and not state.get("prelude_shown"):
                visible = state["prelude"]+visible
                state["prelude_shown"] = True
            # Models sometimes omit the requested prose and start tool input
            # immediately. Derive a short factual summary from completed node
            # data before rendering, without another model call.
            for call in delta.get("tool_calls") or []:
                fn = call.get("function") or {}
                key = str(call.get("index", 0))
                pending_call = state.setdefault("preview_calls", {}).setdefault(key, {"name":"", "arguments":""})
                if fn.get("name"):
                    pending_call["name"] = fn["name"]
                arguments = fn.get("arguments", "")
                if isinstance(arguments, str):
                    pending_call["arguments"] += arguments
                if not state.get("intro", "").strip() and pending_call["name"].endswith(("render_technical_architecture","render_data_chart")):
                    try:
                        payload = json.loads(pending_call["arguments"])
                    except (ValueError, TypeError):
                        continue
                    if isinstance(payload, dict):
                        visible += self._quick_chart_summary(payload) if pending_call["name"].endswith("render_data_chart") else self._quick_summary(payload)
                        state["intro"] = visible
                state["preview_blocked"] = True
            if "content" in delta or visible:
                delta["content"] = visible
            for key in ("reasoning_content", "reasoning"):
                if key in delta:
                    delta[key] = ""
        return event

    @staticmethod
    def _renderer():
        candidates = [os.environ.get("OPENWEBUI_FIREWORKS_RENDERER_TOOL", ""),
            str(Path.home() / "Library/Application Support/OpenWebUIRuntime/openwebui-fireworks-renderer-tool.py")]
        try:
            from open_webui.env import DATA_DIR
            candidates[1:1]=[str(Path(DATA_DIR)/'visual-profile/openwebui-fireworks-renderer-tool.py'),str(Path(DATA_DIR).parent/'openwebui-fireworks-renderer-tool.py')]
        except ImportError:
            pass
        for env in ("LOCALAPPDATA", "APPDATA"):
            if os.environ.get(env):
                candidates.append(str(Path(os.environ[env]) / "OpenWebUIRuntime/openwebui-fireworks-renderer-tool.py"))
        path = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
        if path is None:
            raise RuntimeError("找不到伺服器 Renderer")
        spec = importlib.util.spec_from_file_location("fireworks_artifact_renderer", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Tools()

    @staticmethod
    def _quadrant_data(source):
        """Read a bounded declarative Mermaid subset, never execute model code."""
        if len(source) > 20_000 or not re.match(r"\s*quadrantChart\b", source):
            return None
        title, axes, labels, coordinates = "品牌定位圖（定性示意）", {}, [], [[], []]
        for line in source.splitlines()[1:]:
            line = line.strip()
            if line.startswith("title "):
                title = line[6:].strip().strip('"')
            axis = re.fullmatch(r"([xy])-axis\s+(.+?)\s+-->\s+(.+)", line)
            if axis:
                axes[axis[1]] = axis[2].strip('"')+" → "+axis[3].strip('"')
            point = re.fullmatch(r'(?P<label>"[^"\n]+"|[^:\n]+)\s*:\s*\[\s*(?P<x>[-+\d.eE]+)\s*,\s*(?P<y>[-+\d.eE]+)\s*\]', line)
            if point:
                try:
                    values = [float(point['x']),float(point['y'])]
                except ValueError:
                    return None
                if any(not 0 <= v <= 1 for v in values):
                    return None
                labels.append(point['label'].strip().strip('"'))
                for index,value in enumerate(values):
                    coordinates[index].append(value)
            elif line and not (line == "quadrantChart" or line.startswith(("title ","x-axis ","y-axis ","quadrant-", "%%"))):
                return None
        if set(axes) != {'x','y'} or not 2 <= len(labels) <= 12:
            return None
        return dict(title=title, labels=labels, series=[{"name":axes[axis],"values":coordinates[i]} for i,axis in enumerate(('x','y'))],
            unit="相對位置（0–1）", chart_type="quadrant", data_kind="illustrative",
            note="模型定性示意，非市場調查、客觀品牌評分或市佔率；保留原回覆相對座標，不代表產品全系列。", sources=[], better="neutral")

    @staticmethod
    def _diagram_data(text):
        # Parse JSON data only; never execute model-provided shell/Python/JS.
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", text[:200_000]):
            try:
                obj, _ = decoder.raw_decode(text[match.start():])
            except ValueError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("nodes"), list) and isinstance(obj.get("edges"), list):
                if not all(isinstance(n, dict) for n in obj["nodes"] + obj["edges"]):
                    continue
                if obj["nodes"] and not any("level" in n for n in obj["nodes"]):
                    levels = {n.get("id"): 0 for n in obj["nodes"]}
                    for _ in range(min(len(levels), 6)):
                        changed = False
                        for e in obj["edges"]:
                            a, b = e.get("from"), e.get("to")
                            if a in levels and b in levels and levels[a] >= levels[b] and levels[a] < 5:
                                levels[b] = levels[a] + 1
                                changed = True
                        if not changed:
                            break
                    for n in obj["nodes"]:
                        n["level"] = levels[n.get("id")]
                return {k: v for k, v in obj.items() if k in {"title", "subtitle", "nodes", "edges", "groups", "visual_family", "layout"}}
        return None

    @staticmethod
    def _set_response(assistant, text):
        assistant["content"] = text
        # Structured output is rendered ahead of legacy content. Both must
        # change, otherwise old code/tool failures survive refresh.
        assistant["output"] = [{"id": "msg_" + uuid.uuid4().hex, "type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text", "text": text}]}]
        assistant["done"] = True

    @classmethod
    async def _recover_plan(cls, request, user, model, text, context, numeric=False):
        """Constrained data-only retry, independent of native tool support."""
        from open_webui.models.users import Users
        from open_webui.utils.chat import generate_chat_completion
        selected_user = await Users.get_user_by_id(user["id"])
        if selected_user is None:
            return None, None
        snapshot = {key:copy.deepcopy(getattr(request.state,key)) for key in ("bypass_filter","bypass_system_prompt","metadata") if hasattr(request.state,key)}
        try:
            form = {"model":model,"stream":False,"max_tokens":3200,
                "messages":[{"role":"system","content":cls._CHART_PLAN_INSTRUCTION if numeric else cls._PLAN_INSTRUCTION},{"role":"user","content":("需求："+text+"\n先前可供參考的說明（非實測依據，以需求為準）："+context)[:6500]}],
                "response_format":{"type":"json_schema","json_schema":{"name":"statistical_chart" if numeric else "technical_architecture","strict":not numeric,"schema":cls._chart_plan_schema() if numeric else cls._plan_schema()}},
                "metadata":{"task":"architecture_plan_recovery"}}
            if (request.app.state.MODELS.get(model) or {}).get("owned_by") == "ollama":
                form["options"] = {"num_predict":3200,"temperature":.1,"think":"low" if "gpt-oss" in model.lower() else False}
            response = await generate_chat_completion(request,form,selected_user,bypass_system_prompt=True)
            if not isinstance(response,dict):
                return None,None
            content = cls._text(((response.get("choices") or [{}])[0].get("message") or {}).get("content"))
            if numeric:
                try:
                    data=json.loads(content)
                except ValueError:data=None
                if not isinstance(data,dict) or not isinstance(data.get('labels'),list) or not isinstance(data.get('series'),list):data=None
                if data:data={k:v for k,v in data.items() if k in {'title','labels','series','unit','chart_type','data_kind','sources','note','better','options'}}
                return data,response.get('usage')
            return cls._diagram_data(content), response.get("usage")
        finally:
            for key in ("bypass_filter","bypass_system_prompt","metadata"):
                if key in snapshot:
                    setattr(request.state,key,snapshot[key])
                elif hasattr(request.state,key):
                    delattr(request.state,key)

    @staticmethod
    def _architecture_results(state):
        return list(dict.fromkeys([*state.get('architecture_artifacts',[]), *([state['artifact']] if state.get('artifact','').startswith('![') else [])]))

    @staticmethod
    def _remove_visual_data(raw):
        decoder=json.JSONDecoder();spans=[]
        for match in list(re.finditer(r'\{',raw[:200_000]))[:200]:
            try:obj,length=decoder.raw_decode(raw[match.start():])
            except ValueError:continue
            if isinstance(obj,dict) and (('nodes' in obj and 'edges' in obj) or ('labels' in obj and 'series' in obj)):
                spans.append((match.start(),match.start()+length))
        for start,end in reversed(spans):raw=raw[:start]+raw[end:]
        return raw

    async def _recover_architecture(self,state,raw,text,request,user,emitter):
        data=self._diagram_data(raw)
        if data is None and request is not None and user and state.get('model'):
            try:
                if emitter:await emitter({'type':'status','data':{'description':'正在補齊報告中的架構圖…','done':False}})
                data,usage=await asyncio.wait_for(self._recover_plan(request,user,state['model'],text,state.get('intro','')),timeout=50)
                speed=getattr(request.state,'response_speed',None)
                if speed is not None and usage:speed.setdefault('extra_usage',[]).append(usage)
            except Exception as error:
                logging.getLogger(__name__).warning('Report architecture recovery unavailable (%s)',type(error).__name__)
            finally:
                if emitter:await emitter({'type':'status','data':{'description':'報告架構資料檢查結束','done':True,'hidden':True}})
        if data and data.get('title'):
            result=await self._renderer().render_technical_architecture(**self._enforce_host_constraint(data,text),__event_emitter__=emitter,__request__=request)
            if result.startswith('!['):return result
            state['architecture_error']=result
            logging.getLogger(__name__).warning('Report architecture renderer: %s',result)
        return None

    async def outlet(self, body: dict, __event_emitter__=None, __request__=None, __user__=None, __model__=None) -> dict:
        messages = body.get("messages", [])
        assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        text = self._text(user.get("content"))
        chart,architecture,report = self._visual_intents(text)
        raw_content = self._text(assistant.get("content")) if assistant else ""
        # Even an unsolicited positioning chart must not fall through to the
        # browser's Mermaid parser. Recovery uses source data, not a new model.
        quadrant_blocks = list(re.finditer(r"```(?:mermaid)?\s*\n(\s*quadrantChart\b[\s\S]*?)```", raw_content, re.I))
        chart = chart or bool(quadrant_blocks)
        if assistant is None or not (chart or self._wants_diagram(text)):
            return body
        state = self._state(__request__) or {}
        if chart:
            raw = "".join(state.get("chunks", [])) or self._text(assistant.get("content"))
            artifacts = list(dict.fromkeys(state.get("chart_artifacts", [])))
            render_error=''
            for block in re.finditer(r"```(?:mermaid)?\s*\n(\s*quadrantChart\b[\s\S]*?)```", raw, re.I):
                if artifacts:
                    break
                data = self._quadrant_data(block[1])
                if data:
                    try:
                        recovered = await self._renderer().render_data_chart(**data, __event_emitter__=__event_emitter__, __request__=__request__)
                        if recovered.startswith("!["):
                            artifacts.append(recovered)
                        else:
                            render_error=recovered
                    except Exception as error:
                        logging.getLogger(__name__).warning("Positioning chart recovery failed (%s)", type(error).__name__)
            # Recover data-only chart payloads from models which miss native
            # tool calling. Never evaluate model-supplied JS or HTML.
            decoder = json.JSONDecoder()
            payloads = []
            for match in list(re.finditer(r"\{", raw[:200_000]))[:200]:
                try:
                    obj, end = decoder.raw_decode(raw[match.start():])
                except ValueError:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("labels"), list) and isinstance(obj.get("series"), list):
                    payloads.append((match.start(), match.start()+end, obj))
            if not artifacts and payloads:
                data = {k:v for k,v in payloads[0][2].items() if k in {"title","labels","series","unit","data_kind","chart_type","sources","note","better","options"}}
                if all(key in data for key in ("title","labels","series","unit","data_kind")):
                    try:
                        recovered = await self._renderer().render_data_chart(**data, __event_emitter__=__event_emitter__, __request__=__request__)
                        if recovered.startswith("!["):
                            artifacts.append(recovered)
                        else:
                            render_error=recovered
                    except Exception as error:
                        logging.getLogger(__name__).warning('Chart data recovery failed (%s)',type(error).__name__)
            for start, end, _ in reversed(payloads):
                raw = raw[:start]+raw[end:]
            architecture_results=self._architecture_results(state)
            if architecture and not architecture_results:
                result=await self._recover_architecture(state,raw,text,__request__,__user__,__event_emitter__)
                if result:architecture_results.append(result)
            explicit_numeric=bool(re.search(r'長條圖|柱[狀形]圖|折線圖|雷達圖|散[點佈]圖|氣泡圖|圓餅圖|環形圖|瀑布圖|儀表[盤板]|甘特圖|漏斗圖|數值.{0,8}圖|(?:bar|line|radar|scatter|bubble|pie|gauge|gantt) chart',text,re.I))
            if not artifacts and (architecture or report) and explicit_numeric and __request__ is not None and __user__ and state.get('model'):
                try:
                    if __event_emitter__:await __event_emitter__({'type':'status','data':{'description':'正在補齊報告中的數值圖…','done':False}})
                    data,usage=await asyncio.wait_for(self._recover_plan(__request__,__user__,state['model'],text,'',numeric=True),timeout=50)
                    speed=getattr(__request__.state,'response_speed',None)
                    if speed is not None and usage:speed.setdefault('extra_usage',[]).append(usage)
                    if data:
                        recovered=await self._renderer().render_data_chart(**data,__event_emitter__=__event_emitter__,__request__=__request__)
                        if recovered.startswith('!['):artifacts.append(recovered)
                        else:render_error=recovered
                except Exception as error:logging.getLogger(__name__).warning('Report numeric recovery unavailable (%s)',type(error).__name__)
                finally:
                    if __event_emitter__:await __event_emitter__({'type':'status','data':{'description':'報告數值資料檢查結束','done':True,'hidden':True}})
            raw=self._remove_visual_data(raw)
            # Preserve the analysis; never replace it with an architecture-only
            # response. Fenced model source is hidden even when tools fail.
            prose = re.sub(r"```[^\n]*\n.*?(?:```|\Z)", "", raw, flags=re.S)
            prose = re.sub(r"<(?:svg|script|html)\b.*?(?:</(?:svg|script|html)>|\Z)", "", prose, flags=re.I|re.S)
            # Only actual renderer artifacts may stand in for a generated plot.
            prose = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", prose)
            prose = re.sub(r'\{\{\s*render_(?:technical_architecture|data_chart)\s*\}\}', '',prose)
            if state.get('structured'):
                # A data-only planner must never expose arbitrary/error JSON.
                prose=state.get('intro','').strip()
                if not prose and payloads:
                    prose=self._quick_chart_summary(payloads[0][2]).strip()
            numeric_results=list(artifacts)
            artifacts=list(dict.fromkeys([*architecture_results,*numeric_results]))
            for artifact in artifacts:
                prose = prose.replace(artifact, "")
                for url in re.findall(r"\]\(([^)]+)\)", artifact):
                    prose = re.sub(r"!?\[[^\]]*\]\("+re.escape(url)+r"\)", "", prose)
            if not artifacts:
                failure=render_error or '本次圖表未完成：模型未提供符合樣板的有效資料；不會編造數值、補零或顯示假成品。'
                prose='\n\n'.join(p for p in [prose.strip(),failure] if p)
            elif architecture and not architecture_results:
                prose+='\n\n架構圖未完成：未取得有效設備與連線；以上數值圖不代表架構圖已完成。'
                if state.get('architecture_error'):
                    prose+='\n'+state['architecture_error']
            elif architecture_results and not numeric_results and chart:
                prose+='\n\n已附架構圖；未取得可驗證、同條件的數值資料，未產生數值統計圖。定性差異以文字／比較表說明，不編造效能數字。'
            self._set_response(assistant, "\n\n".join(p for p in [prose.strip(), *artifacts] if p))
            return body
        result = state.get("artifact")
        if not result:
            raw = "".join(state.get("chunks", [])) or self._text(assistant.get("content"))
            data = self._diagram_data(raw)
            if data is None and __request__ is not None and __user__ and state.get("model"):
                try:
                    if __event_emitter__:
                        await __event_emitter__({"type":"status","data":{"description":"正在由伺服器整理架構並繪圖…","done":False}})
                    data, usage = await asyncio.wait_for(self._recover_plan(__request__,__user__,state["model"],text,state.get("intro", "")),timeout=50)
                    speed = getattr(__request__.state,"response_speed",None)
                    if speed is not None and usage:
                        # Preserve raw per-call usage; the speed filter owns
                        # unit conversion and deduplication.
                        speed.setdefault("extra_usage", []).append(usage)
                except Exception as error:
                    logging.getLogger(__name__).warning("Architecture plan recovery unavailable (%s)",type(error).__name__)
                finally:
                    if __event_emitter__:
                        await __event_emitter__({"type":"status","data":{"description":"架構資料檢查結束","done":True,"hidden":True}})
            if data and data.get("title"):
                data = self._enforce_host_constraint(data,text)
                result = await self._renderer().render_technical_architecture(**data, __event_emitter__=__event_emitter__, __request__=__request__)
        if not result:
            result = "本次架構圖未完成：模型沒有提交可繪製的節點與連線。請重新生成；未產生成品，不會顯示暫存圖或繪圖程式碼。"
        # Keep the useful architecture explanation that was already displayed.
        intro = state.get("intro", "").strip()
        if report:
            raw=self._text(assistant.get('content')) or ''.join(state.get('chunks',[]))
            raw=self._remove_visual_data(raw)
            intro=re.sub(r'```[^\n]*\n.*?(?:```|\Z)','',raw,flags=re.S)
            intro=re.sub(r'!\[[^\]]*\]\([^)]+\)','',intro).strip()
        results=self._architecture_results(state) or [result]
        self._set_response(assistant, "\n\n".join(part for part in [intro,*results] if part))
        return body
