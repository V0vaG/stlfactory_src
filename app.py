from __future__ import annotations

import json
import re
from pathlib import Path
import shutil
import subprocess

from flask import Flask, jsonify, render_template, request, send_file

PROJECT_ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
MODELS_DIR = PROJECT_ROOT / "models"
EXPORT_FCSTD_SCRIPT = PROJECT_ROOT / "export_fcstd.py"
PARAMETERS_FILENAME = "parameters.json"

DEFAULT_PARAMETER_SCHEMA: list[dict[str, str]] = [
    {"label": "Length", "cell": "A1"},
    {"label": "Width", "cell": "A2"},
    {"label": "Height", "cell": "A3"},
]

CELL_RE = re.compile(r"^[A-Z]+\d+$")


def _parse_label_cell_string(s: str) -> dict[str, str] | None:
    """Parse one token like 'Length = A1' into label + spreadsheet cell."""
    if "=" not in s:
        return None
    label_part, cell_part = s.split("=", 1)
    label = label_part.strip()
    cell_u = cell_part.strip().upper()
    if not label or not CELL_RE.match(cell_u):
        return None
    return {"label": label, "cell": cell_u}


def _list_models() -> list[str]:
    if not MODELS_DIR.exists():
        return []
    return sorted(
        [
            entry.name
            for entry in MODELS_DIR.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ],
        key=str.lower,
    )


def _normalize_parameter_schema(data: object) -> list[dict[str, str]]:
    """Accepts:
    - [{"label": "…", "cell": "A1"}, …]
    - [["Length = A1", "Width = A2", …]]  or  ["Length = A1", …]
    - [["Length", "Width"]]  -> A1, A2, … (legacy)
    """
    if not isinstance(data, list) or not data:
        return list(DEFAULT_PARAMETER_SCHEMA)

    first = data[0]
    if isinstance(first, dict):
        out: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            cell = item.get("cell")
            if label is not None and cell is not None:
                cell_u = str(cell).strip().upper()
                if CELL_RE.match(cell_u):
                    out.append({"label": str(label).strip(), "cell": cell_u})
        return out if out else list(DEFAULT_PARAMETER_SCHEMA)

    def row_from_strings(tokens: list[str]) -> list[dict[str, str]]:
        parsed_row: list[dict[str, str]] = []
        auto_i = 0
        for token in tokens:
            raw = str(token).strip()
            p = _parse_label_cell_string(raw)
            if p is not None:
                parsed_row.append(p)
                continue
            if raw:
                parsed_row.append({"label": raw, "cell": f"A{auto_i + 1}"})
                auto_i += 1
        return parsed_row

    if isinstance(first, list):
        row = [str(x) for x in first]
        out = row_from_strings(row)
        return out if out else list(DEFAULT_PARAMETER_SCHEMA)

    if isinstance(first, str):
        row = [str(x) for x in data]
        out = row_from_strings(row)
        return out if out else list(DEFAULT_PARAMETER_SCHEMA)

    return list(DEFAULT_PARAMETER_SCHEMA)


def _load_parameter_schema(model_dir: Path) -> list[dict[str, str]]:
    path = model_dir / PARAMETERS_FILENAME
    if not path.is_file():
        return list(DEFAULT_PARAMETER_SCHEMA)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return list(DEFAULT_PARAMETER_SCHEMA)
    return _normalize_parameter_schema(data)


def _parameter_schemas_for_ui() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {"_default": list(DEFAULT_PARAMETER_SCHEMA)}
    for name in _list_models():
        out[name] = _load_parameter_schema(_model_folder(name))
    return out


def _schema_for_submission(model_name: str | None) -> list[dict[str, str]]:
    if model_name:
        return _load_parameter_schema(_model_folder(model_name))
    return list(DEFAULT_PARAMETER_SCHEMA)


def _render_home(
    error: str | None,
    values: dict[str, str],
    param_values: dict[str, str],
) -> str:
    return render_template(
        "index.html",
        error=error,
        values=values,
        param_values=param_values,
        models=_list_models(),
        parameter_schemas=_parameter_schemas_for_ui(),
    )


def _model_folder(model_name: str) -> Path:
    return MODELS_DIR / Path(model_name).name


def _first_file_by_extension(folder: Path, extension: str) -> Path | None:
    files = sorted(
        [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == extension.lower()]
    )
    return files[0] if files else None


def _first_file_by_extensions(folder: Path, extensions: list[str]) -> Path | None:
    for extension in extensions:
        match = _first_file_by_extension(folder, extension)
        if match is not None:
            return match
    return None


def _param_strings_from_form(schema: list[dict[str, str]], form) -> dict[str, str]:
    raw: dict[str, str] = {}
    for entry in schema:
        cell = entry["cell"]
        if not CELL_RE.match(cell):
            continue
        raw[cell] = form.get(f"param_{cell}", "").strip()
    return raw


