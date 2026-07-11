const customerSelect = document.querySelector("#customerSelect");
const runButton = document.querySelector("#runButton");
const goal = document.querySelector("#goal");
const auditId = document.querySelector("#auditId");
const customerStrip = document.querySelector("#customerStrip");
const steps = document.querySelector("#steps");
const verification = document.querySelector("#verification");
const impact = document.querySelector("#impact");
const journeyStatus = document.querySelector("#journeyStatus");
const auditTimeline = document.querySelector("#auditTimeline");
const llmUsage = document.querySelector("#llmUsage");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function titleCaseStatus(status) {
  return status.replaceAll("_", " ");
}

function moneyCrore(value) {
  return new Intl.NumberFormat("en-IN").format(value);
}

function renderCustomer(customer, bankMitra) {
  customerStrip.innerHTML = `
    <div>
      <strong>${escapeHtml(customer.name)}</strong>
      <span>${escapeHtml(customer.village)} | ${escapeHtml(customer.segment)}</span>
    </div>
    <div class="tags">
      <span class="tag">${escapeHtml(customer.language)}</span>
      <span class="tag">KYC: ${escapeHtml(customer.kyc_level)}</span>
      <span class="tag">UPI: ${escapeHtml(customer.upi_status.replaceAll("_", " "))}</span>
      <span class="tag">Mitra: ${escapeHtml(bankMitra.name)}</span>
    </div>
  `;
}

function renderSteps(items) {
  if (!items.length) {
    steps.innerHTML = `<p>No executable steps because consent or eligibility is blocked.</p>`;
    return;
  }
  steps.innerHTML = items.map((step) => {
    const stateClass = step.status === "blocked" ? "blocked" : "ready";
    const payload = step.payload || {};
    const skillUsed = payload.skill_used;
    const reasoningTrace = payload.reasoning_trace || [];
    return `
      <div class="step">
        <div>
          <p class="eyebrow">${escapeHtml(step.agent)}</p>
          <h4>${escapeHtml(step.title)}</h4>
          ${skillUsed ? `<span class="skill-tag">${escapeHtml(skillUsed.replaceAll("_", " "))}</span>` : ""}
        </div>
        <div>
          <p>${escapeHtml(step.detail)}</p>
          <dl class="reasoning">
            <dt>Why</dt>
            <dd>${escapeHtml(payload.why_this_action || "Rule-based next best action.")}</dd>
            <dt>Mitra check</dt>
            <dd>${escapeHtml(payload.bank_mitra_must_verify || "Confirm customer authorisation.")}</dd>
          </dl>
          ${reasoningTrace.length ? `<p class="trace-note">LLM verified in ${reasoningTrace.length} round(s), final score ${escapeHtml(reasoningTrace[reasoningTrace.length - 1]?.score ?? "n/a")}/100.</p>` : ""}
        </div>
        <span class="status ${stateClass}">${escapeHtml(titleCaseStatus(step.status))}</span>
      </div>
    `;
  }).join("");
}

function renderVerification(item) {
  const warnings = item.warnings || [];
  const blocked = item.blocked || [];
  const checks = item.policy_checks || [];
  const passedBlock = item.passed
    ? `<div class="check"><strong>Passed</strong><p>Consent, KYC, and submission checks allow assisted execution.</p></div>`
    : `<div class="block"><strong>Human resolution required</strong><p>The copilot stopped before risky execution.</p></div>`;
  verification.innerHTML = [
    passedBlock,
    `<div class="check"><strong>Human-in-the-loop</strong><p>${escapeHtml(item.human_authorisation || "Bank Mitra authorisation required.")}</p></div>`,
    `<div class="check"><strong>RBI posture</strong><p>${escapeHtml(item.rbi_posture || "No autonomous money movement.")}</p></div>`,
    ...checks.map((check) => `<div class="${check.status === "blocked" ? "block" : check.status === "warning" ? "warn" : "check"}"><strong>${escapeHtml(check.name)}</strong><p>${escapeHtml(check.detail)}</p></div>`),
    ...warnings.map((warning) => `<div class="warn"><strong>Warning</strong><p>${escapeHtml(warning)}</p></div>`),
    ...blocked.map((message) => `<div class="block"><strong>Blocked</strong><p>${escapeHtml(message)}</p></div>`),
  ].join("");
}

function renderAuditTimeline(items) {
  auditTimeline.innerHTML = items.map((event) => (
    `<div class="audit-event ${event.status === "blocked" ? "blocked-event" : ""}">
      <span>${escapeHtml(event.stage)}</span>
      <p>${escapeHtml(event.message)}</p>
    </div>`
  )).join("");
}

function renderImpact(item) {
  impact.innerHTML = `
    <div>
      <div class="big-number">${moneyCrore(item.annual_incremental_activations)}</div>
      <p>Illustrative yearly digital activations from +${item.monthly_incremental_activations_per_outlet} per outlet per month.</p>
    </div>
    <div>
      <div class="big-number">Rs ${item.annual_value_crore_rs} cr</div>
      <p>Illustrative annual value at Rs 600 blended value per activation.</p>
    </div>
  `;
}

function renderLlmUsage(item) {
  if (!item) {
    llmUsage.innerHTML = `<p>No LLM usage recorded for this run.</p>`;
    return;
  }
  llmUsage.innerHTML = `
    <div>
      <div class="big-number">$${item.total_cost_usd.toFixed(4)}</div>
      <p>${item.total_calls} LLM call(s), ${item.total_input_tokens}+${item.total_output_tokens} tokens (cumulative this server run).</p>
    </div>
  `;
}

async function loadCustomers() {
  const response = await fetch("/api/customers");
  const customers = await response.json();
  customerSelect.innerHTML = customers.map((customer) => (
    `<option value="${escapeHtml(customer.customer_id)}">${escapeHtml(customer.name)} - ${escapeHtml(customer.language)}</option>`
  )).join("");
}

async function runJourney() {
  runButton.disabled = true;
  runButton.textContent = "Running agents...";
  const response = await fetch(`/api/run?customer=${customerSelect.value}`);
  const data = await response.json();
  if (!response.ok) {
    auditId.textContent = "Error";
    if (data.error === "llm_unavailable") {
      goal.textContent = "LLM unavailable: ANTHROPIC_API_KEY is not set on the server. This build requires real LLM narration and will not fall back to rule-based-only mode.";
    } else {
      goal.textContent = `Unable to run journey: ${data.error || "request failed"}`;
    }
    runButton.disabled = false;
    runButton.textContent = "Run Assisted Journey";
    return;
  }
  auditId.textContent = data.audit_id;
  goal.textContent = data.goal;
  journeyStatus.textContent = titleCaseStatus(data.outcome.journey_status);
  renderCustomer(data.customer, data.bank_mitra);
  renderSteps(data.steps);
  renderVerification(data.verification);
  renderAuditTimeline(data.audit_timeline || []);
  renderImpact(data.impact);
  renderLlmUsage(data.llm_usage);
  runButton.disabled = false;
  runButton.textContent = "Run Assisted Journey";
}

loadCustomers().then(runJourney);
runButton.addEventListener("click", runJourney);
customerSelect.addEventListener("change", runJourney);
