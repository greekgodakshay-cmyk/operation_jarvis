// Operation JARVIS — Local Dashboard Controller

let currentSummary = null;
let allTools = [];

document.addEventListener("DOMContentLoaded", () => {
  fetchSummary();
  // Poll summary every 5 seconds
  setInterval(fetchSummary, 5000);
});

function switchTab(tabName) {
  document.querySelectorAll(".nav-tab").forEach(tab => tab.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));

  const targetTab = Array.from(document.querySelectorAll(".nav-tab")).find(t => 
    t.textContent.toLowerCase().includes(tabName.toLowerCase())
  );
  if (targetTab) targetTab.classList.add("active");

  const targetPane = document.getElementById(`tab-${tabName}`);
  if (targetPane) targetPane.classList.add("active");
}

async function fetchSummary() {
  try {
    const res = await fetch("/api/v1/dashboard/summary");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentSummary = data;
    renderSummary(data);
  } catch (err) {
    console.error("Failed to fetch dashboard summary:", err);
    updateSystemStatus("degraded", "OFFLINE / UNREACHABLE");
  }
}

function renderSummary(data) {
  // 1. System Status Pill
  const isStopped = data.emergency_stopped;
  const status = data.status;
  if (isStopped) {
    updateSystemStatus("stopped", "EMERGENCY STOPPED");
  } else if (status === "online") {
    updateSystemStatus("online", "ONLINE");
  } else {
    updateSystemStatus("degraded", "DEGRADED");
  }

  // 2. Hardware metrics
  const sys = data.system;
  document.getElementById("statCpuRam").textContent = `${sys.cpu_percent}% CPU / ${sys.ram_used_gb} GB`;
  document.getElementById("statGpu").textContent = `${sys.gpu} (${sys.vram_allocated_gb} / ${sys.vram_total_gb} GB VRAM)`;

  // 3. Overview stats
  document.getElementById("statAgentCount").textContent = `${data.agents.length} Active`;
  document.getElementById("statToolsCount").textContent = `${data.capabilities.total_tools} Registered`;
  const byLvl = data.capabilities.by_level;
  document.getElementById("statToolsLevels").textContent = `Safe: ${byLvl.LEVEL_1_SAFE || 0} | Ctrl: ${byLvl.LEVEL_2_CONTROLLED || 0} | Restr: ${byLvl.LEVEL_3_RESTRICTED || 0}`;
  document.getElementById("tabToolCount").textContent = data.capabilities.total_tools;

  document.getElementById("statMemoryCount").textContent = `${data.knowledge.memory_nodes.toLocaleString()} Records`;
  document.getElementById("statDocCount").textContent = `${data.knowledge.indexed_documents} Documents`;
  document.getElementById("statChunkCount").textContent = `${data.knowledge.indexed_chunks} Total Chunks Indexed`;

  document.getElementById("statSchedCount").textContent = `${data.schedules.total} Active`;

  // 4. Pending Approvals Banner
  const sec = data.security;
  const banner = document.getElementById("approvalBanner");
  if (sec.pending_approvals > 0) {
    banner.style.display = "flex";
    document.getElementById("approvalBannerText").textContent = 
      `${sec.pending_approvals} Level 3 Restricted action(s) require operator authorization.`;
  } else {
    banner.style.display = "none";
  }

  // 5. Recent Tasks Table
  renderRecentTasks(sec.recent_tasks);

  // 6. Agents Grid
  renderAgents(data.agents);

  // 7. Models and Spending
  const llm = data.llm;
  if (llm && llm.usage) {
    document.getElementById("valSpendingLimit").textContent = `$${llm.usage.spending_limit_usd.toFixed(2)} USD`;
    document.getElementById("valCurrentSpend").textContent = `$${llm.usage.total_cost_usd.toFixed(4)} USD`;
  }

  // 8. Capabilities Table
  allTools = data.capabilities.tools;
  renderCapabilities(allTools);

  // 9. Schedules Table
  renderSchedules(data.schedules.items);

  // 10. Documents Table
  renderDocuments(data.knowledge.documents);

  // 11. Email & Calendar Feeds
  renderComms(data.communications);

  // 12. Security Approvals Pane
  renderSecurityApprovals(sec.pending_tasks);
}

