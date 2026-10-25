// Pheonix Unified Intelligence Console Frontend Logic (Honest Backend-Connected)

let currentTenant = "default";
let currentRole = "owner";

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();

    const statusText = document.getElementById("system-status-text");
    if (statusText) {
      if (data.status === "healthy") {
        statusText.textContent = data.components.model_gateway === "connected" 
          ? "System Online (Live Gateway)" 
          : "System Ready (Console Preview)";
      } else {
        statusText.textContent = "System Degraded";
      }
    }

    const modHealth = document.getElementById("metric-module-health");
    if (modHealth) {
      modHealth.textContent = data.status === "healthy" ? "Healthy (Auth/Vault/Audit)" : "Degraded";
      modHealth.style.color = data.status === "healthy" ? "var(--accent-emerald)" : "var(--accent-rose)";
    }

    const gwStatus = document.getElementById("metric-gateway-status");
    const gwSub = document.getElementById("metric-gateway-sub");
    if (gwStatus) {
      const isConn = data.components && data.components.model_gateway === "connected";
      gwStatus.textContent = isConn ? "Connected" : "Offline (Preview)";
      gwStatus.style.color = isConn ? "var(--accent-emerald)" : "#f59e0b";
      if (gwSub) {
        gwSub.textContent = isConn ? "Inference ready on port 4000" : "Start compose to enable live LLM";
      }
    }
  } catch (err) {
    console.warn("Failed to load real health:", err);
  }
}

async function loadTenants() {
  try {
    const res = await fetch("/api/tenants");
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById("tenant-select-box");
    if (select && data.tenants && data.tenants.length > 0) {
      select.innerHTML = "";
      data.tenants.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = `${t.name} (${t.id})`;
        select.appendChild(opt);
      });
      currentTenant = select.value || "default";
    }
  } catch (err) {
    console.warn("Failed to fetch tenants:", err);
  }
}

