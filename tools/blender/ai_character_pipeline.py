"""
LIFE RPG — AI-only Character Pipeline v2 (local parametric fallback).

Every output of this script is PROTOTYPE / AI_GENERATED / NOT_PRODUCTION_APPROVED.

Context: there is no human 3D artist and (in this environment) no reachable external
AI mesh service (Tripo/Meshy) and no MPFB/MB-Lab addon — see docs/PLUGIN_STATUS.md.
Per the pipeline rules, this falls back to a LOCAL PARAMETRIC human generator: a
cross-section (lofted-ring) body whose per-region girth is parameter-driven, so it
produces genuinely different abdomen / waist / chest / hips / face volumes — unlike
the capsule regression placeholder, which cannot.

One consistent base topology (same vertex order + faces) is shared across the lean /
average / fat variants and across all shape keys, so the 10 body morphs are real
topology-preserving vertex deltas.

Rig: a hand-built armature using the EXACT spec section-5 bone names
(hips/spine/chest/neck/head, shoulder/upper_arm/forearm/hand, thigh/shin/foot/toe),
with branch bones (chest->shoulder, hips->thigh) intentionally NOT connected. Rigify
is available in Blender but its generated bone names do not match this required
convention, so the "corrected equivalent hierarchy" (pipeline rule 7) is used and
this choice is recorded in AI_PIPELINE_MANIFEST.json.

Run headless (one variant per file, all from the same topology):
    blender --background --python tools/blender/ai_character_pipeline.py -- \
        --outdir assets/characters/ai_prototype
"""

import json
import math
import os
import sys
from typing import Dict, List, Tuple

import bpy
import mathutils

Vector = mathutils.Vector

HEIGHT_M = 1.75
RING_SEGMENTS = 16  # vertices per cross-section ring -> fixed topology

# ---------------------------------------------------------------------------
# Parametric body definition
#
# The body is built from tubes; each tube is a stack of cross-section "stations".
# A station's effective (width, depth) radius responds to body parameters, so a
# large `fat` value inflates belly/waist/hips/chest/face while `muscle` widens
# shoulders/chest/arms. `resp` maps a parameter name -> (d_width, d_depth) added
# per unit of that parameter (fractions of the base radius).
# ---------------------------------------------------------------------------

# Body parameters (0..~1). height_tall/short are handled as a direct vertical
# scale, not as girth, so they are not in this list.
BODY_PARAMS = ("fat", "muscle", "thin", "shoulder_wide", "waist_narrow",
               "chest_thick", "arm_mass", "leg_mass")


def p(**kw) -> Dict[str, float]:
    d = {k: 0.0 for k in BODY_PARAMS}
    d.update(kw)
    return d


# Variant parameter sets (all share the base topology).
VARIANTS = {
    "lean":    p(thin=0.85, muscle=0.30, fat=0.00),
    "average": p(fat=0.35, muscle=0.30),
    "fat":     p(fat=0.95, muscle=0.15),
}

# A station: (z, width, depth, resp). resp: param -> (d_width_frac, d_depth_frac).
# Torso + head as one tube (hips -> crown).
TORSO_STATIONS = [
    # z,     width, depth, resp
    (0.930, 0.150, 0.115, {"fat": (0.35, 0.35), "thin": (-0.28, -0.30), "waist_narrow": (-0.05, -0.05)}),  # pelvis/hips
    (1.010, 0.150, 0.120, {"fat": (0.45, 0.55), "thin": (-0.30, -0.34)}),                                   # lower belly
    (1.080, 0.140, 0.120, {"fat": (0.50, 0.70), "thin": (-0.32, -0.36)}),                                   # belly (max fat)
    (1.160, 0.128, 0.100, {"fat": (0.40, 0.55), "thin": (-0.30, -0.34), "waist_narrow": (-0.28, -0.30)}),   # waist
    (1.250, 0.150, 0.120, {"fat": (0.28, 0.40), "muscle": (0.16, 0.22), "chest_thick": (0.06, 0.34)}),      # lower chest
    (1.340, 0.172, 0.135, {"fat": (0.20, 0.28), "muscle": (0.30, 0.30), "chest_thick": (0.10, 0.40)}),      # chest
    (1.410, 0.205, 0.120, {"muscle": (0.34, 0.14), "shoulder_wide": (0.42, 0.10), "fat": (0.10, 0.12)}),    # shoulders
    (1.470, 0.070, 0.070, {"fat": (0.20, 0.20)}),                                                            # neck base
    (1.510, 0.058, 0.060, {}),                                                                               # neck
    (1.575, 0.082, 0.088, {"fat": (0.35, 0.30)}),                                                            # jaw (face fullness)
    (1.630, 0.094, 0.100, {"fat": (0.30, 0.24)}),                                                            # mid-face
    (1.685, 0.092, 0.098, {"fat": (0.16, 0.14)}),                                                            # cranium
    (1.735, 0.020, 0.022, {}),                                                                               # crown
]

