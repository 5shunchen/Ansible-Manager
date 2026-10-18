# Ansible Manager 应用部署手册（am-containerd 隔离容器）

本文档说明如何把 **ansible-manager 自身**作为一个 app，通过平台的"应用主机 → 装 App"按钮，部署到远程目标机上运行。

部署形态：在目标机 `/opt/am-containerd/` 下跑一套**独立的 containerd**（二进制改名为 `am-containerd` / `am-ctr`），与系统 docker/containerd 完全隔离；ansible-manager 作为一个容器跑在这套 am-containerd 里。

---

## 1. 整体架构

```
┌─────────────────────────── 控制端（构建机）──────────────────────────┐
│  ansible-manager 平台（当前 .114:3000）                                │
│    ├─ docker build  → ansible-manager:local 镜像                      │
│    ├─ docker save    → data/plugins/bundle/ansible-manager-local.tar  │
│    └─ 应用主机页 → 装 App → 调起 am_app role（ansible）                │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ SSH + ansible-playbook
                               ▼
┌─────────────────────────── 目标机（.127）──────────────────────────────┐
│  /opt/am-containerd/                                                   │
│    ├─ bin/am-containerd    （独立 containerd daemon）                  │
│    ├─ bin/am-ctr           （独立 ctr 客户端）                         │
│    ├─ run/containerd/containerd.sock  （独立 socket）                  │
│    ├─ var/lib/containerd/  （独立镜像/快照存储）                       │
│    ├─ data/                （挂载进容器 /app/data，持久化 SQLite 等）  │
│    └─ containerd.log                                                  │
│                                                                        │
│  容器：ansible-manager  (am-ctr run --net-host，占宿主机 3000 端口)    │
│    └─ uvicorn app.main:app --host 0.0.0.0 --port 3000                 │
└────────────────────────────────────────────────────────────────────────┘
```

**关键隔离性**：
- 不注册 systemd 服务，不写 `/etc/containerd/config.toml`
- 不读系统 `/var/run/docker.sock` 或 `/run/containerd/containerd.sock`
- 系统 `docker ps` 看不到这套容器；`am-ctr` 也看不到系统 docker 的容器

---

## 2. 镜像构建（在控制端）

### 2.1 前置条件
- 控制端已装 docker（本项目用 docker-ce 26.1.4）
- 仓库根目录 `/root/ai/ansible-manager/Dockerfile` 已就绪（多阶段：node 构建前端 → python:3.11-slim 跑后端）

### 2.2 构建并导出 tar

```bash
cd /root/ai/ansible-manager

# 构建镜像
docker build -t ansible-manager:local .

# 导出为 tar（供 am-ctr import）
docker save -o backend/data/plugins/bundle/ansible-manager-local.tar ansible-manager:local

# 顺手把 containerd 套件二进制打成 bundle（只需要做一次）
cd /tmp && tar czf \
  /root/ai/ansible-manager/backend/data/plugins/bundle/containerd-bundle-1.6.33.tar.gz \
  -C /usr/bin containerd containerd-shim containerd-shim-runc-v1 containerd-shim-runc-v2 ctr runc
```

产物：
```
backend/data/plugins/bundle/
├── ansible-manager-local.tar           (~275 MB，应用镜像)
└── containerd-bundle-1.6.33.tar.gz      (~ 43 MB，containerd 套件)
```

> 这两个 tar 的路径在插件 `am-app` 的 `config` 里登记（平台数据库 `plugin.config`），role 执行时直接从控制端 `copy` 过去。

---

## 3. 部署（在平台 UI 上一键完成）

### 3.1 登记目标机为应用主机
应用主机页 → 新增主机 → 填 IP / SSH 端口 / root / 密码。

### 3.2 目标机前置准备（CentOS 7 等老系统）
ansible 2.17 要求目标机 Python ≥ 3.10。CentOS 7 自带 python3.6 不够，需要装个 miniconda：

```bash
# 在目标机上
bash /tmp/miniconda-py310.sh -b -p /opt/miniconda3
/opt/miniconda3/bin/python --version   # Python 3.10.10
```

