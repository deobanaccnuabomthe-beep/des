"""
Generates a technical PLACEHOLDER character mesh for LIFE RPG, matching the
measurable requirements in docs/character-spec.md (units, orientation, origin,
A-pose, bone list, shape-key names, export format) so the app pipeline in
src/character/ can be exercised end to end before the commissioned artist
delivers the real base mesh.

This is NOT the stylized PSO2-like art the spec calls for — it is a rough
capsule humanoid built from Blender's Skin modifier. Its only job is to prove
morph targets, rig, and animation clips flow correctly through the .glb into
three.js.

Run headless:
    blender --background --python tools/blender/generate_placeholder_character.py \
        -- --output assets/characters/base_mesh_placeholder.glb
"""

import math
import sys
from typing import Dict, List, Tuple

import bpy
import mathutils

Vector = mathutils.Vector

HEIGHT_M = 1.75

# Joint positions in meters, Blender Z-up, origin at ground between the feet.
# A-pose: arms angled ~45 degrees down from horizontal, per spec section 3.
JOINTS: Dict[str, Tuple[float, float, float]] = {
    "hips": (0.0, 0.0, 0.98),
    "spine": (0.0, 0.0, 1.10),
    "chest": (0.0, 0.0, 1.32),
    "neck": (0.0, 0.0, 1.50),
    "head": (0.0, 0.0, 1.62),
    "head_top": (0.0, 0.0, 1.735),
    "shoulder.L": (0.17, 0.0, 1.46),
    "upper_arm.L": (0.17, 0.0, 1.46),
    "elbow.L": (0.37, 0.0, 1.26),
    "hand.L": (0.50, 0.0, 1.00),
    "thigh.L": (0.09, 0.0, 0.98),
    "knee.L": (0.10, 0.0, 0.52),
    "ankle.L": (0.10, 0.0, 0.10),
    "toe.L": (0.10, 0.13, 0.02),
}


def mirror_name(name: str) -> str:
    return name.replace(".L", ".R")


def mirrored_pos(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (-pos[0], pos[1], pos[2])


def all_joints() -> Dict[str, Tuple[float, float, float]]:
    joints = dict(JOINTS)
    for name, pos in list(JOINTS.items()):
        if name.endswith(".L"):
            joints[mirror_name(name)] = mirrored_pos(pos)
    return joints


# Skeleton edges as (parent, child) — also the armature's bone hierarchy.
EDGES: List[Tuple[str, str]] = [
    ("hips", "spine"),
    ("spine", "chest"),
    ("chest", "neck"),
    ("neck", "head"),
    ("head", "head_top"),
    ("chest", "shoulder.L"),
    ("shoulder.L", "elbow.L"),
    ("elbow.L", "hand.L"),
    ("hips", "thigh.L"),
    ("thigh.L", "knee.L"),
    ("knee.L", "ankle.L"),
    ("ankle.L", "toe.L"),
]


def all_edges() -> List[Tuple[str, str]]:
    edges = list(EDGES)
    for a, b in EDGES:
        if a.endswith(".L") or b.endswith(".L"):
            edges.append((mirror_name(a) if a.endswith(".L") else a,
                           mirror_name(b) if b.endswith(".L") else b))
    return edges


# Per-joint skin radius (meters), roughly the limb/torso half-thickness.
RADIUS: Dict[str, float] = {
    "hips": 0.15,
    "spine": 0.13,
    "chest": 0.17,
    "neck": 0.055,
    "head": 0.115,
    "head_top": 0.03,
    "shoulder.L": 0.07,
    "upper_arm.L": 0.07,
    "elbow.L": 0.05,
    "hand.L": 0.045,
    "thigh.L": 0.11,
    "knee.L": 0.075,
    "ankle.L": 0.055,
    "toe.L": 0.04,
}


def radius_for(name: str) -> float:
    base = name.replace(".R", ".L") if name.endswith(".R") else name
    return RADIUS.get(base, 0.07)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions, bpy.data.materials):
        for block in list(block_collection):
            if block.users == 0:
                block_collection.remove(block)


