"""
Stylization Prototype v1.1 — addresses the specific gaps flagged in review of v1:

  1. v1 only tested two EXTREME body configs (easy case). This adds a near-identical
     pair (C vs D: same height/shoulder/legs, only a small face-width + eye-spacing
     difference) — the harder, more meaningful case.
  2. v1 had no eye geometry at all. This adds simple sphere "eye landmark" markers
     (NOT real eye geometry — no eyelid, iris, or socket) so eye spacing / height /
     angle / depth can at least be parametrized and checked to survive stylization
     proportionally. This is a proxy for identity anchor ②, not a substitute for
     testing on the artist's real head topology.
  3. v1 only rendered one front angle, unlabeled, which made images hard to tell
     apart. This renders front + profile per character and burns in a text label
     (name + key params) on every image.

Still NOT addressed (blocked on the artist's real base mesh, or requires human
subjects, per docs/stylization-prototype-v1.md): real face topology (nose, jaw,
cheekbones, brow), hair/clothing/color that could dominate perception, silhouette-
only vs face-only vs full-character layering, and a human blind test matching
stylized characters back to their realistic originals.

Run headless:
    blender --background --python tools/blender/generate_stylization_prototype_v1_1.py -- \
        --outdir assets/characters/stylization_prototype_v1_1
"""

import math
import os
import sys
from typing import Dict, Tuple

import bpy
import mathutils

Vector = mathutils.Vector

CHARACTERS = {
    # Kept from v1 for continuity — the easy, extreme case.
    "A": {
        "height_m": 1.60, "shoulder_scale": 0.85, "body_fat": 0.75,
        "leg_length_scale": 0.85, "face_width_scale": 1.25,
        "eye_spacing_scale": 1.15, "eye_height_scale": 1.0, "eye_angle_deg": -6.0, "eye_depth_scale": 1.0,
    },
    "B": {
        "height_m": 1.90, "shoulder_scale": 1.15, "body_fat": 0.15,
        "leg_length_scale": 1.15, "face_width_scale": 0.80,
        "eye_spacing_scale": 0.90, "eye_height_scale": 1.0, "eye_angle_deg": 8.0, "eye_depth_scale": 1.0,
    },
    # New: the harder case — nearly identical body, small face/eye differences only.
    "C": {
        "height_m": 1.75, "shoulder_scale": 1.0, "body_fat": 0.45,
        "leg_length_scale": 1.0, "face_width_scale": 1.05,
        "eye_spacing_scale": 1.08, "eye_height_scale": 1.0, "eye_angle_deg": -3.0, "eye_depth_scale": 1.0,
    },
    "D": {
        "height_m": 1.75, "shoulder_scale": 1.0, "body_fat": 0.50,
        "leg_length_scale": 1.0, "face_width_scale": 0.95,
        "eye_spacing_scale": 0.94, "eye_height_scale": 1.0, "eye_angle_deg": 3.0, "eye_depth_scale": 1.0,
    },
}

STYLIZE = {
    "target_heads": 3.75,
    "head_enlarge": 1.55,
    "horizontal_keep": 0.88,
    "girth_boost": 1.12,
}

BASE_RADIUS = {
    "hips": 0.15, "spine": 0.13, "chest": 0.17, "neck": 0.055, "head": 0.115, "head_top": 0.03,
    "shoulder.L": 0.07, "elbow.L": 0.05, "hand.L": 0.045,
    "thigh.L": 0.11, "knee.L": 0.075, "ankle.L": 0.055, "toe.L": 0.04,
}

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


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def compute_realistic_joints(p: dict) -> Dict[str, Tuple[float, float, float]]:
    h = p["height_m"] / 1.75
    leg = p["leg_length_scale"]
    sh = p["shoulder_scale"]

    hips_z, spine_z, chest_z = 0.98 * h, 1.10 * h, 1.32 * h
    neck_z, head_z, head_top_z = 1.50 * h, 1.62 * h, 1.735 * h

    leg_span_reference = hips_z - 0.10 * h
    leg_span = leg_span_reference * leg
    ankle_z = max(0.02 * h, hips_z - leg_span)
    knee_z = hips_z - leg_span * 0.53
    toe_z = max(0.0, ankle_z - 0.08 * h)

    joints = {
        "hips": (0.0, 0.0, hips_z), "spine": (0.0, 0.0, spine_z), "chest": (0.0, 0.0, chest_z),
        "neck": (0.0, 0.0, neck_z), "head": (0.0, 0.0, head_z), "head_top": (0.0, 0.0, head_top_z),
        "shoulder.L": (0.17 * sh, 0.0, chest_z + 0.14 * h),
        "elbow.L": (0.37 * sh, 0.0, chest_z - 0.06 * h),
        "hand.L": (0.50 * sh, 0.0, chest_z - 0.32 * h),
        "thigh.L": (0.09, 0.0, hips_z), "knee.L": (0.10, 0.0, knee_z),
        "ankle.L": (0.10, 0.0, ankle_z), "toe.L": (0.10, 0.13, toe_z),
    }
    mirrored = {}
    for name, pos in joints.items():
        if name.endswith(".L"):
            mirrored[name.replace(".L", ".R")] = (-pos[0], pos[1], pos[2])
    joints.update(mirrored)
    return joints