function updateSystemStatus(type, label) {
  const pill = document.getElementById("systemStatusPill");
  pill.className = `status-pill status-${type}`;
  document.getElementById("systemStatusText").textContent = label;

  const btn = document.getElementById("btnEmergencyStop");
  if (type === "stopped") {
    btn.textContent = "RESET EMERGENCY STOP";
    btn.className = "btn btn-warning btn-sm";
  } else {
    btn.textContent = "EMERGENCY STOP";
    btn.className = "btn btn-danger btn-sm";
  }
}

function renderRecentTasks(tasks) {
  const tbody = document.getElementById("tableRecentTasks");
  if (!tasks || tasks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No recent tasks logged.</td></tr>';
    return;
  }
  tbody.innerHTML = tasks.map(t => `
    <tr>
      <td><code>${t.task_id}</code></td>
      <td>${escapeHtml(t.objective)}</td>
      <td><span class="badge ${getStatusBadge(t.status)}">${t.status}</span></td>
      <td>${t.created_at || "N/A"}</td>
    </tr>
  `).join("");
}

function renderAgents(agents) {
  const grid = document.getElementById("agentsGrid");
  if (!agents || agents.length === 0) {
    grid.innerHTML = '<p class="text-muted">No agents registered.</p>';
    return;
  }
  grid.innerHTML = agents.map(a => `
    <div class="agent-card">
      <div class="agent-card-header">
        <span class="agent-name">${escapeHtml(a.name)}</span>
        <span class="badge badge-level-1">${a.status}</span>
      </div>
      <div class="agent-meta">Tier: ${a.tier} • Endpoint: ${a.runtime_endpoint}</div>
      <div class="agent-caps">
        ${(a.capabilities || []).map(c => `<span class="cap-tag">${c}</span>`).join("")}
      </div>
    </div>
  `).join("");
}

function renderCapabilities(tools) {
  const tbody = document.getElementById("tableCapabilities");
  if (!tools || tools.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-muted">No capabilities found.</td></tr>';
    return;
  }
  tbody.innerHTML = tools.map(t => {
    let badgeClass = "badge-level-1";
    if (t.permission_level === "LEVEL_2_CONTROLLED") badgeClass = "badge-level-2";
    if (t.permission_level === "LEVEL_3_RESTRICTED") badgeClass = "badge-level-3";
    return `
      <tr>
        <td><strong>${escapeHtml(t.name)}</strong></td>
        <td><span class="badge ${badgeClass}">${t.permission_level}</span></td>
        <td>${escapeHtml(t.description)}</td>
      </tr>
    `;
  }).join("");
}

function filterTools() {
  const query = document.getElementById("toolSearchInput").value.toLowerCase();
  const filtered = allTools.filter(t => 
    t.name.toLowerCase().includes(query) || 
    t.description.toLowerCase().includes(query) ||
    t.permission_level.toLowerCase().includes(query)
  );
  renderCapabilities(filtered);
}

