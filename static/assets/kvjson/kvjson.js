(function () {
  function parseValue(text) {
    // try JSON first (numbers, arrays, objects, booleans)
    if (text === "") return "";
    try {
      return JSON.parse(text);
    } catch (e) {
      // fallback to string
      return text;
    }
  }

  function toDisplay(val) {
    if (typeof val === "string") return val;
    try { return JSON.stringify(val); } catch(e) { return String(val); }
  }

  function buildRow(key, val) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input class="kvjson-input kvjson-key" placeholder="key" value="${key || ""}"></td>
      <td><input class="kvjson-input kvjson-val" placeholder='value or JSON' value="${toDisplay(val) || ""}"></td>
      <td><button type="button" class="kvjson-row-remove">×</button></td>
    `;
    return tr;
  }

  function syncHidden(div) {
    const hidden = div.querySelector('input[type="hidden"]');
    const rows = div.querySelectorAll(".kvjson-rows tr");
    const data = {};
    rows.forEach(r => {
      const key = r.querySelector(".kvjson-key").value.trim();
      const valRaw = r.querySelector(".kvjson-val").value;
      if (!key) return;
      if (data.hasOwnProperty(key)) return; // ignore duplicates
      data[key] = parseValue(valRaw);
    });
    hidden.value = JSON.stringify(data);
  }

  function loadInitial(div) {
    const hidden = div.querySelector('input[type="hidden"]');
    let data = {};
    try { data = JSON.parse(hidden.value || "{}"); } catch(e) {}
    const tbody = div.querySelector(".kvjson-rows");
    tbody.innerHTML = "";
    Object.keys(data).forEach(k => tbody.appendChild(buildRow(k, data[k])));
  }

  function addRow(div, key="", val="") {
    const tbody = div.querySelector(".kvjson-rows");
    tbody.appendChild(buildRow(key, val));
    syncHidden(div);
  }

  function onChange(div, e) {
    if (e.target.closest(".kvjson-key") || e.target.closest(".kvjson-val")) {
      syncHidden(div);
    }
  }

  function onClick(div, e) {
    if (e.target.classList.contains("kvjson-row-remove")) {
      e.preventDefault();
      const tr = e.target.closest("tr");
      tr.parentNode.removeChild(tr);
      syncHidden(div);
    }
    if (e.target.classList.contains("kvjson-add")) {
      e.preventDefault();
      addRow(div);
    }
  }

  function init(div) {
    loadInitial(div);
    div.addEventListener("input", e => onChange(div, e));
    div.addEventListener("click", e => onClick(div, e));
    // ensure sync before submit
    const form = div.closest("form");
    if (form && !form.dataset.kvjsonBound) {
      form.dataset.kvjsonBound = "1";
      form.addEventListener("submit", () => {
        document.querySelectorAll(".kvjson-widget").forEach(syncHidden);
      });
    }
    // if empty, start with one row
    if (!div.querySelector(".kvjson-rows tr")) addRow(div);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-kvjson]").forEach(init);
  });
})();