def compute_realistic_radii(p: dict) -> Dict[str, Tuple[float, float]]:
    fat_mult = 0.85 + 0.5 * p["body_fat"]
    radii = {}
    for name in BASE_RADIUS:
        r = BASE_RADIUS[name]
        if name in ("hips", "spine", "chest"):
            r *= fat_mult
        radii[name] = (r, r)
        if name.endswith(".L"):
            radii[name.replace(".L", ".R")] = (r, r)
    radii["head"] = (BASE_RADIUS["head"] * p["face_width_scale"], BASE_RADIUS["head"])
    radii["head_top"] = (BASE_RADIUS["head_top"], BASE_RADIUS["head_top"])
    return radii


def stylize(joints, radii):
    neck_z = joints["neck"][2]
    head_top_z = joints["head_top"][2]
    head_span = head_top_z - neck_z
    head_span_stylized = head_span * STYLIZE["head_enlarge"]
    target_total = head_span_stylized * STYLIZE["target_heads"]
    body_span_stylized = target_total - head_span_stylized
    vscale = body_span_stylized / neck_z if neck_z > 1e-6 else 1.0
    hscale = STYLIZE["horizontal_keep"]

    new_joints = {}
    for name, (x, y, z) in joints.items():
        new_z = body_span_stylized + (z - neck_z) * STYLIZE["head_enlarge"] if name in ("head", "head_top") else z * vscale
        new_joints[name] = (x * hscale, y * hscale, new_z)

    new_radii = {}
    for name, (rx, ry) in radii.items():
        boost = STYLIZE["girth_boost"] * (STYLIZE["head_enlarge"] if name in ("head", "head_top") else 1.0)
        new_radii[name] = (rx * boost, ry * boost)

    return new_joints, new_radii


def eye_marker_positions(joints, radii, p, mirror=False):
    """Proxy eye landmarks: two small ellipsoids near head front, positioned/scaled
    analytically from the same head joint+radius the mesh uses, so they move through
    stylization exactly like the head does. NOT real eye geometry."""
    head_x, head_y, head_z = joints["head"]
    head_rx, head_ry = radii["head"]
    spacing = head_rx * 0.5 * p["eye_spacing_scale"]
    height_off = head_ry * 0.05 * p["eye_height_scale"]
    depth = head_ry * 1.05 * p["eye_depth_scale"]  # >1.0 so the marker sits proud of the head surface, not embedded in it
    side = -1 if mirror else 1
    # The "front" camera in this script sits at -Y looking toward +Y (see setup_scene /
    # frame_and_render), which faces the -Y side of the character — so eyes go on -Y.
    return (head_x + side * spacing, head_y - depth, head_z + height_off), p["eye_angle_deg"] * side


def add_eye_markers(name_prefix, joints, radii, p, mat, parent):
    """Creates eye spheres at world coords computed while `parent` still sits at the
    origin, then parents them to it — so translating `parent` afterward (to lay
    characters out side by side) carries the eyes along without re-deriving offsets."""
    for mirror, tag in ((False, "L"), (True, "R")):
        pos, angle = eye_marker_positions(joints, radii, p, mirror)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, location=pos, segments=12, ring_count=8)
        eye = bpy.context.active_object
        eye.name = f"{name_prefix}_eye_{tag}"
        eye.scale = (1.0, 0.35, 0.6)
        eye.rotation_euler = (0, 0, math.radians(angle))
        eye.data.materials.append(mat)
        eye.parent = parent


def build_mesh(name, joints, radii, edges):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    names = list(joints.keys())
    index_of = {n: i for i, n in enumerate(names)}
    mesh.from_pydata([joints[n] for n in names], [(index_of[a], index_of[b]) for a, b in edges], [])
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
    subsurf.levels = subsurf.render_levels = 2
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


