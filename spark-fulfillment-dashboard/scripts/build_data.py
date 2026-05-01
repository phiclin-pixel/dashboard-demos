from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_XLSX = Path("/home/phiclin/dashboard-imports/xinghuo-fulfillment-tracking.xlsx")
DEFAULT_OUTPUT_JSON = ROOT / "data" / "dashboard-data.json"
MONTHS = [f"{i}月" for i in range(1, 13)]
EXCEL_EPOCH = datetime(1899, 12, 30)

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

IN_TRANSIT_HEADERS = {
    "business_unit": "业务单元",
    "node_status": "节点完成情况",
    "unrecognized": "未计收金额",
    "converted_not_collected": "已转化未回款",
    "payment_code": "付款编码",
    "contract_no": "合同编号",
    "deleted": "是否删除",
    "opportunity_code": "商机编码",
    "client": "签约客户",
    "final_user": "最终用户",
    "region_2026": "26年区域划分",
    "customer_group_2026": "26年客群划分",
    "contract_amount": "合同金额 （万元）",
    "payment_type": "货款类别",
    "base_payment": "基准回款金额 （万元）",
    "delivery_dept": "交付部",
    "project_manager_formula": "项目经理 （公式）",
    "project_code": "项目编码 （公式）",
    "project_name": "项目名称 （公式）",
    "army_focus": "是否为军团重点项目",
    "milestone": "里程碑节点（POMP)",
    "acceptance_tag": "验收节点打标（初验/终验）",
    "project_type": "立项类型(公式)",
    "project_status": "项目状态(公式)",
    "delivery_progress": "交付进度",
    "baseline_year": "26年基线转化年份-1月拧合定稿",
    "baseline_month": "26年基线转化月份-1月拧合定稿",
    "pomp_pred_month": "POMP 最新预测月份(公式)",
    "pomp_pred_year": "POMP 最新预测年份(公式)",
    "pomp_actual_month": "POMP 实际达成月份(公式)",
    "pomp_actual_year": "POMP 实际达成年份(公式)",
    "delivery_group": "项目归属交付小组",
    "project_manager": "项目经理",
    "live_pred_time": "实时转化时间预测",
    "live_pred_year": "实时转化时间预测转化年份",
    "live_pred_month": "实时转化时间预测转化月份",
    "actual_finish_time": "实际转化完成时间",
    "actual_finish_month": "实际转化完成时间转化月份",
    "recognized_forecast": "确收预测",
    "recognized_amount": "确收金额 （合同额）",
    "gross_profit": "上报收入毛利",
    "risk_degree": "风险度",
    "cost_amount": "成本金额",
    "progress_note": "项目进展： 例：11月完成上线，12月推进验收 卡点：**产品尚未发版， 诉求：**产线**人需要保障**时间完成发版",
    "industry_qt": "行业划分-qt",
    "analysis_tag": "分析标签",
    "pause_reason": "暂停交付原因",
    "paid_amount": "已回款 金额（万）",
    "collection_forecast_month": "回款\"月初\" 预测月份",
    "receivable_progress": "回款进展 （应收账款BY列分类“逾期”“当月到期”必填）",
    "receivable_risk_level": "风险等级",
    "receivable_risk_desc": "风险描述（中高风险需要描述）",
    "resource_need": "资源诉求",
    "ar_balance": "应收账款余额 （基准回款金额-已回款金额）",
    "ar_category": "应收账款分类 （内部）",
    "bad_debt_age": "逾期坏账账龄分类",
    "posted_tax_amount": "账面借方累计含税发生额（万元）",
    "accounting_year": "计收年份",
    "achieved_amount": "付款条件约定达成金额（万元）",
    "latest_collection_due": "约定最晚回款时间",
    "due_amount": "到期欠款（万元）",
    "due_months": "欠款时长（月）",
    "overdue_months": "逾期时长（月）",
    "pending_conversion": "待转化交易款（万元）",
    "not_due_amount": "未到期欠款",
    "securitization_ok": "是否满足资产证券化条件",
}

PRODUCT_HEADERS = [
    "智能客服",
    "智能语音",
    "知识运营",
    "营销助手",
    "行业大师",
    "底座",
    "审核平台",
    "商城业务",
    "保险",
]

OTC_HEADERS = {
    "contract_no": "合同编号",
    "contract_name": "合同名称",
    "business_unit": "业务单元",
    "client": "签约客户",
    "sales_platform": "销售平台归属",
    "project_name": "项目名称",
    "project_status": "项目状态",
    "delivery_progress": "交付进度",
    "project_manager": "项目经理",
    "payment_node": "付款节点",
    "base_payment": "基准付款金额（万元）",
    "latest_collection_due": "约定最晚回款时间",
    "paid_amount": "累计回款金额（万元）",
    "due_amount": "到期欠款（万元）",
    "due_months": "欠款时长（月）",
    "overdue_months": "逾期时长（月）",
    "normal_delivery": "正常交付款（万元）",
    "delayed_delivery": "延期交付款（万元）",
    "abnormal_delivery": "异常交付款（万元）",
    "not_due_amount": "未到期欠款（万元）",
    "securitization_ok": "是否满足资产证券化条件",
    "conversion_type": "转化类型",
    "ar_balance": "履约应收余额（万元）",
    "ar_category": "履约应收余额分类",
    "contract_status": "合同状态",
    "include_target": "是否纳入回款目标",
    "collection_status": "合同回款状态",
    "delivery_type": "履约类型",
    "delivery_manager": "交付经理",
    "department": "部门",
}

