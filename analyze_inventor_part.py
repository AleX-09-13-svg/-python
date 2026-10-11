import json
import math
from datetime import datetime

import pythoncom
import win32com.client.dynamic


REPORT_JSON = "inventor_part_report.json"
REPORT_TXT = "inventor_part_report.txt"


def get_inventor():
    inventor_unknown = pythoncom.GetActiveObject("Inventor.Application")
    inventor_dispatch = inventor_unknown.QueryInterface(pythoncom.IID_IDispatch)
    return win32com.client.dynamic.Dispatch(inventor_dispatch)


def safe_get(label, getter):
    try:
        return make_json_safe(getter())
    except Exception as error:
        return f"<error reading {label}: {error}>"


def make_json_safe(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return str(value)

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def point_to_dict(point):
    return {
        "x": safe_get("point.X", lambda: point.X),
        "y": safe_get("point.Y", lambda: point.Y),
        "z": safe_get("point.Z", lambda: point.Z),
    }


def box_to_dict(box):
    min_point = box.MinPoint
    max_point = box.MaxPoint
    return {
        "min": point_to_dict(min_point),
        "max": point_to_dict(max_point),
        "size": {
            "x": safe_get("box size X", lambda: max_point.X - min_point.X),
            "y": safe_get("box size Y", lambda: max_point.Y - min_point.Y),
            "z": safe_get("box size Z", lambda: max_point.Z - min_point.Z),
        },
    }


def collection_count(obj, attr_name):
    return safe_get(attr_name, lambda: getattr(obj, attr_name).Count)


def collect_body_info(body, index):
    info = {
        "index": index,
        "name": safe_get("body.Name", lambda: body.Name),
        "is_solid": safe_get("body.IsSolid", lambda: body.IsSolid),
        "visible": safe_get("body.Visible", lambda: body.Visible),
        "faces_count": collection_count(body, "Faces"),
        "edges_count": collection_count(body, "Edges"),
        "vertices_count": collection_count(body, "Vertices"),
        "shells_count": collection_count(body, "Shells"),
        "range_box": safe_get("body.RangeBox", lambda: box_to_dict(body.RangeBox)),
        "oriented_minimum_range_box": safe_get(
            "body.OrientedMinimumRangeBox",
            lambda: box_to_dict(body.OrientedMinimumRangeBox),
        ),
    }

    info["volume"] = safe_get("body.Volume", lambda: body.Volume)

    return info


def collect_feature_summary(features):
    summary = {
        "count": safe_get("Features.Count", lambda: features.Count),
        "items": [],
    }

    count = summary["count"]
    if not isinstance(count, int):
        return summary

    for index in range(1, count + 1):
        feature = features.Item(index)
        summary["items"].append(
            {
                "index": index,
                "name": safe_get("feature.Name", lambda: feature.Name),
                "type": safe_get("feature.Type", lambda: feature.Type),
                "suppressed": safe_get("feature.Suppressed", lambda: feature.Suppressed),
                "health_status": safe_get(
                    "feature.HealthStatus",
                    lambda: feature.HealthStatus,
                ),
            }
        )

    return summary


def collect_sketch_summary(sketches):
    summary = {
        "count": safe_get("Sketches.Count", lambda: sketches.Count),
        "items": [],
    }

    count = summary["count"]
    if not isinstance(count, int):
        return summary

    for index in range(1, count + 1):
        sketch = sketches.Item(index)
        summary["items"].append(
            {
                "index": index,
                "name": safe_get("sketch.Name", lambda: sketch.Name),
                "visible": safe_get("sketch.Visible", lambda: sketch.Visible),
                "consumed": safe_get("sketch.Consumed", lambda: sketch.Consumed),
                "sketch_points": collection_count(sketch, "SketchPoints"),
                "sketch_lines": collection_count(sketch, "SketchLines"),
                "sketch_circles": collection_count(sketch, "SketchCircles"),
            }
        )

    return summary


def collect_parameter_summary(parameters):
    summary = {
        "count": safe_get("Parameters.Count", lambda: parameters.Count),
        "items": [],
    }

    count = summary["count"]
    if not isinstance(count, int):
        return summary

    for index in range(1, count + 1):
        parameter = parameters.Item(index)
        summary["items"].append(
            {
                "index": index,
                "name": safe_get("parameter.Name", lambda: parameter.Name),
                "expression": safe_get(
                    "parameter.Expression",
                    lambda: parameter.Expression,
                ),
                "value": safe_get("parameter.Value", lambda: parameter.Value),
                "units": safe_get("parameter.Units", lambda: parameter.Units),
            }
        )

    return summary


def collect_report():
    inv = get_inventor()

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "inventor": {
            "caption": safe_get("Application.Caption", lambda: inv.Caption),
            "visible": safe_get("Application.Visible", lambda: inv.Visible),
            "documents_count": safe_get("Application.Documents.Count", lambda: inv.Documents.Count),
        },
    }

    if inv.Documents.Count == 0:
        report["error"] = "No open documents in Inventor."
        return report

    doc = inv.ActiveDocument
    comp_def = doc.ComponentDefinition

    report["document"] = {
        "display_name": safe_get("Document.DisplayName", lambda: doc.DisplayName),
        "full_file_name": safe_get("Document.FullFileName", lambda: doc.FullFileName),
        "document_type": safe_get("Document.DocumentType", lambda: doc.DocumentType),
        "dirty": safe_get("Document.Dirty", lambda: doc.Dirty),
    }

    report["component_definition"] = {
        "material": safe_get("ComponentDefinition.Material.Name", lambda: comp_def.Material.Name),
        "has_multiple_solid_bodies": safe_get(
            "ComponentDefinition.HasMultipleSolidBodies",
            lambda: comp_def.HasMultipleSolidBodies,
        ),
        "model_geometry_version": safe_get(
            "ComponentDefinition.ModelGeometryVersion",
            lambda: comp_def.ModelGeometryVersion,
        ),
        "range_box": safe_get("ComponentDefinition.RangeBox", lambda: box_to_dict(comp_def.RangeBox)),
    }

    mass = comp_def.MassProperties
    report["mass_properties"] = {
        "mass": safe_get("MassProperties.Mass", lambda: mass.Mass),
        "volume": safe_get("MassProperties.Volume", lambda: mass.Volume),
        "area": safe_get("MassProperties.Area", lambda: mass.Area),
        "center_of_mass": safe_get(
            "MassProperties.CenterOfMass",
            lambda: point_to_dict(mass.CenterOfMass),
        ),
    }

    bodies = comp_def.SurfaceBodies
    bodies_count = safe_get("SurfaceBodies.Count", lambda: bodies.Count)
    report["surface_bodies"] = {
        "count": bodies_count,
        "items": [],
    }
    if isinstance(bodies_count, int):
        for index in range(1, bodies_count + 1):
            report["surface_bodies"]["items"].append(
                collect_body_info(bodies.Item(index), index)
            )

    report["features"] = collect_feature_summary(comp_def.Features)
    report["sketches"] = collect_sketch_summary(comp_def.Sketches)
    report["parameters"] = collect_parameter_summary(comp_def.Parameters)

    report["work_geometry"] = {
        "work_planes": collection_count(comp_def, "WorkPlanes"),
        "work_axes": collection_count(comp_def, "WorkAxes"),
        "work_points": collection_count(comp_def, "WorkPoints"),
    }

    return report