function renderSchedules(schedules) {
  const tbody = document.getElementById("tableSchedules");
  if (!schedules || schedules.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No scheduled tasks active.</td></tr>';
    return;
  }
  tbody.innerHTML = schedules.map(s => `
    <tr>
      <td><strong>${escapeHtml(s.name)}</strong><br><small class="text-muted">${escapeHtml(s.objective)}</small></td>
      <td>${s.schedule_type} (${s.interval_seconds ? s.interval_seconds + 's' : 'Once'})</td>
      <td>${s.next_run_at || 'None'}</td>
      <td><span class="badge ${s.status === 'ACTIVE' ? 'badge-level-1' : 'badge-level-2'}">${s.status}</span></td>
      <td>
        ${s.status === 'ACTIVE' ? 
          `<button class="btn btn-secondary btn-sm" onclick="controlSchedule('${s.schedule_id}', 'pause')">Pause</button>` :
          `<button class="btn btn-primary btn-sm" onclick="controlSchedule('${s.schedule_id}', 'resume')">Resume</button>`
        }
        <button class="btn btn-secondary btn-sm" onclick="controlSchedule('${s.schedule_id}', 'run_now')">Run</button>
        <button class="btn btn-danger btn-sm" onclick="controlSchedule('${s.schedule_id}', 'cancel')">Cancel</button>
      </td>
    </tr>
  `).join("");
}

