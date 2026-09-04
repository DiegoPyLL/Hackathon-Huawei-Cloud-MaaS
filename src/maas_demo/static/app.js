const promptInput = document.querySelector("#prompt");
const submitButton = document.querySelector("#submit");
const answer = document.querySelector("#answer");
const status = document.querySelector("#status");
const modeBadge = document.querySelector("#mode-badge");
const liveLog = document.querySelector("#live-log");
const pipeline = document.querySelector("#pipeline");
const incidentList = document.querySelector("#incidents");
const taskList = document.querySelector("#tasks");
const findingList = document.querySelector("#findings");
const approvalList = document.querySelector("#approvals");
const severityChart = document.querySelector("#severity-chart");
const triageCount = document.querySelector("#triage-count");
const metric = {
  mode: document.querySelector("#metric-mode"),
  model: document.querySelector("#metric-model"),
  calls: document.querySelector("#metric-calls"),
  latency: document.querySelector("#metric-latency"),
};

const SEVERITIES = ["critica", "alta", "media", "baja"];
const taskNodes = new Map();
const budgetFill = document.querySelector("#budget-fill");
const budgetText = document.querySelector("#budget-text");
const BUDGET_SECONDS = 150;
let budgetTimer = null;

function setMode(mode) {
  modeBadge.textContent = mode === "live" ? "LIVE · Huawei MaaS" : "MOCK · Sin consumo cloud";
  modeBadge.dataset.mode = mode;
}

function setPhase(phase, state) {
  const step = pipeline.querySelector(`[data-phase="${phase}"]`);
  if (step) step.dataset.state = state;
}

function startBudget() {
  stopBudget();
  const startedAt = performance.now();
  budgetFill.dataset.state = "activo";
  budgetTimer = setInterval(() => {
    const elapsed = (performance.now() - startedAt) / 1000;
    const remaining = Math.max(0, BUDGET_SECONDS - elapsed);
    const pct = Math.round((remaining / BUDGET_SECONDS) * 100);
    budgetFill.style.width = `${pct}%`;
    budgetText.textContent = `${remaining.toFixed(1)}s`;
    if (remaining <= 0) stopBudget();
  }, 100);
}

function stopBudget() {
  if (budgetTimer) { clearInterval(budgetTimer); budgetTimer = null; }
}

