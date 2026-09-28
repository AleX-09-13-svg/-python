import importlib.util
from pathlib import Path

from common.constants import DRILLING_SKETCH_PREFIX
from common.selected_workflow import hide_sketches, selected_context
from common.settings import hole_direction, load_settings
import confirmat.confirmat as confirmat_module


VENEER_FRAME_THICKNESS_PARAM = "\u0422\u043e\u043b\u0449\u0438\u043d\u0430_\u043a\u0430\u0440\u043a\u0430\u0441\u0430_\u0428\u041f\u041e\u041d"


CREATE_SKETCHES_SCRIPT = Path(__file__).resolve().with_name(
    "001_createSketches_for_Conf.py"
)


def load_create_sketches_module():
    spec = importlib.util.spec_from_file_location(
        "create_sketches_for_confirmat",
        CREATE_SKETCHES_SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def use_veneer_frame_thickness(create_sketches):
    create_sketches.FRAME_THICKNESS_PARAM = VENEER_FRAME_THICKNESS_PARAM
    confirmat_module.FRAME_THICKNESS_PARAM = VENEER_FRAME_THICKNESS_PARAM
    load_settings()["confirmat"]["outer_3pcs"]["depth"] = VENEER_FRAME_THICKNESS_PARAM


def main():
    doc, comp, faces = selected_context("Confirmat 3pcs")
    if not faces:
        return

    create_sketches = load_create_sketches_module()
    use_veneer_frame_thickness(create_sketches)
    required_parameters = (
        create_sketches.EDGE_OFFSET_FRAME_PARAM,
        create_sketches.EDGE_OFFSET_DRAWER_PARAM,
        create_sketches.FRAME_THICKNESS_PARAM,
    )
    if not create_sketches.ensure_parameters(comp, required_parameters):
        return

    create_sketches.ensure_keep_excel_parameters(comp, required_parameters)
    protected_parameter_expressions = create_sketches.parameter_expressions(
        comp,
        required_parameters,
    )

    sketches = create_sketches.create_sketches_for_faces(
        doc.Parent,
        doc,
        faces,
        DRILLING_SKETCH_PREFIX,
        None,
        "Drilling",
        "Selected drilling",
    )
    if create_sketches.should_update_document():
        doc.Update()
        # if create_sketches.restore_missing_parameters(
        #     comp,
        #     protected_parameter_expressions,
        # ):
        #     doc.Update()

    created = confirmat_module.create_confirmat_features(
        doc,
        sketches=sketches,
        faces=faces,
        face_label="selected",
        direction=hole_direction("positive"),
    )
    hide_sketches(sketches, "Confirmat 3pcs")
    print("Confirmat 3pcs hole features created:", created)


if __name__ == "__main__":
    main()
