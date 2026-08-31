const promptInput = document.querySelector("#prompt");
const submitButton = document.querySelector("#submit");
const answer = document.querySelector("#answer");
const status = document.querySelector("#status");
const modeBadge = document.querySelector("#mode-badge");
const metricMode = document.querySelector("#metric-mode");
const metricModel = document.querySelector("#metric-model");
const metricLatency = document.querySelector("#metric-latency");

function setMode(mode) {
  modeBadge.textContent = mode === "live" ? "LIVE · Huawei MaaS" : "MOCK · Sin consumo cloud";
  modeBadge.dataset.mode = mode;
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    setMode(health.mode);
    metricMode.textContent = health.mode;
    metricModel.textContent = health.model;
  } catch {
    modeBadge.textContent = "Servicio no disponible";
  }
}

function consumeSseBlock(block) {
  const dataLine = block.split("\n").find((line) => line.startsWith("data:"));
  if (!dataLine) return;
  const event = JSON.parse(dataLine.slice(5).trim());
  if (event.type === "delta") answer.textContent += event.delta;
  if (event.type === "done") {
    status.textContent = "Completado";
    metricMode.textContent = event.mode;
    metricModel.textContent = event.model;
    metricLatency.textContent = `${event.latency_ms} ms`;
    setMode(event.mode);
  }
  if (event.type === "error") throw new Error(event.error);
}

async function generateBrief() {
  const content = promptInput.value.trim();
  if (!content) {
    promptInput.focus();
    status.textContent = "Describe un reto primero";
    return;
  }

  submitButton.disabled = true;
  answer.textContent = "";
  status.textContent = "Generando…";
  metricLatency.textContent = "—";

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content }] }),
    });
    if (!response.ok || !response.body) {
      const payload = await response.json();
      throw new Error(payload.error || "No se pudo iniciar la respuesta.");
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
    answer.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
  });
});
submitButton.addEventListener("click", generateBrief);
loadHealth();
