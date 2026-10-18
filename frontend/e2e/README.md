# E2E UI 自动化测试（Playwright 无头浏览器）

不依赖 x11 / 图形界面，使用 Playwright headless Chromium 做端到端 UI 自动化测试。

## 前置条件

1. 后端已运行：`http://192.168.31.114:3000`（单端口模式）
2. 目标主机可用：`192.168.31.26 root/123`（SSH 密码认证）
3. 已安装依赖：`npm install playwright` 并下载旧版 chromium（兼容 CentOS 7 GLIBC 2.17）

## 运行

```bash
# 一键跑全部用例
node e2e/run-all.mjs

# 单独跑某个用例
node e2e/tests/01-login.mjs
```

通过环境变量可切换被测地址：

```bash
E2E_BASE_URL=http://<host>:3000 node e2e/run-all.mjs
```

## 用例清单

| 文件 | 覆盖功能 |
|---|---|
| `tests/01-login.mjs` | 登录页：主机密码登录、连接测试按钮（测通/错误密码拒绝） |
| `tests/02-agent-list.mjs` | Agent 主机列表：系统/CPU/内存列、真实数据、Agent 状态列、操作按钮 |
| `tests/03-terminal.mjs` | Web 终端：xterm 挂载、WS 连接、shell 提示符输出 |
| `tests/04-files.mjs` | 文件管理：页面挂载、目录列表渲染 |
| `helpers.mjs` | 共享 helper：浏览器启动、登录、结果收集器 |

## 说明

- 所有测试用例通过后以退出码 0 结束，任一失败退出码 1（可接 CI）
- 浏览器全程 headless，不打开任何窗口
