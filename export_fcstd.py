import FreeCAD as App
import Mesh
import os
import sys

args = sys.argv

fcstd_file = None
params = []

for arg in args:
    if arg.lower().endswith(".fcstd"):
        fcstd_file = arg
    elif "=" in arg:
        params.append(arg)

if fcstd_file is None:
    raise RuntimeError("No .FCStd file provided")

fcstd_file = os.path.abspath(fcstd_file)

if not os.path.exists(fcstd_file):
    raise RuntimeError(f"File not found: {fcstd_file}")

out_file = os.path.splitext(fcstd_file)[0] + ".stl"

doc = App.openDocument(fcstd_file)

sheet = doc.getObject("Spreadsheet")
if sheet is None:
    raise RuntimeError("Spreadsheet not found")

for arg in params:
    cell, value = arg.split("=", 1)
    print(f"Setting {cell} = {value}")
    sheet.set(cell, value)

doc.recompute()

body = None
for obj in doc.Objects:
    if obj.TypeId == "PartDesign::Body":
        body = obj
        break

if body is None:
    raise RuntimeError("No PartDesign Body found")

obj = body.Tip

print("Exporting:", obj.Name, obj.Label)
Mesh.export([obj], out_file)

print("STL exported:", out_file)
