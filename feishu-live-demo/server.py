from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import queue
import random
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_FILE = BASE_DIR / "data" / "mock_feishu_tables.json"
TZ = timezone(timedelta(hours=8))
HEALTH_ORDER = {"红": 0, "黄": 1, "绿": 2}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def now_cn() -> datetime:
    return datetime.now(TZ)


def now_iso() -> str:
    return now_cn().isoformat(timespec="seconds")


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_label(value: str) -> str:
    return f"{int(value.split('-')[1])}月"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def money(value: float) -> str:
    return f"¥ {value:,.0f} 万"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def max_timestamp(*groups: list[dict]) -> str:
    stamps = [item["updated_at"] for group in groups for item in group]
    return max(stamps) if stamps else now_iso()


class DashboardState:
    def __init__(self, data_file: Path) -> None:
        self.data = load_json(data_file)
        self.lock = threading.Lock()
        self.rng = random.Random(20260501)
        self.version = 1
        self.clients: set[queue.Queue] = set()
        self.activity = deque(
            [
                {
                    "time": "12:16",
                    "source": "财务经营立方",
                    "title": "4 月回款口径补录",
                    "detail": "SaaS 订阅与解决方案两条业务线更新了本周实收。",
                    "tone": "teal",
                },
                {
                    "time": "12:09",
                    "source": "交付重点跟踪",
                    "title": "制造二期验收风险升高",
                    "detail": "DLV-101 缺陷关闭率未达标，预警升为红色。",
                    "tone": "red",
                },
                {
                    "time": "11:58",
                    "source": "项目台账",
                    "title": "金融私有化部署推进到 57%",
                    "detail": "项目已完成环境部署，进入安全测评前准备。",
                    "tone": "amber",
                },
                {
                    "time": "11:41",
                    "source": "经营动作清单",
                    "title": "海外门户资源补位方案更新",
                    "detail": "新增外包前端候选，预计下周释放联调风险。",
                    "tone": "slate",
                },
            ],
            maxlen=14,
        )

    def snapshot(self) -> dict:
        with self.lock:
            payload = build_dashboard_snapshot(self.data, self.version, list(self.activity))
        return payload

    def raw_snapshot(self) -> dict:
        with self.lock:
            return {
                "version": self.version,
                "generated_at": now_iso(),
                "workspace_name": self.data["workspace_name"],
                "tables": copy.deepcopy(self.data),
            }

    def register_client(self) -> queue.Queue:
        channel: queue.Queue = queue.Queue()
        with self.lock:
            self.clients.add(channel)
        return channel

    def unregister_client(self, channel: queue.Queue) -> None:
        with self.lock:
            self.clients.discard(channel)

    def mutate(self, trigger: str) -> dict:
        with self.lock:
            mutation = self.rng.choice(
                [
                    self._mutate_project,
                    self._mutate_delivery,
                    self._mutate_finance,
                    self._mutate_action,
                ]
            )
            event = mutation()
            self.version += 1
            self.activity.appendleft(event)
            snapshot = build_dashboard_snapshot(self.data, self.version, list(self.activity))
            clients = list(self.clients)

        message = {"event": "dashboard", "data": snapshot, "trigger": trigger}
        stale: list[queue.Queue] = []
        for channel in clients:
            try:
                channel.put_nowait(message)
            except queue.Full:
                stale.append(channel)
        if stale:
            with self.lock:
                for channel in stale:
                    self.clients.discard(channel)
        return snapshot

    def _ordinary(self, table_id: str) -> dict:
        for table in self.data["ordinary_tables"]:
            if table["table_id"] == table_id:
                return table
        raise KeyError(table_id)

    def _cube(self, table_id: str) -> dict:
        for table in self.data["multidimensional_tables"]:
            if table["table_id"] == table_id:
                return table
        raise KeyError(table_id)

    def _stamp_table(self, table: dict) -> None:
        table["updated_at"] = now_iso()

    def _mutate_project(self) -> dict:
        table = self._ordinary("tbl_project_register")
        candidates = [record for record in table["records"] if record["stage"] != "暂停"]
        record = self.rng.choice(candidates)
        old_progress = record["progress"]
        delta = self.rng.choice([3, 4, 5, 6, -2])
        record["progress"] = clamp(old_progress + delta, 18, 100)
        if record["progress"] >= 86 and record["stage"] == "实施中":
            record["stage"] = "验收中"
        elif record["progress"] >= 72 and record["stage"] == "规划中":
            record["stage"] = "实施中"
        if record["health"] == "红" and delta > 0 and self.rng.random() > 0.35:
            record["health"] = "黄"
        elif record["health"] == "黄" and delta > 0 and self.rng.random() > 0.58:
            record["health"] = "绿"
        elif delta < 0 and self.rng.random() > 0.55:
            record["health"] = "黄" if record["health"] == "绿" else "红"
        record["revenue_recognized"] = round(record["revenue_recognized"] + max(delta, 0) * self.rng.randint(2, 7), 1)
        record["last_update"] = now_cn().strftime("%Y-%m-%d %H:%M")
        self._stamp_table(table)
        return {
            "time": now_cn().strftime("%H:%M"),
            "source": table["name"],
            "title": f"{record['project_name']} 进度更新至 {record['progress']}%",
            "detail": f"{record['owner']} 刷新了 {record['next_milestone']}，项目健康状态为 {record['health']}。",
            "tone": {"红": "red", "黄": "amber", "绿": "teal"}[record["health"]],
        }

    def _mutate_delivery(self) -> dict:
        table = self._ordinary("tbl_delivery_watchlist")
        record = self.rng.choice(table["records"])
        old_completion = record["completion"]
        delta = self.rng.choice([4, 6, 8, -3])
        record["completion"] = clamp(old_completion + delta, 16, 100)
        if record["completion"] >= 90 and record["health"] == "红":
            record["health"] = "黄"
        elif record["completion"] >= 82 and record["health"] == "黄" and self.rng.random() > 0.45:
            record["health"] = "绿"
        elif delta < 0 and self.rng.random() > 0.55:
            record["health"] = "红"
        if record["completion"] >= 96:
            record["acceptance_status"] = "待客户签收"
        elif record["completion"] >= 70:
            record["acceptance_status"] = "推进中"
        self._stamp_table(table)
        return {
            "time": now_cn().strftime("%H:%M"),
            "source": table["name"],
            "title": f"{record['delivery_id']} 完成度调整为 {record['completion']}%",
            "detail": f"{record['milestone']} 当前状态 {record['acceptance_status']}，风险色标 {record['health']}。",
            "tone": {"红": "red", "黄": "amber", "绿": "teal"}[record["health"]],
        }

    def _mutate_finance(self) -> dict:
        table = self._cube("cube_finance_actuals")
        recent = [record for record in table["records"] if record["month"] in {"2026-04", "2026-05", "2026-06"}]
        record = self.rng.choice(recent)
        delta_revenue = self.rng.randint(-12, 22)
        delta_cash = delta_revenue + self.rng.randint(-9, 6)
        record["revenue_actual"] = round(max(record["revenue_actual"] + delta_revenue, 80), 1)
        record["cash_in"] = round(max(record["cash_in"] + delta_cash, 60), 1)
        if self.rng.random() > 0.65:
            record["cost_actual"] = round(max(record["cost_actual"] + self.rng.randint(-6, 8), 40), 1)
        self._stamp_table(table)
        return {
            "time": now_cn().strftime("%H:%M"),
            "source": table["name"],
            "title": f"{month_label(record['month'])} {record['business_line']} 财务口径刷新",
            "detail": f"营收更新为 {money(record['revenue_actual'])}，实收更新为 {money(record['cash_in'])}。",
            "tone": "teal" if delta_revenue >= 0 else "amber",
        }

    def _mutate_action(self) -> dict:
        table = self._ordinary("tbl_action_register")
        record = self.rng.choice(table["records"])
        delta = self.rng.choice([5, 7, 9, -4])
        record["progress"] = clamp(record["progress"] + delta, 10, 100)
        if record["progress"] >= 92:
            record["status"] = "待验证"
        elif record["progress"] >= 80 and record["status"] == "高优先级":
            record["status"] = "推进中"
        elif delta < 0 and self.rng.random() > 0.5:
            record["status"] = "阻塞中"
        self._stamp_table(table)
        return {
            "time": now_cn().strftime("%H:%M"),
            "source": table["name"],
            "title": f"{record['topic']} 进度 {record['progress']}%",
            "detail": f"{record['owner']} 更新了动作状态，当前为 {record['status']}，影响域 {record['impact_area']}。",
            "tone": "slate" if record["status"] == "推进中" else "amber",
        }


