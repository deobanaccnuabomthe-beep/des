"""
LIFE RPG — Character Pipeline v2 (local PROCEDURAL fallback).

Every output is PROTOTYPE / PROCEDURAL_GENERATED / NOT_PRODUCTION_APPROVED.

No human artist, and in this environment no reachable external AI mesh service
(Tripo/Meshy) and no MPFB/MB-Lab addon — see docs/PLUGIN_STATUS.md. This is a LOCAL,
deterministic PROCEDURAL generator (not an external AI model), so the manifest label is
PROCEDURAL_GENERATED.

Topology approach (fixes the v2a tube prototype, which had 80 boundary edges and 5
disconnected shells): the body is built ONCE with Blender's Skin modifier on a connected,
branching skeleton, which welds the arms and legs into the torso as a SINGLE watertight
manifold surface (no open boundaries, no seams). That frozen mesh M — its vertices and
faces — is the one canonical topology.

  - average.glb = M (canonical neutral base) + the 10 body morphs.
  - lean.glb / fat.glb = the SAME topology M with a thin / fat displacement field baked
    into the basis (comparison outputs, not separate progression bases), + the morphs.

Because every variant and every shape key is an analytic displacement of the same frozen
M vertex list, topology is identical across all of them and all morphs preserve it.

Rig: hand-built armature with the exact spec bone names, branch bones (chest->shoulder,
hips->thigh) intentionally unconnected. Rigify is available but its naming does not match
the required convention (docs/PLUGIN_STATUS.md).

Run:
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

# --- Skin skeleton (for mesh generation only; NOT the rig). Elliptical radii
#     (rx=half-width, ry=half-depth) give real torso volume (belly deeper than wide). ---
SKIN_JOINTS: Dict[str, Tuple[float, float, float]] = {
    "pelvis": (0.0, 0.0, 0.94), "belly": (0.0, 0.01, 1.06), "waist": (0.0, 0.0, 1.17),
    "chest": (0.0, 0.0, 1.32), "shoulders": (0.0, 0.0, 1.44), "neck": (0.0, 0.0, 1.50),
    "head": (0.0, 0.0, 1.60), "head_top": (0.0, 0.0, 1.70),
    "shoulder.L": (0.06, 0.0, 1.46), "upper_arm.L": (0.18, 0.0, 1.43),
    "forearm.L": (0.37, 0.0, 1.24), "hand.L": (0.50, 0.0, 1.00),
    "thigh.L": (0.09, 0.0, 0.92), "shin.L": (0.10, 0.0, 0.50),
    "foot.L": (0.10, 0.0, 0.10), "toe.L": (0.10, 0.12, 0.03),
}
SKIN_RADII: Dict[str, Tuple[float, float]] = {
    "pelvis": (0.155, 0.125), "belly": (0.150, 0.140), "waist": (0.120, 0.100),
    "chest": (0.175, 0.140), "shoulders": (0.140, 0.110), "neck": (0.055, 0.055),
    "head": (0.100, 0.110), "head_top": (0.050, 0.050),
    "shoulder.L": (0.062, 0.062), "upper_arm.L": (0.060, 0.060),
    "forearm.L": (0.048, 0.048), "hand.L": (0.045, 0.045),
    "thigh.L": (0.110, 0.110), "shin.L": (0.070, 0.070),
    "foot.L": (0.055, 0.055), "toe.L": (0.040, 0.040),
}
SKIN_EDGES = [
    ("pelvis", "belly"), ("belly", "waist"), ("waist", "chest"), ("chest", "shoulders"),
    ("shoulders", "neck"), ("neck", "head"), ("head", "head_top"),
    ("shoulders", "shoulder.L"), ("shoulder.L", "upper_arm.L"),
    ("upper_arm.L", "forearm.L"), ("forearm.L", "hand.L"),
    ("pelvis", "thigh.L"), ("thigh.L", "shin.L"), ("shin.L", "foot.L"), ("foot.L", "toe.L"),
]
SKIN_ROOT = "pelvis"


def _mirror(d, is_radii=False):
    out = dict(d)
    for name, val in list(d.items()):
        if name.endswith(".L"):
            r = name.replace(".L", ".R")
            out[r] = val if is_radii else (-val[0], val[1], val[2])
    return out


def skin_joints():
    return _mirror(SKIN_JOINTS)


def skin_radii():
    return _mirror(SKIN_RADII, is_radii=True)


def skin_edges():
    e = list(SKIN_EDGES)
    for a, b in SKIN_EDGES:
        if a.endswith(".L") or b.endswith(".L"):
            e.append((a.replace(".L", ".R") if a.endswith(".L") else a,
                       b.replace(".L", ".R") if b.endswith(".L") else b))
    return e


def build_frozen_base():
    """Skin modifier -> one watertight manifold mesh; returns (verts, faces) of the
    frozen canonical topology, plus the joint dict for field computations."""
    joints = skin_joints()
    radii = skin_radii()
    edges = skin_edges()

    mesh = bpy.data.meshes.new("skin_skeleton")
    names = list(joints.keys())
    idx = {n: i for i, n in enumerate(names)}
    mesh.from_pydata([joints[n] for n in names], [(idx[a], idx[b]) for a, b in edges], [])
    mesh.update()
    obj = bpy.data.objects.new("BaseTmp", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    skin = obj.modifiers.new("Skin", type="SKIN")
    layer = mesh.skin_vertices[0].data
    for n, i in idx.items():
        layer[i].radius = radii[n]
    layer[idx[SKIN_ROOT]].use_root = True
    sub = obj.modifiers.new("Subsurf", type="SUBSURF")
    sub.levels = sub.render_levels = 2
    bpy.ops.object.modifier_apply(modifier=skin.name)
    bpy.ops.object.modifier_apply(modifier=sub.name)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    verts = [v.co.copy() for v in obj.data.vertices]
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    bpy.data.objects.remove(obj, do_unlink=True)
    return verts, faces, joints


# ---------------------------------------------------------------------------
# Analytic displacement fields — used both for the 10 morphs and for the
# lean/fat variant bake. All operate on the frozen vertex list, so topology
# is preserved exactly.
# ---------------------------------------------------------------------------
def _closest_on_seg(pt, a, b):
    ab = b - a
    d = ab.length_squared
    if d < 1e-9:
        return a
    t = max(0.0, min(1.0, (pt - a).dot(ab) / d))
    return a + ab * t


def radial_push(coords, segments, radius, amount):
    out = [Vector((0, 0, 0)) for _ in coords]
    for i, co in enumerate(coords):
        best = None
        for a, b in segments:
            c = _closest_on_seg(co, a, b)
            dist = (co - c).length
            if best is None or dist < best[0]:
                best = (dist, c)
        dist, c = best
        if dist >= radius:
            continue
        fall = (1.0 - dist / radius) ** 2
        dirv = co - c
        if dirv.length < 1e-6:
            continue
        out[i] = dirv.normalized() * (amount * fall)
    return out


def add(*fields):
    n = len(fields[0])
    return [sum((f[i] for f in fields), Vector((0, 0, 0))) for i in range(n)]


def seg(joints, a, b):
    return (Vector(joints[a]), Vector(joints[b]))


def bump(coords, center, extent, amount, direction=None):
    """Smooth ellipsoidal region bump: vertices inside the ellipsoid (radii=extent)
    around `center` move by `amount` * quadratic-falloff, either radially outward
    (direction=None) or along a fixed `direction`. This gives anatomically-placed
    volume (deltoid, pectoral, biceps, glute, calf) without spikes, since the falloff
    is smooth and the region is broad."""
    cx = Vector(center)
    ex, ey, ez = extent
    fixed = Vector(direction).normalized() if direction is not None else None
    out = [Vector((0, 0, 0)) for _ in coords]
    for i, co in enumerate(coords):
        d = Vector(((co.x - cx.x) / ex, (co.y - cx.y) / ey, (co.z - cx.z) / ez))
        r = d.length
        if r >= 1.0:
            continue
        fall = (1.0 - r) ** 2
        if fixed is not None:
            out[i] = fixed * (amount * fall)
        else:
            dirv = co - cx
            if dirv.length < 1e-6:
                continue
            out[i] = dirv.normalized() * (amount * fall)
    return out


def mirror_bumps(coords, center_L, extent, amount, direction_L=None):
    """Place a symmetric pair of bumps at +/-X. For a fixed direction, the X sign is
    mirrored so both sides push outward consistently."""
    cx, cy, cz = center_L
    right_dir = None
    if direction_L is not None:
        right_dir = (-direction_L[0], direction_L[1], direction_L[2])
    return add(
        bump(coords, (cx, cy, cz), extent, amount, direction_L),
        bump(coords, (-cx, cy, cz), extent, amount, right_dir),
    )


def shoulder_wide_field(coords, joints, amount=0.075):
    """Widen the shoulders: push the deltoid/upper-arm-root region outward along X so
    the shoulder span visibly broadens. Peak at shoulder height, smooth falloff — no
    spike. Also nudges the very top of the arm outward so the silhouette widens."""
    out = [Vector((0, 0, 0)) for _ in coords]
    z_peak, z_span = 1.44, 0.16
    for i, co in enumerate(coords):
        if abs(co.x) < 0.04 or abs(co.z - z_peak) > z_span:
            continue
        zfall = (1.0 - abs(co.z - z_peak) / z_span) ** 2
        # taper laterally so the outer arm is carried out a bit but the hand is not
        lat = max(0.0, 1.0 - max(0.0, abs(co.x) - 0.30) / 0.25)
        sign = 1.0 if co.x >= 0 else -1.0
        out[i] = Vector((sign * amount * zfall * lat, 0, 0))
    return out


def waist_narrow_field(coords, joints, amount=0.075):
    """Pull the waist in (both X and Y) with a torso-only vertical falloff centred on
    the waist station, for a clear V-taper."""
    out = [Vector((0, 0, 0)) for _ in coords]
    z_waist, z_span = 1.17, 0.13
    for i, co in enumerate(coords):
        if abs(co.z - z_waist) > z_span:
            continue
        # only the torso shell, not arms passing nearby
        if abs(co.x) > 0.22:
            continue
        zfall = (1.0 - abs(co.z - z_waist) / z_span) ** 2
        radial = Vector((co.x, co.y, 0.0))
        if radial.length < 1e-6:
            continue
        out[i] = radial.normalized() * (-amount * zfall)
    return out


def fat_field(coords, joints, s=1.0):
    """Belly (front-heavy) + waist + hips/glute + chest fullness + fuller face."""
    torso = [seg(joints, "pelvis", "belly"), seg(joints, "belly", "waist"),
             seg(joints, "waist", "chest")]
    hips = [seg(joints, "pelvis", "thigh.L"), seg(joints, "pelvis", "thigh.R")]
    head = [seg(joints, "head", "head")]
    belly_front = bump(coords, (0.0, 0.13, 1.07), (0.16, 0.14, 0.14), 0.06 * s, direction=(0, 1, 0))
    glute = mirror_bumps(coords, (0.08, -0.10, 0.95), (0.12, 0.12, 0.14), 0.035 * s, direction_L=(0, -1, 0))
    return add(
        radial_push(coords, torso, radius=0.30, amount=0.075 * s),
        radial_push(coords, hips, radius=0.24, amount=0.05 * s),
        radial_push(coords, head, radius=0.14, amount=0.032 * s),
        belly_front, glute,
    )


def thin_field(coords, joints, s=1.0):
    body = [seg(joints, "pelvis", "belly"), seg(joints, "belly", "waist"),
            seg(joints, "waist", "chest"),
            seg(joints, "upper_arm.L", "forearm.L"), seg(joints, "upper_arm.R", "forearm.R"),
            seg(joints, "thigh.L", "shin.L"), seg(joints, "thigh.R", "shin.R")]
    return radial_push(coords, body, radius=0.26, amount=-0.05 * s)


def muscle_field(coords, joints, s=1.0):
    """Region-aware: deltoid, pectoral, biceps, thigh and calf bumps, so the muscular
    direction reads anatomically rather than as a uniform tube inflation."""
    deltoid = mirror_bumps(coords, (0.17, 0.0, 1.44), (0.11, 0.11, 0.10), 0.045 * s)
    pectoral = mirror_bumps(coords, (0.07, 0.11, 1.33), (0.10, 0.09, 0.10), 0.04 * s, direction_L=(0, 1, 0))
    biceps = mirror_bumps(coords, (0.275, 0.0, 1.335), (0.09, 0.09, 0.13), 0.04 * s)
    thigh = mirror_bumps(coords, (0.10, 0.0, 0.80), (0.13, 0.13, 0.16), 0.045 * s)
    calf = mirror_bumps(coords, (0.10, -0.02, 0.38), (0.10, 0.10, 0.12), 0.04 * s)
    shoulders = shoulder_wide_field(coords, joints, amount=0.03 * s)
    return add(deltoid, pectoral, biceps, thigh, calf, shoulders)


def morph_fields(coords, joints):
    """The 10 body morphs as analytic fields on the frozen base."""
    return {
        "body_muscle": muscle_field(coords, joints),
        "body_fat": fat_field(coords, joints, s=0.9),
        "body_thin": thin_field(coords, joints),
        "shoulder_wide": shoulder_wide_field(coords, joints, amount=0.075),
        "waist_narrow": waist_narrow_field(coords, joints, amount=0.055),
        "chest_thick": mirror_bumps(coords, (0.06, 0.12, 1.33), (0.12, 0.10, 0.12), 0.05, direction_L=(0, 1, 0)),
        "arm_mass": radial_push(coords, [seg(joints, "upper_arm.L", "forearm.L"), seg(joints, "forearm.L", "hand.L"),
                                          seg(joints, "upper_arm.R", "forearm.R"), seg(joints, "forearm.R", "hand.R")],
                                radius=0.13, amount=0.05),
        "leg_mass": radial_push(coords, [seg(joints, "thigh.L", "shin.L"), seg(joints, "shin.L", "foot.L"),
                                          seg(joints, "thigh.R", "shin.R"), seg(joints, "shin.R", "foot.R")],
                                radius=0.15, amount=0.055),
        "height_tall": [Vector((0, 0, co.z * 0.06)) for co in coords],
        "height_short": [Vector((0, 0, -co.z * 0.06)) for co in coords],
    }


# Variant basis = frozen base + a field (identity for average).
def variant_field(name, coords, joints):
    if name == "lean":
        return thin_field(coords, joints, s=1.0)
    if name == "fat":
        return fat_field(coords, joints, s=1.2)
    return [Vector((0, 0, 0)) for _ in coords]


# --- rig (spec bones; branch bones unconnected) ---
RIG_JOINTS = {
    "hips": (0.0, 0.0, 0.98), "spine": (0.0, 0.0, 1.10), "chest": (0.0, 0.0, 1.32),
    "neck": (0.0, 0.0, 1.50), "head": (0.0, 0.0, 1.60),
    "shoulder.L": (0.06, 0.0, 1.45), "upper_arm.L": (0.18, 0.0, 1.43),
    "forearm.L": (0.37, 0.0, 1.24), "hand.L": (0.50, 0.0, 1.00),
    "thigh.L": (0.09, 0.0, 0.95), "shin.L": (0.10, 0.0, 0.50),
    "foot.L": (0.10, 0.0, 0.10), "toe.L": (0.10, 0.12, 0.03),
}
RIG_EDGES = [
    ("hips", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head"),
    ("chest", "shoulder.L"), ("shoulder.L", "upper_arm.L"), ("upper_arm.L", "forearm.L"), ("forearm.L", "hand.L"),
    ("hips", "thigh.L"), ("thigh.L", "shin.L"), ("shin.L", "foot.L"), ("foot.L", "toe.L"),
]
RIG_BRANCH = {("chest", "shoulder.L"), ("chest", "shoulder.R"), ("hips", "thigh.L"), ("hips", "thigh.R")}


def rig_joints():
    return _mirror(RIG_JOINTS)


def rig_edges():
    e = list(RIG_EDGES)
    for a, b in RIG_EDGES:
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
        b = eb.new(name)
        b.head = Vector(joints[name])
        kids = [y for x, y in edges if x == name]
        b.tail = Vector(joints[kids[0]]) if kids else Vector(joints[name]) + Vector((0, 0, 0.05))
        created[name] = b
        return b

    for a, b in edges:
        ensure(a)
        ensure(b)
    for a, b in edges:
        created[b].parent = created[a]
        created[b].use_connect = (a, b) not in RIG_BRANCH
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def build_mesh(name, verts, faces):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    # Smart UV Project so the GLB carries a TEXCOORD_0 (unblocks skin/clothing tint,
    # texture-memory and UV-padding review). Auto-unwrap, not a hand-laid production UV.
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    mat = bpy.data.materials.new("skin")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.68, 0.58, 1.0)
    obj.data.materials.append(mat)
    return obj


def add_morphs(obj, basis_coords, joints):
    obj.shape_key_add(name="Basis")
    fields = morph_fields(basis_coords, joints)
    for morph, field in fields.items():
        key = obj.shape_key_add(name=morph)
        for i, co in enumerate(basis_coords):
            key.data[i].co = co + field[i]
        key.value = 0.0


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

    def new_action(n):
        a = bpy.data.actions.new(n)
        arm_obj.animation_data_create()
        arm_obj.animation_data.action = a
        a.use_fake_user = True
        return a

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
    # Seamless turntable: the last frame stops one frame-step short of a full turn, so
    # frame n and frame 1 are NOT the same 0deg/360deg pose. Looping frame n -> 1 then
    # advances exactly one step, with no duplicate-endpoint hitch.
    last_angle = 360.0 * (n - 1) / n
    for f, ang in [(1, 0.0), (n, math.radians(last_angle))]:
        kf("hips", f, rot=(0, 0, ang))
    bpy.ops.object.mode_set(mode="OBJECT")


def bounds_z(obj):
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    return min(zs), max(zs)


def normalize(mesh_obj, arm_obj, target=HEIGHT_M):
    mn, mx = bounds_z(mesh_obj)
    s = target / (mx - mn)
    z_off = -mn * s
    for o in (mesh_obj, arm_obj):
        o.scale = (s, s, s)
        o.location = (0, 0, z_off)
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")
    nmn, nmx = bounds_z(mesh_obj)
    return {"scale": round(s, 5), "min_z": round(nmn, 4), "height_m": round(nmx - nmn, 4)}


def export(path, mesh_obj, arm_obj):
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True,
                               use_selection=True, export_animations=True,
                               export_morph=True, export_skins=True, export_apply=False)


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                 bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b, do_unlink=True)


def build_variant(name, base_verts, faces, joints, outdir):
    clear()
    field = variant_field(name, base_verts, joints)
    basis = [base_verts[i] + field[i] for i in range(len(base_verts))]
    mesh_obj = build_mesh(f"{name}_body", basis, faces)
    add_morphs(mesh_obj, basis, joints)
    arm_obj = build_armature(rig_joints(), rig_edges())
    nb = normalize(mesh_obj, arm_obj)
    skin_to_armature(mesh_obj, arm_obj)
    add_animations(arm_obj)
    tris = sum(len(p.vertices) - 2 for p in mesh_obj.data.polygons)
    path = os.path.join(outdir, f"{name}.glb")
    export(path, mesh_obj, arm_obj)
    return {"variant": name, "vertices": len(mesh_obj.data.vertices), "triangles": tris,
            "height_m": nb["height_m"], "min_z": nb["min_z"], "glb": path}


def parse_args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[a.index("--outdir") + 1] if "--outdir" in a else "assets/characters/ai_prototype"


def main():
    outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)
    clear()
    base_verts, faces, joints = build_frozen_base()

    reports = {}
    # average first = canonical neutral base; lean/fat are comparison outputs.
    for name in ("average", "lean", "fat"):
        reports[name] = build_variant(name, base_verts, faces, joints, outdir)

    summary = {
        "labels": ["PROTOTYPE", "PROCEDURAL_GENERATED", "NOT_PRODUCTION_APPROVED"],
        "source_method": "local procedural Skin-modifier human (single watertight manifold)",
        "canonical_base": "average.glb",
        "comparison_outputs": ["lean.glb", "fat.glb"],
        "topology": {"vertices": reports["average"]["vertices"], "triangles": reports["average"]["triangles"],
                     "consistent_across_variants": True},
        "morphs": list(morph_fields(base_verts, joints).keys()),
        "variants": reports,
    }
    with open(os.path.join(outdir, "generation_report.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("Procedural pipeline v2 done:")
    print(json.dumps({k: {"verts": v["vertices"], "tris": v["triangles"], "h": v["height_m"]}
                      for k, v in reports.items()}, indent=2))


if __name__ == "__main__":
    main()
