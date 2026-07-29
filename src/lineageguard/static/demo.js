"use strict";

const SCENARIO_ID = "drop-orders-order-total";
const state = { accessKey: "" };
const snapshotMode = document.body.dataset.demoMode === "snapshot";
const idleButtonLabel = snapshotMode ? "Inspect verified evidence" : "Run impact review";

const elements = {
  run: document.querySelector("#run-review"),
  runLabel: document.querySelector("#run-review span"),
  freshness: document.querySelector("#result-freshness"),
  empty: document.querySelector("#empty-state"),
  loading: document.querySelector("#loading-state"),
  error: document.querySelector("#error-state"),
  errorTitle: document.querySelector("#error-title"),
  errorMessage: document.querySelector("#error-message"),
  retry: document.querySelector("#retry-review"),
  keyForm: document.querySelector("#access-key-form"),
  keyInput: document.querySelector("#access-key"),
  result: document.querySelector("#result-state"),
  verdict: document.querySelector("#verdict"),
  severity: document.querySelector("#severity"),
  downstream: document.querySelector("#downstream-total"),
  complete: document.querySelector("#lineage-complete"),
  summary: document.querySelector("#decision-summary"),
  assets: document.querySelector("#lineage-assets"),
  more: document.querySelector("#more-assets"),
  owners: document.querySelector("#owners-detail"),
  migration: document.querySelector("#migration-detail"),
  query: document.querySelector("#query-detail"),
  latency: document.querySelector("#latency"),
};

function showState(name) {
  elements.empty.hidden = name !== "empty";
  elements.loading.hidden = name !== "loading";
  elements.error.hidden = name !== "error";
  elements.result.hidden = name !== "result";
}

function prettyPlatform(platform) {
  const names = { dbt: "dbt model", looker: "Looker", powerbi: "Power BI", snowflake: "Snowflake", tableau: "Tableau" };
  return names[String(platform).toLowerCase()] || platform || "DataHub asset";
}

function selectRepresentativeAssets(assets) {
  const selected = [];
  const seenPlatforms = new Set();
  for (const asset of assets) {
    const platform = String(asset.platform || "unknown").toLowerCase();
    if (!seenPlatforms.has(platform)) {
      selected.push(asset);
      seenPlatforms.add(platform);
    }
    if (selected.length === 3) break;
  }
  for (const asset of assets) {
    if (selected.length === 3) break;
    if (!selected.includes(asset)) selected.push(asset);
  }
  return selected;
}

function actionByKind(actions, kind) {
  return actions.find((action) => action.kind === kind);
}

function renderResult(payload) {
  const artifact = payload.artifact;
  const evidence = artifact.evidence;
  elements.verdict.textContent = String(payload.verdict).toUpperCase();
  elements.severity.textContent = String(payload.severity).toUpperCase();
  elements.downstream.textContent = String(evidence.downstream_total);
  elements.complete.textContent = evidence.lineage_complete ? "Lineage complete" : "Lineage incomplete";
  elements.summary.textContent = artifact.summary;

  const representative = selectRepresentativeAssets(artifact.impacted_assets);
  elements.assets.replaceChildren(...representative.map((asset) => {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    const detail = document.createElement("span");
    name.textContent = asset.name;
    detail.textContent = `${prettyPlatform(asset.platform)} · degree ${asset.degree}`;
    item.append(name, detail);
    return item;
  }));
  const remaining = Math.max(0, evidence.downstream_total - representative.length);
  elements.more.textContent = `+${remaining} more`;
  elements.more.hidden = remaining === 0;

  const notify = actionByKind(artifact.required_actions, "notify_owners");
  const migrate = actionByKind(artifact.required_actions, "migrate_dependents");
  const validate = actionByKind(artifact.required_actions, "run_validation");
  elements.owners.textContent = notify ? `${notify.owner_urns.length} accountable owners` : "Owner routing required";
  elements.migration.textContent = migrate ? `${migrate.asset_urns.length} impacted assets` : "Compatibility work required";
  elements.query.textContent = validate ? `${artifact.validation_queries.length} read-only query` : "Validation required";
  elements.latency.textContent = payload.result_meta || `${Number(payload.latency_ms).toFixed(0)} ms · ${payload.request_id.slice(0, 8)}`;
  elements.freshness.textContent = payload.result_freshness || "Live result";
  showState("result");
}

function errorCopy(status, code) {
  if (status === 401) return ["Access key required", "Enter the demo access key to run this review."];
  if (status === 429) return ["Review limit reached", "Wait a minute before running the fixed scenario again."];
  if (status === 504) return ["DataHub took too long", "The request timed out without returning a partial decision."];
  if (status === 502) return ["Artifact rejected", "The generated decision did not pass deterministic validation."];
  if (code === "server_busy") return ["Review already running", "The demo is at capacity. Try again in a moment."];
  return ["DataHub unavailable", "The review could not reach the upstream metadata graph. Try again shortly."];
}

function renderError(status, body = {}) {
  const [title, message] = snapshotMode
    ? ["Evidence unavailable", "The committed verification snapshot could not be loaded. Try again shortly."]
    : errorCopy(status, body.error);
  elements.errorTitle.textContent = title;
  elements.errorMessage.textContent = message;
  elements.keyForm.hidden = snapshotMode || status !== 401;
  elements.retry.hidden = !snapshotMode && status === 401;
  elements.freshness.textContent = "No decision returned";
  showState("error");
  if (!snapshotMode && status === 401) elements.keyInput.focus();
}

async function runReview() {
  showState("loading");
  elements.run.disabled = true;
  elements.run.setAttribute("aria-busy", "true");
  elements.runLabel.textContent = snapshotMode ? "Loading verified evidence…" : "Tracing DataHub lineage…";
  elements.freshness.textContent = "Review in progress";
  const headers = { "Content-Type": "application/json" };
  if (state.accessKey) headers.Authorization = `Bearer ${state.accessKey}`;

  try {
    const response = snapshotMode
      ? await fetch("snapshot.json", { cache: "no-store", headers: { Accept: "application/json" } })
      : await fetch("/api/review", {
          method: "POST",
          headers,
          body: JSON.stringify({ scenario_id: SCENARIO_ID }),
        });
    let body = {};
    try { body = await response.json(); } catch (_) { body = {}; }
    if (!response.ok) {
      renderError(response.status, body);
      return;
    }
    renderResult(body);
  } catch (_) {
    renderError(0);
  } finally {
    elements.run.disabled = false;
    elements.run.removeAttribute("aria-busy");
    elements.runLabel.textContent = idleButtonLabel;
  }
}

elements.run.addEventListener("click", runReview);
elements.retry.addEventListener("click", runReview);
elements.keyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.accessKey = elements.keyInput.value;
  elements.keyInput.value = "";
  runReview();
});