MARKETING_SKIP_GROUPS = {"合计", "历史BF", "26年前已转化", "存量项目", "增量项目"}
MARKETING_SKIP_TEAMS = {"业务部", "交付部", "总计", "全年预测", "实际达成", "待完成预测"}


@dataclass
class SheetData:
    name: str
    dimension: str
    row_count: int
    col_count: int
    rows: list[list[str]]


class WorkbookParser:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._zip = ZipFile(path)
        self._shared_strings = self._load_shared_strings()
        self._sheet_targets = self._load_sheet_targets()

    def close(self) -> None:
        self._zip.close()

    def _load_shared_strings(self) -> list[str]:
        strings: list[str] = []
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return strings
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        for si in root.findall("main:si", NS):
            strings.append("".join(text.text or "" for text in si.iterfind(".//main:t", NS)))
        return strings

    def _load_sheet_targets(self) -> dict[str, str]:
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("pkgrel:Relationship", NS)
        }
        targets: dict[str, str] = {}
        for sheet in workbook.findall("main:sheets/main:sheet", NS):
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rid]
            targets[sheet.attrib["name"]] = "xl/" + target if not target.startswith("xl/") else target
        return targets

    def _cell_value(self, cell: ET.Element) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "s":
            value = cell.find("main:v", NS)
            return self._shared_strings[int(value.text)] if value is not None and value.text else ""
        if cell_type == "inlineStr":
            inline = cell.find("main:is", NS)
            if inline is None:
                return ""
            return "".join(text.text or "" for text in inline.iterfind(".//main:t", NS))
        value = cell.find("main:v", NS)
        return value.text if value is not None and value.text is not None else ""

    def load_sheet(self, name: str) -> SheetData:
        root = ET.fromstring(self._zip.read(self._sheet_targets[name]))
        rows = root.findall("main:sheetData/main:row", NS)
        row_map: dict[int, dict[int, str]] = {}
        max_col = 0
        for row in rows:
            row_number = int(row.attrib["r"])
            cells: dict[int, str] = {}
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                col_idx = column_to_index(match.group(1))
                cells[col_idx] = self._cell_value(cell)
                max_col = max(max_col, col_idx)
            row_map[row_number] = cells

        arrays: list[list[str]] = []
        for row_number in range(1, max(row_map) + 1 if row_map else 1):
            current = [""] * (max_col + 1)
            for col_idx, value in row_map.get(row_number, {}).items():
                current[col_idx] = value
            arrays.append(current)

        dimension = ""
        dimension_node = root.find("main:dimension", NS)
        if dimension_node is not None:
            dimension = dimension_node.attrib.get("ref", "")

        return SheetData(
            name=name,
            dimension=dimension,
            row_count=len(arrays),
            col_count=max_col + 1,
            rows=arrays,
        )


def column_to_index(column: str) -> int:
    total = 0
    for char in column:
        total = total * 26 + ord(char) - 64
    return total - 1


def clean_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\u3000", " ").replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def to_float(value: object) -> float:
    text = clean_text(value)
    if text in {"", "-", "/", "#REF!", "#DIV/0!", "None"}:
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def maybe_int(value: float) -> int | float:
    return int(value) if float(value).is_integer() else round(value, 2)


def format_wan(value: float) -> str:
    if abs(value) >= 10000:
        return f"{value / 10000:.2f} 亿"
    return f"{value:,.2f} 万"


def format_pct(numerator: float, denominator: float) -> str:
    if not denominator:
        return "0.0%"
    return f"{numerator / denominator * 100:.1f}%"


def excel_serial_to_datetime(value: object) -> datetime | None:
    number = to_float(value)
    if not number or number < 10000 or number > 80000:
        return None
    return EXCEL_EPOCH + timedelta(days=number)


def year_from_value(value: object) -> int | None:
    text = clean_text(value)
    match = re.search(r"(20\d{2})年", text)
    if match:
        return int(match.group(1))
    date = excel_serial_to_datetime(text)
    if date is not None:
        return date.year
    return None


def month_label_from_value(value: object) -> str | None:
    text = clean_text(value)
    match = re.search(r"([1-9]|1[0-2])月", text)
    if match:
        return f"{int(match.group(1))}月"
    date = excel_serial_to_datetime(text)
    if date is not None:
        return f"{date.month}月"
    return None


def month_serial_label(value: object) -> str | None:
    date = excel_serial_to_datetime(value)
    if date is None:
        return None
    return f"{date.year}-{date.month:02d}"


def normalize_headers(row: list[str]) -> list[str]:
    return [clean_text(item) for item in row]


