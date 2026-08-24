// SPDX-License-Identifier: ISC
// Per-repository audit report. Reads the JSON the renderer inlined and builds the tables.
//
// The data arrives inlined rather than fetched: reports are opened from disk and from artifact
// downloads as often as from a server, and a fetch would silently render an empty page there.
(function () {
  "use strict";
  var el = document.getElementById("audit-data");
  if (!el) { return; }
  var data;
  try { data = JSON.parse(el.textContent); } catch (e) {
    document.getElementById("findings").textContent = "Report data could not be parsed.";
    return;
  }
  var findings = (data && data.findings) || [];
  var host = document.getElementById("findings");
  if (!host) { return; }
  if (!findings.length) {
    host.textContent = "No findings recorded for this audit.";
    return;
  }
  var order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
  findings.slice().sort(function (a, b) {
    var d = (order[a.severity] ?? 9) - (order[b.severity] ?? 9);
    return d !== 0 ? d : String(a.file || "").localeCompare(String(b.file || ""));
  }).forEach(function (f) {
    // Every field originates in a third-party audited repository: text nodes only,
    // never HTML parsing (vibe-195 / grill H3).
    var row = document.createElement("tr");
    var sevCell = document.createElement("td");
    var sev = document.createElement("span");
    sev.className = "sev sev-" + String(f.severity || "info");
    sev.textContent = String(f.severity || "info");
    sevCell.appendChild(sev);
    row.appendChild(sevCell);
    var ruleCell = document.createElement("td");
    var rule = document.createElement("code");
    rule.textContent = String(f.rule_id || "");
    ruleCell.appendChild(rule);
    row.appendChild(ruleCell);
    var fileCell = document.createElement("td");
    var file = document.createElement("code");
    file.textContent = String(f.file || "") + (f.line == null ? "" : ":" + f.line);
    fileCell.appendChild(file);
    row.appendChild(fileCell);
    var summaryCell = document.createElement("td");
    summaryCell.textContent = String(f.summary || "");
    row.appendChild(summaryCell);
    host.appendChild(row);
  });
})();
