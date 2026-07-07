let currentDatasetName = null;
let lastBatchResults = [];
let pressureProgressTimer = null;

const $ = (selector) => document.querySelector(selector);
const STORAGE_KEY = "modelBatchTestState";
const RESTORE_KEY = "modelBatchTestRestoreOnNextLoad";
let isRestoringState = false;

function modelConfig() {
  const requestBody = parseRequestBody();
  return {
    api_url: $("#apiUrl").value.trim(),
    model: $("#modelName").value.trim(),
    request_body: requestBody,
  };
}

bindIfPresent("#modelPreset", "change", (event) => {
  const option = event.target.selectedOptions[0];
  if (!option || !option.dataset.apiUrl || !option.dataset.model) {
    return;
  }
  $("#apiUrl").value = option.dataset.apiUrl;
  $("#modelName").value = option.dataset.model;
  syncRequestBody();
});

bindIfPresent("#modelName", "input", () => {
  syncRequestBody();
});
bindIfPresent("#singlePrompt", "input", () => {
  syncRequestBody();
});
bindIfPresent("#pressurePrompt", "input", () => {
  syncRequestBody();
});
bindIfPresent("#pressureModeToggle", "click", togglePressureMode);
bindIfPresent("#requestBody", "input", () => {
  validateRequestBody();
});
bindIfPresent("#resetRequestBody", "click", () => {
  renderRequestBody(buildDefaultRequestBody());
});
bindIfPresent("#formatRequestBody", "click", formatRequestBody);

function showJson(element, data) {
  element.textContent = JSON.stringify(data, null, 2);
}

function setBusy(button, busy, text) {
  if (!button.dataset.label) {
    button.dataset.label = button.textContent;
  }
  button.disabled = busy;
  button.textContent = busy ? text : button.dataset.label;
}

function buildDefaultRequestBody() {
  return {
    model: $("#modelName").value.trim(),
    messages: [
      {
        role: "user",
        content: currentPromptValue(),
      },
    ],
    temperature: 0.7,
    stream: false,
  };
}

function renderRequestBody(body) {
  $("#requestBody").value = JSON.stringify(body, null, 2);
  validateRequestBody();
}

function formatRequestBody() {
  try {
    const body = JSON.parse($("#requestBody").value);
    if (!body || Array.isArray(body) || typeof body !== "object") {
      throw new Error("请求体必须是 JSON object");
    }
    renderRequestBody(body);
    setRequestBodyStatus("请求体 JSON 已格式化。", false);
  } catch (error) {
    setRequestBodyStatus(`无法格式化：${error.message}`, true);
  }
}

function parseRequestBody() {
  try {
    if (!$("#requestBody")) {
      return null;
    }
    const body = JSON.parse($("#requestBody").value);
    if (!body || Array.isArray(body) || typeof body !== "object") {
      throw new Error("请求体必须是 JSON object");
    }
    setRequestBodyStatus("请求体 JSON 有效，会作为实际模型 API 请求体发送。", false);
    return body;
  } catch (error) {
    setRequestBodyStatus(`请求体 JSON 无效：${error.message}`, true);
    throw error;
  }
}

function validateRequestBody() {
  try {
    parseRequestBody();
    return true;
  } catch {
    return false;
  }
}

function syncRequestBody() {
  if (!$("#requestBody") || !$("#modelName")) {
    return;
  }

  let body;
  try {
    body = JSON.parse($("#requestBody").value || "{}");
  } catch {
    setRequestBodyStatus("请求体 JSON 无效，修正后才会继续同步 prompt。", true);
    return;
  }

  if (!body || Array.isArray(body) || typeof body !== "object") {
    body = {};
  }

  body.model = $("#modelName").value.trim();
  if (!Array.isArray(body.messages)) {
    body.messages = [];
  }

  let userMessage = [...body.messages].reverse().find((message) => message && message.role === "user");
  if (!userMessage) {
    userMessage = { role: "user", content: "" };
    body.messages.push(userMessage);
  }
  userMessage.content = currentPromptValue();
  renderRequestBody(body);
}

