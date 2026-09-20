"""
Stylization Prototype v1 — tests whether "identity" survives a soft-chibi anime
stylization pass, independent of the commissioned artist's actual sculpting.

Builds two REALISTIC-proportion mannequins from very different parameters (see
CHARACTERS below), then derives a STYLIZED (~3.5-4 heads tall) version of each
using the SAME transform function. If, after stylization, A and B still read as
two different people (different silhouette, different face width, different
relative height), the proportion pipeline is sound — this is the test the
project brief asked for, not final character art.

Identity anchors kept from the realistic scan-derived mannequin (per the brief):
  1. Head shape (width via face_width param)
  2. Eye configuration — not modeled yet (no eye geometry on this placeholder;
     left as a TODO once the artist's head topology exists)
  3. Body silhouette (shoulder width vs hip vs leg length ratios)
  4. Height / proportion (A and B are NOT normalized to the same height)

Freely stylized: head size (soft-chibi enlarge), overall vertical compression
(legs/torso shortened toward ~3.5-4 heads), general girth/roundness.

Run headless:
    blender --background --python tools/blender/generate_stylization_prototype.py -- \
        --outdir assets/characters/stylization_prototype
"""

import json
import math
import os
import sys
from typing import Dict, Tuple

import bpy
import mathutils

Vector = mathutils.Vector

CHARACTERS = {
    "A": {
        "height_m": 1.60,
        "shoulder_scale": 0.85,   # low/narrow shoulders
        "body_fat": 0.75,         # high
        "leg_length_scale": 0.85, # short legs relative to torso
        "face_width_scale": 1.25, # wide face
    },
    "B": {
        "height_m": 1.90,
        "shoulder_scale": 1.15,   # broad shoulders
        "body_fat": 0.15,         # low
        "leg_length_scale": 1.15, # long legs relative to torso
        "face_width_scale": 0.80, # narrow face
    },
}

STYLIZE = {
    "target_heads": 3.75,     # soft-chibi anime target, per the brief's 3.5-4 range
    "head_enlarge": 1.55,     # freely stylized: bigger head
    "horizontal_keep": 0.88,  # fraction of realistic horizontal offsets kept —
                               # kept high (not shrunk to match vertical compression)
                               # so shoulder-width / face-width identity differences
                               # between characters stay readable after stylization
    "girth_boost": 1.12,      # softer, rounder limbs or "soft chibi" look
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials):
        for block in list(block_collection):
            if block.users == 0:
                block_collection.remove(block)


def compute_realistic_joints(p: dict) -> Dict[str, Tuple[float, float, float]]:
    """Same body graph as generate_placeholder_character.py, but every offset is
    driven by this character's params instead of fixed constants."""
    h = p["height_m"] / 1.75  # overall scale relative to the 1.75m reference rig
    leg = p["leg_length_scale"]
    sh = p["shoulder_scale"]

    # Reference (1.75m) Z heights, then apply per-character height scale.
    hips_z = 0.98 * h
    spine_z = 1.10 * h
    chest_z = 1.32 * h
    neck_z = 1.50 * h
    head_z = 1.62 * h
    head_top_z = 1.735 * h

    # leg_length_scale stretches/compresses the whole hips-to-ground leg span
    # around a fixed hip height, independent of overall height scale.
    leg_span_reference = hips_z - 0.10 * h
    leg_span = leg_span_reference * leg
    ankle_z = max(0.02 * h, hips_z - leg_span)
    knee_z = hips_z - leg_span * 0.53
    toe_z = max(0.0, ankle_z - 0.08 * h)

    joints = {
        "hips": (0.0, 0.0, hips_z),
        "spine": (0.0, 0.0, spine_z),
        "chest": (0.0, 0.0, chest_z),
        "neck": (0.0, 0.0, neck_z),
        "head": (0.0, 0.0, head_z),
        "head_top": (0.0, 0.0, head_top_z),
        "shoulder.L": (0.17 * sh, 0.0, chest_z + 0.14 * h),
        "elbow.L": (0.37 * sh, 0.0, chest_z - 0.06 * h),
        "hand.L": (0.50 * sh, 0.0, chest_z - 0.32 * h),
        "thigh.L": (0.09, 0.0, hips_z),
        "knee.L": (0.10, 0.0, knee_z),
        "ankle.L": (0.10, 0.0, ankle_z),
        "toe.L": (0.10, 0.13, toe_z),
    }
    mirrored = {}
    for name, pos in joints.items():
        if name.endswith(".L"):
            mirrored[name.replace(".L", ".R")] = (-pos[0], pos[1], pos[2])
    joints.update(mirrored)
    return joints


