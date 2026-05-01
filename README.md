# Dashboard Demos

一个用于演示经营数据可视化的前端原型仓库，当前包含两类内容：

- 4 个静态经营/财务/项目分析看板页面
- 1 个基于 mock 飞书表格数据的实时经营看板原型

## 在线访问

- 仓库主页预览：
  `https://phiclin-pixel.github.io/dashboard-demos/`
- 飞书实时经营看板 Demo：
  `https://phiclin-pixel.github.io/dashboard-demos/feishu-live-demo/static/index.html`

## 包含内容

- `index.html`
  GitHub Pages 首页，汇总所有 demo 入口。
- `dashboard-1-overview.html`
  经营总览大屏。
- `dashboard-2-quarterly.html`
  季度 / 年度对比分析。
- `dashboard-3-projects.html`
  项目过程看板。
- `dashboard-4-financial.html`
  财务指标仪表盘。
- `feishu-live-demo/`
  飞书实时经营看板原型，包含 mock 表格数据、前端页面和本地实时服务。

## 飞书实时经营看板说明

这个 demo 验证的是一条最小闭环：

`飞书普通表格 / 多维表格 -> 聚合中间层 -> 经营看板`

在线版为了适配 GitHub Pages，使用静态快照进行展示；本地运行服务时，可以切换为带 `/api` 和 `/events` 的实时模式。

详细说明见：

- [feishu-live-demo/README.md](./feishu-live-demo/README.md)

## 本地运行实时版

```bash
cd feishu-live-demo
python3 server.py --port 8765
```

然后访问：

- `http://127.0.0.1:8765/`

## 后续接真实飞书时建议补的部分

1. 飞书开放平台认证与 API 适配层。
2. 统一字段映射和指标口径配置。
3. 增量同步、Webhook 和权限控制。
