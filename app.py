from pathlib import Path
import shutil
import subprocess

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
MODELS_DIR = Path(__file__).resolve().parent / "models"


def _list_models() -> list[str]:
    if not MODELS_DIR.exists():
        return []
    return sorted(
        [entry.name for entry in MODELS_DIR.iterdir() if entry.is_dir()],
        key=str.lower,
    )


def _render_home(error: str | None, values: dict[str, str]) -> str:
    return render_template(
        "index.html",
        error=error,
        values=values,
        models=_list_models(),
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


def _convert_cad_to_stl(cad_file: Path, stl_file: Path) -> str | None:
    freecad_bin = (
        shutil.which("freecadcmd")
        or shutil.which("FreeCADCmd")
        or ("/snap/bin/freecad.cmd" if Path("/snap/bin/freecad.cmd").exists() else None)
    )
    if freecad_bin is None:
        return "FreeCAD CLI is not installed. Install it (snap: freecad) to enable auto-conversion."

    python_code = (
        "import FreeCAD, Import, Mesh;"
        "doc=Import.open("
        f"{str(cad_file)!r}"
        ");"
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
                "Please export your model to STEP (.step/.stp) and place it in the same folder."
            )
        return f"FreeCAD conversion failed: {err or 'unknown error'}"
    return None


@app.get("/")
def home():
    return _render_home(
        error=None,
        values={
            "model_name": "",
        },
    )


@app.post("/download-model-stl")
def download_model_stl():
    model_name = request.form.get("model_name", "").strip()
    values = {
        "model_name": model_name,
    }

    if not model_name:
        return _render_home(error="Please select a model first.", values=values), 400

    model_dir = _model_folder(model_name)
    if not model_dir.exists() or not model_dir.is_dir():
        return _render_home(error=f"Model folder '{model_name}' was not found.", values=values), 404

    stl_file = _first_file_by_extension(model_dir, ".stl")
    if stl_file is None:
        source_file = _first_file_by_extensions(
            model_dir,
            [".step", ".stp", ".iges", ".igs", ".sldprt"],
        )
        if source_file is None:
            return _render_home(
                error=(
                    f"No convertible CAD file found in '{model_name}'. "
                    "Add one of: .step, .stp, .iges, .igs, or .sldprt."
                ),
                values=values,
            ), 400

        generated_stl = model_dir / f"{source_file.stem}.stl"
        conversion_error = _convert_cad_to_stl(source_file, generated_stl)
        if conversion_error:
            return _render_home(error=conversion_error, values=values), 400
        stl_file = generated_stl if generated_stl.exists() else _first_file_by_extension(model_dir, ".stl")
        if stl_file is None:
            return _render_home(
                error="Conversion finished but no STL file was found in the model folder.",
                values=values,
            ), 500

    return send_file(
        stl_file,
        mimetype="model/stl",
        as_attachment=True,
        download_name=stl_file.name,
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