def build_skin_mesh(joints: Dict[str, Tuple[float, float, float]], edges: List[Tuple[str, str]]):
    mesh = bpy.data.meshes.new("body_skeleton")
    names = list(joints.keys())
    index_of = {name: i for i, name in enumerate(names)}
    verts = [joints[name] for name in names]
    edge_idx = [(index_of[a], index_of[b]) for a, b in edges]
    mesh.from_pydata(verts, edge_idx, [])
    mesh.update()

    obj = bpy.data.objects.new("Body", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    skin_mod = obj.modifiers.new("Skin", type="SKIN")
    skin_layer = mesh.skin_vertices[0].data
    for name, i in index_of.items():
        skin_layer[i].radius = (radius_for(name), radius_for(name))
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

    return obj, index_of


def add_materials(obj):
    skin_mat = bpy.data.materials.new("skin")
    skin_mat.use_nodes = True
    skin_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.68, 0.58, 1.0)
    obj.data.materials.append(skin_mat)


def closest_point_on_segment(p: Vector, a: Vector, b: Vector) -> Vector:
    ab = b - a
    denom = ab.length_squared
    if denom < 1e-9:
        return a
    t = max(0.0, min(1.0, (p - a).dot(ab) / denom))
    return a + ab * t


def build_shape_keys(obj, joints: Dict[str, Tuple[float, float, float]]):
    mesh = obj.data
    obj.shape_key_add(name="Basis")
    basis = mesh.shape_keys.key_blocks["Basis"]
    base_coords = [v.co.copy() for v in basis.data]
    joint_vecs = {name: Vector(pos) for name, pos in joints.items()}

    def bone_pair(prefix_l: str):
        return [(joint_vecs[prefix_l], joint_vecs[mirror_name(prefix_l)])] if prefix_l.endswith(".L") else \
               [(joint_vecs[prefix_l], joint_vecs[prefix_l])]

    def radial_push(segments: List[Tuple[Vector, Vector]], radius: float, amount: float):
        """Push vertices outward from the given bone segments, falling off with distance."""
        offsets = [Vector((0, 0, 0)) for _ in base_coords]
        for i, co in enumerate(base_coords):
            best = None
            for a, b in segments:
                closest = closest_point_on_segment(co, a, b)
                dist = (co - closest).length
                if best is None or dist < best[0]:
                    best = (dist, closest)
            dist, closest = best
            if dist >= radius:
                continue
            falloff = (1.0 - dist / radius) ** 2
            direction = co - closest
            if direction.length < 1e-6:
                continue
            direction.normalize()
            offsets[i] = direction * (amount * falloff)
        return offsets

    def axis_push(z_range: Tuple[float, float], x_min_abs: float, axis: Vector, amount: float, falloff_edge: float = 0.05):
        offsets = [Vector((0, 0, 0)) for _ in base_coords]
        z_lo, z_hi = z_range
        for i, co in enumerate(base_coords):
            if not (z_lo <= co.z <= z_hi) or abs(co.x) < x_min_abs:
                continue
            edge_dist = min(co.z - z_lo, z_hi - co.z)
            falloff = min(1.0, edge_dist / falloff_edge) if falloff_edge > 0 else 1.0
            sign = 1.0 if co.x >= 0 else -1.0
            offsets[i] = axis * (amount * falloff) * (sign if axis.x != 0 else 1.0)
        return offsets

    def make_shape_key(name: str, offsets: List[Vector]):
        key = obj.shape_key_add(name=name)
        for i, co in enumerate(base_coords):
            key.data[i].co = co + offsets[i]
        key.value = 0.0
        return key

    torso_limbs = [
        (joint_vecs["chest"], joint_vecs["shoulder.L"]),
        (joint_vecs["chest"], joint_vecs["shoulder.R"]),
        (joint_vecs["shoulder.L"], joint_vecs["elbow.L"]),
        (joint_vecs["shoulder.R"], joint_vecs["elbow.R"]),
        (joint_vecs["hips"], joint_vecs["thigh.L"]),
        (joint_vecs["hips"], joint_vecs["thigh.R"]),
        (joint_vecs["thigh.L"], joint_vecs["knee.L"]),
        (joint_vecs["thigh.R"], joint_vecs["knee.R"]),
        (joint_vecs["hips"], joint_vecs["spine"]),
        (joint_vecs["spine"], joint_vecs["chest"]),
    ]
    make_shape_key("body_muscle", radial_push(torso_limbs, radius=0.22, amount=0.055))

    torso_only = [(joint_vecs["hips"], joint_vecs["spine"]), (joint_vecs["spine"], joint_vecs["chest"]),
                  (joint_vecs["head"], joint_vecs["head"])]
    make_shape_key("body_fat", radial_push(torso_only, radius=0.26, amount=0.06))
    make_shape_key("body_thin", radial_push(torso_limbs, radius=0.24, amount=-0.035))

    make_shape_key(
        "shoulder_wide",
        axis_push((1.40, 1.52), x_min_abs=0.10, axis=Vector((1, 0, 0)), amount=0.05),
    )
    make_shape_key(
        "waist_narrow",
        radial_push([(joint_vecs["hips"], joint_vecs["spine"])], radius=0.20, amount=-0.035),
    )
    make_shape_key(
        "chest_thick",
        axis_push((1.20, 1.42), x_min_abs=0.0, axis=Vector((0, 1, 0)), amount=0.04),
    )
    make_shape_key(
        "arm_mass",
        radial_push(
            [(joint_vecs["shoulder.L"], joint_vecs["elbow.L"]), (joint_vecs["elbow.L"], joint_vecs["hand.L"]),
             (joint_vecs["shoulder.R"], joint_vecs["elbow.R"]), (joint_vecs["elbow.R"], joint_vecs["hand.R"])],
            radius=0.14, amount=0.045,
        ),
    )
    make_shape_key(
        "leg_mass",
        radial_push(
            [(joint_vecs["thigh.L"], joint_vecs["knee.L"]), (joint_vecs["knee.L"], joint_vecs["ankle.L"]),
             (joint_vecs["thigh.R"], joint_vecs["knee.R"]), (joint_vecs["knee.R"], joint_vecs["ankle.R"])],
            radius=0.16, amount=0.045,
        ),
    )
    make_shape_key(
        "height_tall",
        legwise_stretch(joint_vecs, base_coords, direction=1.0),
    )
    make_shape_key(
        "height_short",
        legwise_stretch(joint_vecs, base_coords, direction=-1.0),
    )

    head_z = joint_vecs["head"].z
    head_region = [(v, v) for v in [joint_vecs["head"]]]
    make_shape_key("face_wide", axis_push((head_z - 0.10, head_z + 0.10), x_min_abs=0.02, axis=Vector((1, 0, 0)), amount=0.03))
    make_shape_key("face_narrow", axis_push((head_z - 0.10, head_z + 0.10), x_min_abs=0.02, axis=Vector((1, 0, 0)), amount=-0.025))
    make_shape_key("jaw_square", axis_push((head_z - 0.13, head_z - 0.02), x_min_abs=0.01, axis=Vector((1, 0, 0)), amount=0.025))
    make_shape_key("jaw_round", radial_push(head_region, radius=0.10, amount=0.02))
    make_shape_key("eyes_wide_set", axis_push((head_z - 0.02, head_z + 0.03), x_min_abs=0.02, axis=Vector((1, 0, 0)), amount=0.02))
    make_shape_key("eyes_close_set", axis_push((head_z - 0.02, head_z + 0.03), x_min_abs=0.02, axis=Vector((1, 0, 0)), amount=-0.018))
    make_shape_key("nose_wide", axis_push((head_z - 0.03, head_z + 0.02), x_min_abs=0.0, axis=Vector((0, -1, 0)), amount=0.015))
    make_shape_key("nose_narrow", axis_push((head_z - 0.03, head_z + 0.02), x_min_abs=0.0, axis=Vector((0, -1, 0)), amount=-0.012))