def write_text_report(report):
    lines = []
    lines.append("Inventor Part Report")
    lines.append("====================")
    lines.append(f"Created at: {report.get('created_at')}")
    lines.append("")

    if "error" in report:
        lines.append(f"Error: {report['error']}")
        return "\n".join(lines)

    document = report["document"]
    comp_def = report["component_definition"]
    mass = report["mass_properties"]
    bodies = report["surface_bodies"]

    lines.append(f"Document: {document['display_name']}")
    lines.append(f"Path: {document['full_file_name']}")
    lines.append(f"Material: {comp_def['material']}")
    lines.append(f"Multiple solid bodies: {comp_def['has_multiple_solid_bodies']}")
    lines.append("")

    lines.append("Mass properties")
    lines.append(f"  Mass: {mass['mass']}")
    lines.append(f"  Volume: {mass['volume']}")
    lines.append(f"  Area: {mass['area']}")
    lines.append(f"  Center of mass: {mass['center_of_mass']}")
    lines.append("")

    lines.append(f"Surface bodies: {bodies['count']}")
    for body in bodies["items"]:
        lines.append(f"  Body {body['index']}: {body['name']}")
        lines.append(f"    Solid: {body['is_solid']}")
        lines.append(f"    Visible: {body['visible']}")
        lines.append(f"    Faces: {body['faces_count']}")
        lines.append(f"    Edges: {body['edges_count']}")
        lines.append(f"    Vertices: {body['vertices_count']}")
        lines.append(f"    Shells: {body['shells_count']}")
    lines.append("")

    lines.append(f"Features: {report['features']['count']}")
    for feature in report["features"]["items"]:
        lines.append(
            f"  {feature['index']}. {feature['name']} "
            f"(type={feature['type']}, suppressed={feature['suppressed']})"
        )
    lines.append("")

    lines.append(f"Sketches: {report['sketches']['count']}")
    for sketch in report["sketches"]["items"]:
        lines.append(
            f"  {sketch['index']}. {sketch['name']} "
            f"(points={sketch['sketch_points']}, lines={sketch['sketch_lines']}, "
            f"circles={sketch['sketch_circles']})"
        )
    lines.append("")

    lines.append(f"Parameters: {report['parameters']['count']}")
    for parameter in report["parameters"]["items"]:
        lines.append(
            f"  {parameter['index']}. {parameter['name']} = "
            f"{parameter['expression']} [{parameter['units']}]"
        )

    return "\n".join(lines)


def main():
    report = collect_report()
    text_report = write_text_report(report)

    with open(REPORT_JSON, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2, allow_nan=False)

    with open(REPORT_TXT, "w", encoding="utf-8") as file:
        file.write(text_report)

    print(text_report)
    print("")
    print(f"Saved: {REPORT_JSON}")
    print(f"Saved: {REPORT_TXT}")


if __name__ == "__main__":
    main()
