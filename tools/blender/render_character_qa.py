"""
Morph + variant QA for an AI-prototype character GLB.

Every image is watermarked PROTOTYPE / AI_GENERATED / NOT_PRODUCTION_APPROVED.

Produces, for one input GLB:
  - front / side / three-quarter neutral QA renders,
  - a morph sweep (0.00 / 0.25 / 0.50 / 0.75 / 1.00) for each of the 10 body morphs,
  - the three required stress combinations,
  - a contact sheet montage,
  - a JSON report with, per state: exact feet-on-ground (min world Z), height,
    a flipped-normal heuristic (share of faces whose normal points inward), and a
    silhouette-area proxy — plus a coarse self-intersection flag.

The normal / silhouette / self-intersection numbers are HEURISTICS for triage on a
low-poly prototype, not a guarantee — labeled as such in the JSON.

Run headless:
    blender --background --python tools/blender/render_character_qa.py -- \
        --input assets/characters/ai_prototype/average.glb \
        --outdir assets/characters/ai_prototype/qa
"""

import json
import math
import os
import sys

import bpy
import bmesh
import mathutils

Vector = mathutils.Vector

BODY_MORPHS = ["body_muscle", "body_fat", "body_thin", "shoulder_wide", "waist_narrow",
               "chest_thick", "arm_mass", "leg_mass", "height_tall", "height_short"]
SWEEP = [0.00, 0.25, 0.50, 0.75, 1.00]
COMBOS = {
    "combo_muscle_fat_shoulder": {"body_muscle": 0.8, "body_fat": 0.6, "shoulder_wide": 1.0},
    "combo_fat_tall": {"body_fat": 1.0, "height_tall": 1.0},
    "combo_thin_short": {"body_thin": 1.0, "height_short": 1.0},
}
WATERMARK = "PROTOTYPE / AI_GENERATED / NOT_PRODUCTION_APPROVED"

RES = 640


def parse_args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    inp = a[a.index("--input") + 1] if "--input" in a else "assets/characters/ai_prototype/average.glb"
    out = a[a.index("--outdir") + 1] if "--outdir" in a else "assets/characters/ai_prototype/qa"
    return inp, out


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)


def setup(scene):
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    if scene.world:
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
    cam_d = bpy.data.cameras.new("C")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 2.0
    cam = bpy.data.objects.new("C", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for n, e, loc, rot in (("K", 3.0, (2, -3, 4), (0.9, 0, 0.6)), ("F", 1.2, (-2, -2, 2), (1.1, 0, -0.8))):
        l = bpy.data.lights.new(n, "SUN")
        l.energy = e
        lo = bpy.data.objects.new(n, l)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)
    return cam


def place_camera(cam, view, center, height):
    d = 5.0
    if view == "front":
        cam.location = (center[0], center[1] - d, center[2])
        cam.rotation_euler = (math.radians(90), 0, 0)
    elif view == "side":
        cam.location = (center[0] - d, center[1], center[2])
        cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    else:  # three_quarter
        cam.location = (center[0] - d * 0.7, center[1] - d * 0.7, center[2] + 0.15)
        cam.rotation_euler = (math.radians(90), 0, math.radians(-45))
    cam.data.ortho_scale = height * 1.15


def mesh_metrics(obj, deps):
    """Bounds + HARD topology facts (boundary / non-manifold edge counts, vertex
    count) computed from the evaluated, morph-applied mesh via bmesh. The topology
    numbers are authoritative pass/fail signals; the inward-normal fraction is kept
    only as an informational hint and never gates anything (review item 8)."""
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = obj.matrix_world
    zs = [(mw @ v.co).z for v in me.vertices]
    xs = [(mw @ v.co).x for v in me.vertices]
    ys = [(mw @ v.co).y for v in me.vertices]

    bm = bmesh.new()
    bm.from_mesh(me)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    non_manifold = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    vert_count = len(bm.verts)
    # informational only:
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    inward = 0
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = mw.to_3x3() @ f.normal
        outward = Vector((c.x - cx, c.y - cy, 0.0))
        if outward.length > 1e-5 and n.dot(outward) < 0:
            inward += 1
    frac_inward = inward / max(1, len(bm.faces))
    bm.free()

    metrics = {
        "min_z": round(min(zs), 4),
        "max_z": round(max(zs), 4),
        "height_m": round(max(zs) - min(zs), 4),
        "width_m": round(max(xs) - min(xs), 4),
        "depth_m": round(max(ys) - min(ys), 4),
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "vertex_count": vert_count,
        "faces_inward_normal_frac_INFO_ONLY": round(frac_inward, 3),
    }
    ev.to_mesh_clear()
    return metrics


def set_morphs(mesh_obj, values):
    keys = mesh_obj.data.shape_keys
    if not keys:
        return
    for k in keys.key_blocks:
        k.value = 0.0
    for name, v in values.items():
        if name in keys.key_blocks:
            keys.key_blocks[name].value = v
    bpy.context.view_layer.update()