def build_dashboard_snapshot(data: dict, version: int, activity: list[dict]) -> dict:
    tables = {table["table_id"]: table for table in data["ordinary_tables"]}
    cubes = {table["table_id"]: table for table in data["multidimensional_tables"]}

    projects = tables["tbl_project_register"]["records"]
    deliveries = tables["tbl_delivery_watchlist"]["records"]
    actions = tables["tbl_action_register"]["records"]
    finance = cubes["cube_finance_actuals"]["records"]

    revenue_actual = sum(item["revenue_actual"] for item in finance)
    revenue_plan = sum(item["revenue_plan"] for item in finance)
    gross_profit = sum(item["revenue_actual"] - item["cost_actual"] for item in finance)
    cash_in = sum(item["cash_in"] for item in finance)
    attainment = revenue_actual / revenue_plan * 100 if revenue_plan else 0
    gross_margin = gross_profit / revenue_actual * 100 if revenue_actual else 0
    cash_rate = cash_in / revenue_actual * 100 if revenue_actual else 0
    active_projects = [item for item in projects if item["stage"] != "暂停"]
    warning_projects = [item for item in projects if item["health"] != "绿"]
    due_soon_deliveries = [item for item in deliveries if days_until(item["due_date"]) <= 14]
    red_deliveries = [item for item in deliveries if item["health"] == "红"]
    blocked_actions = [item for item in actions if item["status"] in {"阻塞中", "高优先级"}]

    monthly = []
    for month in sorted({item["month"] for item in finance}):
        rows = [item for item in finance if item["month"] == month]
        plan = sum(item["revenue_plan"] for item in rows)
        actual = sum(item["revenue_actual"] for item in rows)
        cash = sum(item["cash_in"] for item in rows)
        margin = (
            sum(item["revenue_actual"] - item["cost_actual"] for item in rows) / actual * 100 if actual else 0
        )
        monthly.append(
            {
                "month": month,
                "label": month_label(month),
                "plan": round(plan, 1),
                "actual": round(actual, 1),
                "cash_in": round(cash, 1),
                "margin": round(margin, 1),
            }
        )

    line_totals: dict[str, dict] = defaultdict(lambda: {"plan": 0.0, "actual": 0.0, "cash": 0.0, "cost": 0.0})
    for row in finance:
        bucket = line_totals[row["business_line"]]
        bucket["plan"] += row["revenue_plan"]
        bucket["actual"] += row["revenue_actual"]
        bucket["cash"] += row["cash_in"]
        bucket["cost"] += row["cost_actual"]
    line_performance = []
    for business_line, values in line_totals.items():
        actual = values["actual"]
        margin_value = (actual - values["cost"]) / actual * 100 if actual else 0
        attainment_value = actual / values["plan"] * 100 if values["plan"] else 0
        line_performance.append(
            {
                "business_line": business_line,
                "actual": round(actual, 1),
                "plan": round(values["plan"], 1),
                "cash": round(values["cash"], 1),
                "margin": round(margin_value, 1),
                "attainment": round(attainment_value, 1),
            }
        )
    line_performance.sort(key=lambda item: item["actual"], reverse=True)

    health_counts = Counter(item["health"] for item in projects)
    stage_counts = Counter(item["stage"] for item in projects)

    focus_projects = []
    for item in sorted(
        projects,
        key=lambda row: (
            PRIORITY_ORDER.get(row["priority"], 9),
            HEALTH_ORDER.get(row["health"], 9),
            days_until(row["milestone_due"]),
        ),
    )[:6]:
        focus_projects.append(
            {
                "project_code": item["project_code"],
                "project_name": item["project_name"],
                "owner": item["owner"],
                "business_line": item["business_line"],
                "stage": item["stage"],
                "health": item["health"],
                "progress": item["progress"],
                "milestone": item["next_milestone"],
                "milestone_due": item["milestone_due"],
                "days_to_due": days_until(item["milestone_due"]),
                "blocker": item["blocker"],
                "revenue_recognized": item["revenue_recognized"],
                "priority": item["priority"],
            }
        )

    delivery_focus = []
    for item in sorted(
        deliveries,
        key=lambda row: (
            PRIORITY_ORDER.get(row["priority"], 9),
            HEALTH_ORDER.get(row["health"], 9),
            days_until(row["due_date"]),
        ),
    )[:8]:
        delivery_focus.append(
            {
                "delivery_id": item["delivery_id"],
                "project_code": item["project_code"],
                "milestone": item["milestone"],
                "owner": item["owner"],
                "due_date": item["due_date"],
                "days_to_due": days_until(item["due_date"]),
                "priority": item["priority"],
                "completion": item["completion"],
                "health": item["health"],
                "acceptance_status": item["acceptance_status"],
                "note": item["note"],
            }
        )

    action_board = []
    for item in sorted(
        actions,
        key=lambda row: (days_until(row["due_date"]), 100 - row["progress"]),
    )[:5]:
        action_board.append(
            {
                "topic": item["topic"],
                "owner": item["owner"],
                "impact_area": item["impact_area"],
                "due_date": item["due_date"],
                "days_to_due": days_until(item["due_date"]),
                "progress": item["progress"],
                "status": item["status"],
                "expected_gain": item["expected_gain"],
            }
        )

    alerts = []
    for item in projects:
        if item["health"] == "红" or item["stage"] == "暂停":
            alerts.append(
                {
                    "level": "critical",
                    "title": f"{item['project_name']} 需要经营介入",
                    "detail": f"{item['priority']} / {item['stage']} / {item['next_milestone']}，阻塞：{item['blocker']}",
                    "owner": item["owner"],
                    "due_date": item["milestone_due"],
                }
            )
    for item in deliveries:
        if item["health"] != "绿" and days_until(item["due_date"]) <= 10:
            alerts.append(
                {
                    "level": "warning" if item["health"] == "黄" else "critical",
                    "title": f"{item['delivery_id']} 临近交付窗口",
                    "detail": f"{item['milestone']} {item['completion']}%，当前状态 {item['acceptance_status']}。",
                    "owner": item["owner"],
                    "due_date": item["due_date"],
                }
            )
    for item in actions:
        if days_until(item["due_date"]) <= 7 and item["progress"] < 75:
            alerts.append(
                {
                    "level": "attention",
                    "title": item["topic"],
                    "detail": f"{item['status']}，预计收益：{item['expected_gain']}。",
                    "owner": item["owner"],
                    "due_date": item["due_date"],
                }
            )
    alerts.sort(key=lambda item: (alert_rank(item["level"]), item["due_date"]))
    alerts = alerts[:7]

    source_tables = []
    for table in data["ordinary_tables"]:
        source_tables.append(
            {
                "name": table["name"],
                "table_id": table["table_id"],
                "shape": "普通表格",
                "row_count": len(table["records"]),
                "field_count": len(table["fields"]),
                "updated_at": table["updated_at"],
                "sync_mode": "Webhook / 定时轮询可替换",
            }
        )
    for table in data["multidimensional_tables"]:
        source_tables.append(
            {
                "name": table["name"],
                "table_id": table["table_id"],
                "shape": "多维表格",
                "row_count": len(table["records"]),
                "field_count": len(table["dimensions"]) + len(table["metrics"]),
                "updated_at": table["updated_at"],
                "sync_mode": "立方聚合 / 指标透视",
            }
        )

    return {
        "workspace_name": data["workspace_name"],
        "version": version,
        "generated_at": now_iso(),
        "source_summary": {
            "ordinary_tables": len(data["ordinary_tables"]),
            "multidimensional_tables": len(data["multidimensional_tables"]),
            "last_sync": max_timestamp(data["ordinary_tables"], data["multidimensional_tables"]),
            "mode": "Mock 飞书实时同步",
        },
        "kpis": [
            {
                "id": "revenue",
                "label": "营收累计",
                "display": money(revenue_actual),
                "detail": f"计划达成 {pct(attainment)}",
                "signal": "逐月来自财务经营立方的实时汇总",
                "tone": "teal",
            },
            {
                "id": "gross_margin",
                "label": "综合毛利率",
                "display": pct(gross_margin),
                "detail": f"毛利额 {money(gross_profit)}",
                "signal": "解决方案与交付服务是拉低点",
                "tone": "ink",
            },
            {
                "id": "cash_rate",
                "label": "回款转换率",
                "display": pct(cash_rate),
                "detail": f"累计实收 {money(cash_in)}",
                "signal": "临近交付项目是本周回款抓手",
                "tone": "amber",
            },
            {
                "id": "active_projects",
                "label": "活跃项目数",
                "display": f"{len(active_projects)} 个",
                "detail": f"其中预警项目 {len(warning_projects)} 个",
                "signal": "P0 / P1 项目占比偏高",
                "tone": "rose",
            },
            {
                "id": "delivery_warning",
                "label": "交付预警",
                "display": f"{len(red_deliveries) + len(blocked_actions)} 项",
                "detail": f"14 天内关键节点 {len(due_soon_deliveries)} 项",
                "signal": "红灯里程碑需要经营例会逐项盯办",
                "tone": "slate",
            },
        ],
        "trend": monthly,
        "health": {
            "total_projects": len(projects),
            "health_counts": {
                "red": health_counts.get("红", 0),
                "amber": health_counts.get("黄", 0),
                "green": health_counts.get("绿", 0),
            },
            "stage_counts": dict(stage_counts),
        },
        "line_performance": line_performance,
        "focus_projects": focus_projects,
        "delivery_focus": delivery_focus,
        "action_board": action_board,
        "alerts": alerts,
        "source_tables": source_tables,
        "activity": activity,
        "architecture": [
            "飞书普通表格",
            "飞书多维表格",
            "聚合中间层",
            "SSE 实时看板",
        ],
    }


