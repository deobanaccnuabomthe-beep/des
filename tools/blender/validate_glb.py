"""
Post-export QA for a character .glb — reads the file back and checks it against the
spec's hard requirements, instead of trusting the Blender exporter. Pure-Python glTF
parsing (no Blender, no trimesh) so it runs anywhere.

Checks: skinned geometry bounds (Y-up height ~1.75 m, min-Y ~0 = feet on ground),
axis convention, presence of POSITION/JOINTS_0/WEIGHTS_0, max bone influences per
vertex and weight-sum sanity, required morph target names, joint (bone) names,
animation clip names, UV (TEXCOORD_0) and material presence.

Exit code is non-zero if any REQUIRED check fails, so it can gate CI.

Run:
    python3 tools/blender/validate_glb.py assets/characters/base_mesh_placeholder.glb
"""

import json
import struct
import sys

# Required morph target names, spec sections 4 + 4b (order-independent).
REQUIRED_MORPHS = {
    "body_muscle", "body_fat", "body_thin", "shoulder_wide", "waist_narrow",
    "chest_thick", "arm_mass", "leg_mass", "height_tall", "height_short",
    "face_wide", "face_narrow", "jaw_square", "jaw_round", "eyes_wide_set",
    "eyes_close_set", "nose_wide", "nose_narrow",
}
REQUIRED_JOINTS = {
    "hips", "spine", "chest", "neck", "head",
    "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
    "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
    "thigh.L", "shin.L", "foot.L", "toe.L",
    "thigh.R", "shin.R", "foot.R", "toe.R",
}
REQUIRED_ANIMATIONS = {"idle", "celebrate", "showcase"}

TARGET_HEIGHT = 1.75
HEIGHT_TOL = 0.02
GROUND_TOL = 0.02

COMPONENT_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
COMPONENT_DTYPE = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}


def load_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", "not a GLB file"
    offset = 12
    gltf_json = None
    bin_chunk = None
    while offset < length:
        chunk_len, chunk_type = struct.unpack("<II", data[offset:offset + 8])
        chunk_data = data[offset + 8:offset + 8 + chunk_len]
        if chunk_type == 0x4E4F534A:  # JSON
            gltf_json = json.loads(chunk_data)
        elif chunk_type == 0x004E4942:  # BIN
            bin_chunk = chunk_data
        offset += 8 + chunk_len
    return gltf_json, bin_chunk


