from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
MODELS_DIR = Path(__file__).resolve().parent / "models"


def _list_models() -> list[str]:
    if not MODELS_DIR.exists():
        return []
    return sorted(
        [entry.name for entry in MODELS_DIR.iterdir() if entry.is_dir()],
        key=str.lower,
    )


@app.get("/")
def home():
    return render_template(
        "index.html",
        error=None,
        values={"shape": "cube", "width": "20", "height": "20", "depth": "20"},
        models=_list_models(),
    )


def _rectangular_prism_stl(width: float, height: float, depth: float) -> str:
    """Build an ASCII STL for a rectangular prism centered at origin."""
    hx = width / 2.0
    hy = height / 2.0
    hz = depth / 2.0

    vertices = {
        "nbl": (-hx, -hy, -hz),  # near bottom left
        "nbr": (hx, -hy, -hz),
        "ntl": (-hx, hy, -hz),
        "ntr": (hx, hy, -hz),
        "fbl": (-hx, -hy, hz),   # far bottom left
        "fbr": (hx, -hy, hz),
        "ftl": (-hx, hy, hz),
        "ftr": (hx, hy, hz),
    }

    facets = [
        # top (+y)
        ((0.0, 1.0, 0.0), ("ntl", "ftl", "ftr")),
        ((0.0, 1.0, 0.0), ("ntl", "ftr", "ntr")),
        # bottom (-y)
        ((0.0, -1.0, 0.0), ("nbl", "fbr", "fbl")),
        ((0.0, -1.0, 0.0), ("nbl", "nbr", "fbr")),
        # left (-x)
        ((-1.0, 0.0, 0.0), ("nbl", "ftl", "ntl")),
        ((-1.0, 0.0, 0.0), ("nbl", "fbl", "ftl")),
        # right (+x)
        ((1.0, 0.0, 0.0), ("nbr", "ntr", "ftr")),
        ((1.0, 0.0, 0.0), ("nbr", "ftr", "fbr")),
        # front (-z)
        ((0.0, 0.0, -1.0), ("nbl", "ntl", "ntr")),
        ((0.0, 0.0, -1.0), ("nbl", "ntr", "nbr")),
        # back (+z)
        ((0.0, 0.0, 1.0), ("fbl", "ftr", "ftl")),
        ((0.0, 0.0, 1.0), ("fbl", "fbr", "ftr")),
    ]

    lines = ["solid cube"]
    for normal, triangle in facets:
        lines.append(
            f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}"
        )
        lines.append("    outer loop")
        for vertex_name in triangle:
            x, y, z = vertices[vertex_name]
            lines.append(f"      vertex {x:.6f} {y:.6f} {z:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid cube")
    lines.append("")
    return "\n".join(lines)


@app.post("/generate-stl")
def generate_stl():
    shape = request.form.get("shape", "cube")
    width_raw = request.form.get("width", "")
    height_raw = request.form.get("height", "")
    depth_raw = request.form.get("depth", "")

    values = {
        "shape": shape,
        "width": width_raw,
        "height": height_raw,
        "depth": depth_raw,
    }

    if shape != "cube":
        return (
            render_template(
                "index.html",
                error="Only cube is supported for now.",
                values=values,
                models=_list_models(),
            ),
            400,
        )

    try:
        width = float(width_raw)
        height = float(height_raw)
        depth = float(depth_raw)
    except ValueError:
        return render_template(
            "index.html",
            error="Dimensions must be valid numbers.",
            values=values,
            models=_list_models(),
        ), 400

    if width <= 0 or height <= 0 or depth <= 0:
        return render_template(
            "index.html",
            error="All dimensions must be greater than 0.",
            values=values,
            models=_list_models(),
        ), 400

    stl_content = _rectangular_prism_stl(width, height, depth)
    filename = f"cube_{width:g}x{height:g}x{depth:g}.stl"
    return Response(
        stl_content,
        mimetype="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
