# 飞书经营看板实时原型

这个目录是一个可直接运行的动态网页服务原型，用来演示下面这条链路：

`飞书普通表格 / 多维表格 -> 聚合中间层 -> 经营看板实时推送`

当前版本先用 mock 数据把产品形态跑通，便于你确认看板结构、口径和交互方式。后续只需要把 mock 数据接入层替换成真实飞书 API。

## 目录结构

- `data/mock_feishu_tables.json`
  模拟的飞书表格数据，包含：
  - 项目台账
  - 交付重点跟踪
  - 经营动作清单
  - 财务经营立方
- `server.py`
  Python 标准库实现的轻量服务：
  - 提供原始表格接口
  - 做经营口径聚合
  - 提供 SSE 实时推送
  - 定时模拟表格更新
- `static/`
  单页前端页面，原生 HTML/CSS/JS，无框架依赖

## 本地运行

```bash
cd /home/phiclin/dashboard-demos/feishu-live-demo
python3 server.py --port 8765
```

启动后打开：

- `http://127.0.0.1:8765/`

可用接口：

- `GET /api/dashboard`
  聚合后的经营看板数据
- `GET /api/tables`
  原始 mock 表格数据
- `POST /api/mutate`
  手动模拟一次表格变更
- `GET /events`
  SSE 实时事件流

## 这个原型验证了什么

1. 多张来源表可以先统一成一层标准记录模型，而不是让前端直接拼飞书 API。
2. 财务、项目、交付、经营动作可以在中间层做二次聚合和统一告警。
3. 看板不需要静态发布，可以做成一个持续运行的动态网页服务。
4. 当表格变化时，服务端可以直接推事件给前端，不必整页刷新。

## 上真实飞书时的建议结构

建议按四层来做：

1. `Feishu Adapter`
   负责调用飞书开放平台，读取普通表格和多维表格，处理认证、分页、限流、字段映射。
2. `Normalization Layer`
   把不同表结构统一成项目、交付、财务、动作这些标准实体。
3. `Aggregation / Rules Layer`
   负责 KPI 口径、预警规则、趋势汇总、重点项目排序、经营动作闭环。
4. `Dashboard Delivery Layer`
   负责对前端输出 JSON、SSE 或 WebSocket。

## 后续最值得补的三件事

1. 接真实飞书 API，并把 mock loader 替换成 adapter。
2. 给指标口径和预警规则加配置化能力。
3. 增加登录、权限和多看板视图。
