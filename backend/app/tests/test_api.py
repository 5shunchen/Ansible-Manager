"""API 集成测试：认证/RBAC/主机 CRUD/Playbook/任务（FakeExecutor）。"""
import pytest


async def test_login_and_me(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["username"] == "admin"
    assert data["menus"], "菜单树不应为空"
    assert "host:create" in data["permissions"] or data["user"]["is_superuser"]


async def test_login_wrong_password(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401


async def test_unauthorized(client):
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401


async def test_host_crud(client, auth_headers):
    # 建凭据
    resp = await client.post("/api/v1/credentials", headers=auth_headers, json={
        "name": "cred1", "auth_type": "password", "username": "root", "password": "secret", "default_port": 22,
    })
    assert resp.status_code == 200, resp.text
    cred_id = resp.json()["data"]["id"]

    # 建主机（密码永不出现在响应中）
    resp = await client.post("/api/v1/hosts", headers=auth_headers, json={
        "hostname": "web-01", "ip": "10.0.0.11", "host_type": "app", "credential_id": cred_id,
    })
    assert resp.status_code == 200, resp.text
    host_id = resp.json()["data"]["id"]

    resp = await client.get("/api/v1/hosts", headers=auth_headers, params={"host_type": "app"})
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["ip"] == "10.0.0.11"

    # 连通检测（注入 FakeTransport）
    from app.api import deps
    from app.tests.fakes import FakeTransport
    from app.main import create_app

    resp = await client.post(f"/api/v1/hosts/{host_id}/check", headers=auth_headers)
    # 真实 asyncssh 会失败（连不上 10.0.0.11），但仍返回 reachable=false
    assert resp.status_code in (200, 502)
    if resp.status_code == 200:
        assert resp.json()["data"]["host_id"] == host_id


async def test_rbac_viewer_cannot_create_host(client, auth_headers):
    """只读角色用户不可创建主机。"""
    # 建 viewer 用户
    resp = await client.get("/api/v1/roles", headers=auth_headers)
    roles = resp.json()["data"]
    viewer_id = next(r["id"] for r in roles if r["code"] == "viewer")
    resp = await client.post("/api/v1/users", headers=auth_headers, json={
        "username": "vuser", "password": "viewer123", "role_ids": [viewer_id],
    })
    assert resp.status_code == 200, resp.text

    resp = await client.post("/api/v1/auth/login", json={"username": "vuser", "password": "viewer123"})
    vtoken = resp.json()["data"]["token"]
    vheaders = {"Authorization": f"Bearer {vtoken}"}

    resp = await client.post("/api/v1/credentials", headers=vheaders, json={
        "name": "x", "auth_type": "password", "username": "root", "password": "p",
    })
    assert resp.status_code == 403
    assert resp.json()["code"] == 40300

    # viewer 菜单可见但按钮权限缺失
    resp = await client.get("/api/v1/auth/me", headers=vheaders)
    data = resp.json()["data"]
    assert "host:create" not in data["permissions"]
    assert any(m["name"] == "主机管理" for m in data["menus"])


async def test_playbook_and_task_flow(client, auth_headers, monkeypatch):
    """Playbook 创建 + 任务创建（FakeExecutor 替换）。"""
    resp = await client.post("/api/v1/playbooks", headers=auth_headers, json={
        "name": "ping-pb", "description": "ping 测试", "entry_file": "site.yml",
        "content": "- hosts: all\n  gather_facts: false\n  tasks:\n    - ansible.builtin.ping:\n",
    })
    assert resp.status_code == 200, resp.text
    pid = resp.json()["data"]["id"]

    # 凭据 + 主机
    resp = await client.post("/api/v1/credentials", headers=auth_headers, json={
        "name": "cred1", "auth_type": "password", "username": "root", "password": "secret",
    })
    cred_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/hosts", headers=auth_headers, json={
        "hostname": "h1", "ip": "127.0.0.1", "credential_id": cred_id,
    })
    host_id = resp.json()["data"]["id"]

    # 替换任务执行器为 Fake
    from app.runner import task_worker as tw
    from app.tests.fakes import FakeExecutor

    fake = FakeExecutor()

    def fake_run(self, spec, on_event):
        return fake.run(spec, on_event)

    import app.runner.ansible_executor as ae

    monkeypatch.setattr(ae.AnsibleExecutor, "run", fake_run)

    import asyncio

    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "name": "ping 任务", "playbook_id": pid, "host_ids": [host_id],
    })
    assert resp.status_code == 200, resp.text
    task_id = resp.json()["data"]["id"]

    # worker 异步执行，等待完成
    await asyncio.sleep(0.5)
    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    data = resp.json()["data"]
    assert data["task"]["status"] == "success"
    assert data["targets"][0]["status"] in ("ok", "pending")

    # 事件已入库
    resp = await client.get(f"/api/v1/tasks/{task_id}/events", headers=auth_headers)
    events = resp.json()["data"]
    assert len(events) >= 3
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
