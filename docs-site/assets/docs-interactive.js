/* Progressive enhancement for the OQ index. The source table remains readable
 * if JavaScript is unavailable. The roadmap has its own spatial controller. */
(function () {
  "use strict";

  const OQ_STATUS = window.wiki.OQ_STATUS;

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

  function enhance() {
    const article = document.querySelector(".md-content__inner");
    if (!article) return;
    enhanceQuestions(article);
  }

  if (typeof document$ !== "undefined") document$.subscribe(enhance);
  else document.addEventListener("DOMContentLoaded", enhance);
})();
