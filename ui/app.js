// Maison Grader UI: static pages that call the two services from the browser.
// The services speak integer mm; cm exists only here, in what the user types and reads.
// Routes live in the URL hash (#/styles/3), so any static host can serve this one page.

"use strict";

const CONFIG = window.MAISON_CONFIG;
const main = document.getElementById("main");

// ---- Talking to the services ----

// Generous on purpose: on Azure the first request after idle may wait for the
// container to start and the database to resume (up to about a minute).
const TIMEOUT_MS = 100000;

async function api(service, path, options = {}) {
  const request = { method: options.method || "GET", signal: AbortSignal.timeout(TIMEOUT_MS) };
  if (options.body !== undefined) {
    request.headers = { "Content-Type": "application/json" };
    request.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(CONFIG[service] + path, request);
  } catch (error) {
    throw new Error(`The ${service} service can't be reached right now. ` +
                    "If the app has been idle it may be starting up: try again in a minute.");
  }
  if (response.status === 204) return null;
  let body = null;
  try { body = await response.json(); } catch (error) { /* not JSON */ }
  if (!response.ok) throw new Error((body && body.error) || `${service} answered ${response.status}`);
  return body;
}

// ---- cm <-> mm, exact (no floating point), same rules as the old cm_to_mm ----

function cmToMm(text, field) {
  const match = /^(-?)(\d*)(?:\.(\d)0*)?$/.exec(String(text).trim());
  if (!match || (match[2] === "" && match[3] === undefined)) {
    throw new Error(`${field}: "${text}" is not a number in cm with at most one decimal (1 mm)`);
  }
  const mm = Number(match[2] || 0) * 10 + Number(match[3] || 0);
  return match[1] ? -mm : mm;
}

function cm(mm) {
  return mm === null || mm === undefined ? "—" : (mm / 10).toFixed(1);
}

// ---- Rendering helpers ----

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function errorBox(message = "") {
  return `<p class="error" role="alert">${esc(message)}</p>`;
}

function showError(form, error) {
  form.closest("section, main").querySelector(".error").textContent = error.message;
}

// Run an async submit handler with the button disabled and errors shown in the page.
function onSubmit(form, handler) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      await handler(new FormData(form));
    } catch (error) {
      showError(form, error);
    } finally {
      button.disabled = false;
    }
  });
}

// ---- Pages ----

async function stylesPage() {
  const styles = await api("specs", "/styles");
  main.innerHTML = `
    <h1>Styles</h1>
    ${errorBox()}
    ${styles.length ? `
      <div class="scroll"><table>
        <tr><th>Code</th><th>Name</th><th>Base size</th></tr>
        ${styles.map((s) => `
          <tr><td><a href="#/styles/${s.id}">${esc(s.code)}</a></td>
              <td class="text">${esc(s.name)}</td><td>${esc(s.base_size)}</td></tr>`).join("")}
      </table></div>` : `<p class="meta">No styles yet. Create the first one below.</p>`}
    <h2>New style</h2>
    <form class="inline" id="new-style">
      <label>Code <input name="code" required></label>
      <label>Name <input class="wide" name="name" required></label>
      <label>Sizes, smallest first <input class="wide" name="sizes" placeholder="XS, S, M, L, XL" required></label>
      <label>Base size <input name="base_size" placeholder="M" required></label>
      <button>Create style</button>
    </form>`;
  onSubmit(document.getElementById("new-style"), async (form) => {
    const created = await api("specs", "/styles", { method: "POST", body: {
      code: form.get("code"), name: form.get("name"), base_size: form.get("base_size"),
      sizes: form.get("sizes").split(",").map((s) => s.trim()).filter(Boolean),
    } });
    location.hash = `#/styles/${created.id}`;
  });
}