def days_until(value: str) -> int:
    return (parse_day(value) - now_cn().date()).days


def alert_rank(value: str) -> int:
    return {"critical": 0, "warning": 1, "attention": 2}.get(value, 9)


class DashboardHandler(BaseHTTPRequestHandler):
    state: DashboardState

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/api/dashboard":
            self._send_json(self.state.snapshot())
            return
        if route == "/api/tables":
            self._send_json(self.state.raw_snapshot())
            return
        if route == "/api/healthz":
            self._send_json({"status": "ok", "time": now_iso()})
            return
        if route == "/events":
            self._handle_events()
            return
        self._serve_static(route)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/mutate":
            snapshot = self.state.mutate(trigger="manual")
            self._send_json({"status": "ok", "snapshot": snapshot}, status=HTTPStatus.ACCEPTED)
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, route: str) -> None:
        target = "index.html" if route in {"", "/"} else route.lstrip("/")
        path = (STATIC_DIR / target).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime, _ = mimetypes.guess_type(path.name)
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        if path.suffix == ".html":
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _handle_events(self) -> None:
        channel = self.state.register_client()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self._emit_event("dashboard", self.state.snapshot())
            while True:
                try:
                    message = channel.get(timeout=20)
                except queue.Empty:
                    self._emit_event("heartbeat", {"time": now_iso()})
                    continue
                self._emit_event(message["event"], message["data"])
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.state.unregister_client(channel)

    def _emit_event(self, event: str, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        message = f"event: {event}\ndata: {body}\n\n".encode("utf-8")
        self.wfile.write(message)
        self.wfile.flush()


def run_server(host: str, port: int, interval: int) -> None:
    state = DashboardState(DATA_FILE)
    DashboardHandler.state = state
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    simulator = threading.Thread(target=simulation_loop, args=(state, interval), daemon=True)
    simulator.start()
    print(f"Serving dashboard on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def simulation_loop(state: DashboardState, interval: int) -> None:
    while True:
        time.sleep(interval)
        state.mutate(trigger="auto")


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu live dashboard demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=int, default=8, help="simulation interval in seconds")
    args = parser.parse_args()
    run_server(args.host, args.port, args.interval)


if __name__ == "__main__":
    main()