def records_from_sheet(sheet: SheetData, header_row_number: int) -> list[dict[str, str]]:
    headers = normalize_headers(sheet.rows[header_row_number - 1])
    index = {header: idx for idx, header in enumerate(headers) if header}
    records: list[dict[str, str]] = []
    for row in sheet.rows[header_row_number:]:
        if not any(clean_text(cell) for cell in row):
            continue
        record = {header: clean_text(row[idx]) for header, idx in index.items()}
        records.append(record)
    return records


def get_field(record: dict[str, str], field: str) -> str:
    return clean_text(record.get(field, ""))


def risk_rank(value: str) -> int:
    value = clean_text(value)
    return {
        "高(冲刺)": 3,
        "高": 3,
        "中": 2,
        "低": 1,
    }.get(value, 0)


def receivable_risk_rank(value: str) -> int:
    value = clean_text(value)
    return {
        "高风险": 3,
        "中风险": 2,
        "低风险": 1,
    }.get(value, 0)


def ar_bucket(label: str) -> str:
    text = clean_text(label)
    if "正常交付款" in text:
        return "正常交付款"
    if "延期交付款" in text:
        return "延期交付款"
    if "未到期" in text or "未来到期" in text:
        return "未到期"
    if "当月到期" in text:
        return "当月到期"
    if "24个月以上" in text:
        return "逾期24个月以上"
    if "18-24个月" in text:
        return "逾期18-24个月"
    if "12-18个月" in text:
        return "逾期12-18个月"
    if "6-12个月" in text:
        return "逾期6-12个月"
    if "≤6个月" in text or "<=6个月" in text:
        return "逾期6个月内"
    return "其他"


def major_client_mask(name: str) -> str:
    text = clean_text(name)
    if len(text) <= 4:
        return text
    return text[:2] + "…" + text[-2:]


def mask_reference(value: str, head: int = 4, tail: int = 4) -> str:
    text = clean_text(value)
    if text in {"", "/", "-", "无", "未填写"}:
        return "未标识"
    if len(text) <= head + tail:
        return text
    return text[:head] + "…" + text[-tail:]


def compact_project_label(project_code: str, project_name: str) -> str:
    code = clean_text(project_code)
    name = clean_text(project_name)
    if code not in {"", "/", "-", "无", "未填写"}:
        return mask_reference(code, 3, 4)
    if not name:
        return "项目未命名"
    if len(name) <= 8:
        return name[0] + "…" + name[-1] if len(name) > 2 else name
    return name[:2] + "…" + name[-2:]


