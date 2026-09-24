/* Progressive enhancement for the OQ index and the roadmap. Both source tables
 * remain readable if JavaScript is unavailable. */
(function () {
  "use strict";

  const OQ_STATUS = {
    "offen": "open",
    "in arbeit": "progress",
    "teilweise geklärt": "partial",
    "weitgehend geklärt": "partial",
    "geklärt": "resolved",
    "beantwortet": "resolved",
    "verworfen": "discarded",
  };

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function enhanceQuestions(article) {
    if (!article.querySelector("#oq-01")) return;
    const table = article.querySelector("table");
    if (!table || table.dataset.enhanced === "true") return;
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    if (!rows.length || rows.some((row) => row.cells.length !== 4)) return;

    table.id = "oq-index";
    table.dataset.enhanced = "true";
    const controls = make("div", "oq-controls");
    const filters = make("div", "oq-filters");
    filters.setAttribute("role", "group");
    filters.setAttribute("aria-label", "OQ-Status");
    const input = make("input", "oq-search");
    input.type = "search";
    input.setAttribute("aria-label", "OQ suchen");
    input.placeholder = "Nummer oder Titel suchen";
    const count = make("output", "oq-count");
    count.setAttribute("aria-live", "polite");

    const choices = [
      ["Alle", "all"], ["Jetzt", "focus"], ["Offen", "open"],
      ["In Arbeit", "progress"], ["Teilweise", "partial"],
      ["Geklärt", "resolved"], ["Verworfen", "discarded"],
    ];
    let selected = "all";
    const buttons = [];
    for (const [label, value] of choices) {
      const button = make("button", "oq-filter", label);
      button.type = "button";
      button.setAttribute("aria-pressed", value === selected ? "true" : "false");
      button.addEventListener("click", () => {
        selected = value;
        buttons.forEach(([other, key]) => other.setAttribute("aria-pressed", key === selected ? "true" : "false"));
        update();
      });
      buttons.push([button, value]);
      filters.append(button);
    }

    for (const row of rows) {
      const cell = row.cells[2];
      const label = cell.textContent.trim();
      const category = OQ_STATUS[label.toLocaleLowerCase("de")];
      if (!category) return;
      row.dataset.status = category;
      row.dataset.focus = row.cells[1].textContent.trim() === "Jetzt" ? "true" : "false";
      row.dataset.search = `${row.cells[0].textContent} ${row.cells[3].textContent}`.toLocaleLowerCase("de");
      const badge = make("span", `oq-badge oq-badge--${category}`, label);
      cell.replaceChildren(badge);
    }

    function update() {
      const query = input.value.trim().toLocaleLowerCase("de");
      let visible = 0;
      for (const row of rows) {
        const matchesStatus = selected === "all" || (selected === "focus" ? row.dataset.focus === "true" : row.dataset.status === selected);
        row.hidden = !(matchesStatus && row.dataset.search.includes(query));
        if (!row.hidden) visible += 1;
      }
      count.textContent = `${visible} von ${rows.length} Fragen`;
    }

    input.addEventListener("input", update);
    controls.append(filters, input, count);
    table.before(controls);
    update();
  }

  function appendOqLinks(parent, value) {
    let last = 0;
    for (const match of value.matchAll(/\bOQ-\d+\b/g)) {
      parent.append(document.createTextNode(value.slice(last, match.index)));
      const link = make("a", "", match[0]);
      link.href = `open-questions.html#oq-${match[0].slice(3)}`;
      parent.append(link);
      last = match.index + match[0].length;
    }
    parent.append(document.createTextNode(value.slice(last)));
  }

  function enhanceRoadmap(article) {
    if (!article.querySelector("h1#roadmap")) return;
    const table = article.querySelector("table");
    if (!table || table.dataset.enhanced === "true") return;
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    if (rows.length !== 9 || rows.some((row, i) => row.cells.length !== 6 || row.cells[0].textContent.trim() !== `P${i}`)) return;

    const list = make("ol", "roadmap-list");
    list.dataset.roadmap = "";
    for (const row of rows) {
      const cells = row.cells;
      const phase = cells[0].textContent.trim();
      const goal = cells[1].textContent.trim();
      const status = cells[5].textContent.trim();
      const state = status.match(/\b(erreicht|teilweise|blockiert|offen)\b/i);
      if (!state) return;
      const kind = state[1].toLocaleLowerCase("de") === "erreicht" ? "done" :
        state[1].toLocaleLowerCase("de") === "teilweise" ? "partial" :
        state[1].toLocaleLowerCase("de") === "blockiert" ? "blocked" : "open";
      const item = make("li", "roadmap-item");
      const details = make("details", `roadmap-phase roadmap-phase--${kind}`);
      const summary = make("summary", "roadmap-summary");
      summary.append(make("strong", "roadmap-number", phase), make("span", "roadmap-goal", goal));
      summary.append(make("span", `roadmap-state roadmap-state--${kind}`, kind === "done" ? "erreicht" : kind === "partial" ? "teilweise" : kind === "blocked" ? "blockiert" : phase === "P8" ? "optional" : "offen"));
      summary.append(make("span", "roadmap-chevron", "›"));
      details.append(summary);
      const body = make("div", "roadmap-detail");
      const exit = make("p", "", `Exit-Kriterium: ${cells[4].textContent.trim()}`);
      const requirements = make("p", "", `Kamera: ${cells[2].textContent.trim()} · GSVmulti-Spezifikation: ${cells[3].textContent.trim()}`);
      const note = make("p", "roadmap-note");
      appendOqLinks(note, status);
      body.append(exit, requirements, note);
      details.append(body);
      item.append(details);
      list.append(item);
    }
    table.id = "roadmap-phases";
    table.dataset.enhanced = "true";
    table.before(list);
    table.hidden = true;
  }

  function enhance() {
    const article = document.querySelector(".md-content__inner");
    if (!article) return;
    enhanceQuestions(article);
    enhanceRoadmap(article);
  }

  if (typeof document$ !== "undefined") document$.subscribe(enhance);
  else document.addEventListener("DOMContentLoaded", enhance);
})();
