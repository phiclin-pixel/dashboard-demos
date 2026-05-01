const DATA_URL = "./data/dashboard-data.json";

const toneClass = {
  teal: "tone-teal",
  amber: "tone-amber",
  ink: "tone-ink",
  rose: "tone-rose",
  slate: "tone-slate",
  critical: "tone-critical",
};

const numberFormat = new Intl.NumberFormat("zh-CN");

function formatWan(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (Math.abs(value) >= 10000) {
    return `${(value / 10000).toFixed(2)} 亿`;
  }
  return `${value.toFixed(2)} 万`;
}

function formatPct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "0.0%";
  return `${value.toFixed(1)}%`;
}

function safeText(value, fallback = "-") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function mountHtml(id, html) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = html;
}

function sumBy(items, key) {
  return items.reduce((sum, item) => sum + (Number(item[key]) || 0), 0);
}

function renderHero(data) {
  document.getElementById("page-title").textContent = data.meta.title;
  const sheetText = data.meta.source_sheets
    .map((sheet) => `${sheet.name} ${numberFormat.format(sheet.rows)} 行`)
    .join(" · ");
  mountHtml(
    "hero-meta",
    [
      `来源文件：<strong>${safeText(data.meta.source_file)}</strong>`,
      `台账口径：<strong>${safeText(data.meta.as_of_hint)}</strong>`,
      `生成时间：<strong>${safeText(data.meta.generated_at.replace("T", " "))}</strong>`,
      `数据表：${sheetText}`,
    ].join("<br>")
  );

  const trend = data.trend || [];
  const plan = sumBy(trend, "plan");
  const forecast = sumBy(trend, "forecast");
  const actual = sumBy(trend, "actual");
  const collection = sumBy(trend, "collection");
  const forecastRate = plan ? (forecast / plan) * 100 : 0;
  const actualRate = plan ? (actual / plan) * 100 : 0;

  mountHtml(
    "hero-metrics",
    [
      {
        label: "全年确收计划",
        value: formatWan(plan),
        detail: "来自在途项目基线月份分布",
      },
      {
        label: "最新预测覆盖率",
        value: formatPct(forecastRate),
        detail: `最新预测 ${formatWan(forecast)}`,
      },
      {
        label: "实际达成率",
        value: formatPct(actualRate),
        detail: `已实际达成 ${formatWan(actual)}`,
      },
      {
        label: "回款压力池",
        value: formatWan(collection),
        detail: "按 2026 回款预测月份聚合",
      },
    ]
      .map(
        (item) => `
          <div class="hero-metric">
            <span class="label">${item.label}</span>
            <span class="value">${item.value}</span>
            <p class="detail">${item.detail}</p>
          </div>
        `
      )
      .join("")
  );
}

function renderKpis(kpis) {
  mountHtml(
    "kpi-grid",
    kpis
      .map(
        (item) => `
          <article class="kpi-card ${toneClass[item.tone] || ""}">
            <p class="label">${safeText(item.label)}</p>
            <strong class="value">${safeText(item.display)}</strong>
            <p class="detail">${safeText(item.detail)}</p>
          </article>
        `
      )
      .join("")
  );
}

function renderTrendSummary(trend) {
  const plan = sumBy(trend, "plan");
  const forecast = sumBy(trend, "forecast");
  const actual = sumBy(trend, "actual");
  const collection = sumBy(trend, "collection");
  const gap = forecast - actual;
  const maxMonth = [...trend].sort((a, b) => b.forecast - a.forecast)[0];
  const minMonth = [...trend].sort((a, b) => b.actual - a.actual)[0];

  mountHtml(
    "trend-summary",
    [
      {
        label: "计划总量",
        value: formatWan(plan),
        detail: "全年基线确收",
      },
      {
        label: "预测总量",
        value: formatWan(forecast),
        detail: `覆盖率 ${formatPct(plan ? (forecast / plan) * 100 : 0)}`,
      },
      {
        label: "实际总量",
        value: formatWan(actual),
        detail: `达成率 ${formatPct(plan ? (actual / plan) * 100 : 0)}`,
      },
      {
        label: "预测-实际缺口",
        value: formatWan(gap),
        detail: safeText(maxMonth ? `预测峰值 ${maxMonth.month}` : "-"),
      },
      {
        label: "回款预测池",
        value: formatWan(collection),
        detail: safeText(minMonth ? `已达成高点 ${minMonth.month}` : "-"),
      },
    ]
      .map(
        (item) => `
          <div class="mini-stat">
            <span class="label">${item.label}</span>
            <span class="value">${item.value}</span>
            <p class="detail">${item.detail}</p>
          </div>
        `
      )
      .join("")
  );
}

