const state = {
  snapshot: null,
  eventSource: null,
  isStaticPreview: window.location.hostname.endsWith("github.io"),
};

const elements = {
  architectureStrip: document.getElementById("architectureStrip"),
  kpiGrid: document.getElementById("kpiGrid"),
  trendChart: document.getElementById("trendChart"),
  trendMeta: document.getElementById("trendMeta"),
  healthDonut: document.getElementById("healthDonut"),
  sourceSummary: document.getElementById("sourceSummary"),
  linePerformance: document.getElementById("linePerformance"),
  projectList: document.getElementById("projectList"),
  deliveryTable: document.getElementById("deliveryTable"),
  alertsList: document.getElementById("alertsList"),
  actionBoard: document.getElementById("actionBoard"),
  activityFeed: document.getElementById("activityFeed"),
  sourceTables: document.getElementById("sourceTables"),
  simulateBtn: document.getElementById("simulateBtn"),
  streamDot: document.getElementById("streamDot"),
  streamStatus: document.getElementById("streamStatus"),
  lastUpdated: document.getElementById("lastUpdated"),
  sourceMode: document.getElementById("sourceMode"),
  sourceShape: document.getElementById("sourceShape"),
  footerVersion: document.getElementById("footerVersion"),
  tablesLink: document.getElementById("tablesLink"),
};

document.addEventListener("DOMContentLoaded", () => {
  bootstrap();
});

async function bootstrap() {
  bindActions();
  configureMode();
  if (state.isStaticPreview) {
    await fetchStaticSnapshot();
    setConnectionState("preview", "静态预览");
    return;
  }

  await fetchSnapshot();
  connectEvents();
}