EDGES_TEMPLATE = [
    ("hips", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head"), ("head", "head_top"),
    ("chest", "shoulder.L"), ("shoulder.L", "elbow.L"), ("elbow.L", "hand.L"),
    ("hips", "thigh.L"), ("thigh.L", "knee.L"), ("knee.L", "ankle.L"), ("ankle.L", "toe.L"),
]


def all_edges():
    edges = list(EDGES_TEMPLATE)
    for a, b in EDGES_TEMPLATE:
        if a.endswith(".L") or b.endswith(".L"):
            edges.append((a.replace(".L", ".R") if a.endswith(".L") else a,
                           b.replace(".L", ".R") if b.endswith(".L") else b))
    return edges


BASE_RADIUS = {
    "hips": 0.15, "spine": 0.13, "chest": 0.17, "neck": 0.055, "head": 0.115, "head_top": 0.03,
    "shoulder.L": 0.07, "elbow.L": 0.05, "hand.L": 0.045,
    "thigh.L": 0.11, "knee.L": 0.075, "ankle.L": 0.055, "toe.L": 0.04,
}


def compute_realistic_radii(p: dict) -> Dict[str, Tuple[float, float]]:
    fat = p["body_fat"]
    fat_mult = 0.85 + 0.5 * fat  # 0 -> 0.85x, 1 -> 1.35x on torso girth
    face_w = p["face_width_scale"]

    radii = {}
    for name in BASE_RADIUS:
        r = BASE_RADIUS[name]
        if name in ("hips", "spine", "chest"):
            r *= fat_mult
        radii[name] = (r, r)
        if name.endswith(".L"):
            radii[name.replace(".L", ".R")] = (r, r)

    radii["head"] = (BASE_RADIUS["head"] * face_w, BASE_RADIUS["head"])
    radii["head_top"] = (BASE_RADIUS["head_top"], BASE_RADIUS["head_top"])
    return radii


def stylize(joints: Dict[str, Tuple[float, float, float]], radii: Dict[str, Tuple[float, float]],
            height_m: float) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, Tuple[float, float]]]:
    """Applies the same soft-chibi transform to any character's realistic joints/radii."""
    neck_z = joints["neck"][2]
    head_top_z = joints["head_top"][2]
    head_span = head_top_z - neck_z
    head_span_stylized = head_span * STYLIZE["head_enlarge"]

    target_total = head_span_stylized * STYLIZE["target_heads"]
    body_span_realistic = neck_z  # ground (z=0) to neck
    body_span_stylized = target_total - head_span_stylized
    vscale = body_span_stylized / body_span_realistic if body_span_realistic > 1e-6 else 1.0
    hscale = STYLIZE["horizontal_keep"]

    new_joints = {}
    for name, (x, y, z) in joints.items():
        if name in ("head", "head_top"):
            new_z = body_span_stylized + (z - neck_z) * STYLIZE["head_enlarge"]
        else:
            new_z = z * vscale
        new_joints[name] = (x * hscale, y * hscale, new_z)

    new_radii = {}
    for name, (rx, ry) in radii.items():
        boost = STYLIZE["girth_boost"]
        if name in ("head", "head_top"):
            boost *= STYLIZE["head_enlarge"]
        new_radii[name] = (rx * boost, ry * boost)

    return new_joints, new_radii


def measure(joints, radii) -> dict:
    total_height = joints["head_top"][2]
    head_span = joints["head_top"][2] - joints["neck"][2]
    return {
        "total_height_m": round(total_height, 3),
        "head_to_body_ratio_heads": round(total_height / head_span, 2),
        "shoulder_width_m": round(joints["shoulder.L"][0] * 2, 3),
        "face_width_m": round(radii["head"][0] * 2, 3),
        "leg_length_m": round(joints["hips"][2] - joints["ankle.L"][2], 3),
    }