function setRequestBodyStatus(message, isError) {
  const status = $("#requestBodyStatus");
  status.textContent = message;
  status.classList.toggle("fail", isError);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

bindIfPresent("#runSingle", "click", async () => {
  const button = $("#runSingle");
  setBusy(button, true, "调用中...");
  try {
    const data = await postJson("/api/test", {
      ...modelConfig(),
      prompt: $("#singlePrompt").value,
    });
    showJson($("#singleResult"), data);
  } catch (error) {
    showJson($("#singleResult"), { error: error.message });
  } finally {
    setBusy(button, false);
  }
});

bindIfPresent("#uploadDataset", "click", async () => {
  const file = $("#datasetFile").files[0];
  if (!file) {
    $("#datasetInfo").textContent = "请选择 CSV、JSON、JSONL、XLSX 或 XLS 文件。";
    return;
  }

  lastBatchResults = [];
  if ($("#exportBatch")) {
    $("#exportBatch").disabled = true;
  }

  const button = $("#uploadDataset");
  const formData = new FormData();
  formData.append("file", file);
  setBusy(button, true, "解析中...");

  try {
    const response = await fetch("/api/datasets", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "upload failed");
    }
    currentDatasetName = data.dataset.stored_name;
    $("#runBatch").disabled = false;
    $("#datasetInfo").textContent = `已上传：${data.dataset.original_name}，共 ${data.count} 条。`;
    renderBatchPreview(data.preview);
  } catch (error) {
    $("#datasetInfo").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
});

bindIfPresent("#runBatch", "click", async () => {
  const button = $("#runBatch");
  setBusy(button, true, "测试中...");
  try {
    const data = await postJson("/api/batch-test", {
      ...modelConfig(),
      dataset_name: currentDatasetName,
    });
    lastBatchResults = data.results || [];
    if ($("#exportBatch")) {
      $("#exportBatch").disabled = lastBatchResults.length === 0;
    }
    renderBatchResults(data.results);
    $("#datasetInfo").textContent = `批量测试完成：成功 ${data.ok}，失败 ${data.failed}，总计 ${data.total}。`;
  } catch (error) {
    $("#datasetInfo").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
});

bindIfPresent("#exportBatch", "click", async () => {
  const button = $("#exportBatch");
  if (!lastBatchResults.length) {
    $("#datasetInfo").textContent = "没有可导出的批量测试结果。";
    return;
  }

  setBusy(button, true, "导出中...");
  try {
    const response = await fetch("/api/export-batch-results", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results: lastBatchResults }),
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "export failed");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filenameFromDisposition(response.headers.get("Content-Disposition")) || "batch_results.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    $("#datasetInfo").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
});

bindIfPresent("#runPressure", "click", async () => {
  const button = $("#runPressure");
  let progressStarted = false;
  setBusy(button, true, "压测中...");
  $("#pressureCards").innerHTML = "";
  $("#pressureResult").textContent = "";

  try {
    const pressureMode = $("#pressureMode")?.value || "requests";
    const concurrency = Number($("#concurrency").value);
    const totalRequests = Number($("#totalRequests")?.value);
    const durationSeconds = Number($("#durationSeconds")?.value);
    if (!Number.isInteger(concurrency) || concurrency < 1) {
      throw new Error("并发数必须是大于 0 的整数");
    }
    if (pressureMode === "requests" && (!Number.isInteger(totalRequests) || totalRequests < 1)) {
      throw new Error("总请求数必须是大于 0 的整数");
    }
    if (pressureMode === "duration" && (!Number.isInteger(durationSeconds) || durationSeconds < 1)) {
      throw new Error("持续时间必须是大于 0 的整数秒");
    }

    const requestPayload = {
      ...modelConfig(),
      prompt: $("#pressurePrompt").value,
      pressure_mode: pressureMode,
      concurrency,
      total_requests: totalRequests,
      duration_seconds: durationSeconds,
    };

    startPressureProgress({ mode: pressureMode, totalRequests, durationSeconds, concurrency });
    progressStarted = true;
    const data = await postJson("/api/pressure-test", requestPayload);
    completePressureProgress(data);
    renderPressureCards(data);
    showJson($("#pressureResult"), data);
  } catch (error) {
    if (progressStarted) {
      failPressureProgress(error.message);
    }
    showJson($("#pressureResult"), { error: error.message });
  } finally {
    setBusy(button, false);
  }
});

function renderBatchPreview(records) {
  renderRows(
    records.map((record) => ({
      id: record.id,
      prompt: record.prompt,
      output: record.expected || "",
      latency_ms: "",
      ok: true,
      status: "预览",
    })),
  );
}

function renderBatchResults(records) {
  renderRows(
    records.map((record) => ({
      id: record.id,
      prompt: record.prompt,
      output: record.output || record.error || "",
      latency_ms: record.latency_ms || "",
      ok: record.ok,
      status: record.ok ? "成功" : "失败",
    })),
  );
}

function renderRows(records) {
  const tbody = $("#batchTable tbody");
  tbody.innerHTML = "";
  records.forEach((record) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(record.id)}</td>
      <td>${escapeHtml(record.prompt)}</td>
      <td>${escapeHtml(record.output)}</td>
      <td>${escapeHtml(record.latency_ms)}</td>
      <td class="${record.ok ? "ok" : "fail"}">${escapeHtml(record.status)}</td>
    `;
    tbody.appendChild(row);
  });
}

function renderPressureCards(data) {
  const metrics = [
    ["总请求", data.total],
    ["成功率", `${data.ok}/${data.total}`],
    ["QPS", data.qps],
    ["P95 耗时", `${data.latency_ms.p95 || "-"} ms`],
  ];
  $("#pressureCards").innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function startPressureProgress({ mode, totalRequests, durationSeconds, concurrency }) {
  stopPressureProgressTimer();
  const progress = $("#pressureProgress");
  if (!progress) {
    return;
  }

  const fill = $("#pressureProgressFill");
  const title = $("#pressureProgressTitle");
  const percent = $("#pressureProgressPercent");
  const detail = $("#pressureProgressDetail");
  const startedAt = Date.now();
  let displayedPercent = 5;
  const targetText = mode === "duration" ? `持续 ${durationSeconds}s` : `总请求 ${totalRequests}`;

  progress.classList.remove("hidden", "progress-error", "progress-done");
  fill.style.width = `${displayedPercent}%`;
  title.textContent = "压测请求已提交";
  percent.textContent = `${displayedPercent}%`;
  detail.textContent = `并发 ${concurrency}，${targetText}，正在等待模型服务返回。`;

  pressureProgressTimer = window.setInterval(() => {
    const elapsedSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
    if (mode === "duration") {
      displayedPercent = Math.min(95, Math.max(5, (elapsedSeconds / durationSeconds) * 95));
    } else {
      displayedPercent = Math.min(92, displayedPercent + Math.max(1, (92 - displayedPercent) * 0.08));
    }
    const rounded = Math.round(displayedPercent);
    fill.style.width = `${rounded}%`;
    title.textContent = `压测运行中，已用时 ${elapsedSeconds}s`;
    percent.textContent = `${rounded}%`;
    detail.textContent = `并发 ${concurrency}，${targetText}。结果会在后端完成后展示。`;
  }, 700);
}

function completePressureProgress(data) {
  stopPressureProgressTimer();
  const progress = $("#pressureProgress");
  if (!progress) {
    return;
  }

  progress.classList.add("progress-done");
  $("#pressureProgressFill").style.width = "100%";
  $("#pressureProgressTitle").textContent = "压测完成";
  $("#pressureProgressPercent").textContent = "100%";
  $("#pressureProgressDetail").textContent = `成功 ${data.ok}，失败 ${data.failed}，耗时 ${data.duration_seconds}s。`;
}

function failPressureProgress(message) {
  stopPressureProgressTimer();
  const progress = $("#pressureProgress");
  if (!progress) {
    return;
  }

  progress.classList.add("progress-error");
  $("#pressureProgressTitle").textContent = "压测失败";
  $("#pressureProgressPercent").textContent = "--";
  $("#pressureProgressDetail").textContent = message;
}

function stopPressureProgressTimer() {
  if (pressureProgressTimer) {
    window.clearInterval(pressureProgressTimer);
    pressureProgressTimer = null;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function filenameFromDisposition(disposition) {
  if (!disposition) {
    return null;
  }
  const match = disposition.match(/filename="?([^"]+)"?/);
  return match ? match[1] : null;
}

function currentPromptValue() {
  if ($("#singlePrompt")) {
    return $("#singlePrompt").value;
  }
  if ($("#pressurePrompt")) {
    return $("#pressurePrompt").value;
  }
  return "{{prompt}}";
}

function togglePressureMode() {
  const modeInput = $("#pressureMode");
  if (!modeInput) {
    return;
  }
  modeInput.value = modeInput.value === "duration" ? "requests" : "duration";
  syncPressureModeFields();
}

function syncPressureModeFields() {
  const mode = $("#pressureMode")?.value || "requests";
  const isDuration = mode === "duration";
  $("#totalRequestsField")?.classList.toggle("hidden", isDuration);
  $("#durationSecondsField")?.classList.toggle("hidden", !isDuration);

  const toggle = $("#pressureModeToggle");
  if (toggle) {
    toggle.dataset.mode = mode;
    toggle.querySelector(".mode-toggle-current").textContent = isDuration ? "按持续时间" : "按总请求数";
    toggle.querySelector(".mode-toggle-next").textContent = isDuration ? "点击切换为按总请求数" : "点击切换为按持续时间";
  }
}

function bindIfPresent(selector, eventName, handler) {
  const element = $(selector);
  if (element) {
    element.addEventListener(eventName, handler);
  }
}

document.querySelectorAll('a[href^="/"]').forEach((link) => {
  link.addEventListener("click", () => {
    saveState();
    sessionStorage.setItem(RESTORE_KEY, "1");
  });
});

function getState() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveState(extra = {}) {
  if (isRestoringState) {
    return;
  }

  const state = {
    ...getState(),
    ...extra,
  };
  writeCurrentValue(state, "apiUrl", "#apiUrl");
  writeCurrentValue(state, "modelName", "#modelName");
  writeCurrentValue(state, "modelPreset", "#modelPreset");
  writeCurrentValue(state, "requestBody", "#requestBody");
  writeCurrentValue(state, "singlePrompt", "#singlePrompt");
  writeCurrentValue(state, "pressurePrompt", "#pressurePrompt");
  writeCurrentValue(state, "pressureMode", "#pressureMode");
  writeCurrentValue(state, "concurrency", "#concurrency");
  writeCurrentValue(state, "totalRequests", "#totalRequests");
  writeCurrentValue(state, "durationSeconds", "#durationSeconds");
  writeCurrentText(state, "datasetInfo", "#datasetInfo");
  if (currentDatasetName) {
    state.currentDatasetName = currentDatasetName;
  }

  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function writeCurrentValue(state, key, selector) {
  const element = $(selector);
  if (element) {
    state[key] = element.value;
  }
}

function writeCurrentText(state, key, selector) {
  const element = $(selector);
  if (element && element.textContent) {
    state[key] = element.textContent;
  }
}

function restoreState() {
  if (sessionStorage.getItem(RESTORE_KEY) !== "1") {
    return;
  }

  sessionStorage.removeItem(RESTORE_KEY);
  const state = getState();
  isRestoringState = true;

  setValueIfPresent("#apiUrl", state.apiUrl);
  setValueIfPresent("#modelName", state.modelName);
  setValueIfPresent("#modelPreset", state.modelPreset);
  setValueIfPresent("#singlePrompt", state.singlePrompt);
  setValueIfPresent("#pressurePrompt", state.pressurePrompt);
  setValueIfPresent("#pressureMode", state.pressureMode);
  setValueIfPresent("#concurrency", state.concurrency);
  setValueIfPresent("#totalRequests", state.totalRequests);
  setValueIfPresent("#durationSeconds", state.durationSeconds);
  setValueIfPresent("#requestBody", state.requestBody);

  currentDatasetName = state.currentDatasetName || null;
  if ($("#runBatch") && currentDatasetName) {
    $("#runBatch").disabled = false;
  }
  if ($("#datasetInfo") && state.datasetInfo) {
    $("#datasetInfo").textContent = state.datasetInfo;
  }

  isRestoringState = false;
}

function setValueIfPresent(selector, value) {
  const element = $(selector);
  if (element && value !== undefined && value !== null) {
    element.value = value;
  }
}

restoreState();
syncPressureModeFields();

if ($("#requestBody") && !$("#requestBody").value.trim()) {
  renderRequestBody(buildDefaultRequestBody());
} else if ($("#requestBody")) {
  validateRequestBody();
}