function finishBudget(state) {
  stopBudget();
  budgetFill.dataset.state = state;
  budgetFill.style.width = state === "agotado" ? "0%" : "100%";
  if (state === "agotado") budgetText.textContent = "agotado";
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function tag(text, kind) {
  const node = element("span", "tag", text);
  if (kind) node.dataset.kind = kind;
  return node;
}

function evidenceList(items) {
  const list = element("ul", "evidence");
  (items || []).forEach((item) => list.append(element("li", null, item)));
  return list;
}

function renderSeverityChart(incidents) {
  severityChart.replaceChildren();
  const total = incidents.length || 1;
  SEVERITIES.forEach((severity) => {
    const count = incidents.filter((incident) => incident.severidad === severity).length;
    const row = element("div", "chart-row");
    row.append(element("span", "chart-label", severity));
    const track = element("div", "chart-track");
    const bar = element("div", "chart-bar");
    bar.dataset.severity = severity;
    bar.style.width = `${Math.round((count / total) * 100)}%`;
    track.append(bar);
    row.append(track, element("span", "chart-value", String(count)));
    severityChart.append(row);
  });
}

function renderIncidents(incidents, discarded, deferred) {
  triageCount.textContent = String(incidents.length);
  renderSeverityChart(incidents);
  incidentList.replaceChildren();
  incidents.forEach((incident) => {
    const card = element("li", "card");
    card.dataset.severity = incident.severidad;
    const head = element("div", "card-head");
    head.append(element("strong", null, `${incident.id} · ${incident.titulo}`));
    head.append(tag(incident.severidad, "severidad"));
    card.append(head);
    const tags = element("div", "tags");
    tags.append(tag(incident.tipo), tag(incident.canal));
    if (incident.ataque_activo) tags.append(tag("ataque activo", "alerta"));
    incident.especialistas.forEach((specialist) => tags.append(tag(specialist, "rol")));
    card.append(tags, evidenceList(incident.evidencia));
    card.append(element("p", "muted", incident.motivo_ruteo));
    incidentList.append(card);
  });
  [["Descartado", discarded], ["Diferido", deferred]].forEach(([label, items]) => {
    (items || []).forEach((item) => {
      const text = typeof item === "string" ? item : `${item.incidente_id}: ${item.motivo}`;
      incidentList.append(element("li", "card discarded", `${label} — ${text}`));
    });
  });
}

function upsertTask(event) {
  const key = `${event.incidente_id}·${event.especialista}`;
  let node = taskNodes.get(key);
  if (!node) {
    node = element("li", "task");
    node.append(element("span", "task-name", key.replace("·", " · ")));
    node.append(element("span", "task-state"));
    taskNodes.set(key, node);
    taskList.append(node);
  }
  node.dataset.state = event.estado;
  node.querySelector(".task-state").textContent = event.estado;
}

function renderFinding(finding) {
  const card = element("li", "card");
  card.dataset.state = finding.estado;
  const head = element("div", "card-head");
  head.append(element("strong", null, `${finding.incidente_id} · ${finding.especialista}`));
  if (finding.confianza) head.append(tag(`confianza ${finding.confianza}`, "confianza"));
  card.append(head);
  if (finding.estado === "fallido") {
    card.append(element("p", "error-text", finding.error || "El especialista falló."));
  } else {
    card.append(element("p", null, finding.causa_raiz || "Sin causa raíz propuesta."));
    card.append(evidenceList(finding.evidencia));
    if (finding.descartado && finding.descartado.length) {
      card.append(element("p", "muted", `Descartado: ${finding.descartado.join(" · ")}`));
    }
    if (finding.viabilidad) card.append(tag(finding.viabilidad, "viabilidad"));
  }
  findingList.append(card);
}

async function decideApproval(card, approvalId, decision) {
  const response = await fetch(`/api/aprobaciones/${approvalId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  const payload = await response.json();
  card.dataset.state = response.ok ? payload.estado : "error";
  card.querySelector(".approval-state").textContent = response.ok ? payload.estado : payload.error;
}

function renderApproval(event) {
  const card = element("li", "card approval");
  card.dataset.state = "pendiente";
  const head = element("div", "card-head");
  head.append(element("strong", null, event.action_id));
  head.append(tag(`riesgo ${event.riesgo}`, "riesgo"));
  card.append(head, element("span", "approval-state", "pendiente"));
  const actions = element("div", "tags");
  ["aprobada", "rechazada"].forEach((decision) => {
    const button = element("button", null, decision === "aprobada" ? "Aprobar" : "Rechazar");
    button.type = "button";
    button.addEventListener("click", () => decideApproval(card, event.aprobacion_id, decision));
    actions.append(button);
  });
  card.append(actions);
  approvalList.append(card);
}

function consumeEvent(event) {
  if (event.type === "fase") {
    setPhase(event.fase, "activo");
    if (event.fase === "ingesta") { liveLog.textContent = "Volcado recibido, clasificando…"; startBudget(); }
    if (event.fase === "despacho") liveLog.textContent = "Despachando especialistas en paralelo…";
    if (event.fase === "presupuesto_agotado") { liveLog.textContent = "Presupuesto de corrida agotado — entregando resultado parcial."; finishBudget("agotado"); }
  }
  if (event.type === "triage") {
    setPhase("ingesta", "ok");
    setPhase("triage", "ok");
    renderIncidents(event.incidentes, event.descartados, event.diferidos);
    liveLog.textContent = `${event.incidentes.length} incidentes clasificados.`;
  }
  if (event.type === "tarea") {
    upsertTask(event);
    liveLog.textContent = `${event.especialista} → ${event.incidente_id}: ${event.estado}`;
  }
  if (event.type === "hallazgo") renderFinding(event.hallazgo);
  if (event.type === "aprobacion") renderApproval(event);
  if (event.type === "accion_registrada") {
    liveLog.textContent = `Acción de bajo riesgo registrada: ${event.action_id}`;
  }
  if (event.type === "delta") {
    setPhase("despacho", "ok");
    setPhase("consolidacion", "activo");
    if (answer.dataset.streaming !== "1") {
      answer.textContent = "";
      answer.dataset.streaming = "1";
    }
    answer.textContent += event.delta;
  }
  if (event.type === "done") {
    ["ingesta", "triage", "despacho", "consolidacion"].forEach((phase) => setPhase(phase, "ok"));
    status.textContent = event.status === "completada" ? "Completado" : "Parcial";
    liveLog.textContent = `Corrida ${event.run_id.slice(0, 8)} · ${event.fallidos} fallidos · ${event.diferidos.length} diferidos`;
    finishBudget(event.status === "completada" ? "ok" : "agotado");
    metric.mode.textContent = event.mode;
    metric.model.textContent = event.modelos.triage;
    metric.calls.textContent = String(event.llamadas);
    metric.latency.textContent = `${event.latency_ms} ms`;
    setMode(event.mode);
  }
  if (event.type === "error") throw new Error(event.error);
}

function consumeSseBlock(block) {
  const dataLine = block.split("\n").find((line) => line.startsWith("data:"));
  if (dataLine) consumeEvent(JSON.parse(dataLine.slice(5).trim()));
}

function reset() {
  [incidentList, taskList, findingList, approvalList, severityChart].forEach((node) => node.replaceChildren());
  taskNodes.clear();
  triageCount.textContent = "0";
  answer.textContent = "";
  delete answer.dataset.streaming;
  pipeline.querySelectorAll("[data-phase]").forEach((step) => delete step.dataset.state);
  metric.latency.textContent = "—";
  metric.calls.textContent = "—";
  stopBudget();
  budgetFill.style.width = "100%";
  budgetFill.dataset.state = "";
  budgetText.textContent = "—";
}

async function investigateIncident() {
  const content = promptInput.value.trim();
  if (!content) {
    promptInput.focus();
    status.textContent = "Pega el incidente primero";
    return;
  }

  submitButton.disabled = true;
  reset();
  status.textContent = "Investigando…";
  liveLog.textContent = "Enviando el volcado al orquestador…";

  try {
    const response = await fetch("/api/incidentes/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canal: "monitoreo", prompt: content }),
    });
    if (!response.ok || !response.body) {
      const payload = await response.json();
      throw new Error(payload.error || "No se pudo iniciar la corrida.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      blocks.filter(Boolean).forEach(consumeSseBlock);
      if (done) break;
    }
    if (buffer.trim()) consumeSseBlock(buffer);
  } catch (error) {
    status.textContent = "Error";
    liveLog.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    setMode(health.mode);
    metric.mode.textContent = health.mode;
    metric.model.textContent = health.model;
  } catch {
    modeBadge.textContent = "Servicio no disponible";
  }
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});
submitButton.addEventListener("click", investigateIncident);
loadHealth();
