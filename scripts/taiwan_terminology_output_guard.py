"""
title: 臺灣資訊術語輸出校正
description: 搭配「臺灣資訊術語對照表」知識庫，將一般技術回答中的常見中國大陸資訊術語校正為臺灣慣用詞；保留程式碼、網址與明確的兩岸術語對照內容。
version: 1.1.0
"""

import re


class Filter:
    """Open WebUI global outlet filter for high-confidence terminology fixes."""

    _REPLACEMENTS = {
        "本地文件": "本機檔案",
        "本地檔案": "本機檔案",
        "文件夾": "資料夾",
        "資料夾": "資料夾",
        "默認值": "預設值",
        "默认值": "預設值",
        "操作系統": "作業系統",
        "操作系统": "作業系統",
        "源代碼": "原始碼",
        "源代码": "原始碼",
        "二進制": "二進位",
        "二进制": "二進位",
        "字符串": "字串",
        "字節": "位元組",
        "字节": "位元組",
        "進程": "處理程序",
        "进程": "處理程序",
        "線程": "執行緒",
        "线程": "執行緒",
        "緩存": "快取",
        "缓存": "快取",
        "數據庫": "資料庫",
        "数据库": "資料庫",
        "數據": "資料",
        "数据": "資料",
        "信息": "資訊",
        "默認": "預設",
        "默认": "預設",
        "軟件": "軟體",
        "软件": "軟體",
        "硬件": "硬體",
        "網絡": "網路",
        "网络": "網路",
        "服務器": "伺服器",
        "服务器": "伺服器",
        "客户端": "用戶端",
        "客戶端": "用戶端",
        "端口": "連接埠",
        "帶寬": "頻寬",
        "带宽": "頻寬",
        "接口": "介面",
        "調用": "呼叫",
        "调用": "呼叫",
        "兼容": "相容",
        "支持": "支援",
        "視頻": "影片",
        "视频": "影片",
        "內存": "記憶體",
        "内存": "記憶體",
        "硬盤": "硬碟",
        "硬盘": "硬碟",
        "全局": "全域",
        "節點": "節點",
        "节点": "節點",
        "鼠標": "滑鼠",
        "鼠标": "滑鼠",
        "打印機": "印表機",
        "打印机": "印表機",
        "打印": "列印",
        "字符": "字元",
        "算法": "演算法",
        "數組": "陣列",
        "数组": "陣列",
        "變量": "變數",
        "变量": "變數",
        "函數": "函式",
        "函数": "函式",
        "參數": "參數",
        "参数": "參數",
        "應用程序": "應用程式",
        "应用程序": "應用程式",
        "用戶": "使用者",
        "用户": "使用者",
        "添加": "新增",
        "搜索": "搜尋",
        "查找": "尋找",
        "反饋": "意見回饋",
        "反馈": "意見回饋",
    }

    _PROTECTED = re.compile(
        r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`|https?://[^\s<>]+)",
        re.MULTILINE,
    )
    _COMPARISON_REQUEST = re.compile(
        r"(兩岸|台灣.{0,8}(中國大陸|大陸)|中國大陸.{0,8}台灣|簡體.{0,8}繁體|"
        r"繁體.{0,8}簡體).{0,16}(術語|用語|名詞|翻譯|對照|差異)|"
        r"(術語|用語|名詞).{0,16}(對照表|兩岸差異)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self):
        self._ordered_replacements = sorted(
            self._REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True
        )

    def _should_preserve_comparison(self, body: dict) -> bool:
        for message in reversed(body.get("messages", [])):
            if message.get("role") == "user":
                content = message.get("content") or ""
                return bool(self._COMPARISON_REQUEST.search(str(content)))
        return False

    def _normalize_plain_text(self, text: str) -> str:
        for source, target in self._ordered_replacements:
            text = text.replace(source, target)
        return text

    def _normalize_content(self, content: str) -> str:
        parts = self._PROTECTED.split(content)
        return "".join(
            part if index % 2 else self._normalize_plain_text(part)
            for index, part in enumerate(parts)
        )

    async def outlet(self, body: dict, __user__: dict | None = None) -> dict:
        if self._should_preserve_comparison(body):
            return body

        target_id = body.get("id")
        for message in reversed(body.get("messages", [])):
            if message.get("role") != "assistant":
                continue
            if target_id and message.get("id") not in (None, target_id):
                continue
            content = message.get("content")
            if isinstance(content, str) and content:
                message["content"] = self._normalize_content(content)
            for output in message.get("output") or []:
                if output.get("type") == "message":
                    for part in output.get("content") or []:
                        if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                            part["text"] = self._normalize_content(part["text"])
            break

        return body