# Legs: two vertical tubes. Given as (z, radius, resp), circular rings.
LEG_STATIONS = [
    (0.930, 0.098, {"fat": (0.30, 0.30), "leg_mass": (0.28, 0.28), "thin": (-0.24, -0.24)}),  # upper thigh
    (0.740, 0.092, {"fat": (0.26, 0.26), "leg_mass": (0.34, 0.34), "thin": (-0.26, -0.26)}),  # mid thigh
    (0.510, 0.062, {"leg_mass": (0.18, 0.18), "fat": (0.14, 0.14)}),                           # knee
    (0.360, 0.072, {"leg_mass": (0.30, 0.30), "fat": (0.16, 0.16)}),                           # calf
    (0.110, 0.045, {"fat": (0.10, 0.10)}),                                                      # ankle
]
LEG_X = 0.085  # hip half-separation

# Arms: two tubes angled down ~45deg (A-pose). Given as (t, radius, resp) where t is
# fraction 0..1 from shoulder to wrist; centerline goes from shoulder to hand joint.
ARM_STATIONS = [
    (0.00, 0.058, {"muscle": (0.34, 0.34), "arm_mass": (0.30, 0.30), "fat": (0.16, 0.16)}),  # deltoid
    (0.28, 0.050, {"muscle": (0.30, 0.30), "arm_mass": (0.34, 0.34), "fat": (0.14, 0.14)}),  # biceps
    (0.52, 0.041, {"arm_mass": (0.20, 0.20), "fat": (0.10, 0.10)}),                           # elbow
    (0.78, 0.040, {"arm_mass": (0.22, 0.22), "fat": (0.10, 0.10)}),                           # forearm
    (1.00, 0.034, {"fat": (0.06, 0.06)}),                                                      # wrist
]
ARM_SHOULDER = Vector((0.19, 0.0, 1.40))
ARM_HAND = Vector((0.52, 0.0, 1.00))  # A-pose: hand down and out


def eff_radius(base_w, base_d, resp, params) -> Tuple[float, float]:
    w, d = base_w, base_d
    for name, (dw, dd) in resp.items():
        v = params.get(name, 0.0)
        w += base_w * dw * v
        d += base_d * dd * v
    return max(0.01, w), max(0.01, d)


def ring(center: Vector, u: Vector, v: Vector, rw: float, rd: float) -> List[Vector]:
    verts = []
    for k in range(RING_SEGMENTS):
        a = 2.0 * math.pi * k / RING_SEGMENTS
        verts.append(center + u * (rw * math.cos(a)) + v * (rd * math.sin(a)))
    return verts


def perp_basis(axis: Vector) -> Tuple[Vector, Vector]:
    axis = axis.normalized()
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u).normalized()
    return u, v