def setup_scene():
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    if scene.world:
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(target)
    constraint = cam_obj.constraints.new(type="TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"

    for lname, energy, loc, rot in (("Key", 3.0, (2, -3, 4), (0.9, 0, 0.6)), ("Fill", 1.0, (-2, -2, 2), (1.1, 0, -0.8))):
        light = bpy.data.lights.new(lname, type="SUN")
        light.energy = energy
        light_obj = bpy.data.objects.new(lname, light)
        light_obj.location = loc
        light_obj.rotation_euler = rot
        bpy.context.collection.objects.link(light_obj)

    return cam_obj, target


def frame_and_render(cam_obj, target, objs, view, path, margin=1.25):
    aspect = bpy.context.scene.render.resolution_x / bpy.context.scene.render.resolution_y
    xs, ys, zs = [], [], []
    for obj in objs:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
    min_x, max_x, min_y, max_y, min_z, max_z = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    cx, cy, cz = (min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2
    height = max_z - min_z

    if view == "front":
        width = max_x - min_x
        cam_obj.location = (cx, cy - 5.0, cz)
    else:  # profile
        width = max_y - min_y
        cam_obj.location = (cx - 5.0, cy, cz)
    target.location = (cx, cy, cz)
    cam_obj.data.ortho_scale = max(width, height * aspect) * margin

    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def label_image(path, lines):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(path).convert("RGB")
    band_h = 26 * (len(lines) + 1)
    canvas = Image.new("RGB", (img.width, img.height + band_h), (20, 20, 22))
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        # layout_engine=BASIC sidesteps a raqm text-shaping bug (observed with this
        # Pillow/FreeType combo) that occasionally rasterizes a multi-hundred-megapixel
        # mask for an ordinary short line and trips Pillow's decompression-bomb guard.
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20,
                                   layout_engine=ImageFont.Layout.BASIC)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16,
                                         layout_engine=ImageFont.Layout.BASIC)
    except OSError:
        font = font_small = ImageFont.load_default()
    y = img.height + 6
    draw.text((10, y), lines[0], fill=(255, 255, 255), font=font)
    for line in lines[1:]:
        y += 24
        draw.text((10, y), line, fill=(200, 200, 205), font=font_small)
    canvas.save(path)


def param_summary(name, p):
    return [
        f"{name}",
        f"height {p['height_m']:.2f}m  shoulder x{p['shoulder_scale']:.2f}  body_fat {p['body_fat']:.2f}  leg x{p['leg_length_scale']:.2f}",
        f"face_width x{p['face_width_scale']:.2f}  eye_spacing x{p['eye_spacing_scale']:.2f}  eye_angle {p['eye_angle_deg']:+.0f}deg",
    ]


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    return args[args.index("--outdir") + 1] if "--outdir" in args else "assets/characters/stylization_prototype_v1_1"


def main():
    outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)
    clear_scene()
    edges = all_edges()

    eye_mat = bpy.data.materials.new("eye_marker")
    eye_mat.use_nodes = True
    eye_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.08, 1.0)

    cam_obj, target = setup_scene()
    built = {}
    spacing = 1.6

    for i, (char_name, p) in enumerate(CHARACTERS.items()):
        real_joints = compute_realistic_joints(p)
        real_radii = compute_realistic_radii(p)
        style_joints, style_radii = stylize(real_joints, real_radii)

        real_obj = build_mesh(f"{char_name}_realistic", real_joints, real_radii, edges)
        add_eye_markers(f"{char_name}_realistic", real_joints, real_radii, p, eye_mat, real_obj)
        style_obj = build_mesh(f"{char_name}_stylized", style_joints, style_radii, edges)
        add_eye_markers(f"{char_name}_stylized", style_joints, style_radii, p, eye_mat, style_obj)

        real_obj.location.x = i * spacing
        style_obj.location.x = i * spacing + spacing * len(CHARACTERS)

        built[char_name] = {"real": real_obj, "style": style_obj}

    # Per-character labeled front+profile renders (realistic and stylized).
    for char_name, objs in built.items():
        for variant, obj in objs.items():
            related = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(obj.name)]
            for o in bpy.data.objects:
                if o.type == "MESH":
                    o.hide_render = o not in related
            for view in ("front", "profile"):
                path = os.path.join(outdir, f"{char_name}_{variant}_{view}.png")
                frame_and_render(cam_obj, target, related, view, path)
                label_image(path, param_summary(f"{char_name} ({variant}, {view})", CHARACTERS[char_name]))

    # The key comparison: C vs D, stylized only, front — the near-identical hard case.
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not (o.name.startswith("C_stylized") or o.name.startswith("D_stylized"))
    hard_case_objs = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]
    path = os.path.join(outdir, "hard_case_C_vs_D_stylized_front.png")
    frame_and_render(cam_obj, target, hard_case_objs, "front", path)
    label_image(path, ["C vs D - near-identical bodies, small face/eye differences only",
                        "This is the test v1 did NOT run. Extreme A/B was the easy case."])

    for o in bpy.data.objects:
        o.hide_render = False if o.type == "MESH" else o.hide_render

    print(f"Wrote v1.1 outputs to {outdir}")


if __name__ == "__main__":
    main()
