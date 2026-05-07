/**
 * Parameter inputs from parameters.json (no ES imports — runs even if Three.js CDN fails).
 */
(function () {
  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el || !el.textContent) return {};
    try {
      return JSON.parse(el.textContent);
    } catch {
      return {};
    }
  }

  var form = document.querySelector("form[action='/download-model-stl']");
  var modelSelect = document.getElementById("model_name");
  var paramFieldsEl = document.getElementById("param-fields");
  var paramHintEl = document.getElementById("paramHint");

  if (!form || !paramFieldsEl || !paramHintEl) return;

  var parameterSchemas = readJsonScript("parameter-schemas");
  var initialParamValues = readJsonScript("initial-param-values");

  function schemaForModel(modelName) {
    if (!modelName) return [];
    var s = parameterSchemas[modelName];
    return Array.isArray(s) ? s : [];
  }

  function currentInputValues() {
    var out = {};
    form.querySelectorAll("[data-param-cell]").forEach(function (input) {
      var cell = input.getAttribute("data-param-cell");
      if (cell) out[cell] = input.value;
    });
    return out;
  }

  function buildParameterFields() {
    var modelName = (modelSelect && modelSelect.value) || "";
    var preserved = currentInputValues();
    paramFieldsEl.innerHTML = "";

    if (!modelName) {
      paramHintEl.textContent =
        "Select a model to enter parameters from its parameters.json.";
      return;
    }

    var schema = schemaForModel(modelName);
    if (!schema.length) {
      paramHintEl.textContent =
        'This folder has no parameters.json (or it is empty). Add one, e.g. [["Length = A1", "Width = A2", "Height = A3"]].';
      return;
    }

    paramHintEl.textContent =
      'Enter values for each spreadsheet cell defined in parameters.json (e.g. "Length = A1").';

    var heading = document.createElement("h3");
    heading.className = "param-fields-heading";
    heading.textContent = "Parameters";
    paramFieldsEl.appendChild(heading);

    var grid = document.createElement("div");
    grid.className = "grid param-fields-grid";

    for (var i = 0; i < schema.length; i++) {
      var entry = schema[i];
      var cell = entry.cell;
      var label = entry.label;
      var id = "param_" + cell;

      var labelEl = document.createElement("label");
      labelEl.setAttribute("for", id);
      labelEl.textContent = label + " → " + cell + " (mm)";

      var input = document.createElement("input");
      input.id = id;
      input.name = "param_" + cell;
      input.type = "text";
      input.inputMode = "decimal";
      input.autocomplete = "off";
      input.placeholder = "e.g. 50";
      input.dataset.paramCell = cell;
      input.className = "param-input";

      var val =
        (preserved[cell] !== undefined && preserved[cell] !== "") ? preserved[cell] : (initialParamValues[cell] || "");
      if (val !== "") input.value = String(val);

      var wrap = document.createElement("div");
      wrap.className = "param-field";
      wrap.appendChild(labelEl);
      wrap.appendChild(input);
      grid.appendChild(wrap);
    }

    paramFieldsEl.appendChild(grid);
  }

  function init() {
    if (modelSelect) {
      modelSelect.addEventListener("change", buildParameterFields);
    }

    var initialModel = paramFieldsEl.getAttribute("data-initial-model") || "";
    var currentModel = (modelSelect && modelSelect.value) || "";
    var serverRendered = !!paramFieldsEl.querySelector("input[data-param-cell]");

    if (initialModel && currentModel === initialModel && serverRendered) {
      paramHintEl.textContent =
        'Enter values for each spreadsheet cell defined in parameters.json (e.g. "Length = A1").';
      return;
    }

    buildParameterFields();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