async function controlSchedule(id, action) {
  try {
    const res = await fetch(`/api/v1/schedules/${id}/${action}`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    fetchSummary();
  } catch (err) {
    alert(`Failed to ${action} schedule: ${err.message}`);
  }
}

async function createSchedule() {
  const name = document.getElementById("newSchedName").value.trim();
  const interval = parseInt(document.getElementById("newSchedInterval").value) || 3600;
  const objective = document.getElementById("newSchedObjective").value.trim();

  if (!name || !objective) {
    alert("Please enter schedule name and objective.");
    return;
  }

  try {
    const res = await fetch("/api/v1/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        objective: objective,
        schedule_type: "INTERVAL",
        interval_seconds: interval
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    document.getElementById("newSchedName").value = "";
    document.getElementById("newSchedObjective").value = "";
    fetchSummary();
    alert("Schedule created successfully!");
  } catch (err) {
    alert(`Failed to create schedule: ${err.message}`);
  }
}

function renderDocuments(docs) {
  const tbody = document.getElementById("tableDocuments");
  if (!docs || docs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No documents ingested.</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => `
    <tr>
      <td><strong>${escapeHtml(d.filename)}</strong></td>
      <td>${d.total_chunks} chunks (${d.page_count} pages)</td>
      <td>${d.created_at || 'N/A'}</td>
      <td><span class="badge badge-level-1">INDEXED</span></td>
    </tr>
  `).join("");
}

async function ingestDocument() {
  const path = document.getElementById("inputIngestPath").value.trim();
  if (!path) {
    alert("Please enter a file path.");
    return;
  }
  try {
    const res = await fetch("/api/v1/documents/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: path })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Ingestion failed");
    document.getElementById("inputIngestPath").value = "";
    fetchSummary();
    alert(`Document ingested successfully! Chunks: ${data.total_chunks}`);
  } catch (err) {
    alert(`Ingestion error: ${err.message}`);
  }
}

async function runRagEvaluation() {
  const reportBox = document.getElementById("ragReportView");
  reportBox.style.display = "block";
  reportBox.textContent = "Running standardized retrieval evaluation against local memory store...";

  try {
    const res = await fetch("/api/v1/rag/evaluate");
    const data = await res.json();
    const m = data.metrics;
    document.getElementById("ragHitRate").textContent = `${(m.hit_rate_at_k * 100).toFixed(1)}%`;
    document.getElementById("ragMRR").textContent = m.mean_reciprocal_rank.toFixed(4);
    document.getElementById("ragLatency").textContent = `${m.average_latency_ms.toFixed(2)} ms`;
    document.getElementById("ragRejection").textContent = `${(m.negative_rejection_rate * 100).toFixed(1)}%`;

    // Fetch markdown text
    const mdRes = await fetch("/api/v1/rag/report");
    const mdText = await mdRes.text();
    reportBox.textContent = mdText;
  } catch (err) {
    reportBox.textContent = `Evaluation failed: ${err.message}`;
  }
}

function renderComms(comms) {
  // Emails
  const emailList = document.getElementById("emailList");
  if (!comms.recent_emails || comms.recent_emails.length === 0) {
    emailList.innerHTML = '<p class="text-muted">No emails in inbox.</p>';
  } else {
    emailList.innerHTML = comms.recent_emails.map(e => `
      <div class="feed-item">
        <div class="feed-header">
          <span>From: ${escapeHtml(e.sender)}</span>
          <span>${e.date || ''}</span>
        </div>
        <div class="feed-title">${escapeHtml(e.subject)}</div>
        <div class="feed-body">${escapeHtml(e.snippet)}</div>
      </div>
    `).join("");
  }

  // Calendar
  const calList = document.getElementById("calendarList");
  if (!comms.upcoming_events || comms.upcoming_events.length === 0) {
    calList.innerHTML = '<p class="text-muted">No upcoming calendar events.</p>';
  } else {
    calList.innerHTML = comms.upcoming_events.map(ev => `
      <div class="feed-item">
        <div class="feed-header">
          <span>${ev.start_time} - ${ev.end_time}</span>
          <span>${ev.location || 'Local'}</span>
        </div>
        <div class="feed-title">${escapeHtml(ev.title)}</div>
        <div class="feed-body">${escapeHtml(ev.description || 'No description')}</div>
      </div>
    `).join("");
  }
}

function renderSecurityApprovals(pendingTasks) {
  const container = document.getElementById("pendingApprovalsList");
  if (!pendingTasks || pendingTasks.length === 0) {
    container.innerHTML = '<p class="text-muted">No pending approvals at this time. All operations nominal.</p>';
    return;
  }
  container.innerHTML = pendingTasks.map(t => `
    <div class="feed-item">
      <div class="feed-header">
        <span>Task ID: <code>${t.task_id}</code></span>
        <span>${t.created_at || ''}</span>
      </div>
      <div class="feed-title">${escapeHtml(t.objective)}</div>
      <div class="input-action-bar" style="margin-top: 8px;">
        <button class="btn btn-primary btn-sm" onclick="approveTask('${t.task_id}', true)">Authorize Action</button>
        <button class="btn btn-danger btn-sm" onclick="approveTask('${t.task_id}', false)">Deny Action</button>
      </div>
    </div>
  `).join("");
}

async function approveTask(taskId, approved) {
  try {
    const res = await fetch(`/api/v1/tasks/${taskId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: taskId, approved: approved })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    fetchSummary();
    alert(`Task approval resolved: ${approved ? 'Authorized' : 'Denied'}`);
  } catch (err) {
    alert(`Failed to resolve approval: ${err.message}`);
  }
}

async function submitObjective() {
  const input = document.getElementById("inputUserObjective");
  const objective = input.value.trim();
  if (!objective) return;

  const resultBox = document.getElementById("quickTaskResult");
  resultBox.style.display = "block";
  resultBox.textContent = `Executing objective: "${objective}"...`;

  try {
    const res = await fetch("/api/v1/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective: objective, async_execution: false })
    });
    const data = await res.json();
    resultBox.textContent = JSON.stringify(data, null, 2);
    input.value = "";
    fetchSummary();
  } catch (err) {
    resultBox.textContent = `Execution failed: ${err.message}`;
  }
}

async function toggleEmergencyStop() {
  const isStopped = currentSummary ? currentSummary.emergency_stopped : false;
  const action = isStopped ? "reset" : "trigger";
  const confirmMsg = isStopped ? 
    "Reset emergency stop and resume workstation runtime?" :
    "TRIGGER EMERGENCY STOP? All tool executions will immediately halt!";
  
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch("/api/v1/security/emergency_stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action })
    });
    const data = await res.json();
    fetchSummary();
  } catch (err) {
    alert(`Failed to toggle emergency stop: ${err.message}`);
  }
}

function getStatusBadge(status) {
  if (status === "COMPLETED" || status === "VERIFIED") return "badge-level-1";
  if (status === "RUNNING" || status === "PLANNING" || status === "EXECUTING") return "badge-level-2";
  return "badge-level-3";
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
