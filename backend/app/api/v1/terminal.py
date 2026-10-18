"""Web 终端路由：WS /ws/terminal/{host_id}，paramiko PTY ↔ xterm.js。"""
import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AuthError
from app.core.security import decode_token

terminals_router = APIRouter(prefix="/ws", tags=["terminal"])


@terminals_router.websocket("/terminal/{host_id}")
async def terminal_ws(ws: WebSocket, host_id: int):
    token = ws.query_params.get("token", "")
    try:
        payload = decode_token(token) if token else None
        if not payload:
            raise AuthError("未认证")
    except AuthError:
        await ws.close(code=4401)
        return

    from app.services import config_service, host_service
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        enabled = await config_service.get_bool(db, "terminal.enabled", True)
        if not enabled:
            await ws.close(code=4403)
            return
        host = await host_service.get_host(db, host_id)
        target = await host_service.build_ssh_target(db, host)

    # 先 accept 再做后续动作：避免 paramiko import / SSH 连接 hang 住时前端一直转圈
    await ws.accept()

    try:
        import paramiko
    except ImportError:
        await ws.send_json({"type": "output", "data": "\r\n[错误] 后端缺少 paramiko 依赖，无法建立 SSH 终端\r\n"})
        await ws.close(code=4502)
        return

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=target.ip, port=target.port,
                       username=target.username, password=target.password, timeout=10)
    except Exception as e:  # noqa: BLE001
        await ws.send_json({"type": "output", "data": f"\r\n[SSH 连接失败] {e}\r\n"})
        await ws.close(code=4502)
        return

    ch = client.invoke_shell(term="xterm-256color", width=80, height=24)
    ch.settimeout(None)  # 阻塞读，有数据才返回

    loop = asyncio.get_event_loop()

    def _sync_read() -> bytes:
        """阻塞读（在线程中执行，不阻塞事件循环）。"""
        try:
            return ch.recv(4096)
        except Exception:  # noqa: BLE001
            return b""

    async def _reader():
        try:
            while True:
                data = await loop.run_in_executor(None, _sync_read)
                if data:
                    await ws.send_json({"type": "output", "data": data.decode(errors="replace")})
                elif ch.exit_status_ready():
                    break
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                await ws.close(code=1000)
            except Exception:  # noqa: BLE001
                pass

    reader = asyncio.get_event_loop().create_task(_reader())
    try:
        while True:
            raw = await ws.receive_json()
            mtype = raw.get("type")
            if mtype == "input":
                ch.send(raw.get("data", ""))
            elif mtype == "resize":
                ch.resize_pty(width=raw.get("cols", 80), height=raw.get("rows", 24))
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        reader.cancel()
        ch.close()
        client.close()
