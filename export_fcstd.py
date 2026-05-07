import json
import os
import sys
from pathlib import Path

import FreeCAD as App
import Mesh

# Skip host binary / script file entry (FreeCADCmd argv varies by OS/build).
_argv = sys.argv[1:]


def _cell_text(val: object) -> str:
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        return f"{val:g}"
    return str(val).strip()


fcstd_file: str | None = None
param_json_path = os.environ.get("STL_FACTORY_PARAMS_FILE")
cli_params: list[str] = []

for arg in _argv:
    low = arg.lower()
    if low.endswith(".py"):
        continue
    if low.endswith(".fcstd"):
        fcstd_file = arg
    elif low.endswith(".json") and Path(arg).is_file():
        param_json_path = arg
    elif "=" in arg:
        cli_params.append(arg)

merged: dict[str, str] = {}
if param_json_path:
    jp = Path(param_json_path)
    if jp.is_file():
        raw = json.loads(jp.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("Params JSON must be an object, e.g. {\"A1\": 50}")
        for cell, val in raw.items():
            merged[str(cell)] = _cell_text(val)

for item in cli_params:
    cell, value = item.split("=", 1)
    merged[cell.strip()] = value.strip()

print(f"STL_FACTORY argv_extras={_argv!r}", flush=True)
print(f"STL_FACTORY merged={merged!r}", flush=True)

if fcstd_file is None:
    raise RuntimeError("No .FCStd file provided")

fcstd_path = Path(fcstd_file).resolve()

if not fcstd_path.is_file():
    raise RuntimeError(f"File not found: {fcstd_path}")

out_file = fcstd_path.with_suffix(".stl")

doc = App.openDocument(str(fcstd_path))

sheet = doc.getObject("Spreadsheet")
if sheet is None:
    for o in doc.Objects:
        if getattr(o, "TypeId", "") == "Spreadsheet::Sheet":
            sheet = o
            break
if sheet is None:
    raise RuntimeError("Spreadsheet not found")

for cell in sorted(merged.keys()):
    txt = merged[cell]
    print(f"Setting {cell} = {txt}", flush=True)
    sheet.set(cell, txt)

doc.recompute()
doc.recompute()

body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        body = obj
        break

if body is None:
    raise RuntimeError("No PartDesign Body found")

obj = body.Tip

print("Exporting:", obj.Name, obj.Label, flush=True)
Mesh.export([obj], str(out_file))

print("STL exported:", out_file, flush=True)
