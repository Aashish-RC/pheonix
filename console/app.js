// Pheonix Unified Intelligence Console Frontend Logic

let currentTenant = "tenant_enterprise_alpha";
let currentRole = "owner";
let auditSequence = 3;

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
  }
}

function onTenantChange(tenantId) {
  currentTenant = tenantId;
  appendAuditRecord(`tenant.switched -> ${tenantId}`);
}

function onRoleChange(role) {
  currentRole = role;
  appendAuditRecord(`role.assumed -> ${role}`);
}

function renderCanvas() {
  const code = document.getElementById("canvas-code-input").value;
  const iframe = document.getElementById("canvas-iframe");
  if (iframe) {
    iframe.srcdoc = code;
  }
}

function appendAuditRecord(action) {
  auditSequence++;
  const tbody = document.getElementById("audit-table-body");
  if (!tbody) return;

  const row = document.createElement("tr");
  const now = new Date().toISOString().replace("T", " ").substring(0, 19);
  const randHash = Array.from({length: 6}, () => Math.floor(Math.random()*16).toString(16)).join("");

  row.innerHTML = `
    <td>#${auditSequence}</td>
    <td>${now}</td>
    <td>${currentTenant}</td>
    <td>${currentRole}</td>
    <td>${action}</td>
    <td><code style="color: var(--accent-cyan);">${randHash}...e1f8</code></td>
    <td><span class="badge-verified">&#10003; Verified</span></td>
  `;
  tbody.appendChild(row);
}

function sendMessage() {
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

  // Check if simulated consequential action requested
  const isConsequential = /delete|payment|drop|deploy/i.test(text);
  const isCaptcha = /captcha|turnstile|verify/i.test(text);

  if (isCaptcha) {
    document.getElementById("takeover-banner").style.display = "flex";
  }

  // Simulate streaming assistant message
  const botCard = document.createElement("div");
  botCard.className = "message-card";
  botCard.innerHTML = `
    <div class="avatar bot-avatar">PH</div>
    <div class="message-bubble">
      <p id="msg-stream-${Date.now()}">Processing request through ${currentTenant} router...</p>
      ${isConsequential ? `
        <div class="approval-banner">
          <div class="approval-text">
            <strong>Security Confirmation Required:</strong> Mode 'Ask on changes' detected consequential command.
          </div>
          <div class="approval-btn-group">
            <button class="btn-approve" onclick="approveAction(this)">Approve</button>
            <button class="btn-reject" onclick="rejectAction(this)">Reject</button>
          </div>
        </div>
      ` : ""}
      <div class="tool-chip">
        <span class="tool-chip-name">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          orchestrator:dispatch_step
        </span>
        <span class="tool-chip-badge">24ms (OK)</span>
      </div>
    </div>
  `;
  container.appendChild(botCard);
  container.scrollTop = container.scrollHeight;

  appendAuditRecord(`agent.query: "${text.substring(0, 30)}..."`);
}

function approveAction(btn) {
  const banner = btn.closest(".approval-banner");
  banner.innerHTML = `<span style="color: var(--accent-emerald); font-size: 0.85rem; font-weight: 600;">&#10003; Action Approved by ${currentRole}</span>`;
  appendAuditRecord("security.action_approved");
}

function rejectAction(btn) {
  const banner = btn.closest(".approval-banner");
  banner.innerHTML = `<span style="color: var(--accent-rose); font-size: 0.85rem; font-weight: 600;">&#10007; Action Blocked by ${currentRole}</span>`;
  appendAuditRecord("security.action_rejected");
}

function resolveTakeover() {
  document.getElementById("takeover-banner").style.display = "none";
  appendAuditRecord("browser.takeover_resolved_by_human");
  alert("Human takeover resolved! Control returned to automated agent.");
}

function abortTakeover() {
  document.getElementById("takeover-banner").style.display = "none";
  appendAuditRecord("browser.takeover_aborted");
}

function optimizePrompt() {
  const input = document.getElementById("prompt-tuner-input").value;
  const output = document.getElementById("prompt-tuner-output");
  output.textContent = 
`You are an expert autonomous assistant for Pheonix (${currentTenant}).

### Directives:
- Core Objective: ${input}
- Constraints: Maintain strict data privacy; enforce sandbox limits; cite primary sources.
- Output Format: JSON schema conforming with validation error handlers.

### Few-Shot Example:
User: Verify system health
Assistant: {"status": "healthy", "latency_ms": 12.4, "checks": ["vault", "orchestrator"]}`;
  appendAuditRecord("prompt_assistant.optimized");
}

function checkUpdates() {
  alert("Update Channel: main (commit 71d7547)\nChannel Status: Up-to-date with upstream origin/main.");
  appendAuditRecord("release.update_channel_checked");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Initial render
window.addEventListener("DOMContentLoaded", () => {
  renderCanvas();
});