def build_mesh(name: str, joints, radii, edges):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    names = list(joints.keys())
    index_of = {n: i for i, n in enumerate(names)}
    verts = [joints[n] for n in names]
    edge_idx = [(index_of[a], index_of[b]) for a, b in edges]
    mesh.from_pydata(verts, edge_idx, [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    skin_mod = obj.modifiers.new("Skin", type="SKIN")
    skin_layer = mesh.skin_vertices[0].data
    for n, i in index_of.items():
        skin_layer[i].radius = radii.get(n, (0.07, 0.07))
    skin_layer[index_of["hips"]].use_root = True

    subsurf = obj.modifiers.new("Subsurf", type="SUBSURF")
    subsurf.levels = 2
    subsurf.render_levels = 2

    bpy.ops.object.modifier_apply(modifier=skin_mod.name)
    bpy.ops.object.modifier_apply(modifier=subsurf.name)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles()
    bpy.ops.mesh.dissolve_degenerate()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

    mat = bpy.data.materials.new(f"{name}_skin")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.68, 0.58, 1.0)
    obj.data.materials.append(mat)
    return obj


def setup_render_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in
                           bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    if scene.world:
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

    cam_data = bpy.data.cameras.new("CompareCam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("CompareCam", cam_data)
    cam_obj.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    key = bpy.data.lights.new("Key", type="SUN")
    key.energy = 3.0
    key_obj = bpy.data.objects.new("Key", key)
    key_obj.location = (2, -3, 4)
    key_obj.rotation_euler = (0.9, 0, 0.6)
    bpy.context.collection.objects.link(key_obj)

    fill = bpy.data.lights.new("Fill", type="SUN")
    fill.energy = 1.0
    fill_obj = bpy.data.objects.new("Fill", fill)
    fill_obj.location = (-2, -2, 2)
    fill_obj.rotation_euler = (1.1, 0, -0.8)
    bpy.context.collection.objects.link(fill_obj)

    return cam_obj


def frame_camera_on(cam_obj, objs, margin=1.2):
    scene = bpy.context.scene
    aspect = scene.render.resolution_x / scene.render.resolution_y
    xs, zs = [], []
    for obj in objs:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            xs.append(world.x)
            zs.append(world.z)
    min_x, max_x, min_z, max_z = min(xs), max(xs), min(zs), max(zs)
    width, height = max_x - min_x, max_z - min_z
    center_x, center_z = (min_x + max_x) / 2, (min_z + max_z) / 2

    cam_obj.data.ortho_scale = max(width, height * aspect) * margin
    cam_obj.location = (center_x, -5.0, center_z)


def export_glb(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True,
                               use_selection=True, export_apply=False)


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    outdir = args[args.index("--outdir") + 1] if "--outdir" in args else "assets/characters/stylization_prototype"
    return outdir


def main():
    outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)
    clear_scene()

    edges = all_edges()
    objects = {}
    report = {}
    spacing = 0.9

    for i, (char_name, params) in enumerate(CHARACTERS.items()):
        realistic_joints = compute_realistic_joints(params)
        realistic_radii = compute_realistic_radii(params)

        stylized_joints, stylized_radii = stylize(realistic_joints, realistic_radii, params["height_m"])

        report[char_name] = {
            "params": params,
            "realistic": measure(realistic_joints, realistic_radii),
            "stylized": measure(stylized_joints, stylized_radii),
        }

        real_obj = build_mesh(f"{char_name}_realistic", realistic_joints, realistic_radii, edges)
        style_obj = build_mesh(f"{char_name}_stylized", stylized_joints, stylized_radii, edges)

        real_obj.location.x = i * spacing * 4
        style_obj.location.x = i * spacing * 4 + spacing * 2

        export_glb(real_obj, os.path.join(outdir, f"character_{char_name}_realistic.glb"))
        export_glb(style_obj, os.path.join(outdir, f"character_{char_name}_stylized.glb"))
        objects[char_name] = (real_obj, style_obj)

    cam_obj = setup_render_scene()
    all_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]

    frame_camera_on(cam_obj, all_meshes)
    render(os.path.join(outdir, "comparison_all.png"))

    for name, (real_obj, style_obj) in objects.items():
        for obj in all_meshes:
            obj.hide_render = obj not in (real_obj, style_obj)
        frame_camera_on(cam_obj, [real_obj, style_obj])
        render(os.path.join(outdir, f"comparison_{name}_before_after.png"))
    for obj in all_meshes:
        obj.hide_render = False

    stylized_objs = [obj for obj in all_meshes if obj.name.endswith("_stylized")]
    for obj in all_meshes:
        obj.hide_render = obj not in stylized_objs
    frame_camera_on(cam_obj, stylized_objs)
    render(os.path.join(outdir, "comparison_stylized_only.png"))

    report_path = os.path.join(outdir, "identity_preservation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote stylization prototype outputs to {outdir}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