def legwise_stretch(joint_vecs, base_coords, direction: float) -> List[Vector]:
    hips_z = joint_vecs["hips"].z
    offsets = [Vector((0, 0, 0)) for _ in base_coords]
    for i, co in enumerate(base_coords):
        if co.z < hips_z:
            offsets[i] = Vector((0, 0, -0.05 * direction * (1.0 - co.z / hips_z)))
        elif co.z >= hips_z:
            span = 1.0
            t = min(1.0, (co.z - hips_z) / span)
            offsets[i] = Vector((0, 0, 0.05 * direction * t))
    return offsets


BONE_NAME_EXCLUDE = {"head_top"}


def build_armature(joints: Dict[str, Tuple[float, float, float]], edges: List[Tuple[str, str]]):
    """Builds the rig from the same joint graph used for the skin mesh, minus the
    head_top helper joint (spec section 5 doesn't call for a bone there — it only
    exists to round out the head shape)."""
    bone_edges = [(a, b) for a, b in edges if a not in BONE_NAME_EXCLUDE and b not in BONE_NAME_EXCLUDE]

    arm_data = bpy.data.armatures.new("BodyArmature")
    arm_obj = bpy.data.objects.new("Armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = arm_data.edit_bones
    created = {}

    def ensure_bone(name):
        if name in created:
            return created[name]
        bone = edit_bones.new(name)
        bone.head = Vector(joints[name])
        children = [b for a, b in bone_edges if a == name]
        if children:
            bone.tail = Vector(joints[children[0]])
        else:
            bone.tail = Vector(joints[name]) + Vector((0, 0, 0.05))
        created[name] = bone
        return bone

    for parent, child in bone_edges:
        ensure_bone(parent)
        ensure_bone(child)
    for parent, child in bone_edges:
        if parent in created and child in created:
            created[child].parent = created[parent]
            created[child].use_connect = True

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
        action = bpy.data.actions.new(name)
        arm_obj.animation_data_create()
        arm_obj.animation_data.action = action
        return action

    chest = arm_obj.pose.bones.get("chest")
    hand_l = arm_obj.pose.bones.get("hand.L")
    hand_r = arm_obj.pose.bones.get("hand.R")
    shoulder_l = arm_obj.pose.bones.get("shoulder.L")
    shoulder_r = arm_obj.pose.bones.get("shoulder.R")

    def keyframe(bone, frame, location=None, rotation_euler=None):
        if location is not None:
            bone.location = location
            bone.keyframe_insert("location", frame=frame)
        if rotation_euler is not None:
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = rotation_euler
            bone.keyframe_insert("rotation_euler", frame=frame)

    # idle: 3.5s loop, subtle chest bob
    new_action("idle")
    idle_len = int(3.5 * fps)
    for frame, z in [(1, 0.0), (idle_len // 2, 0.01), (idle_len, 0.0)]:
        keyframe(chest, frame, location=(0, 0, z))
    arm_obj.animation_data.action.use_fake_user = True

    # celebrate: 2s one-shot, arms raised
    new_action("celebrate")
    cel_len = int(2 * fps)
    if shoulder_l and shoulder_r:
        keyframe(shoulder_l, 1, rotation_euler=(0, 0, 0))
        keyframe(shoulder_r, 1, rotation_euler=(0, 0, 0))
        keyframe(shoulder_l, cel_len // 2, rotation_euler=(math.radians(-70), 0, 0))
        keyframe(shoulder_r, cel_len // 2, rotation_euler=(math.radians(-70), 0, 0))
        keyframe(shoulder_l, cel_len, rotation_euler=(math.radians(-70), 0, 0))
        keyframe(shoulder_r, cel_len, rotation_euler=(math.radians(-70), 0, 0))
    arm_obj.animation_data.action.use_fake_user = True

    # showcase: 4s loop, full turntable spin on the root bone
    new_action("showcase")
    show_len = int(4 * fps)
    hips = arm_obj.pose.bones.get("hips")
    for frame, angle in [(1, 0.0), (show_len, 360.0)]:
        keyframe(hips, frame, rotation_euler=(0, 0, math.radians(angle)))
    arm_obj.animation_data.action.use_fake_user = True

    bpy.ops.object.mode_set(mode="OBJECT")


def finalize_transforms(mesh_obj, arm_obj):
    for obj in (mesh_obj, arm_obj):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        obj.select_set(False)


def export_glb(path: str):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_yup=True,
        export_animations=True,
        export_morph=True,
        export_skins=True,
        export_apply=False,
    )


def parse_args():
    argv = sys.argv
    if "--" not in argv:
        return "assets/characters/base_mesh_placeholder.glb"
    idx = argv.index("--")
    args = argv[idx + 1:]
    if "--output" in args:
        return args[args.index("--output") + 1]
    return "assets/characters/base_mesh_placeholder.glb"


def main():
    output_path = parse_args()
    clear_scene()

    joints = all_joints()
    edges = all_edges()

    mesh_obj, _ = build_skin_mesh(joints, edges)
    add_materials(mesh_obj)
    build_shape_keys(mesh_obj, joints)

    arm_obj = build_armature(joints, edges)
    skin_to_armature(mesh_obj, arm_obj)
    add_animations(arm_obj)
    finalize_transforms(mesh_obj, arm_obj)

    export_glb(output_path)
    print(f"Exported placeholder character to {output_path}")


if __name__ == "__main__":
    main()