function bindActions() {
  elements.simulateBtn.addEventListener("click", async () => {
    if (state.isStaticPreview) {
      return;
    }
    elements.simulateBtn.disabled = true;
    elements.simulateBtn.textContent = "正在模拟变更...";
    try {
      const response = await fetch("/api/mutate", {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      setConnectionState("offline", "模拟失败");
    } finally {
      window.setTimeout(() => {
        elements.simulateBtn.disabled = false;
        elements.simulateBtn.textContent = "模拟一次表格变更";
      }, 300);
    }
  });
}

function configureMode() {
  elements.tablesLink.href = state.isStaticPreview ? "../data/mock_feishu_tables.json" : "/api/tables";
  if (state.isStaticPreview) {
    elements.simulateBtn.disabled = true;
    elements.simulateBtn.textContent = "GitHub Pages 不支持实时推送";
    elements.sourceMode.textContent = "Mock 飞书静态预览";
    elements.sourceShape.textContent = "由静态快照驱动，未连接服务端";
  }
}

async function fetchSnapshot() {
  const response = await fetch("/api/dashboard", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  applySnapshot(payload);
}

async function fetchStaticSnapshot() {
  const response = await fetch("./mock-dashboard.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  payload.source_summary.mode = "Mock 飞书静态预览";
  applySnapshot(payload);
}

function connectEvents() {
  const source = new EventSource("/events");
  state.eventSource = source;

  source.addEventListener("open", () => {
    setConnectionState("live", "实时推送中");
  });

  source.addEventListener("dashboard", (event) => {
    const payload = JSON.parse(event.data);
    applySnapshot(payload);
    setConnectionState("live", "实时推送中");
  });

  source.addEventListener("heartbeat", () => {
    setConnectionState("live", "实时推送中");
  });

  source.onerror = () => {
    setConnectionState("offline", "连接重试中");
  };
}

function applySnapshot(snapshot) {
  state.snapshot = snapshot;
  document.title = `${snapshot.workspace_name} | 经营看板实时原型`;
  elements.footerVersion.textContent = `版本 ${snapshot.version}`;
  elements.lastUpdated.textContent = `最近刷新 ${formatDateTime(snapshot.generated_at)}`;
  elements.sourceMode.textContent = snapshot.source_summary.mode;
  elements.sourceShape.textContent = `${snapshot.source_summary.ordinary_tables} 张普通表格 + ${snapshot.source_summary.multidimensional_tables} 张多维表格`;

  renderArchitecture(snapshot.architecture);
  renderKpis(snapshot.kpis);
  renderTrend(snapshot.trend);
  renderHealth(snapshot.health, snapshot.source_summary, snapshot.trend);
  renderLinePerformance(snapshot.line_performance);
  renderProjects(snapshot.focus_projects);
  renderDeliveries(snapshot.delivery_focus);
  renderAlerts(snapshot.alerts);
  renderActions(snapshot.action_board);
  renderActivity(snapshot.activity);
  renderSourceTables(snapshot.source_tables);
}

function renderArchitecture(steps) {
  elements.architectureStrip.innerHTML = steps
    .map(
      (step, index) => `
        <div class="arch-pill">
          <span class="arch-index">${index + 1}</span>
          <span>${escapeHtml(step)}</span>
        </div>
      `,
    )
    .join("");
}

function renderKpis(kpis) {
  elements.kpiGrid.innerHTML = kpis
    .map(
      (item) => `
        <article class="kpi-card tone-${escapeHtml(item.tone)}">
          <div class="kpi-label">${escapeHtml(item.label)}</div>
          <div class="kpi-value">${escapeHtml(item.display)}</div>
          <div class="kpi-detail">${escapeHtml(item.detail)}</div>
          <div class="kpi-signal">${escapeHtml(item.signal)}</div>
        </article>
      `,
    )
    .join("");
}

function renderTrend(months) {
  const width = 760;
  const height = 290;
  const pad = { top: 18, right: 20, bottom: 44, left: 44 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(...months.flatMap((item) => [item.plan, item.actual, item.cash_in])) * 1.18;
  const step = months.length > 1 ? plotWidth / (months.length - 1) : plotWidth;
  const toX = (index) => pad.left + step * index;
  const toY = (value) => pad.top + ((maxValue - value) / maxValue) * plotHeight;
  const planPoints = months.map((item, index) => [toX(index), toY(item.plan)]);
  const actualPoints = months.map((item, index) => [toX(index), toY(item.actual)]);
  const areaPath =
    `M ${pad.left} ${pad.top + plotHeight} ` +
    actualPoints.map(([x, y]) => `L ${x} ${y}`).join(" ") +
    ` L ${pad.left + plotWidth} ${pad.top + plotHeight} Z`;
  const axisTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = maxValue * ratio;
    return { y: toY(value), label: `${Math.round(value)}万` };
  });
  const barWidth = Math.max(18, Math.min(34, plotWidth / months.length / 2));

  const svg = `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="营收计划实际与回款趋势">
      ${axisTicks
        .map(
          (tick) => `
            <line x1="${pad.left}" y1="${tick.y}" x2="${pad.left + plotWidth}" y2="${tick.y}" stroke="rgba(23,33,38,0.08)" stroke-dasharray="4 8" />
            <text x="${pad.left - 10}" y="${tick.y + 4}" text-anchor="end" fill="#5d6d70" font-size="11">${tick.label}</text>
          `,
        )
        .join("")}
      ${months
        .map((item, index) => {
          const x = toX(index);
          const cashY = toY(item.cash_in);
          const barHeight = pad.top + plotHeight - cashY;
          return `
            <rect x="${x - barWidth / 2}" y="${cashY}" width="${barWidth}" height="${barHeight}" rx="10" fill="rgba(193,122,10,0.18)" />
            <text x="${x}" y="${pad.top + plotHeight + 22}" text-anchor="middle" fill="#5d6d70" font-size="12">${item.label}</text>
          `;
        })
        .join("")}
      <path d="${areaPath}" fill="rgba(15,118,110,0.12)" />
      <polyline
        points="${planPoints.map(([x, y]) => `${x},${y}`).join(" ")}"
        fill="none"
        stroke="#c17a0a"
        stroke-width="3"
        stroke-dasharray="8 8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <polyline
        points="${actualPoints.map(([x, y]) => `${x},${y}`).join(" ")}"
        fill="none"
        stroke="#0f766e"
        stroke-width="4"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      ${actualPoints
        .map(
          ([x, y], index) => `
            <circle cx="${x}" cy="${y}" r="5.5" fill="#0f766e" />
            <text x="${x}" y="${y - 12}" text-anchor="middle" fill="#172126" font-size="11">${Math.round(months[index].actual)}</text>
          `,
        )
        .join("")}
    </svg>
    <div class="trend-legend">
      <span><span class="legend-swatch" style="background:#0f766e"></span>实际营收</span>
      <span><span class="legend-swatch" style="background:#c17a0a"></span>计划营收</span>
      <span><span class="legend-swatch" style="background:rgba(193,122,10,0.35)"></span>回款柱</span>
    </div>
  `;

  const latest = months[months.length - 1];
  elements.trendMeta.textContent = `最新月份 ${latest.label}，营收 ${Math.round(latest.actual)} 万，毛利率 ${latest.margin.toFixed(1)}%`;
  elements.trendChart.innerHTML = svg;
}

function renderHealth(health, summary, months) {
  const total = health.total_projects || 1;
  const red = health.health_counts.red || 0;
  const amber = health.health_counts.amber || 0;
  const green = health.health_counts.green || 0;
  const redPct = (red / total) * 100;
  const amberPct = (amber / total) * 100;
  const gradient = `conic-gradient(
    #b85c38 0 ${redPct}%,
    #c17a0a ${redPct}% ${redPct + amberPct}%,
    #177245 ${redPct + amberPct}% 100%
  )`;

  elements.healthDonut.innerHTML = `
    <div class="ring" style="background:${gradient}">
      <div class="ring-hole">
        <div class="ring-number">${health.total_projects}</div>
        <div class="ring-label">项目总数</div>
      </div>
    </div>
    <div class="health-legend">
      ${legendItem("#b85c38", "红色预警", `${red} 个`)}
      ${legendItem("#c17a0a", "黄色关注", `${amber} 个`)}
      ${legendItem("#177245", "绿色在轨", `${green} 个`)}
    </div>
  `;

  const quarterRevenue = months.slice(-3).reduce((sum, item) => sum + item.actual, 0);
  const stages = Object.entries(health.stage_counts)
    .sort((left, right) => right[1] - left[1])
    .map(([stage, count]) => summaryRow(stage, `${count} 个`))
    .join("");

  elements.sourceSummary.innerHTML = `
    ${summaryRow("最近同步", formatDateTime(summary.last_sync))}
    ${summaryRow("最近季度营收", `${Math.round(quarterRevenue)} 万`)}
    ${summaryRow("普通 / 多维", `${summary.ordinary_tables} / ${summary.multidimensional_tables}`)}
    ${stages}
  `;
}

function renderLinePerformance(lines) {
  elements.linePerformance.innerHTML = lines
    .map((item) => {
      const width = Math.min(item.attainment, 132);
      return `
        <div class="line-row">
          <div class="line-head">
            <div class="line-name">${escapeHtml(item.business_line)}</div>
            <div>${escapeHtml(formatMoney(item.actual))}</div>
          </div>
          <div class="line-metrics">
            达成 ${item.attainment.toFixed(1)}% · 毛利率 ${item.margin.toFixed(1)}% · 回款 ${formatMoney(item.cash)}
          </div>
          <div class="line-bar-track">
            <div class="line-bar-fill" style="width:${width}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderProjects(projects) {
  elements.projectList.innerHTML = projects
    .map(
      (item) => `
        <article class="project-card">
          <div class="project-head">
            <div>
              <div class="project-name">${escapeHtml(item.project_name)}</div>
              <div class="project-meta">${escapeHtml(item.project_code)} · ${escapeHtml(item.owner)} · ${escapeHtml(item.business_line)}</div>
            </div>
            <div>${escapeHtml(formatMoney(item.revenue_recognized))}</div>
          </div>
          <div class="badge-row">
            <span class="badge health-${healthClass(item.health)}">${escapeHtml(item.health)}色</span>
            <span class="badge priority-${priorityClass(item.priority)}">${escapeHtml(item.priority)}</span>
            <span class="badge">${escapeHtml(item.stage)}</span>
            <span class="badge">${escapeHtml(item.milestone)}</span>
          </div>
          <div class="project-meta">里程碑 ${escapeHtml(item.milestone_due)} · ${escapeHtml(daysLabel(item.days_to_due))}</div>
          <div class="progress-track">
            <div class="progress-fill" style="width:${item.progress}%"></div>
          </div>
          <div class="project-meta">进度 ${item.progress}% · 阻塞：${escapeHtml(item.blocker)}</div>
        </article>
      `,
    )
    .join("");
}

function renderDeliveries(deliveries) {
  elements.deliveryTable.innerHTML = `
    <table class="delivery-table">
      <thead>
        <tr>
          <th>里程碑</th>
          <th>项目</th>
          <th>Owner</th>
          <th>优先级</th>
          <th>完成度</th>
          <th>状态</th>
          <th>到期</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        ${deliveries
          .map(
            (item) => `
              <tr>
                <td>
                  <strong>${escapeHtml(item.milestone)}</strong><br>
                  <span class="muted">${escapeHtml(item.delivery_id)}</span>
                </td>
                <td>${escapeHtml(item.project_code)}</td>
                <td>${escapeHtml(item.owner)}</td>
                <td><span class="badge priority-${priorityClass(item.priority)}">${escapeHtml(item.priority)}</span></td>
                <td>${item.completion}%</td>
                <td><span class="badge health-${healthClass(item.health)}">${escapeHtml(item.acceptance_status)}</span></td>
                <td>${escapeHtml(item.due_date)}<br><span class="muted">${escapeHtml(daysLabel(item.days_to_due))}</span></td>
                <td>${escapeHtml(item.note)}</td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderAlerts(alerts) {
  elements.alertsList.innerHTML = alerts
    .map(
      (item) => `
        <div class="alert-card alert-${escapeHtml(item.level)}">
          <div class="alert-head">
            <span>${escapeHtml(item.title)}</span>
            <span>${escapeHtml(item.owner)}</span>
          </div>
          <div class="alert-detail">${escapeHtml(item.detail)}</div>
          <div class="alert-foot">节点 ${escapeHtml(item.due_date)} · ${escapeHtml(daysLabel(daysDiff(item.due_date)))}</div>
        </div>
      `,
    )
    .join("");
}

function renderActions(actions) {
  elements.actionBoard.innerHTML = actions
    .map(
      (item) => `
        <div class="action-card">
          <div class="action-head">
            <div class="action-title">${escapeHtml(item.topic)}</div>
            <div>${item.progress}%</div>
          </div>
          <div class="action-meta">${escapeHtml(item.owner)} · ${escapeHtml(item.impact_area)} · ${escapeHtml(item.status)}</div>
          <div class="progress-track action-progress">
            <div class="progress-fill" style="width:${item.progress}%"></div>
          </div>
          <div class="action-meta">截止 ${escapeHtml(item.due_date)} · ${escapeHtml(daysLabel(item.days_to_due))} · 预期收益 ${escapeHtml(item.expected_gain)}</div>
        </div>
      `,
    )
    .join("");
}

function renderActivity(activity) {
  elements.activityFeed.innerHTML = activity
    .map(
      (item) => `
        <div class="activity-item activity-tone ${escapeHtml(item.tone)}">
          <div class="activity-time">${escapeHtml(item.time)}</div>
          <div>
            <div class="activity-head">
              <span class="activity-source">${escapeHtml(item.source)}</span>
            </div>
            <div class="project-name">${escapeHtml(item.title)}</div>
            <div class="activity-detail">${escapeHtml(item.detail)}</div>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderSourceTables(tables) {
  elements.sourceTables.innerHTML = tables
    .map(
      (item) => `
        <div class="source-table-card">
          <div class="source-head">
            <div class="source-name">${escapeHtml(item.name)}</div>
            <span class="badge">${escapeHtml(item.shape)}</span>
          </div>
          <div class="source-meta">
            ${escapeHtml(item.table_id)}<br>
            ${item.row_count} 行 · ${item.field_count} 列/指标 · 最近 ${escapeHtml(formatDateTime(item.updated_at))}
          </div>
          <div class="source-meta">${escapeHtml(item.sync_mode)}</div>
        </div>
      `,
    )
    .join("");
}

function summaryRow(label, value) {
  return `
    <div class="summary-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function legendItem(color, label, value) {
  return `
    <div class="legend-row">
      <div class="legend-left">
        <span class="legend-chip" style="background:${color}"></span>
        <span>${escapeHtml(label)}</span>
      </div>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function setConnectionState(mode, label) {
  elements.streamStatus.textContent = label;
  elements.streamDot.classList.remove("live", "offline");
  if (mode === "live") {
    elements.streamDot.classList.add("live");
  } else if (mode === "offline") {
    elements.streamDot.classList.add("offline");
  } else if (mode === "preview") {
    elements.streamDot.classList.add("offline");
  }
}

function formatMoney(value) {
  return `¥ ${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}万`;
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function healthClass(value) {
  return { 红: "red", 黄: "amber", 绿: "green" }[value] || "green";
}

function priorityClass(value) {
  return String(value).toLowerCase();
}

function daysLabel(days) {
  if (days < 0) {
    return `逾期 ${Math.abs(days)} 天`;
  }
  if (days === 0) {
    return "今天";
  }
  return `${days} 天后`;
}

function daysDiff(dateText) {
  const today = new Date();
  const target = new Date(`${dateText}T00:00:00+08:00`);
  return Math.round((target - today) / 86400000);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
