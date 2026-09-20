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

# Required morph target names. Two profiles: "body" = the 10 body morphs
# (spec section 4 + AI pipeline v2 step 5), "full" = body + the 8 face morphs
# (spec 4b). Selected with --profile; default "full" (the placeholder ships face
# morphs, the AI body prototype does not — face is out of scope for v2).
BODY_MORPHS = {
    "body_muscle", "body_fat", "body_thin", "shoulder_wide", "waist_narrow",
    "chest_thick", "arm_mass", "leg_mass", "height_tall", "height_short",
}
FACE_MORPHS = {
    "face_wide", "face_narrow", "jaw_square", "jaw_round", "eyes_wide_set",
    "eyes_close_set", "nose_wide", "nose_narrow",
}
MORPH_PROFILES = {"body": BODY_MORPHS, "full": BODY_MORPHS | FACE_MORPHS}
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


def validate(path, required_morphs=None):
    if required_morphs is None:
        required_morphs = MORPH_PROFILES["full"]
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

    # --- geometry counts ---
    vert_count = pos_acc["count"]
    if "indices" in prim:
        tri_count = gltf["accessors"][prim["indices"]]["count"] // 3
    else:
        tri_count = vert_count // 3
    check(results, "vertex_count", vert_count > 0, f"{vert_count} vertices", required=False)
    check(results, "triangle_count", tri_count > 0, f"{tri_count} triangles", required=False)

    # --- root transform (we bake normalization, so skinned-mesh nodes must be identity) ---
    bad_roots = []
    for node in gltf.get("nodes", []):
        if "mesh" in node:
            if node.get("scale", [1, 1, 1]) != [1, 1, 1] or \
               any(abs(t) > 1e-4 for t in node.get("translation", [0, 0, 0])):
                bad_roots.append(node.get("name"))
    check(results, "root_transform_identity", not bad_roots,
          f"non-identity mesh nodes: {bad_roots}" if bad_roots else "mesh node transforms are identity")

    # --- morph targets: names + count ---
    target_names = mesh.get("extras", {}).get("targetNames", [])
    target_set = set(target_names)
    missing_morphs = required_morphs - target_set
    check(results, "morph_names_exact", not missing_morphs,
          f"missing={sorted(missing_morphs)}" if missing_morphs
          else f"all {len(required_morphs)} required present ({len(target_names)} total)")
    check(results, "morph_count", len(prim.get("targets", [])) == len(target_names) >= len(required_morphs),
          f"{len(prim.get('targets', []))} morph accessors / {len(target_names)} names / need >= {len(required_morphs)}")

    # --- joints: must be actual MEMBERS of the exported skin, not just scene nodes ---
    nodes = gltf.get("nodes", [])
    skin_joint_names = set()
    if gltf.get("skins"):
        skin_joint_names = {nodes[i].get("name") for i in gltf["skins"][0].get("joints", [])}
    missing_skin_joints = REQUIRED_JOINTS - skin_joint_names
    check(results, "joints_in_skin", not missing_skin_joints,
          f"missing from skin.joints: {sorted(missing_skin_joints)}" if missing_skin_joints
          else f"all {len(REQUIRED_JOINTS)} spec bones are skin members")

    # --- parent/child hierarchy sanity for key chains ---
    name_to_idx = {n.get("name"): i for i, n in enumerate(nodes)}
    children_of = {i: set(n.get("children", [])) for i, n in enumerate(nodes)}
    required_links = [("chest", "shoulder.L"), ("shoulder.L", "upper_arm.L"),
                      ("upper_arm.L", "forearm.L"), ("forearm.L", "hand.L"),
                      ("hips", "thigh.L"), ("thigh.L", "shin.L"), ("shin.L", "foot.L"),
                      ("spine", "chest"), ("neck", "head")]
    broken_links = [f"{a}->{b}" for a, b in required_links
                    if a in name_to_idx and b in name_to_idx
                    and name_to_idx[b] not in children_of.get(name_to_idx[a], set())]
    check(results, "bone_hierarchy", not broken_links,
          f"broken parent->child: {broken_links}" if broken_links else "spec parent->child links intact")

    # --- zero-weight vertices ---
    if has_weights:
        zero_w = sum(1 for w in weights if sum(w) < 1e-6)
        check(results, "no_zero_weight_verts", zero_w == 0,
              f"{zero_w} vertices have all-zero weights", required=False)

    # --- animations: names + duration ---
    anim_names = {a.get("name") for a in gltf.get("animations", [])}
    missing_anims = REQUIRED_ANIMATIONS - anim_names
    check(results, "animation_clips", not missing_anims,
          f"missing={sorted(missing_anims)}" if missing_anims else f"{sorted(anim_names)}")
    durations = animation_durations(gltf, bin_chunk)
    check(results, "animation_durations_positive", all(d > 0 for d in durations.values()) and durations,
          ", ".join(f"{k}={v:.2f}s" for k, v in sorted(durations.items())) or "none")

    # --- topology QA (welded from indices) ---
    topo = analyze_topology(gltf, bin_chunk, prim, attrs)
    if topo is not None:
        check(results, "no_boundary_edges", topo["boundary_edges"] == 0,
              f"{topo['boundary_edges']} boundary edge(s) (unintended open holes)")
        check(results, "manifold_edges", topo["non_manifold_edges"] == 0,
              f"{topo['non_manifold_edges']} non-manifold edge(s) (>2 faces)")
        check(results, "no_loose_vertices", topo["loose_vertices"] == 0,
              f"{topo['loose_vertices']} loose vertex/vertices")
        check(results, "single_connected_component", topo["connected_components"] == 1,
              f"{topo['connected_components']} connected component(s) (body should be 1 watertight shell)")

    # --- height morph keeps feet on the ground (Y-up, at value 1.0) ---
    ground = height_morph_ground_contact(gltf, bin_chunk, prim, target_names, attrs)
    for morph, min_y in ground.items():
        check(results, f"{morph}_feet_grounded", abs(min_y) <= 0.02,
              f"min_Y at {morph}=1.0 is {min_y:+.4f} (want ~0)")

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


