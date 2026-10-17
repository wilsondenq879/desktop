#!/usr/bin/env python3
"""Dependency-free MCP stdio server for ASUSWRT/Asuswrt-Merlin.

The server deliberately does not expose an arbitrary shell tool. It executes a
small allow-list of read-only queries over SSH and a few explicit,
confirmation-gated actions, so it can run on a Windows desktop without an MCP
Python SDK.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "asuswrt-mcp"
SERVER_VERSION = "0.1.0"

_SAFE_NVRAM_KEYS = {
    "productid",
    "firmver",
    "buildno",
    "lan_ipaddr",
    "wan0_state_t",
    "wan0_ipaddr",
    "wan0_gateway",
    "wan0_dns",
    "wl0_ssid",
    "wl1_ssid",
    "wl2_ssid",
    "wl0_radio",
    "wl1_radio",
    "wl2_radio",
}

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "router_get_status",
        "description": "讀取 ASUSWRT 路由器型號、韌體、LAN/WAN、連線時間與記憶體狀態。唯讀。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "router_get_clients",
        "description": "讀取目前路由器看到的用戶端 IP/MAC 鄰居表。唯讀。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "router_get_wireless",
        "description": "讀取無線介面與關聯裝置摘要。唯讀。不同 ASUS 型號可能回傳不同介面名稱。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "router_get_logs",
        "description": "讀取最近的系統日誌（最多 120 行）。唯讀。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "router_get_nvram",
        "description": "讀取一個安全白名單內的 NVRAM 設定值；不接受任意 key 或 shell 語法。唯讀。",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": sorted(_SAFE_NVRAM_KEYS)}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "router_reconnect_wan",
        "description": "重新連線 WAN。這會中斷目前網路，必須明確傳入 confirm=true。",
        "inputSchema": {
            "type": "object",
            "properties": {"confirm": {"type": "boolean", "description": "確認要中斷並重新連線 WAN"}},
            "required": ["confirm"],
            "additionalProperties": False,
        },
    },
    {
        "name": "router_restart_wireless",
        "description": "重啟路由器無線服務，所有 Wi-Fi 用戶端會短暫斷線；必須明確傳入 confirm=true。",
        "inputSchema": {
            "type": "object",
            "properties": {"confirm": {"type": "boolean", "description": "確認要重啟無線服務"}},
            "required": ["confirm"],
            "additionalProperties": False,
        },
    },
    {
        "name": "router_reboot",
        "description": "重新啟動路由器；整個網路會暫時中斷，必須明確傳入 confirm=true。",
        "inputSchema": {
            "type": "object",
            "properties": {"confirm": {"type": "boolean", "description": "確認要重新啟動路由器"}},
            "required": ["confirm"],
            "additionalProperties": False,
        },
    },
]

_READ_COMMANDS = {
    "router_get_status": (
        "printf 'productid='; nvram get productid; "
        "printf 'firmver='; nvram get firmver; "
        "printf 'buildno='; nvram get buildno; "
        "printf 'lan_ipaddr='; nvram get lan_ipaddr; "
        "printf 'wan0_state_t='; nvram get wan0_state_t; "
        "printf 'wan0_ipaddr='; nvram get wan0_ipaddr; "
        "printf 'wan0_gateway='; nvram get wan0_gateway; "
        "printf 'wan0_dns='; nvram get wan0_dns; "
        "printf 'uptime='; uptime; "
        "printf 'memory='; free 2>/dev/null || cat /proc/meminfo 2>/dev/null | head -n 8"
    ),
    "router_get_clients": "echo '[ip-neigh]'; ip neigh show 2>/dev/null; echo '[arp]'; cat /proc/net/arp 2>/dev/null",
    "router_get_wireless": (
        "for i in $(nvram get wl_ifnames 2>/dev/null); do "
        "echo \"[$i]\"; wl -i \"$i\" status 2>/dev/null; "
        "wl -i \"$i\" assoclist 2>/dev/null; "
        "done; "
        "echo '[configured-radios]'; "
        "for k in wl0_radio wl1_radio wl2_radio; do printf \"%s=\" \"$k\"; nvram get \"$k\"; done"
    ),
    "router_get_logs": "(logread 2>/dev/null || cat /var/log/messages 2>/dev/null || dmesg 2>/dev/null) | tail -n 120",
}

_MUTATING_COMMANDS = {
    "router_reconnect_wan": "service restart_wan",
    "router_restart_wireless": "service restart_wireless",
    "router_reboot": "reboot",
}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _json_text(payload)}], "isError": is_error}


def _config() -> dict[str, Any]:
    host = os.environ.get("ASUSWRT_HOST", "").strip()
    if not host:
        raise RuntimeError("未設定 ASUSWRT_HOST；請先設定路由器 LAN IP 或 ZeroTier/Tailscale 可達的位址。")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", host):
        raise RuntimeError("ASUSWRT_HOST 含有不允許的字元。")

    try:
        port = int(os.environ.get("ASUSWRT_SSH_PORT", "22"))
    except ValueError as exc:
        raise RuntimeError("ASUSWRT_SSH_PORT 必須是數字。") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("ASUSWRT_SSH_PORT 必須介於 1 到 65535。")

    key = os.environ.get("ASUSWRT_SSH_KEY", "").strip()
    if key:
        key_path = pathlib.Path(key).expanduser()
        if not key_path.is_file():
            raise RuntimeError(f"SSH key 不存在：{key_path}")
        key = str(key_path)

    return {
        "host": host,
        "port": port,
        "user": os.environ.get("ASUSWRT_SSH_USER", "admin").strip() or "admin",
        "key": key,
        "ssh": os.environ.get("ASUSWRT_SSH_BIN", "ssh").strip() or "ssh",
        "known_hosts": os.environ.get("ASUSWRT_SSH_KNOWN_HOSTS", "").strip(),
        "dry_run": os.environ.get("ASUSWRT_DRY_RUN", "0").lower() in {"1", "true", "yes"},
        "timeout": max(3, min(int(os.environ.get("ASUSWRT_SSH_TIMEOUT", "15")), 60)),
    }


def _ssh(config: dict[str, Any], command: str) -> dict[str, Any]:
    destination = f"{config['user']}@{config['host']}"
    args = [config["ssh"], "-o", "BatchMode=yes", "-o", f"ConnectTimeout={config['timeout']}"]
    if config["known_hosts"]:
        args.extend(["-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={config['known_hosts']}"])
    else:
        # Convenient for a first LAN demo; production should provide a pinned known_hosts file.
        args.extend(["-o", "StrictHostKeyChecking=accept-new"])
    args.extend(["-p", str(config["port"])])
    if config["key"]:
        args.extend(["-i", config["key"]])
    args.extend([destination, command])

    if config["dry_run"]:
        return {"ok": True, "dry_run": True, "command": " ".join(_quote(a) for a in args)}

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=config["timeout"] + 3,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("找不到 ssh.exe；Windows 10/11 請安裝 OpenSSH Client，或設定 ASUSWRT_SSH_BIN。") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("SSH 連線逾時；請確認主機、SSH 服務與 ZeroTier/Tailscale 路由。") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        detail = stderr or stdout or f"ssh exit code {completed.returncode}"
        raise RuntimeError(f"SSH 指令失敗：{detail[-1000:]}")
    return {"ok": True, "dry_run": False, "stdout": stdout, "stderr": stderr}


def _quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@=+,-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def _query(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    config = _config()
    if tool == "router_get_nvram":
        name = str(arguments.get("name", ""))
        if name not in _SAFE_NVRAM_KEYS:
            raise RuntimeError("這個 NVRAM key 不在安全白名單內。")
        command = f"printf '%s=' '{name}'; nvram get '{name}'"
    elif tool in _READ_COMMANDS:
        command = _READ_COMMANDS[tool]
    elif tool in _MUTATING_COMMANDS:
        if arguments.get("confirm") is not True:
            raise RuntimeError("這是會改變路由器狀態的操作；請明確傳入 confirm=true。")
        command = _MUTATING_COMMANDS[tool]
    else:
        raise RuntimeError(f"未知工具：{tool}")

    response = _ssh(config, command)
    return {
        "tool": tool,
        "timestamp": _now(),
        "router": {"host": config["host"], "port": config["port"], "user": config["user"]},
        "transport": "ssh",
        **response,
    }


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOLS}}
    if method == "tools/call":
        params = request.get("params") or {}
        tool = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        try:
            payload = _query(tool, arguments)
            result = _result(payload)
        except Exception as exc:  # Keep MCP transport alive after a router error.
            result = _result({"ok": False, "error": str(exc), "timestamp": _now()}, is_error=True)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = _handle(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as exc:
            sys.stdout.write(
                json.dumps(
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}},
                    ensure_ascii=False,
                )
                + "\n"
            )
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