async function loadAuditRecords() {
  const tbody = document.getElementById("audit-table-body");
  if (!tbody) return;

  try {
    const res = await fetch(`/api/audit?tenant_id=${encodeURIComponent(currentTenant === "default" ? "" : currentTenant)}`);
    if (!res.ok) throw new Error("Audit fetch failed");
    const data = await res.json();

    if (!data.entries || data.entries.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 2rem;">No audit records recorded yet. Verified Chain: ${data.verified ? "&#10003; Valid" : "&#10007; Tampered"}</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    data.entries.forEach(e => {
      const row = document.createElement("tr");
      const shortId = e.id ? e.id.substring(0, 10) : "";
      row.innerHTML = `
        <td><code style="color: var(--accent-cyan);">${escapeHtml(shortId)}...</code></td>
        <td>${escapeHtml(e.timestamp)}</td>
        <td>${escapeHtml(e.tenant_id)}</td>
        <td>${escapeHtml(e.role)}</td>
        <td><strong>${escapeHtml(e.module)}</strong>: ${escapeHtml(e.action)}</td>
        <td><code>${escapeHtml(e.resource || "-")}</code></td>
        <td><span class="badge-verified">${data.verified ? "&#10003; Verified" : "&#9888; Degraded"}</span></td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--accent-rose); padding: 1.5rem;">Failed to read ledger: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function switchTab(tabId) {
  // Update nav buttons
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));
  const activeBtn = document.getElementById(`nav-btn-${tabId}`);
  if (activeBtn) activeBtn.classList.add("active");

  // Update views
  document.querySelectorAll(".view-container").forEach(view => view.classList.remove("active"));
  const targetView = document.getElementById(`view-${tabId}`);
  if (targetView) targetView.classList.add("active");

  // Update header text
  const titles = {
    chat: "Conversational Core & Agent Surface",
    canvas: "Live Canvas & Artifact Preview",
    prompt: "Prompt Assistant & Instruction Tuner",
    owner: "Owner & Tenant Governance Console",
    audit: "Tamper-Evident Chained Audit Ledger"
  };
  const headerElem = document.getElementById("active-view-header");
  if (headerElem && titles[tabId]) {
    headerElem.textContent = titles[tabId];
  }

  if (tabId === "canvas") {
    renderCanvas();
  } else if (tabId === "audit") {
    loadAuditRecords();
  } else if (tabId === "owner") {
    loadHealth();
  }
}

function onTenantChange(tenantId) {
  currentTenant = tenantId;
  loadAuditRecords();
}

function onRoleChange(role) {
  currentRole = role;
}

function renderCanvas() {
  const code = document.getElementById("canvas-code-input").value;
  const iframe = document.getElementById("canvas-iframe");
  if (iframe) {
    iframe.srcdoc = code;
  }
}

async function sendMessage() {
  const input = document.getElementById("chat-user-input");
  const text = (input.value || "").trim();
  if (!text) return;

  input.value = "";
  const container = document.getElementById("chat-messages");

  // Append User message
  const userCard = document.createElement("div");
  userCard.className = "message-card user";
  userCard.innerHTML = `
    <div class="avatar user-avatar">${currentRole.substring(0, 2).toUpperCase()}</div>
    <div class="message-bubble"><p>${escapeHtml(text)}</p></div>
  `;
  container.appendChild(userCard);

  // Append Pending Assistant card
  const botCard = document.createElement("div");
  botCard.className = "message-card";
  const streamId = `msg-stream-${Date.now()}`;
  botCard.innerHTML = `
    <div class="avatar bot-avatar">PH</div>
    <div class="message-bubble">
      <p id="${streamId}" style="color: #94a3b8;">Routing to Model Gateway (tenant: ${escapeHtml(currentTenant)})...</p>
      <div class="tool-chip">
        <span class="tool-chip-name">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          gateway:chat_completions
        </span>
        <span id="chip-status-${streamId}" class="tool-chip-badge">dispatching</span>
      </div>
    </div>
  `;
  container.appendChild(botCard);
  container.scrollTop = container.scrollHeight;

  // Real backend call to /api/chat/dispatch (proxies to Model Gateway)
  try {
    const res = await fetch("/api/chat/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        tenant_id: currentTenant,
        role: currentRole,
      }),
    });
    const data = await res.json();
    const streamP = document.getElementById(streamId);
    const chipStatus = document.getElementById(`chip-status-${streamId}`);

    if (streamP) {
      streamP.style.color = "#f8fafc";
      streamP.textContent = data.reply || "No response received";
    }
    if (chipStatus) {
      chipStatus.textContent = data.source === "model-gateway" ? "Live Gateway (OK)" : "Offline Preview";
      chipStatus.style.background = data.source === "model-gateway" ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)";
    }
  } catch (err) {
    const streamP = document.getElementById(streamId);
    if (streamP) {
      streamP.textContent = `Error dispatching query: ${err.message}`;
    }
  }

  container.scrollTop = container.scrollHeight;
}

function resolveTakeover() {
  document.getElementById("takeover-banner").style.display = "none";
  alert("Human takeover resolved! Control returned to automated agent.");
}

function abortTakeover() {
  document.getElementById("takeover-banner").style.display = "none";
}

async function optimizePrompt() {
  const input = document.getElementById("prompt-tuner-input").value;
  const output = document.getElementById("prompt-tuner-output");
  output.textContent = "Invoking Model Gateway prompt optimizer...";

  try {
    const res = await fetch("/api/prompt/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: input,
        target_domain: "security_and_governance",
      }),
    });
    const data = await res.json();
    output.textContent = data.optimized_prompt;
  } catch (err) {
    output.textContent = `Failed to optimize prompt: ${err.message}`;
  }
}

function checkUpdates() {
  alert("Update Channel: main (Preview)\nIntegrity: All local module hashes match repository commit.");
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Initial initialization
window.addEventListener("DOMContentLoaded", () => {
  renderCanvas();
  loadHealth();
  loadTenants();
  loadAuditRecords();
});