def analyze_topology(gltf, bin_chunk, prim, attrs):
    """Topology QA from the GLB triangle indices. glTF splits vertices at normal/UV
    seams, so positions are welded first (rounded key) — otherwise every hard edge
    would read as a false boundary. Returns boundary/non-manifold edge counts, loose
    vertex count, and connected-component count on the welded surface."""
    if "POSITION" not in attrs or "indices" not in prim:
        return None
    positions = read_accessor(gltf, bin_chunk, attrs["POSITION"])
    raw_idx = [i[0] for i in read_accessor(gltf, bin_chunk, prim["indices"])]

    # weld by rounded position
    weld = {}
    remap = []
    for pos in positions:
        key = (round(pos[0], 5), round(pos[1], 5), round(pos[2], 5))
        if key not in weld:
            weld[key] = len(weld)
        remap.append(weld[key])
    nverts = len(weld)

    edge_faces = {}
    used = set()
    tris = [raw_idx[i:i + 3] for i in range(0, len(raw_idx), 3)]
    for a, b, c in tris:
        wa, wb, wc = remap[a], remap[b], remap[c]
        used.update((wa, wb, wc))
        for u, v in ((wa, wb), (wb, wc), (wc, wa)):
            e = (min(u, v), max(u, v))
            edge_faces[e] = edge_faces.get(e, 0) + 1

    boundary = sum(1 for n in edge_faces.values() if n == 1)
    non_manifold = sum(1 for n in edge_faces.values() if n > 2)
    loose = nverts - len(used)

    # connected components via union-find over welded verts
    parent = list(range(nverts))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (u, v) in edge_faces:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
    components = len({find(i) for i in used}) if used else 0

    return {"welded_vertices": nverts, "boundary_edges": boundary,
            "non_manifold_edges": non_manifold, "loose_vertices": loose,
            "connected_components": components}


def animation_durations(gltf, bin_chunk):
    """Max keyframe time (seconds) per animation, read from sampler input accessors."""
    out = {}
    for anim in gltf.get("animations", []):
        tmax = 0.0
        for sampler in anim.get("samplers", []):
            acc = gltf["accessors"][sampler["input"]]
            if "max" in acc:
                tmax = max(tmax, acc["max"][0])
            else:
                times = read_accessor(gltf, bin_chunk, sampler["input"])
                tmax = max([tmax] + [t[0] for t in times])
        out[anim.get("name", "?")] = tmax
    return out


def height_morph_ground_contact(gltf, bin_chunk, prim, target_names, attrs):
    """min world Y with a height morph fully applied (value 1.0) = basis POSITION +
    that morph's POSITION delta. Confirms feet stay on the ground under height morphs."""
    out = {}
    if "POSITION" not in attrs or not prim.get("targets"):
        return out
    basis = read_accessor(gltf, bin_chunk, attrs["POSITION"])
    for morph in ("height_tall", "height_short"):
        if morph not in target_names:
            continue
        ti = target_names.index(morph)
        target = prim["targets"][ti]
        if "POSITION" not in target:
            continue
        delta = read_accessor(gltf, bin_chunk, target["POSITION"])
        min_y = min(basis[i][1] + delta[i][1] for i in range(len(basis)))
        out[morph] = min_y
    return out


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
    argv = sys.argv[1:]
    flag_vals = {"--json", "--profile"}
    positional = [a for i, a in enumerate(argv)
                  if not a.startswith("--") and (i == 0 or argv[i - 1] not in flag_vals)]
    path = positional[0] if positional else "assets/characters/base_mesh_placeholder.glb"
    json_out = argv[argv.index("--json") + 1] if "--json" in argv else None
    profile = argv[argv.index("--profile") + 1] if "--profile" in argv else "full"
    results = validate(path, MORPH_PROFILES.get(profile, MORPH_PROFILES["full"]))

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

    if json_out:
        summary = {
            "glb": path,
            "required_failed": required_failed,
            "passed": required_failed == 0,
            "checks": [{k: r[k] for k in ("check", "ok", "detail", "required")}
                       for r in results if not r.get("info")],
        }
        with open(json_out, "w") as f:
            json.dump(summary, f, indent=2)

    print()
    if required_failed:
        print(f"{required_failed} REQUIRED check(s) failed.")
        sys.exit(1)
    print("All required checks passed.")


if __name__ == "__main__":
    main()