def _parse_param_floats(
    schema: list[dict[str, str]],
    raw: dict[str, str],
) -> tuple[dict[str, float] | None, str | None]:
    cells = [e["cell"] for e in schema if CELL_RE.match(e["cell"])]
    if not cells:
        return None, None
    present = [c for c in cells if raw.get(c, "") != ""]
    if not present:
        return None, None
    if len(present) != len(cells):
        return None, "Fill all parameter fields for this model, or leave them all empty."
    out: dict[str, float] = {}
    for cell in cells:
        try:
            val = float(raw[cell])
        except ValueError:
            return None, f"Parameter {cell} must be a valid number."
        if val <= 0:
            return None, f"Parameter {cell} must be greater than 0."
        out[cell] = val
    return out, None


def _freecad_script_runners() -> list[list[str]]:
    runners: list[list[str]] = []
    snap_bin = shutil.which("snap")
    if snap_bin:
        runners.append([snap_bin, "run", "freecad.cmd"])
    for candidate in (shutil.which("freecad.cmd"), "/snap/bin/freecad.cmd"):
        if candidate and Path(candidate).exists():
            runners.append([candidate])
    for exe_name in ("freecadcmd", "FreeCADCmd"):
        exe = shutil.which(exe_name)
        if exe:
            runners.append([exe])
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for r in runners:
        key = tuple(r)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def _run_fcstd_export_script(
    fcstd_file: Path,
    param_values: dict[str, float] | None,
) -> str | None:
    if not EXPORT_FCSTD_SCRIPT.is_file():
        return f"Missing export script at {EXPORT_FCSTD_SCRIPT.name} in project root."

    args = [str(EXPORT_FCSTD_SCRIPT.resolve()), str(fcstd_file.resolve())]
    if param_values:
        for cell in sorted(param_values.keys()):
            args.append(f"{cell}={param_values[cell]:g}")

    runners = _freecad_script_runners()
    if not runners:
        return (
            "No FreeCAD runner found for export scripts. Install snap package freecad, "
            "ensure freecad.cmd is on PATH, or install freecadcmd (e.g. apt package freecad)."
        )

    last_err = ""
    cwd = str(PROJECT_ROOT)
    for prefix in runners:
        cmd = prefix + args
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return "Conversion timed out after 180 seconds."
        if result.returncode == 0:
            return None
        last_err = (result.stderr or result.stdout or "").strip()

    return f"FreeCAD export script failed: {last_err or 'unknown error'}"