def generate_vertices(params: Dict[str, float]) -> List[Vector]:
    """Builds the full vertex list for one parameter set. Vertex ORDER is fixed
    (torso rings, then head-crown cap, then L/R legs, then L/R arms), so any two
    calls share topology and can be subtracted to form a morph delta."""
    verts: List[Vector] = []

    # Torso + head tube (rings in XY plane, mirror-symmetric).
    for (z, bw, bd, resp) in TORSO_STATIONS:
        rw, rd = eff_radius(bw, bd, resp, params)
        verts += ring(Vector((0, 0, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), rw, rd)
    verts.append(Vector((0, 0, TORSO_STATIONS[-1][0] + 0.02)))  # crown cap point

    # Legs (two vertical tubes) + foot cap.
    for side in (+1, -1):
        for (z, br, resp) in LEG_STATIONS:
            rw, rd = eff_radius(br, br, resp, params)
            verts += ring(Vector((side * LEG_X, 0, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), rw, rd)
        # simple foot: a forward-offset cap point near the ground
        verts.append(Vector((side * LEG_X, 0.09, 0.03)))

    # Arms (two angled tubes) + hand cap.
    for side in (+1, -1):
        sh = Vector((side * ARM_SHOULDER.x, ARM_SHOULDER.y, ARM_SHOULDER.z))
        hn = Vector((side * ARM_HAND.x, ARM_HAND.y, ARM_HAND.z))
        axis = (hn - sh)
        u, v = perp_basis(axis)
        for (t, br, resp) in ARM_STATIONS:
            rw, rd = eff_radius(br, br, resp, params)
            center = sh.lerp(hn, t)
            verts += ring(center, u, v, rw, rd)
        verts.append(hn + axis.normalized() * 0.04)  # hand cap point

    return verts


def build_faces() -> List[Tuple[int, ...]]:
    """Face connectivity for the fixed topology. Computed once; identical for every
    parameter set. Indices follow the exact order generate_vertices() appends."""
    faces = []
    idx = 0

    def tube_faces(n_rings, cap_top=False, cap_bottom=False):
        nonlocal idx
        start = idx
        for r in range(n_rings - 1):
            for k in range(RING_SEGMENTS):
                a = start + r * RING_SEGMENTS + k
                b = start + r * RING_SEGMENTS + (k + 1) % RING_SEGMENTS
                c = start + (r + 1) * RING_SEGMENTS + (k + 1) % RING_SEGMENTS
                d = start + (r + 1) * RING_SEGMENTS + k
                faces.append((a, b, c, d))
        idx += n_rings * RING_SEGMENTS
        cap_idx = None
        if cap_top:
            cap_idx = idx
            idx += 1
            last = start + (n_rings - 1) * RING_SEGMENTS
            for k in range(RING_SEGMENTS):
                faces.append((last + k, last + (k + 1) % RING_SEGMENTS, cap_idx))
        return cap_idx

    tube_faces(len(TORSO_STATIONS), cap_top=True)          # torso+head, crown cap
    for _ in range(2):
        tube_faces(len(LEG_STATIONS), cap_top=True)         # each leg + foot cap
    for _ in range(2):
        tube_faces(len(ARM_STATIONS), cap_top=True)         # each arm + hand cap
    return faces


# ---------------------------------------------------------------------------
# Morph (shape key) definitions — perturbations of a variant's own params, so
# value 0 = that variant's neutral shape.
# ---------------------------------------------------------------------------
MORPH_PARAM_DELTAS = {
    "body_muscle":   {"muscle": 0.7},
    "body_fat":      {"fat": 0.6},
    "body_thin":     {"thin": 0.8},
    "shoulder_wide": {"shoulder_wide": 1.0},
    "waist_narrow":  {"waist_narrow": 1.0},
    "chest_thick":   {"chest_thick": 1.0},
    "arm_mass":      {"arm_mass": 1.0},
    "leg_mass":      {"leg_mass": 1.0},
}
# height_tall / height_short handled as vertical scale about Z=0 (feet stay grounded).
HEIGHT_MORPHS = {"height_tall": +0.06, "height_short": -0.06}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Force-remove ALL of these datablocks (do_unlink), not just zero-user ones:
    # actions carry use_fake_user=True so they never reach zero users and would
    # otherwise leak from one variant into the next variant's export (idle.001, ...).
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                 bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            coll.remove(block, do_unlink=True)


def build_mesh(name, verts, faces):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # NOTE: no remove_doubles — vertex count must stay exactly len(verts) so shape
    # keys map 1:1 by index and topology is identical across variants. Only fix
    # normal orientation.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

    mat = bpy.data.materials.new("skin")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.68, 0.58, 1.0)
    obj.data.materials.append(mat)
    return obj


def add_shape_keys(obj, base_verts, base_params):
    obj.shape_key_add(name="Basis")
    n = len(base_verts)
    for morph, deltas in MORPH_PARAM_DELTAS.items():
        target_params = dict(base_params)
        for k, dv in deltas.items():
            target_params[k] = min(1.5, target_params.get(k, 0.0) + dv)
        target_verts = generate_vertices(target_params)
        key = obj.shape_key_add(name=morph)
        for i in range(n):
            key.data[i].co = target_verts[i]
        key.value = 0.0
    for morph, amount in HEIGHT_MORPHS.items():
        key = obj.shape_key_add(name=morph)
        for i, co in enumerate(base_verts):
            key.data[i].co = Vector((co.x, co.y, co.z + co.z * amount))
        key.value = 0.0


# ---------------------------------------------------------------------------
# Rig (spec-named, branch bones not connected) — shared joint set across variants.
# ---------------------------------------------------------------------------
JOINTS = {
    "hips": (0.0, 0.0, 0.98), "spine": (0.0, 0.0, 1.10), "chest": (0.0, 0.0, 1.32),
    "neck": (0.0, 0.0, 1.50), "head": (0.0, 0.0, 1.62),
    "shoulder.L": (0.06, 0.0, 1.44), "upper_arm.L": (0.19, 0.0, 1.40),
    "forearm.L": (0.37, 0.0, 1.22), "hand.L": (0.50, 0.0, 1.00),
    "thigh.L": (0.085, 0.0, 0.95), "shin.L": (0.10, 0.0, 0.51),
    "foot.L": (0.10, 0.0, 0.10), "toe.L": (0.10, 0.12, 0.03),
}
EDGES = [
    ("hips", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head"),
    ("chest", "shoulder.L"), ("shoulder.L", "upper_arm.L"), ("upper_arm.L", "forearm.L"), ("forearm.L", "hand.L"),
    ("hips", "thigh.L"), ("thigh.L", "shin.L"), ("shin.L", "foot.L"), ("foot.L", "toe.L"),
]
BRANCH_EDGES = {("chest", "shoulder.L"), ("chest", "shoulder.R"), ("hips", "thigh.L"), ("hips", "thigh.R")}


def all_joints():
    j = dict(JOINTS)
    for name, pos in list(JOINTS.items()):
        if name.endswith(".L"):
            j[name.replace(".L", ".R")] = (-pos[0], pos[1], pos[2])
    return j


def all_edges():
    e = list(EDGES)
    for a, b in EDGES:
        if a.endswith(".L") or b.endswith(".L"):
            e.append((a.replace(".L", ".R") if a.endswith(".L") else a,
                       b.replace(".L", ".R") if b.endswith(".L") else b))
    return e


def build_armature(joints, edges):
    arm = bpy.data.armatures.new("Rig")
    arm_obj = bpy.data.objects.new("Armature", arm)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    created = {}

    def ensure(name):
        if name in created:
            return created[name]
        bone = eb.new(name)
        bone.head = Vector(joints[name])
        kids = [b for a, b in edges if a == name]
        bone.tail = Vector(joints[kids[0]]) if kids else Vector(joints[name]) + Vector((0, 0, 0.05))
        created[name] = bone
        return bone

    for a, b in edges:
        ensure(a)
        ensure(b)
    for a, b in edges:
        created[b].parent = created[a]
        created[b].use_connect = (a, b) not in BRANCH_EDGES
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def skin_to_armature(mesh_obj, arm_obj):
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


def add_animations(arm_obj):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    fps = bpy.context.scene.render.fps

    def new_action(name):
        act = bpy.data.actions.new(name)
        arm_obj.animation_data_create()
        arm_obj.animation_data.action = act
        act.use_fake_user = True
        return act

    def kf(bone, frame, loc=None, rot=None):
        b = arm_obj.pose.bones.get(bone)
        if not b:
            return
        if loc is not None:
            b.location = loc
            b.keyframe_insert("location", frame=frame)
        if rot is not None:
            b.rotation_mode = "XYZ"
            b.rotation_euler = rot
            b.keyframe_insert("rotation_euler", frame=frame)

    new_action("idle")
    n = int(3.5 * fps)
    for f, z in [(1, 0.0), (n // 2, 0.01), (n, 0.0)]:
        kf("chest", f, loc=(0, 0, z))

    new_action("celebrate")
    n = int(2 * fps)
    for f, ang in [(1, 0.0), (n // 2, math.radians(-70)), (n, math.radians(-70))]:
        kf("upper_arm.L", f, rot=(ang, 0, 0))
        kf("upper_arm.R", f, rot=(ang, 0, 0))

    new_action("showcase")
    n = int(4 * fps)
    for f, ang in [(1, 0.0), (n, math.radians(360))]:
        kf("hips", f, rot=(0, 0, ang))
    bpy.ops.object.mode_set(mode="OBJECT")


def mesh_bounds_z(mesh_obj):
    zs = [(mesh_obj.matrix_world @ v.co).z for v in mesh_obj.data.vertices]
    return min(zs), max(zs)


def normalize_to_height(mesh_obj, arm_obj, target_height=HEIGHT_M, target_min_z=0.0):
    min_z, max_z = mesh_bounds_z(mesh_obj)
    scale = target_height / (max_z - min_z)
    z_off = target_min_z - min_z * scale
    for obj in (mesh_obj, arm_obj):
        obj.scale = (scale, scale, scale)
        obj.location = (0.0, 0.0, z_off)
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    nmin, nmax = mesh_bounds_z(mesh_obj)
    return {"before": {"min_z": round(min_z, 4), "max_z": round(max_z, 4)},
            "scale": round(scale, 5),
            "after": {"min_z": round(nmin, 4), "max_z": round(nmax, 4), "height_m": round(nmax - nmin, 4)}}


def export_glb(path, mesh_obj, arm_obj):
    # use_selection so a stray/default scene object can never leak into the export.
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True,
                               use_selection=True,
                               export_animations=True, export_morph=True, export_skins=True,
                               export_apply=False)


def build_variant(variant_name, params, outdir):
    clear_scene()
    verts = generate_vertices(params)
    faces = build_faces()
    mesh_obj = build_mesh(f"{variant_name}_body", verts, faces)
    add_shape_keys(mesh_obj, [Vector(v) for v in verts], params)

    arm_obj = build_armature(all_joints(), all_edges())
    bounds = normalize_to_height(mesh_obj, arm_obj)
    skin_to_armature(mesh_obj, arm_obj)
    add_animations(arm_obj)

    tri_count = sum(len(poly.vertices) - 2 for poly in mesh_obj.data.polygons)
    vert_count = len(mesh_obj.data.vertices)

    path = os.path.join(outdir, f"{variant_name}.glb")
    export_glb(path, mesh_obj, arm_obj)
    return {"variant": variant_name, "params": params, "bounds": bounds,
            "triangles": tri_count, "vertices": vert_count, "glb": path}


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    return args[args.index("--outdir") + 1] if "--outdir" in args else "assets/characters/ai_prototype"


def main():
    outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)
    reports = {}
    for name, params in VARIANTS.items():
        reports[name] = build_variant(name, params, outdir)

    summary = {
        "label": ["PROTOTYPE", "AI_GENERATED", "NOT_PRODUCTION_APPROVED"],
        "source_method": "local parametric cross-section generator (Blender bpy)",
        "ring_segments": RING_SEGMENTS,
        "morphs": list(MORPH_PARAM_DELTAS.keys()) + list(HEIGHT_MORPHS.keys()),
        "variants": reports,
    }
    with open(os.path.join(outdir, "generation_report.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("AI pipeline v2 done:")
    print(json.dumps({k: {"triangles": v["triangles"], "vertices": v["vertices"],
                          "height_m": v["bounds"]["after"]["height_m"]} for k, v in reports.items()}, indent=2))


if __name__ == "__main__":
    main()