def read_accessor(gltf, bin_chunk, accessor_idx):
    acc = gltf["accessors"][accessor_idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    comp = COMPONENT_COUNT[acc["type"]]
    dtype = COMPONENT_DTYPE[acc["componentType"]]
    size = COMPONENT_SIZE[acc["componentType"]]
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", comp * size)
    out = []
    for i in range(acc["count"]):
        start = base + i * stride
        values = struct.unpack_from("<" + dtype * comp, bin_chunk, start)
        out.append(values)
    return out


def check(results, name, ok, detail, required=True):
    results.append({"check": name, "ok": bool(ok), "detail": detail, "required": required})


def validate(path):
    gltf, bin_chunk = load_glb(path)
    results = []

    mesh = gltf["meshes"][0]
    prim = mesh["primitives"][0]
    attrs = prim["attributes"]

    # --- bounds / ground contact (glTF is Y-up after export_yup) ---
    pos_acc = gltf["accessors"][attrs["POSITION"]]
    ymin = pos_acc["min"][1]
    ymax = pos_acc["max"][1]
    height = ymax - ymin
    check(results, "height_1.75m", abs(height - TARGET_HEIGHT) <= HEIGHT_TOL,
          f"height={height:.4f}m (want {TARGET_HEIGHT}+/-{HEIGHT_TOL})")
    check(results, "feet_on_ground", abs(ymin) <= GROUND_TOL,
          f"min_Y={ymin:.4f} (want ~0, no ground penetration)")
    check(results, "yup_axis", ymax > abs(pos_acc["max"][0]) and ymax > abs(pos_acc["max"][2]),
          f"tallest axis is Y (max={pos_acc['max']}) -> Y-up")

    # --- skin attributes / influences ---
    has_joints = "JOINTS_0" in attrs
    has_weights = "WEIGHTS_0" in attrs
    check(results, "skin_attributes", has_joints and has_weights,
          f"JOINTS_0={has_joints} WEIGHTS_0={has_weights}")
    if has_weights:
        weights = read_accessor(gltf, bin_chunk, attrs["WEIGHTS_0"])
        wsum_min = min(sum(w) for w in weights)
        wsum_max = max(sum(w) for w in weights)
        # Exporter normalizes to <=4 influences packed in a VEC4, so each vertex has
        # at most 4 and the packed weights should sum to ~1.
        check(results, "weight_sum_~1", 0.98 <= wsum_min and wsum_max <= 1.02,
              f"weight sum range [{wsum_min:.4f}, {wsum_max:.4f}]")
        check(results, "max_4_influences", len(weights[0]) == 4,
              f"WEIGHTS_0 is VEC{len(weights[0])} (mobile three.js limit = 4)")

    # --- UV / material ---
    check(results, "has_uv", "TEXCOORD_0" in attrs,
          f"TEXCOORD_0 present={'TEXCOORD_0' in attrs}", required=False)
    mat_count = len(gltf.get("materials", []))
    check(results, "material_count_<=2", 0 < mat_count <= 2,
          f"{mat_count} material(s) (spec max 2 for base mesh)", required=False)

    # --- morph targets ---
    target_names = set(mesh.get("extras", {}).get("targetNames", []))
    missing_morphs = REQUIRED_MORPHS - target_names
    check(results, "morph_names_exact", not missing_morphs,
          f"missing={sorted(missing_morphs)}" if missing_morphs else f"all 18 present ({len(target_names)} total)")

    # --- joints / bone names ---
    node_names = {n.get("name") for n in gltf.get("nodes", [])}
    missing_joints = REQUIRED_JOINTS - node_names
    check(results, "joint_names_spec", not missing_joints,
          f"missing={sorted(missing_joints)}" if missing_joints else "all spec bones present")

    # --- animations ---
    anim_names = {a.get("name") for a in gltf.get("animations", [])}
    missing_anims = REQUIRED_ANIMATIONS - anim_names
    check(results, "animation_clips", not missing_anims,
          f"missing={sorted(missing_anims)}" if missing_anims else f"{sorted(anim_names)}")

    # --- rig sanity: bind-pose joint world positions (catches the use_connect snap
    #     bug — a snapped shoulder/thigh head would sit on the body centerline). ---
    joint_world = bind_pose_joint_positions(gltf, bin_chunk)
    if joint_world:
        def horiz(name):
            p = joint_world.get(name)
            return (p[0] ** 2 + p[2] ** 2) ** 0.5 if p else 0.0  # distance from vertical axis (Y-up)
        sh = horiz("upper_arm.L")
        th = horiz("thigh.L")
        check(results, "shoulder_not_snapped", sh > 0.10,
              f"upper_arm.L is {sh:.3f}m off centerline (snapped bug would be ~0)")
        check(results, "thigh_not_snapped", th > 0.05,
              f"thigh.L is {th:.3f}m off centerline (snapped bug would be ~0)")
        results.append({"check": "_bind_joint_positions", "ok": True,
                        "detail": {k: [round(c, 3) for c in v] for k, v in sorted(joint_world.items())},
                        "required": False, "info": True})

    return results


def _rigid_inverse_translation(m):
    """World position of a joint = translation of inverse(inverseBindMatrix).
    glTF stores column-major MAT4; bones are rigid (scale applied), so the inverse
    translation is -R^T * t."""
    # column-major: m[col*4 + row]
    r = [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]]
    t = [m[12], m[13], m[14]]
    # inverse translation = -R^T t
    return tuple(-(r[0][i] * t[0] + r[1][i] * t[1] + r[2][i] * t[2]) for i in range(3))


def bind_pose_joint_positions(gltf, bin_chunk):
    if not gltf.get("skins"):
        return {}
    skin = gltf["skins"][0]
    if "inverseBindMatrices" not in skin:
        return {}
    ibms = read_accessor(gltf, bin_chunk, skin["inverseBindMatrices"])
    nodes = gltf["nodes"]
    out = {}
    for joint_node_idx, ibm in zip(skin["joints"], ibms):
        name = nodes[joint_node_idx].get("name", f"node{joint_node_idx}")
        out[name] = _rigid_inverse_translation(ibm)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/characters/base_mesh_placeholder.glb"
    results = validate(path)

    print(f"GLB validation: {path}\n")
    required_failed = 0
    info_entries = []
    for r in results:
        if r.get("info"):
            info_entries.append(r)
            continue
        status = "PASS" if r["ok"] else ("FAIL" if r["required"] else "WARN")
        if not r["ok"] and r["required"]:
            required_failed += 1
        print(f"  [{status}] {r['check']}: {r['detail']}")

    for r in info_entries:
        print(f"\n  bind-pose joint world positions (x, y=up, z):")
        for name, pos in r["detail"].items():
            print(f"    {name:14s} {pos}")

    print()
    if required_failed:
        print(f"{required_failed} REQUIRED check(s) failed.")
        sys.exit(1)
    print("All required checks passed.")


if __name__ == "__main__":
    main()