def _convert_cad_to_stl(
    cad_file: Path,
    stl_file: Path,
    param_values: dict[str, float] | None = None,
) -> str | None:
    if cad_file.suffix.lower() == ".fcstd" and EXPORT_FCSTD_SCRIPT.is_file():
        script_err = _run_fcstd_export_script(cad_file, param_values)
        if script_err:
            return script_err
        expected = cad_file.with_suffix(".stl")
        if not expected.exists():
            return (
                "Export script finished but expected STL was not found next to the FCStd "
                f"({expected.name})."
            )
        if expected.resolve() != stl_file.resolve():
            shutil.copy2(expected, stl_file)
        return None

    freecad_bin = (
        shutil.which("freecadcmd")
        or shutil.which("FreeCADCmd")
        or ("/snap/bin/freecad.cmd" if Path("/snap/bin/freecad.cmd").exists() else None)
    )
    if freecad_bin is None:
        return "FreeCAD CLI is not installed. Install it (snap: freecad) to enable auto-conversion."

    if cad_file.suffix.lower() == ".fcstd":
        dim_lines: list[str] = []
        if param_values:
            dim_lines.append("sheet = None")
            dim_lines.append("for o in doc.Objects:")
            dim_lines.append(
                "    if getattr(o, 'TypeId', '') == 'Spreadsheet::Sheet' and "
                "(o.Name == 'Spreadsheet' or o.Label == 'Spreadsheet'):"
            )
            dim_lines.append("        sheet = o")
            dim_lines.append("        break")
            dim_lines.append("if sheet is None:")
            dim_lines.append("    for o in doc.Objects:")
            dim_lines.append("        if getattr(o, 'TypeId', '') == 'Spreadsheet::Sheet':")
            dim_lines.append("            sheet = o")
            dim_lines.append("            break")
            dim_lines.append("if sheet is not None:")
            for cell, val in sorted(param_values.items()):
                dim_lines.append(f"    try:")
                dim_lines.append(f"        sheet.set({cell!r}, f'{val:g} mm')")
                dim_lines.append(f"    except Exception:")
                dim_lines.append(f"        pass")

        script_lines = [
            "import FreeCAD, Mesh",
            f"doc = FreeCAD.openDocument({str(cad_file)!r})",
            *dim_lines,
            "doc.recompute()",
            "objs = [o for o in doc.Objects if hasattr(o, 'Shape') and not o.Shape.isNull()]",
            f"Mesh.export(objs, {str(stl_file)!r})",
            "FreeCAD.closeDocument(doc.Name)",
        ]
        python_code = "\n".join(script_lines)
    else:
        python_code = (
            "import FreeCAD, Import, Mesh;"
            "doc=FreeCAD.newDocument('import_doc');"
            "Import.insert("
            f"{str(cad_file)!r}"
            ", doc.Name);"
            "doc.recompute();"
            "objs=[o for o in doc.Objects if hasattr(o, 'Shape') and not o.Shape.isNull()];"
            "Mesh.export(objs, "
            f"{str(stl_file)!r}"
            ");"
            "FreeCAD.closeDocument(doc.Name)"
        )
    try:
        result = subprocess.run(
            [freecad_bin, "-c", python_code],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return "Conversion timed out after 180 seconds."

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        if "no supported file format" in err.lower():
            return (
                f"FreeCAD cannot import {cad_file.suffix} directly on this setup. "
                "Please export your model to STEP (.step/.stp) or use FreeCAD (.FCStd) "
                "and place it in the same folder."
            )
        return f"FreeCAD conversion failed: {err or 'unknown error'}"
    return None


def _prepare_model_stl(
    model_dir: Path,
    param_values: dict[str, float] | None,
) -> tuple[Path | None, str | None]:
    source_file = _first_file_by_extensions(
        model_dir,
        [".FCStd", ".fcstd", ".step", ".stp", ".iges", ".igs", ".sldprt"],
    )
    if source_file is None:
        stl_file = _first_file_by_extension(model_dir, ".stl")
        if stl_file is not None:
            return stl_file, None
        return (
            None,
            "No convertible CAD file found in selected model folder. "
            "Add one of: .FCStd, .step, .stp, .iges, .igs, or .sldprt.",
        )

    generated_stl = model_dir / f"{source_file.stem}.stl"
    if param_values is not None and source_file.suffix.lower() != ".fcstd":
        return (
            None,
            "Entered parameters apply only to FreeCAD .FCStd models with a spreadsheet. "
            "STEP/IGES/SLDPRT files keep their original geometry.",
        )
    if param_values is not None and generated_stl.exists():
        generated_stl.unlink()

    if not generated_stl.exists():
        conversion_error = _convert_cad_to_stl(
            source_file,
            generated_stl,
            param_values=param_values,
        )
        if conversion_error:
            return None, conversion_error

    stl_file = generated_stl if generated_stl.exists() else _first_file_by_extension(model_dir, ".stl")
    if stl_file is None:
        return None, "Conversion finished but no STL file was found in the model folder."
    return stl_file, None


@app.get("/")
def home():
    return _render_home(
        error=None,
        values={"model_name": ""},
        param_values={},
    )


@app.post("/download-model-stl")
def download_model_stl():
    model_name = request.form.get("model_name", "").strip()
    schema = _schema_for_submission(model_name or None)
    raw_params = _param_strings_from_form(schema, request.form)
    param_floats, parse_err = _parse_param_floats(schema, raw_params)
    values = {"model_name": model_name}
    if parse_err:
        return _render_home(error=parse_err, values=values, param_values=raw_params), 400

    if not model_name:
        return (
            _render_home(
                error="Select a model and fill its parameters from parameters.json.",
                values=values,
                param_values=raw_params,
            ),
            400,
        )

    model_dir = _model_folder(model_name)
    if not model_dir.exists() or not model_dir.is_dir():
        return _render_home(
            error=f"Model folder '{model_name}' was not found.",
            values=values,
            param_values=raw_params,
        ), 404

    stl_file, stl_error = _prepare_model_stl(model_dir, param_values=param_floats)
    if stl_error:
        return _render_home(error=stl_error, values=values, param_values=raw_params), 400
    if stl_file is None:
        return _render_home(
            error="Could not prepare STL file.",
            values=values,
            param_values=raw_params,
        ), 500

    return send_file(
        stl_file,
        mimetype="model/stl",
        as_attachment=True,
        download_name=stl_file.name,
    )


@app.post("/preview-model-stl")
def preview_model_stl():
    model_name = request.form.get("model_name", "").strip()
    schema = _schema_for_submission(model_name or None)
    raw_params = _param_strings_from_form(schema, request.form)
    param_floats, parse_err = _parse_param_floats(schema, raw_params)
    if parse_err:
        return jsonify({"error": parse_err}), 400

    if not model_name:
        return jsonify({"error": "Select a model to preview."}), 400

    model_dir = _model_folder(model_name)
    if not model_dir.exists() or not model_dir.is_dir():
        return jsonify({"error": f"Model folder '{model_name}' was not found."}), 404

    stl_file, stl_error = _prepare_model_stl(model_dir, param_values=param_floats)
    if stl_error:
        return jsonify({"error": stl_error}), 400
    if stl_file is None:
        return jsonify({"error": "Could not prepare STL file."}), 500
    return send_file(stl_file, mimetype="model/stl", as_attachment=False)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