async function stylePage(styleId) {
  const { style, sizes, poms } = await api("specs", `/styles/${styleId}`);
  main.innerHTML = `
    <h1>${esc(style.code)} ${esc(style.name)}</h1>
    <p class="meta">Base size ${esc(style.base_size)}. All values in cm.</p>
    ${errorBox()}
    <h2>Size run</h2>
    ${poms.length ? `
      <div class="scroll"><table>
        <tr><th>Point of measure</th><th>Tol ±</th>
          ${sizes.map((s) => `<th class="${s === style.base_size ? "base" : ""}">${esc(s)}</th>`).join("")}</tr>
        ${poms.map((p) => `
          <tr><td>${esc(p.code)} ${esc(p.description)}</td><td>${cm(p.tolerance_mm)}</td>
            ${sizes.map((s) => `<td class="${p.size_run[s] === null ? "missing" : ""}">${cm(p.size_run[s])}</td>`).join("")}
          </tr>`).join("")}
      </table></div>
      <p class="meta">A dash means a grade rule between that size and the base is missing.</p>`
    : `<p class="meta">No points of measure yet. Add one below.</p>`}

    ${poms.length && sizes.length > 1 ? `
      <h2>Grade rules</h2>
      <p class="meta">Each value is how much larger that size is than the size just below it.</p>
      ${poms.map((p) => `
        <form class="inline rules" data-pom="${p.id}">
          <strong style="min-width: 10rem">${esc(p.code)}</strong>
          ${sizes.slice(1).map((s) => `
            <label>${esc(s)} <input name="${esc(s)}" inputmode="decimal"
              value="${p.rules[s] === undefined ? "" : cm(p.rules[s])}"></label>`).join("")}
          <button>Save rules</button>
        </form>`).join("")}` : ""}

    ${poms.length ? `
      <h2>Record sample round</h2>
      <form class="inline" id="new-round">
        <label>Sampled size <select name="size">
          ${sizes.map((s) => `<option ${s === style.base_size ? "selected" : ""}>${esc(s)}</option>`).join("")}
        </select></label>
        <button>Enter factory measurements</button>
      </form>` : ""}

    <h2>Add point of measure</h2>
    <form class="inline" id="new-pom">
      <label>Code <input name="code" required placeholder="CH"></label>
      <label>Description <input class="wide" name="description" required placeholder="Chest, 1 cm below armhole"></label>
      <label>At ${esc(style.base_size)} (cm) <input name="base" inputmode="decimal" required></label>
      <label>Tolerance ± (cm) <input name="tolerance" inputmode="decimal" required></label>
      <button>Add point of measure</button>
    </form>

    <h2>Delete style</h2>
    <form id="delete-style">
      <p class="meta">Removes its sizes, points of measure and grade rules. Sample rounds already recorded keep their own copy of the spec.</p>
      <button class="danger">Delete ${esc(style.code)}</button>
    </form>`;

  main.querySelectorAll("form.rules").forEach((form) => onSubmit(form, async (data) => {
    // Convert every field before sending any, so one bad cell saves nothing.
    const increments = {};
    for (const [size, value] of data.entries()) {
      if (value.trim()) increments[size] = cmToMm(value, size);
    }
    await api("specs", `/styles/${styleId}/poms/${form.dataset.pom}/rules`,
              { method: "PUT", body: { increments_mm: increments } });
    await stylePage(styleId);
  }));
  const newRound = document.getElementById("new-round");
  if (newRound) {
    newRound.addEventListener("submit", (event) => {
      event.preventDefault();
      const size = new FormData(newRound).get("size");
      location.hash = `#/rounds/new?style=${styleId}&size=${encodeURIComponent(size)}`;
    });
  }
  onSubmit(document.getElementById("new-pom"), async (data) => {
    await api("specs", `/styles/${styleId}/poms`, { method: "POST", body: {
      code: data.get("code"), description: data.get("description"),
      base_value_mm: cmToMm(data.get("base"), "Base value"),
      tolerance_mm: cmToMm(data.get("tolerance"), "Tolerance"),
    } });
    await stylePage(styleId);
  });
  onSubmit(document.getElementById("delete-style"), async () => {
    if (!window.confirm(`Delete ${style.code}?`)) return;
    await api("specs", `/styles/${styleId}`, { method: "DELETE" });
    location.hash = "#/styles";
  });
}

async function roundsPage() {
  const rounds = await api("samples", "/rounds");
  main.innerHTML = `
    <h1>Sample rounds</h1>
    <p class="meta">To record a new round, open a style and pick the size the factory sampled.</p>
    ${rounds.length ? `
      <div class="scroll"><table>
        <tr><th>Round</th><th>Style</th><th>Size</th><th>Stage</th><th>Factory</th><th>Recorded (UTC)</th>
            <th>Out of tolerance</th><th>Result</th></tr>
        ${rounds.map((r) => `
          <tr><td><a href="#/rounds/${r.id}">#${r.id}</a></td>
            <td class="text">${esc(r.style_code)}</td><td class="text">${esc(r.size_label)}</td>
            <td class="text">${esc(r.stage)}</td><td class="text">${esc(r.factory)}</td>
            <td class="text">${esc(r.recorded_at)}</td>
            <td>${r.summary.failed} / ${r.summary.total}</td>
            <td class="text">${r.summary.approved ? "Approved" : "Rejected"}</td></tr>`).join("")}
      </table></div>` : `<p class="meta">No sample rounds recorded yet.</p>`}`;
}