装 App 时附加变量传：
```json
{ "ansible_python_interpreter": "/opt/miniconda3/bin/python" }
```

### 3.3 点"装 App"
应用主机行 → **装 App** → 选 `am-app` 插件 → 确认。

后台会拉起一个 task（类型 `app_install`），任务管理页能实时看到日志。完成后：
- 目标机 `/opt/am-containerd/` 已就位
- am-containerd 进程已启动
- ansible-manager 容器已跑起来
- 浏览器访问 `http://<目标机IP>:3000`

---

## 4. 日常运维命令（在目标机上执行）

部署完成后，目标机上 `am-ctr` 已加入 PATH（`/etc/profile.d/am-containerd.sh` + `~/.bashrc`）。**新开一个 SSH 会话**或 `source /etc/profile.d/am-containerd.sh` 后直接用：

```bash
# 环境变量已经由 profile.d 自动设好：
#   AM_CONTAINERD_DIR=/opt/am-containerd
#   CONTAINERD_ADDRESS=/opt/am-containerd/run/containerd/containerd.sock
#   CONTAINERD_NAMESPACE=k8s.io
# 所以所有 am-ctr 命令都不用再敲 --address 和 -n
```

### 4.1 查看

```bash
# 看 am-containerd 进程是否在跑
ps -ef | grep am-containerd

# 看监听端口（uvicorn 应该在 *:3000）
ss -tlnp | grep 3000

# 看所有容器
am-ctr containers list

# 看所有任务（运行态）
am-ctr tasks list

# 看镜像列表
am-ctr images ls

# 看某个容器的详情（id / 镜像 / 状态）
am-ctr containers info ansible-manager

# 看容器日志（容器 stdout/stderr）
am-ctr tasks metrics ansible-manager 2>/dev/null   # 简略
# 真实日志：am-containerd 本身的日志在
tail -f /opt/am-containerd/containerd.log
# 应用日志：目前 uvicorn 输出到容器 stdout，可用 crictl/nerdctl 替代方案不方便时，
# 直接进容器看：
am-ctr tasks exec --exec-id shell-1 ansible-manager sh
```

### 4.2 重启 / 停止 / 启动容器

```bash
# 停止（杀进程，不删容器）
am-ctr tasks kill ansible-manager

# 启动（容器还在，重新跑它）
am-ctr tasks start ansible-manager

# 重启 = 先 kill 再 start
am-ctr tasks kill ansible-manager
am-ctr tasks start ansible-manager
```

### 4.3 删除部署

```bash
# 删容器（先 kill 再 delete）
am-ctr tasks kill ansible-manager
am-ctr containers delete ansible-manager

# 删镜像（可选，释放磁盘）
am-ctr images rm ansible-manager:local
am-ctr images rm docker.io/library/ansible-manager:local

# 停掉 am-containerd daemon 本身
pkill -f /opt/am-containerd/bin/am-containerd

# 彻底卸载（在平台 UI 点"卸载 App"，或手动）：
rm -rf /opt/am-containerd
```

### 4.4 升级镜像（重新部署）

```bash
# 1. 控制端重新 build + save
cd /root/ai/ansible-manager
docker build -t ansible-manager:local .
docker save -o backend/data/plugins/bundle/ansible-manager-local.tar ansible-manager:local

# 2. 平台 UI：应用主机行 → App 列表 → 卸载 → 再装 App
#    （或者直接在应用主机页再点一次"装 App"，role 是幂等的：
#     会重新 import 新镜像 → 停旧容器 → 起新容器）
```

---

## 5. 常见问题

### 5.1 `am-ctr: command not found`
新开会话还没加载 profile。执行：
```bash
source /etc/profile.d/am-containerd.sh
# 或直接用绝对路径
/opt/am-containerd/bin/am-ctr version
```

### 5.2 浏览器访问 `http://<目标机>:3000` 不通
目标机 firewalld 默认不开 3000：
```bash
firewall-cmd --add-port=3000/tcp --permanent
firewall-cmd --reload
```

