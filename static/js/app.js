// Tender Monitor UI helpers (no external dependencies).

function initPortalForm() {
  const sched = document.getElementById("schedule-type");
  const dow = document.getElementById("dow-label");
  function toggleDow() {
    if (dow) dow.style.display = (sched && sched.value === "weekly") ? "" : "none";
  }
  if (sched) { sched.addEventListener("change", toggleDow); toggleDow(); }

  const btn = document.getElementById("test-portal-btn");
  const out = document.getElementById("test-result");
  if (!btn) return;
  btn.addEventListener("click", async function () {
    const urlEl = document.getElementById("portal-url");
    const url = urlEl ? urlEl.value.trim() : "";
    if (!url) { out.hidden = false; out.innerHTML = "<p class='err'>Enter a website URL first.</p>"; return; }
    const modeEl = document.querySelector("[name=browser_mode]");
    const mode = modeEl ? modeEl.value : "headless";
    btn.disabled = true; btn.textContent = "Testing...";
    out.hidden = false; out.innerHTML = "<p>Testing portal, please wait (this launches a browser)...</p>";
    try {
      const fd = new FormData();
      fd.append("url", url);
      fd.append("browser_mode", mode);
      const resp = await fetch("/api/test-portal", { method: "POST", body: fd });
      const data = await resp.json();
      out.innerHTML = renderTestResult(data);
    } catch (e) {
      out.innerHTML = "<p class='err'>Test failed: " + e + "</p>";
    }
    btn.disabled = false; btn.textContent = "Test Portal";
  });
}

function renderTestResult(d) {
  const checks = d.checks || [];
  const rows = checks.map(function (c) {
    const cls = "st-" + String(c.status).replace(/ /g, "-").toLowerCase();
    return "<tr><td>" + c.name + "</td><td class='" + cls + "'>" + c.status +
           "</td><td>" + (c.detail || "") + "</td></tr>";
  }).join("");
  let html = "<h3>Portal Test Result</h3>";
  html += "<p>Automation Readiness: <strong>" + (d.readiness || "?") + "</strong></p>";
  if (d.error) html += "<p class='err'>" + d.error + "</p>";
  html += "<table class='tbl'><thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead><tbody>" +
          rows + "</tbody></table>";
  return html;
}

async function pollStatus() {
  try {
    const resp = await fetch("/api/status");
    const d = await resp.json();
    const pill = document.getElementById("scan-pill");
    if (pill && d.scan) {
      const busy = d.scan.running;
      pill.textContent = busy ? ("Scanning " + (d.scan.current || "")) : "Idle";
      pill.className = "pill " + (busy ? "busy" : "idle");
    }
  } catch (e) { /* ignore transient errors */ }
}

document.addEventListener("DOMContentLoaded", function () {
  pollStatus();
  setInterval(pollStatus, 5000);
});
