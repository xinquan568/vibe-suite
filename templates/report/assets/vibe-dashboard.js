// SPDX-License-Identifier: ISC
// Corpus dashboard: stage counts, score distribution, and the vocabulary graph.
//
// The graph library is vendored (templates/report/vendor/) rather than fetched from a CDN:
// these pages are opened offline and from artifact downloads, and a CDN reference would render
// a blank panel with no indication why.
(function () {
  "use strict";
  var el = document.getElementById("dashboard-data");
  if (!el) { return; }
  var data;
  try { data = JSON.parse(el.textContent); } catch (e) { return; }

  var stages = (data && data.by_status) || {};
  var host = document.getElementById("stages");
  if (host) {
    ["discovered", "audited", "contributed", "tracked", "complete"].forEach(function (s) {
      var card = document.createElement("div");
      card.className = "card";
      card.innerHTML = '<div class="n">' + (stages[s] || 0) + '</div>' +
                       '<div class="k">' + s + "</div>";
      host.appendChild(card);
    });
  }

  // The graph is optional. When the vendored bundle is absent the panel says so rather than
  // leaving an empty box that reads as "no data".
  var graph = document.getElementById("graph");
  if (graph && typeof window.G6 === "undefined") {
    graph.textContent = "Graph unavailable: the vendored bundle did not load.";
  }
})();