def build_dashboard(source_xlsx: Path) -> dict:
    parser = WorkbookParser(source_xlsx)
    try:
        in_transit_sheet = parser.load_sheet("2.1在途交付项目清单")
        otc_sheet = parser.load_sheet("(勿删)OTC履约数据")
        marketing_sheet = parser.load_sheet("营销（勿删）")
        curve_sheet = parser.load_sheet("第一曲线")
    finally:
        parser.close()

    in_transit_records = records_from_sheet(in_transit_sheet, 3)
    otc_records = records_from_sheet(otc_sheet, 3)

    active_nodes = [
        record for record in in_transit_records if get_field(record, IN_TRANSIT_HEADERS["deleted"]) != "删除"
    ]
    valid_otc = [
        record
        for record in otc_records
        if get_field(record, OTC_HEADERS["contract_status"]) not in {"作废", "合同作废"}
    ]

    month_plan = {month: 0.0 for month in MONTHS}
    month_forecast = {month: 0.0 for month in MONTHS}
    month_actual = {month: 0.0 for month in MONTHS}
    month_collection = {month: 0.0 for month in MONTHS}

    business_units: dict[str, dict] = defaultdict(
        lambda: {
            "project_keys": set(),
            "base_payment": 0.0,
            "paid_amount": 0.0,
            "ar_balance": 0.0,
            "due_amount": 0.0,
            "pending_conversion": 0.0,
            "recognized_amount": 0.0,
        }
    )
    delivery_depts: dict[str, dict] = defaultdict(
        lambda: {
            "project_keys": set(),
            "base_payment": 0.0,
            "paid_amount": 0.0,
            "ar_balance": 0.0,
            "recognized_amount": 0.0,
        }
    )
    customer_groups: dict[str, dict] = defaultdict(
        lambda: {
            "project_keys": set(),
            "base_payment": 0.0,
            "recognized_amount": 0.0,
            "ar_balance": 0.0,
        }
    )
    projects: dict[str, dict] = {}

    for record in active_nodes:
        project_key = (
            get_field(record, IN_TRANSIT_HEADERS["project_code"])
            or get_field(record, IN_TRANSIT_HEADERS["project_name"])
            or get_field(record, IN_TRANSIT_HEADERS["payment_code"])
            or get_field(record, IN_TRANSIT_HEADERS["contract_no"])
        )
        if not project_key:
            continue

        business_unit = get_field(record, IN_TRANSIT_HEADERS["business_unit"]) or "未分类"
        delivery_dept = get_field(record, IN_TRANSIT_HEADERS["delivery_dept"]) or "未分配"
        customer_group = get_field(record, IN_TRANSIT_HEADERS["customer_group_2026"]) or "未分组"
        project_name = get_field(record, IN_TRANSIT_HEADERS["project_name"]) or project_key
        recognized_amount = to_float(get_field(record, IN_TRANSIT_HEADERS["recognized_amount"]))
        base_payment = to_float(get_field(record, IN_TRANSIT_HEADERS["base_payment"]))
        paid_amount = to_float(get_field(record, IN_TRANSIT_HEADERS["paid_amount"]))
        ar_balance = to_float(get_field(record, IN_TRANSIT_HEADERS["ar_balance"]))
        due_amount = to_float(get_field(record, IN_TRANSIT_HEADERS["due_amount"]))
        pending_conversion = to_float(get_field(record, IN_TRANSIT_HEADERS["pending_conversion"]))
        unrecognized = to_float(get_field(record, IN_TRANSIT_HEADERS["unrecognized"]))
        converted_not_collected = to_float(get_field(record, IN_TRANSIT_HEADERS["converted_not_collected"]))
        progress_value = to_float(get_field(record, IN_TRANSIT_HEADERS["delivery_progress"]))
        note = get_field(record, IN_TRANSIT_HEADERS["progress_note"])
        risk_desc = get_field(record, IN_TRANSIT_HEADERS["receivable_risk_desc"])
        pause_reason = get_field(record, IN_TRANSIT_HEADERS["pause_reason"])
        risk_degree = get_field(record, IN_TRANSIT_HEADERS["risk_degree"])
        receivable_risk = get_field(record, IN_TRANSIT_HEADERS["receivable_risk_level"])

        bucket = business_units[business_unit]
        bucket["project_keys"].add(project_key)
        bucket["base_payment"] += base_payment
        bucket["paid_amount"] += paid_amount
        bucket["ar_balance"] += ar_balance
        bucket["due_amount"] += due_amount
        bucket["pending_conversion"] += pending_conversion
        bucket["recognized_amount"] += recognized_amount

        bucket = delivery_depts[delivery_dept]
        bucket["project_keys"].add(project_key)
        bucket["base_payment"] += base_payment
        bucket["paid_amount"] += paid_amount
        bucket["ar_balance"] += ar_balance
        bucket["recognized_amount"] += recognized_amount

        bucket = customer_groups[customer_group]
        bucket["project_keys"].add(project_key)
        bucket["base_payment"] += base_payment
        bucket["recognized_amount"] += recognized_amount
        bucket["ar_balance"] += ar_balance

        project = projects.setdefault(
            project_key,
            {
                "project_key": project_key,
                "project_code": get_field(record, IN_TRANSIT_HEADERS["project_code"]),
                "project_name": project_name,
                "client": get_field(record, IN_TRANSIT_HEADERS["client"]),
                "client_masked": major_client_mask(get_field(record, IN_TRANSIT_HEADERS["client"])),
                "business_unit": business_unit,
                "delivery_dept": delivery_dept,
                "customer_group": customer_group,
                "region_2026": get_field(record, IN_TRANSIT_HEADERS["region_2026"]),
                "project_status": get_field(record, IN_TRANSIT_HEADERS["project_status"]),
                "node_status": get_field(record, IN_TRANSIT_HEADERS["node_status"]),
                "project_manager": get_field(record, IN_TRANSIT_HEADERS["project_manager"])
                or get_field(record, IN_TRANSIT_HEADERS["project_manager_formula"]),
                "delivery_group": get_field(record, IN_TRANSIT_HEADERS["delivery_group"]),
                "milestone": get_field(record, IN_TRANSIT_HEADERS["milestone"]),
                "acceptance_tag": get_field(record, IN_TRANSIT_HEADERS["acceptance_tag"]),
                "army_focus": get_field(record, IN_TRANSIT_HEADERS["army_focus"]),
                "industry": get_field(record, IN_TRANSIT_HEADERS["industry_qt"]),
                "analysis_tag": get_field(record, IN_TRANSIT_HEADERS["analysis_tag"]),
                "progress": 0.0,
                "base_payment": 0.0,
                "paid_amount": 0.0,
                "ar_balance": 0.0,
                "due_amount": 0.0,
                "pending_conversion": 0.0,
                "recognized_amount": 0.0,
                "unrecognized": 0.0,
                "converted_not_collected": 0.0,
                "risk_degree": "",
                "receivable_risk_level": "",
                "progress_note": "",
                "risk_desc": "",
                "pause_reason": "",
                "resource_need": "",
                "live_prediction_month": "",
                "actual_month": "",
                "baseline_month": "",
                "product_flags": set(),
            },
        )
        project["progress"] = max(project["progress"], progress_value)
        project["base_payment"] += base_payment
        project["paid_amount"] += paid_amount
        project["ar_balance"] += ar_balance
        project["due_amount"] += due_amount
        project["pending_conversion"] += pending_conversion
        project["recognized_amount"] += recognized_amount
        project["unrecognized"] += unrecognized
        project["converted_not_collected"] += converted_not_collected
        if risk_rank(risk_degree) > risk_rank(project["risk_degree"]):
            project["risk_degree"] = risk_degree
        if receivable_risk_rank(receivable_risk) > receivable_risk_rank(project["receivable_risk_level"]):
            project["receivable_risk_level"] = receivable_risk
        if note and len(note) > len(project["progress_note"]):
            project["progress_note"] = note
        if risk_desc and len(risk_desc) > len(project["risk_desc"]):
            project["risk_desc"] = risk_desc
        if pause_reason and not project["pause_reason"]:
            project["pause_reason"] = pause_reason
        resource_need = get_field(record, IN_TRANSIT_HEADERS["resource_need"])
        if resource_need and not project["resource_need"]:
            project["resource_need"] = resource_need

        baseline_year = year_from_value(get_field(record, IN_TRANSIT_HEADERS["baseline_year"]))
        baseline_month = month_label_from_value(get_field(record, IN_TRANSIT_HEADERS["baseline_month"]))
        live_year = year_from_value(get_field(record, IN_TRANSIT_HEADERS["live_pred_year"]))
        live_month = month_label_from_value(get_field(record, IN_TRANSIT_HEADERS["live_pred_month"]))
        actual_year = year_from_value(get_field(record, IN_TRANSIT_HEADERS["pomp_actual_year"])) or year_from_value(
            get_field(record, IN_TRANSIT_HEADERS["actual_finish_time"])
        )
        actual_month = month_label_from_value(get_field(record, IN_TRANSIT_HEADERS["pomp_actual_month"])) or month_label_from_value(
            get_field(record, IN_TRANSIT_HEADERS["actual_finish_month"])
        )
        collection_month_date = month_serial_label(get_field(record, IN_TRANSIT_HEADERS["collection_forecast_month"]))

        if baseline_year == 2026 and baseline_month in month_plan:
            month_plan[baseline_month] += recognized_amount
            project["baseline_month"] = baseline_month
        if live_year == 2026 and live_month in month_forecast:
            month_forecast[live_month] += recognized_amount
            project["live_prediction_month"] = live_month
        if actual_year == 2026 and actual_month in month_actual:
            month_actual[actual_month] += recognized_amount
            project["actual_month"] = actual_month
        if collection_month_date:
            year_text, month_text = collection_month_date.split("-")
            if year_text == "2026":
                month_label = f"{int(month_text)}月"
                month_collection[month_label] += ar_balance

        for product_header in PRODUCT_HEADERS:
            if clean_text(record.get(product_header)) not in {"", "0", "否"}:
                project["product_flags"].add(product_header)

    project_status_counts = Counter(
        project["project_status"] or "未标注" for project in projects.values()
    )
    node_status_counts = Counter(project["node_status"] or "未标注" for project in projects.values())
    risk_counts = Counter(project["risk_degree"] or "未标注" for project in projects.values())

    top_business_units = []
    for name, value in business_units.items():
        top_business_units.append(
            {
                "name": name,
                "project_count": len(value["project_keys"]),
                "base_payment": round(value["base_payment"], 2),
                "paid_amount": round(value["paid_amount"], 2),
                "ar_balance": round(value["ar_balance"], 2),
                "due_amount": round(value["due_amount"], 2),
                "pending_conversion": round(value["pending_conversion"], 2),
                "recognized_amount": round(value["recognized_amount"], 2),
                "collection_rate": round(
                    (value["paid_amount"] / value["base_payment"] * 100) if value["base_payment"] else 0, 1
                ),
            }
        )
    top_business_units.sort(key=lambda item: item["base_payment"], reverse=True)

    top_delivery_depts = []
    for name, value in delivery_depts.items():
        top_delivery_depts.append(
            {
                "name": name,
                "project_count": len(value["project_keys"]),
                "base_payment": round(value["base_payment"], 2),
                "paid_amount": round(value["paid_amount"], 2),
                "ar_balance": round(value["ar_balance"], 2),
                "recognized_amount": round(value["recognized_amount"], 2),
                "collection_rate": round(
                    (value["paid_amount"] / value["base_payment"] * 100) if value["base_payment"] else 0, 1
                ),
            }
        )
    top_delivery_depts.sort(key=lambda item: item["base_payment"], reverse=True)

    top_customer_groups = []
    for name, value in customer_groups.items():
        top_customer_groups.append(
            {
                "name": name,
                "project_count": len(value["project_keys"]),
                "base_payment": round(value["base_payment"], 2),
                "recognized_amount": round(value["recognized_amount"], 2),
                "ar_balance": round(value["ar_balance"], 2),
            }
        )
    top_customer_groups.sort(key=lambda item: item["base_payment"], reverse=True)

    product_family_summary = []
    for product in PRODUCT_HEADERS:
        matching = [project for project in projects.values() if product in project["product_flags"]]
        product_family_summary.append(
            {
                "name": product,
                "project_count": len(matching),
                "recognized_amount": round(sum(project["recognized_amount"] for project in matching), 2),
                "ar_balance": round(sum(project["ar_balance"] for project in matching), 2),
            }
        )
    product_family_summary.sort(key=lambda item: item["project_count"], reverse=True)

    focus_projects = []
    for project in projects.values():
        score = (
            risk_rank(project["risk_degree"]) * 1_000_000
            + receivable_risk_rank(project["receivable_risk_level"]) * 500_000
            + project["due_amount"] * 100
            + project["pending_conversion"] * 50
            + (200_000 if project["project_status"] == "暂停" else 0)
        )
        focus_projects.append(
            {
                "project_label": compact_project_label(project["project_code"], project["project_name"]),
                "project_ref": mask_reference(project["project_code"] or project["project_key"], 3, 4),
                "client_masked": project["client_masked"],
                "business_unit": project["business_unit"],
                "delivery_dept": project["delivery_dept"],
                "customer_group": project["customer_group"],
                "project_status": project["project_status"],
                "node_status": project["node_status"],
                "risk_degree": project["risk_degree"],
                "receivable_risk_level": project["receivable_risk_level"],
                "progress": round(project["progress"] * 100 if project["progress"] <= 1 else project["progress"], 1),
                "base_payment": round(project["base_payment"], 2),
                "paid_amount": round(project["paid_amount"], 2),
                "ar_balance": round(project["ar_balance"], 2),
                "due_amount": round(project["due_amount"], 2),
                "pending_conversion": round(project["pending_conversion"], 2),
                "recognized_amount": round(project["recognized_amount"], 2),
                "live_prediction_month": project["live_prediction_month"],
                "actual_month": project["actual_month"],
                "baseline_month": project["baseline_month"],
                "milestone": project["milestone"],
                "pause_reason": project["pause_reason"],
                "analysis_tag": project["analysis_tag"],
                "product_flags": sorted(project["product_flags"]),
                "score": round(score, 2),
            }
        )
    focus_projects.sort(key=lambda item: item["score"], reverse=True)

    otc_contracts: dict[str, dict] = {}
    aging_summary = defaultdict(float)
    collection_status_counts = Counter()
    include_target_counts = Counter()
    delivery_type_counts = Counter()

    for record in valid_otc:
        contract_key = get_field(record, OTC_HEADERS["contract_no"])
        if not contract_key:
            continue
        base_payment = to_float(get_field(record, OTC_HEADERS["base_payment"]))
        paid_amount = to_float(get_field(record, OTC_HEADERS["paid_amount"]))
        due_amount = to_float(get_field(record, OTC_HEADERS["due_amount"]))
        not_due_amount = to_float(get_field(record, OTC_HEADERS["not_due_amount"]))
        ar_balance = to_float(get_field(record, OTC_HEADERS["ar_balance"]))
        normal_delivery = to_float(get_field(record, OTC_HEADERS["normal_delivery"]))
        delayed_delivery = to_float(get_field(record, OTC_HEADERS["delayed_delivery"]))
        abnormal_delivery = to_float(get_field(record, OTC_HEADERS["abnormal_delivery"]))
        due_months = to_float(get_field(record, OTC_HEADERS["due_months"]))
        overdue_months = to_float(get_field(record, OTC_HEADERS["overdue_months"]))
        contract = otc_contracts.setdefault(
            contract_key,
            {
                "contract_no": contract_key,
                "contract_name": get_field(record, OTC_HEADERS["contract_name"]),
                "client": get_field(record, OTC_HEADERS["client"]),
                "client_masked": major_client_mask(get_field(record, OTC_HEADERS["client"])),
                "business_unit": get_field(record, OTC_HEADERS["business_unit"]),
                "project_name": get_field(record, OTC_HEADERS["project_name"]),
                "project_manager": get_field(record, OTC_HEADERS["project_manager"]),
                "delivery_manager": get_field(record, OTC_HEADERS["delivery_manager"]),
                "department": get_field(record, OTC_HEADERS["department"]),
                "collection_status": get_field(record, OTC_HEADERS["collection_status"]),
                "include_target": get_field(record, OTC_HEADERS["include_target"]),
                "delivery_type": get_field(record, OTC_HEADERS["delivery_type"]),
                "base_payment": 0.0,
                "paid_amount": 0.0,
                "due_amount": 0.0,
                "not_due_amount": 0.0,
                "ar_balance": 0.0,
                "normal_delivery": 0.0,
                "delayed_delivery": 0.0,
                "abnormal_delivery": 0.0,
                "max_due_months": 0.0,
                "max_overdue_months": 0.0,
                "ar_category": "",
            },
        )
        contract["base_payment"] += base_payment
        contract["paid_amount"] += paid_amount
        contract["due_amount"] += due_amount
        contract["not_due_amount"] += not_due_amount
        contract["ar_balance"] += ar_balance
        contract["normal_delivery"] += normal_delivery
        contract["delayed_delivery"] += delayed_delivery
        contract["abnormal_delivery"] += abnormal_delivery
        contract["max_due_months"] = max(contract["max_due_months"], due_months)
        contract["max_overdue_months"] = max(contract["max_overdue_months"], overdue_months)
        if not contract["ar_category"]:
            contract["ar_category"] = get_field(record, OTC_HEADERS["ar_category"])

        aging_summary[ar_bucket(get_field(record, OTC_HEADERS["ar_category"]))] += ar_balance
        if get_field(record, OTC_HEADERS["collection_status"]):
            collection_status_counts[get_field(record, OTC_HEADERS["collection_status"])] += 1
        if get_field(record, OTC_HEADERS["include_target"]):
            include_target_counts[get_field(record, OTC_HEADERS["include_target"])] += 1
        if get_field(record, OTC_HEADERS["delivery_type"]):
            delivery_type_counts[get_field(record, OTC_HEADERS["delivery_type"])] += 1

    top_overdue_contracts = sorted(
        (
            {
                "contract_ref": mask_reference(contract["contract_no"], 4, 4),
                "client_masked": contract["client_masked"],
                "business_unit": contract["business_unit"],
                "department": contract["department"],
                "collection_status": contract["collection_status"],
                "include_target": contract["include_target"],
                "delivery_type": contract["delivery_type"],
                "ar_category": contract["ar_category"],
                "base_payment": round(contract["base_payment"], 2),
                "paid_amount": round(contract["paid_amount"], 2),
                "due_amount": round(contract["due_amount"], 2),
                "not_due_amount": round(contract["not_due_amount"], 2),
                "ar_balance": round(contract["ar_balance"], 2),
                "normal_delivery": round(contract["normal_delivery"], 2),
                "delayed_delivery": round(contract["delayed_delivery"], 2),
                "abnormal_delivery": round(contract["abnormal_delivery"], 2),
                "max_due_months": round(contract["max_due_months"], 1),
                "max_overdue_months": round(contract["max_overdue_months"], 1),
            }
            for contract in otc_contracts.values()
        ),
        key=lambda item: (item["due_amount"], item["ar_balance"]),
        reverse=True,
    )[:16]

    marketing_rows = marketing_sheet.rows
    marketing_records = []
    current_group = ""
    for row in marketing_rows[2:]:
        values = [clean_text(value) for value in row]
        if len(values) < 34:
            continue
        if values[0]:
            current_group = values[0]
        metrics = [to_float(values[index]) for index in (2, 3, 7, 10, 13, 18, 21, 26, 29)]
        if not any(metric > 0 for metric in metrics):
            continue
        team = values[1]
        if not team or team in MARKETING_SKIP_TEAMS:
            continue
        if current_group in MARKETING_SKIP_GROUPS:
            continue
        marketing_records.append(
            {
                "group": current_group,
                "team": team,
                "overall_base": to_float(values[2]),
                "overall_done": to_float(values[3]),
                "overall_rate": to_float(values[4]) * 100,
                "overall_cash": to_float(values[5]),
                "overall_cash_rate": to_float(values[6]) * 100,
                "overall_forecast": to_float(values[7]),
                "overall_forecast_rate": to_float(values[8]) * 100,
                "bf_base": to_float(values[10]),
                "bf_forecast": to_float(values[11]),
                "bf_done": to_float(values[13]),
                "stock_base": to_float(values[18]),
                "stock_forecast": to_float(values[19]),
                "stock_done": to_float(values[21]),
                "incremental_base": to_float(values[26]),
                "incremental_forecast": to_float(values[27]),
                "incremental_done": to_float(values[29]),
            }
        )

    marketing_team_rank = sorted(marketing_records, key=lambda item: item["overall_base"], reverse=True)[:14]
    marketing_groups: dict[str, dict] = defaultdict(
        lambda: {
            "overall_base": 0.0,
            "overall_done": 0.0,
            "overall_cash": 0.0,
            "overall_forecast": 0.0,
        }
    )
    for record in marketing_records:
        bucket = marketing_groups[record["group"]]
        bucket["overall_base"] += record["overall_base"]
        bucket["overall_done"] += record["overall_done"]
        bucket["overall_cash"] += record["overall_cash"]
        bucket["overall_forecast"] += record["overall_forecast"]

    marketing_group_rank = []
    for name, value in marketing_groups.items():
        marketing_group_rank.append(
            {
                "name": name,
                "overall_base": round(value["overall_base"], 2),
                "overall_done": round(value["overall_done"], 2),
                "overall_cash": round(value["overall_cash"], 2),
                "overall_forecast": round(value["overall_forecast"], 2),
                "overall_done_rate": round(
                    (value["overall_done"] / value["overall_base"] * 100) if value["overall_base"] else 0, 1
                ),
                "overall_forecast_rate": round(
                    (value["overall_forecast"] / value["overall_base"] * 100) if value["overall_base"] else 0, 1
                ),
            }
        )
    marketing_group_rank.sort(key=lambda item: item["overall_base"], reverse=True)

    metadata_row = clean_text(otc_sheet.rows[1][0]) if otc_sheet.row_count >= 2 and otc_sheet.rows[1] else ""

    unique_project_count = len(projects)
    unique_client_count = len({project["client"] for project in projects.values() if project["client"]})
    army_focus_count = sum(1 for project in projects.values() if clean_text(project["army_focus"]) not in {"", "否"})
    paused_project_count = sum(1 for project in projects.values() if project["project_status"] == "暂停")
    medium_high_risk_count = sum(
        1 for project in projects.values() if risk_rank(project["risk_degree"]) >= 2
    )
    total_base_payment = sum(to_float(get_field(record, IN_TRANSIT_HEADERS["base_payment"])) for record in active_nodes)
    total_paid_amount = sum(to_float(get_field(record, IN_TRANSIT_HEADERS["paid_amount"])) for record in active_nodes)
    total_ar_balance = sum(to_float(get_field(record, IN_TRANSIT_HEADERS["ar_balance"])) for record in active_nodes)
    total_due_amount = sum(to_float(get_field(record, IN_TRANSIT_HEADERS["due_amount"])) for record in active_nodes)
    total_pending_conversion = sum(
        to_float(get_field(record, IN_TRANSIT_HEADERS["pending_conversion"])) for record in active_nodes
    )
    otc_total_ar_balance = sum(to_float(get_field(record, OTC_HEADERS["ar_balance"])) for record in valid_otc)
    otc_total_due_amount = sum(to_float(get_field(record, OTC_HEADERS["due_amount"])) for record in valid_otc)

    kpis = [
        {
            "label": "在途项目",
            "value": unique_project_count,
            "display": f"{unique_project_count} 个",
            "detail": f"覆盖客户 {unique_client_count} 家，付款节点 {len(active_nodes)} 条",
            "tone": "teal",
        },
        {
            "label": "军团重点 / 暂停项目",
            "value": army_focus_count,
            "display": f"{army_focus_count} / {paused_project_count}",
            "detail": f"重点项目 {army_focus_count} 个，暂停项目 {paused_project_count} 个",
            "tone": "amber",
        },
        {
            "label": "基准回款金额",
            "value": total_base_payment,
            "display": format_wan(total_base_payment),
            "detail": f"已回款 {format_wan(total_paid_amount)}，回款率 {format_pct(total_paid_amount, total_base_payment)}",
            "tone": "ink",
        },
        {
            "label": "在途应收余额",
            "value": total_ar_balance,
            "display": format_wan(total_ar_balance),
            "detail": f"到期欠款 {format_wan(total_due_amount)}，待转化交易款 {format_wan(total_pending_conversion)}",
            "tone": "rose",
        },
        {
            "label": "OTC履约应收余额",
            "value": otc_total_ar_balance,
            "display": format_wan(otc_total_ar_balance),
            "detail": f"到期欠款 {format_wan(otc_total_due_amount)}，合同数 {len(otc_contracts)} 个",
            "tone": "slate",
        },
        {
            "label": "中高风险项目",
            "value": medium_high_risk_count,
            "display": f"{medium_high_risk_count} 个",
            "detail": f"高(冲刺) {risk_counts.get('高(冲刺)', 0)} 个，中风险 {risk_counts.get('中', 0)} 个",
            "tone": "critical",
        },
    ]

    trend = [
        {
            "month": month,
            "plan": round(month_plan[month], 2),
            "forecast": round(month_forecast[month], 2),
            "actual": round(month_actual[month], 2),
            "collection": round(month_collection[month], 2),
        }
        for month in MONTHS
    ]

    source_sheets = [
        {
            "name": in_transit_sheet.name,
            "dimension": in_transit_sheet.dimension,
            "rows": in_transit_sheet.row_count,
            "columns": in_transit_sheet.col_count,
        },
        {
            "name": otc_sheet.name,
            "dimension": otc_sheet.dimension,
            "rows": otc_sheet.row_count,
            "columns": otc_sheet.col_count,
        },
        {
            "name": marketing_sheet.name,
            "dimension": marketing_sheet.dimension,
            "rows": marketing_sheet.row_count,
            "columns": marketing_sheet.col_count,
        },
        {
            "name": curve_sheet.name,
            "dimension": curve_sheet.dimension,
            "rows": curve_sheet.row_count,
            "columns": curve_sheet.col_count,
        },
    ]

    return {
        "meta": {
            "title": "星火履约经营看板",
            "source_file": source_xlsx.name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_hint": metadata_row,
            "source_sheets": source_sheets,
            "public_notice": "该页面由离线 Excel 导入生成，已按公开预览场景做脱敏和指标汇总。",
        },
        "kpis": kpis,
        "trend": trend,
        "status_breakdown": {
            "project_status": [{"name": key, "value": value} for key, value in project_status_counts.most_common()],
            "node_status": [{"name": key, "value": value} for key, value in node_status_counts.most_common()],
            "risk_degree": [{"name": key, "value": value} for key, value in risk_counts.most_common()],
        },
        "business_unit_rank": top_business_units[:10],
        "delivery_dept_rank": top_delivery_depts[:10],
        "customer_group_rank": top_customer_groups[:10],
        "product_family_rank": product_family_summary,
        "aging_summary": [
            {"name": name, "value": round(value, 2)}
            for name, value in sorted(aging_summary.items(), key=lambda item: item[1], reverse=True)
        ],
        "collection_status_counts": [
            {"name": key, "value": value} for key, value in collection_status_counts.most_common()
        ],
        "include_target_counts": [
            {"name": key, "value": value} for key, value in include_target_counts.most_common()
        ],
        "delivery_type_counts": [
            {"name": key, "value": value} for key, value in delivery_type_counts.most_common()
        ],
        "marketing_team_rank": marketing_team_rank,
        "marketing_group_rank": marketing_group_rank[:8],
        "focus_projects": focus_projects[:16],
        "top_overdue_contracts": top_overdue_contracts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a public dashboard dataset from the Spark fulfillment workbook.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_XLSX, help="Path to the source XLSX workbook.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON, help="Path to the output JSON file.")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source workbook not found: {args.source}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    dashboard = build_dashboard(args.source)
    args.output.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