function renderTrendChart(trend) {
  const width = 980;
  const height = 360;
  const padding = { top: 24, right: 28, bottom: 40, left: 56 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const keys = [
    { key: "plan", label: "计划", color: "#0f766e" },
    { key: "forecast", label: "预测", color: "#1d4ed8" },
    { key: "actual", label: "实际", color: "#d97706" },
    { key: "collection", label: "回款压力", color: "#be123c" },
  ];
  const maxValue = Math.max(
    ...trend.flatMap((item) => keys.map((series) => Number(item[series.key]) || 0)),
    1
  );
  const ticks = 5;
  const xStep = trend.length > 1 ? plotWidth / (trend.length - 1) : plotWidth;
  const y = (value) => padding.top + plotHeight - (value / maxValue) * plotHeight;
  const x = (index) => padding.left + index * xStep;

  const grid = Array.from({ length: ticks }, (_, index) => {
    const value = (maxValue / (ticks - 1)) * index;
    const yPos = y(value);
    return `
      <line x1="${padding.left}" y1="${yPos}" x2="${width - padding.right}" y2="${yPos}" stroke="rgba(22,36,43,0.08)" />
      <text x="${padding.left - 12}" y="${yPos + 4}" text-anchor="end" font-size="11" fill="#66737c">${formatWan(
        value
      )}</text>
    `;
  }).join("");

  const labels = trend
    .map(
      (item, index) => `
        <text x="${x(index)}" y="${height - 14}" text-anchor="middle" font-size="11" fill="#66737c">${item.month}</text>
      `
    )
    .join("");

  const seriesMarkup = keys
    .map((series) => {
      const points = trend
        .map((item, index) => `${x(index)},${y(Number(item[series.key]) || 0)}`)
        .join(" ");
      const dots = trend
        .map(
          (item, index) => `
            <circle cx="${x(index)}" cy="${y(Number(item[series.key]) || 0)}" r="3.5" fill="${series.color}">
              <title>${item.month} · ${series.label} · ${formatWan(Number(item[series.key]) || 0)}</title>
            </circle>
          `
        )
        .join("");
      return `
        <polyline
          fill="none"
          stroke="${series.color}"
          stroke-width="3"
          stroke-linejoin="round"
          stroke-linecap="round"
          points="${points}"
        />
        ${dots}
      `;
    })
    .join("");

  const legend = `
    <div class="legend">
      ${keys
        .map(
          (item) => `
            <div class="legend-item">
              <span class="legend-swatch" style="background:${item.color}"></span>
              <span>${item.label}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;

  mountHtml(
    "trend-chart",
    `
      ${legend}
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="月度确收与回款节奏">
        ${grid}
        ${labels}
        ${seriesMarkup}
      </svg>
    `
  );
}

function renderMetricRows(items, options = {}) {
  const valueKey = options.valueKey || "value";
  const maxValue = Math.max(...items.map((item) => Number(item[valueKey]) || 0), 1);
  return `
    <div class="metric-list">
      ${items
        .map((item) => {
          const value = Number(item[valueKey]) || 0;
          const width = `${(value / maxValue) * 100}%`;
          const detail = options.detail ? options.detail(item) : "";
          const displayValue = options.display ? options.display(item) : formatWan(value);
          return `
            <div class="metric-row">
              <div class="topline">
                <strong>${safeText(item.name)}</strong>
                <span>${displayValue}</span>
              </div>
              <div class="bar"><div class="fill" style="width:${width}"></div></div>
              ${detail ? `<div class="detail">${detail}</div>` : ""}
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderStatusBreakdown(status) {
  const groups = [
    { title: "项目状态", items: status.project_status, display: (item) => `${numberFormat.format(item.value)} 个` },
    { title: "节点状态", items: status.node_status, display: (item) => `${numberFormat.format(item.value)} 个` },
    { title: "风险等级", items: status.risk_degree, display: (item) => `${numberFormat.format(item.value)} 个` },
  ];
  mountHtml(
    "status-breakdown",
    groups
      .map(
        (group) => `
          <section class="status-group">
            <h3>${group.title}</h3>
            ${renderMetricRows(group.items, { valueKey: "value", display: group.display })}
          </section>
        `
      )
      .join("")
  );
}

function renderBusinessCharts(data) {
  mountHtml(
    "business-unit-chart",
    renderMetricRows(data.business_unit_rank, {
      valueKey: "base_payment",
      detail: (item) =>
        `${numberFormat.format(item.project_count)} 个项目 · 回款率 ${formatPct(item.collection_rate)} · 应收 ${formatWan(item.ar_balance)}`,
    })
  );

  mountHtml(
    "delivery-dept-chart",
    renderMetricRows(data.delivery_dept_rank, {
      valueKey: "base_payment",
      detail: (item) =>
        `${numberFormat.format(item.project_count)} 个项目 · 回款率 ${formatPct(item.collection_rate)} · 确收 ${formatWan(item.recognized_amount)}`,
    })
  );

  mountHtml(
    "product-family-chart",
    renderMetricRows(data.product_family_rank, {
      valueKey: "project_count",
      display: (item) => `${numberFormat.format(item.project_count)} 个`,
      detail: (item) => `确收 ${formatWan(item.recognized_amount)} · 应收 ${formatWan(item.ar_balance)}`,
    })
  );

  mountHtml(
    "customer-group-chart",
    renderMetricRows(data.customer_group_rank, {
      valueKey: "base_payment",
      detail: (item) =>
        `${numberFormat.format(item.project_count)} 个项目 · 确收 ${formatWan(item.recognized_amount)} · 应收 ${formatWan(item.ar_balance)}`,
    })
  );
}

function renderReceivablePanels(data) {
  mountHtml(
    "aging-chart",
    renderMetricRows(data.aging_summary, {
      valueKey: "value",
      detail: (item) => `履约应收 ${formatWan(item.value)}`,
    })
  );

  mountHtml(
    "collection-matrix",
    `
      <div class="matrix-list">
        <div>
          <p class="panel-kicker">Collection Status</p>
          ${renderMetricRows(data.collection_status_counts, {
            valueKey: "value",
            display: (item) => `${numberFormat.format(item.value)} 条`,
          })}
        </div>
        <div>
          <p class="panel-kicker">Include Target</p>
          ${renderMetricRows(data.include_target_counts, {
            valueKey: "value",
            display: (item) => `${numberFormat.format(item.value)} 条`,
          })}
        </div>
        <div>
          <p class="panel-kicker">Delivery Type</p>
          ${renderMetricRows(data.delivery_type_counts, {
            valueKey: "value",
            display: (item) => `${numberFormat.format(item.value)} 条`,
          })}
        </div>
      </div>
    `
  );
}

function renderMarketing(data) {
  mountHtml(
    "marketing-summary",
    data.marketing_group_rank
      .map(
        (item) => `
          <article class="marketing-card">
            <h3>${safeText(item.name)}</h3>
            <div class="stats">
              <span>全年基线 ${formatWan(item.overall_base)}</span>
              <span>实际达成率 ${formatPct(item.overall_done_rate)}</span>
              <span>预测覆盖率 ${formatPct(item.overall_forecast_rate)}</span>
              <span>回款 ${formatWan(item.overall_cash)}</span>
            </div>
          </article>
        `
      )
      .join("")
  );

  mountHtml(
    "marketing-team-table",
    `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>板块</th>
              <th>团队</th>
              <th>全年基线</th>
              <th>实际达成</th>
              <th>预测</th>
              <th>回款</th>
            </tr>
          </thead>
          <tbody>
            ${data.marketing_team_rank
              .map(
                (item) => `
                  <tr>
                    <td>${safeText(item.group)}</td>
                    <td>${safeText(item.team)}</td>
                    <td>${formatWan(item.overall_base)}</td>
                    <td>${formatWan(item.overall_done)}<br><span class="muted">${formatPct(item.overall_rate)}</span></td>
                    <td>${formatWan(item.overall_forecast)}<br><span class="muted">${formatPct(item.overall_forecast_rate)}</span></td>
                    <td>${formatWan(item.overall_cash)}<br><span class="muted">${formatPct(item.overall_cash_rate)}</span></td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `
  );
}

function renderFocusProjects(items) {
  mountHtml(
    "focus-table",
    `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>项目标识</th>
              <th>客户</th>
              <th>业务单元</th>
              <th>状态</th>
              <th>风险</th>
              <th>进度</th>
              <th>应收</th>
              <th>到期欠款</th>
              <th>待转化</th>
              <th>节奏</th>
            </tr>
          </thead>
          <tbody>
            ${items
              .map(
                (item) => `
                  <tr>
                    <td>
                      <strong>${safeText(item.project_label)}</strong><br>
                      <span class="muted">${safeText(item.project_ref)}</span>
                    </td>
                    <td>${safeText(item.client_masked)}</td>
                    <td>${safeText(item.business_unit)}<br><span class="muted">${safeText(item.delivery_dept)}</span></td>
                    <td>${safeText(item.project_status, "未标注")}<br><span class="muted">${safeText(item.node_status)}</span></td>
                    <td>
                      <span class="score-pill">${safeText(item.risk_degree, "未标注")}</span><br>
                      <span class="muted">${safeText(item.receivable_risk_level, "无应收风险标注")}</span>
                    </td>
                    <td>${formatPct(Number(item.progress) || 0)}</td>
                    <td>${formatWan(item.ar_balance)}</td>
                    <td>${formatWan(item.due_amount)}</td>
                    <td>${formatWan(item.pending_conversion)}</td>
                    <td>
                      基线 ${safeText(item.baseline_month)} / 预测 ${safeText(item.live_prediction_month)} / 实际 ${safeText(item.actual_month)}<br>
                      <span class="muted">${safeText(item.pause_reason, safeText(item.analysis_tag, "无附加标签"))}</span>
                    </td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `
  );
}

function renderOverdueContracts(items) {
  mountHtml(
    "overdue-table",
    `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>合同标识</th>
              <th>客户</th>
              <th>业务单元</th>
              <th>应收</th>
              <th>到期欠款</th>
              <th>逾期月数</th>
              <th>分类</th>
            </tr>
          </thead>
          <tbody>
            ${items
              .map(
                (item) => `
                  <tr>
                    <td><strong>${safeText(item.contract_ref)}</strong><br><span class="muted">${safeText(item.department, "未标注部门")}</span></td>
                    <td>${safeText(item.client_masked)}</td>
                    <td>${safeText(item.business_unit)}</td>
                    <td>${formatWan(item.ar_balance)}</td>
                    <td>${formatWan(item.due_amount)}</td>
                    <td>${Number(item.max_overdue_months || 0).toFixed(1)} 月</td>
                    <td>
                      ${safeText(item.ar_category)}<br>
                      <span class="muted">${safeText(item.collection_status)} / 目标${safeText(item.include_target)}</span>
                    </td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `
  );
}

function renderSourceAudit(data) {
  const sheetCards = data.meta.source_sheets
    .map(
      (sheet) => `
        <div class="metric-row">
          <div class="topline">
            <strong>${safeText(sheet.name)}</strong>
            <span>${numberFormat.format(sheet.rows)} 行</span>
          </div>
          <div class="detail">维度 ${safeText(sheet.dimension)} · ${numberFormat.format(sheet.columns)} 列</div>
        </div>
      `
    )
    .join("");

  mountHtml(
    "source-audit",
    `
      <div class="audit-list">
        <div class="metric-row">
          <div class="topline">
            <strong>发布说明</strong>
            <span>公开预览版</span>
          </div>
          <div class="detail">${safeText(data.meta.public_notice)}</div>
        </div>
        ${sheetCards}
      </div>
    `
  );
  document.getElementById("footer-note").textContent = data.meta.public_notice;
}

function renderDashboard(data) {
  renderHero(data);
  renderKpis(data.kpis || []);
  renderTrendSummary(data.trend || []);
  renderTrendChart(data.trend || []);
  renderStatusBreakdown(data.status_breakdown || {});
  renderBusinessCharts(data);
  renderReceivablePanels(data);
  renderMarketing(data);
  renderFocusProjects(data.focus_projects || []);
  renderOverdueContracts(data.top_overdue_contracts || []);
  renderSourceAudit(data);
}

async function init() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderDashboard(data);
  } catch (error) {
    const message = `<div class="error-state">数据载入失败：${safeText(error.message)}</div>`;
    [
      "kpi-grid",
      "trend-chart",
      "status-breakdown",
      "business-unit-chart",
      "delivery-dept-chart",
      "product-family-chart",
      "aging-chart",
      "collection-matrix",
      "marketing-summary",
      "focus-table",
      "overdue-table",
      "customer-group-chart",
      "marketing-team-table",
      "source-audit",
    ].forEach((id) => mountHtml(id, message));
    document.getElementById("hero-meta").textContent = "数据载入失败，请检查 dashboard-data.json。";
  }
}

init();
