"""
VNC server management helpers.

This module provides optional support for starting/stopping an x11vnc process
to stream the current desktop to VNC clients (e.g., Android VNC apps).
"""

import atexit
import logging
import os
import shutil
import subprocess
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger("voice-control-vnc")

_vnc_lock = threading.Lock()
_vnc_process: Optional[subprocess.Popen] = None


def is_vnc_enabled() -> bool:
    return os.environ.get("VNC_ENABLED", "false").lower() == "true"


def get_vnc_port() -> int:
    return int(os.environ.get("VNC_PORT", "5901"))


def get_vnc_display() -> str:
    return os.environ.get("VNC_DISPLAY", os.environ.get("DISPLAY", ":0"))


def get_vnc_password() -> Optional[str]:
    password = os.environ.get("VNC_PASSWORD")
    return password if password else None


def get_vnc_host() -> str:
    return os.environ.get("VNC_HOST", "0.0.0.0")


def is_vnc_localhost_only() -> bool:
    return os.environ.get("VNC_LOCALHOST_ONLY", "false").lower() == "true"


def _build_x11vnc_command() -> Dict[str, Any]:
    display = get_vnc_display()
    port = get_vnc_port()
    password = get_vnc_password()

    cmd = [
        "x11vnc",
        "-display", display,
        "-rfbport", str(port),
        "-forever",
        "-shared",
        "-quiet",
        "-repeat",
    ]

    if is_vnc_localhost_only():
        cmd.append("-localhost")

    if password:
        cmd.extend(["-passwd", password])
    else:
        cmd.append("-nopw")

    return {"command": cmd, "display": display, "port": port}


def _get_running_process() -> Optional[subprocess.Popen]:
    global _vnc_process
    if _vnc_process and _vnc_process.poll() is None:
        return _vnc_process
    _vnc_process = None
    return None


def get_vnc_status() -> Dict[str, Any]:
    process = _get_running_process()
    return {
        "enabled": is_vnc_enabled(),
        "running": process is not None,
        "pid": process.pid if process else None,
        "host": get_vnc_host(),
        "port": get_vnc_port(),
        "display": get_vnc_display(),
        "localhost_only": is_vnc_localhost_only(),
    }


def start_vnc_server() -> Dict[str, Any]:
    if not is_vnc_enabled():
        return {"running": False, "error": "VNC is disabled (set VNC_ENABLED=true)."}

    with _vnc_lock:
        process = _get_running_process()
        if process:
            return get_vnc_status()

        if not shutil.which("x11vnc"):
            return {"running": False, "error": "x11vnc not found in PATH."}

        payload = _build_x11vnc_command()
        cmd = payload["command"]
        display = payload["display"]
        port = payload["port"]

        env = os.environ.copy()
        env["DISPLAY"] = display

        logger.info(f"Starting x11vnc on display {display}, port {port}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        _set_vnc_process(process)

    return get_vnc_status()


def stop_vnc_server() -> Dict[str, Any]:
    with _vnc_lock:
        process = _get_running_process()
        if not process:
            return get_vnc_status()

        logger.info("Stopping x11vnc process")
        process.terminate()
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()
        _set_vnc_process(None)

    return get_vnc_status()


def _set_vnc_process(process: Optional[subprocess.Popen]) -> None:
    global _vnc_process
    _vnc_process = process


def ensure_vnc_running() -> Dict[str, Any]:
    status = get_vnc_status()
    if status["enabled"] and not status["running"]:
        return start_vnc_server()
    return status


def register_shutdown_hook() -> None:
    def _shutdown():
        if _get_running_process():
            stop_vnc_server()

    atexit.register(_shutdown)