### 5.3 任务日志报 `the role 'am_app' was not found`
平台后端没把 `ANSIBLE_ROLES_PATH` 注入 ansible-runner。检查：
```bash
grep ANSIBLE_ROLES_PATH /root/ai/ansible-manager/backend/app/runner/ansible_executor.py
# 应该看到在 run() 里设置了 os.environ["ANSIBLE_ROLES_PATH"]=<data/plugins/roles>
```

### 5.4 `am-ctr run` 报 `image "ansible-manager:local": not found`
docker save 导入后镜像名是 `docker.io/library/ansible-manager:local`。role 里会自动 tag 成短名。手动补：
```bash
am-ctr images tag docker.io/library/ansible-manager:local ansible-manager:local
```

### 5.5 容器起来立刻退出
进容器看错误：
```bash
am-ctr tasks exec --exec-id debug-1 ansible-manager uvicorn app.main:app --host 0.0.0.0 --port 3000
# 常见原因：缺 Python 依赖（看 ModuleNotFoundError）
```

---

## 6. 与"工程部署"菜单的区别

| 维度 | 应用主机 → 装 App | 工程部署菜单 |
|---|---|---|
| 部署对象 | ansible-manager **自身**（平台即 app） | 任意业务镜像（nginx / java / …） |
| 触发入口 | 应用主机行内"装 App"按钮 | 部署工程 CRUD + 部署按钮 |
| 镜像来源 | 本机 docker build + tar 分发 | registry 拉取 或 docker build |
| 容器运行时 | am-containerd（同一套底座） | am-containerd（同一套底座） |
| 任务类型 | `app_install` / `app_uninstall` | `deploy` |
| 生命周期记录 | `host_app` 表 | `deploy_project` / `deploy_record` / `deploy_container` |

简单说：**装 App 是"把平台自己装到别的机器上"，工程部署是"把业务镜像装到一群机器上"**。

---

## 7. 从代码仓冷启动（离线场景）

仓库内已经携带好部署所需的全部二进制与 Python 依赖，构建机即使没外网也能拉起平台：

```
仓库根/
├─ backend/wheels/*.whl                # 60 个 python wheel（py3.10 / manylinux x86_64）
├─ backend/requirements-lock.txt       # 版本锁（与 wheels/ 内文件一一对应）
└─ backend/data/plugins/bundle/
   ├─ containerd-bundle-1.6.33.tar.gz # containerd + runc + shim 二进制（走 LFS）
   └─ ansible-manager-local.tar        # ansible-manager 应用镜像（走 LFS）
```

### 7.1 首次 clone / 拉 LFS 对象

```bash
git clone https://github.com/5shunchen/Ansible-Manager.git
cd Ansible-Manager
git lfs install
git lfs pull          # 若 clone 后 tar/wheels 是 13 字节指针文件，先跑这个
```

校验 LFS 落盘：

```bash
ls -lh backend/data/plugins/bundle/
#  ansible-manager-local.tar   ~297M
#  containerd-bundle-1.6.33.tar.gz  ~45M
```

### 7.2 装后端（无外网）

依赖 CentOS 7 目标机自带 python3.6 无法跑 ansible 2.17，需要先装 Miniconda py310：

```bash
# 有网时一次性准备（构建机上）
bash scripts/install_miniconda_py310.sh   # 脚本见 deploy/dev/

# 无外网时，直接用仓库里的 wheels：
/opt/miniconda3/bin/pip install --no-index --find-links=backend/wheels \
    -r backend/requirements-lock.txt
```

### 7.3 起后端

```bash
cd backend
/opt/miniconda3/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 3000
```

### 7.4 起前端（可选；容器部署已自带前端）

```bash
cd frontend
npm ci
npm run build      # 产物 dist/
```

### 7.5 应用主机装 App

1. 前端 → 应用主机 → 新增主机（SSH 可通）
2. 行内点「部署」→ 选 `am_app` 插件 → 提交
3. 任务管理页实时看日志；role 内部会自动把 `containerd-bundle` 与 `ansible-manager-local.tar` 通过 SSH 推到目标机 `/opt/am-containerd/` 并起容器。