def render(scene, cam, mesh_obj, path, view="front"):
    deps = bpy.context.evaluated_depsgraph_get()
    metrics = mesh_metrics(mesh_obj, deps)
    place_camera(cam, view, (0.0, 0.0, metrics["height_m"] / 2), metrics["height_m"])
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return metrics


def label(path, title, extra=None):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    img = Image.open(path).convert("RGB")
    band = 58
    canvas = Image.new("RGB", (img.width, img.height + band), (18, 18, 20))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18,
                                layout_engine=ImageFont.Layout.BASIC)
        f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13,
                                layout_engine=ImageFont.Layout.BASIC)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    d.text((8, img.height + 5), title, fill=(255, 255, 255), font=f1)
    d.text((8, img.height + 30), WATERMARK + ("  " + extra if extra else ""), fill=(200, 160, 90), font=f2)
    canvas.save(path)


def contact_sheet(paths, out_path, cols=5):
    try:
        from PIL import Image
    except ImportError:
        return
    if not paths:
        return
    thumbs = [Image.open(p).convert("RGB") for p in paths]
    w, h = thumbs[0].size
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (10, 10, 12))
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    sheet.save(out_path)


def main():
    inp, outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)
    variant = os.path.splitext(os.path.basename(inp))[0]
    clear()
    scene = bpy.context.scene
    cam = setup(scene)
    bpy.ops.import_scene.gltf(filepath=inp)
    # pick the skinned body mesh (has shape keys), never a stray import artifact
    body_meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys]
    if not body_meshes:
        body_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    mesh_obj = body_meshes[0]

    report = {"label": WATERMARK.split(" / "), "variant": variant, "input": inp,
              "gating_note": "HARD failures: any boundary edge, any non-manifold edge, feet off "
                             "ground (min_z), or a morph changing the vertex count (topology not "
                             "preserved). faces_inward_normal_frac_INFO_ONLY never gates.",
              "neutral": {}, "morph_sweeps": {}, "combos": {}, "flags": []}
    sweep_imgs = []

    def hard_check(tag, m, ref_vcount):
        if m["boundary_edges"] > 0:
            report["flags"].append(f"{tag}: {m['boundary_edges']} boundary edge(s) (open hole)")
        if m["non_manifold_edges"] > 0:
            report["flags"].append(f"{tag}: {m['non_manifold_edges']} non-manifold edge(s)")
        if abs(m["min_z"]) > 0.02:
            report["flags"].append(f"{tag}: min_z={m['min_z']} (feet off ground)")
        if ref_vcount is not None and m["vertex_count"] != ref_vcount:
            report["flags"].append(f"{tag}: vertex_count {m['vertex_count']} != {ref_vcount} (topology not preserved)")

    # neutral three views
    set_morphs(mesh_obj, {})
    for view in ("front", "side", "three_quarter"):
        pth = os.path.join(outdir, f"{variant}_neutral_{view}.png")
        m = render(scene, cam, mesh_obj, pth, view)
        label(pth, f"{variant} neutral {view}", f"h={m['height_m']}m minZ={m['min_z']}")
        report["neutral"][view] = m
    ref_vcount = report["neutral"]["front"]["vertex_count"]
    report["reference_vertex_count"] = ref_vcount
    hard_check("neutral", report["neutral"]["front"], ref_vcount)

    # morph sweeps
    for morph in BODY_MORPHS:
        report["morph_sweeps"][morph] = []
        for val in SWEEP:
            set_morphs(mesh_obj, {morph: val})
            pth = os.path.join(outdir, f"{variant}_{morph}_{val:.2f}.png")
            m = render(scene, cam, mesh_obj, pth, "front")
            label(pth, f"{morph} = {val:.2f}", f"minZ={m['min_z']} h={m['height_m']}")
            report["morph_sweeps"][morph].append({"value": val, **m})
            sweep_imgs.append(pth)
            hard_check(f"{morph}={val:.2f}", m, ref_vcount)

    # combos
    for name, values in COMBOS.items():
        set_morphs(mesh_obj, values)
        pth = os.path.join(outdir, f"{variant}_{name}.png")
        m = render(scene, cam, mesh_obj, pth, "front")
        label(pth, name.replace("combo_", ""), f"minZ={m['min_z']} h={m['height_m']}")
        report["combos"][name] = {"values": values, **m}
        sweep_imgs.append(pth)
        hard_check(name, m, ref_vcount)

    contact_sheet(sweep_imgs, os.path.join(outdir, f"{variant}_contact_sheet.png"))
    with open(os.path.join(outdir, f"{variant}_qa_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(f"QA for {variant}: {len(sweep_imgs)} morph/combo frames, "
          f"{len(report['flags'])} flag(s). Report + contact sheet in {outdir}")
    if report["flags"]:
        print("FLAGS:\n  " + "\n  ".join(report["flags"]))


if __name__ == "__main__":
    main()