// Client-side call to specs for the form; the server-side call happens on submit.
async function newRoundPage(params) {
  const styleId = Number(params.get("style"));
  const size = params.get("size") || "";
  const spec = await api("specs", `/styles/${styleId}/spec/${encodeURIComponent(size)}`);
  main.innerHTML = `
    <h1>New sample round: ${esc(spec.style_code)}, size ${esc(size)}</h1>
    <p class="meta">Enter every measurement from the factory sample, in cm. A round is saved only if every point of measure has a value.</p>
    ${errorBox()}
    <form id="record">
      <div class="inline">
        <label>Stage <select name="stage" required>
          <option>proto</option><option>fit</option><option>pre-production</option>
        </select></label>
        <label>Factory <input class="wide" name="factory" maxlength="100" placeholder="Leave empty if unknown"></label>
      </div>
      <div class="scroll"><table>
        <tr><th>Point of measure</th><th>Spec</th><th>Tol ±</th><th>Measured (cm)</th></tr>
        ${spec.poms.map((p) => `
          <tr><td>${esc(p.code)} ${esc(p.description)}</td><td>${cm(p.target_mm)}</td>
            <td>${cm(p.tolerance_mm)}</td>
            <td><input name="${esc(p.code)}" inputmode="decimal" required></td></tr>`).join("")}
      </table></div>
      <p><button>Record round</button></p>
    </form>`;
  onSubmit(document.getElementById("record"), async (data) => {
    const measured = {};
    for (const p of spec.poms) measured[p.code] = cmToMm(data.get(p.code), p.code);
    const created = await api("samples", "/rounds", { method: "POST", body: {
      style_id: styleId, size, stage: data.get("stage"), factory: data.get("factory"),
      measured_mm: measured,
    } });
    location.hash = `#/rounds/${created.id}`;
  });
}

async function roundPage(roundId) {
  const { round, measurements, summary } = await api("samples", `/rounds/${roundId}`);
  main.innerHTML = `
    <h1>Round #${round.id}: ${esc(round.style_code)}, size ${esc(round.size_label)}</h1>
    <p class="meta">Stage ${esc(round.stage)}, factory ${esc(round.factory)}, recorded ${esc(round.recorded_at)}. Spec values are the copy taken when the round was recorded. All values in cm.</p>
    <h2>${summary.approved ? "Approved" : "Rejected"}: ${summary.failed} of ${summary.total} out of tolerance</h2>
    ${summary.failed_codes.length ? `<p class="meta">Out of tolerance: ${summary.failed_codes.map(esc).join(", ")}</p>` : ""}
    <div class="scroll"><table>
      <tr><th>Point of measure</th><th>Spec</th><th>Tol ±</th><th>Measured</th><th>Deviation</th><th>Result</th></tr>
      ${measurements.map((m) => `
        <tr><td>${esc(m.pom_code)} ${esc(m.description)}</td><td>${cm(m.target_mm)}</td>
          <td>${cm(m.tolerance_mm)}</td><td>${cm(m.measured_mm)}</td>
          <td>${m.deviation_mm > 0 ? "+" : ""}${cm(m.deviation_mm)}</td>
          <td class="text ${m.passes ? "" : "fail"}">${m.passes ? "Pass" : "Fail"}</td></tr>`).join("")}
    </table></div>
    <p><a href="#/rounds">All sample rounds</a></p>`;
}

// ---- Router ----

async function route() {
  const [path, query] = (location.hash.slice(1) || "/styles").split("?");
  const params = new URLSearchParams(query);
  let match;
  try {
    if (path === "/styles") await stylesPage();
    else if ((match = /^\/styles\/(\d+)$/.exec(path))) await stylePage(Number(match[1]));
    else if (path === "/rounds") await roundsPage();
    else if (path === "/rounds/new") await newRoundPage(params);
    else if ((match = /^\/rounds\/(\d+)$/.exec(path))) await roundPage(Number(match[1]));
    else main.innerHTML = `<h1>Not found</h1><p><a href="#/styles">Styles</a></p>`;
  } catch (error) {
    // One service down only breaks the pages that need it; the nav still works.
    main.innerHTML = `<h1>Can't show this page</h1>${errorBox(error.message)}`;
  }
}

window.addEventListener("hashchange", route);
route();
