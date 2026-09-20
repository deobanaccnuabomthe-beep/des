"""
Renders quick preview stills of an exported character .glb at different shape-key
states, so a human can eyeball the placeholder mesh without opening Blender.

Run headless:
    blender --background --python tools/blender/render_preview.py -- \
        --input assets/characters/base_mesh_placeholder.glb \
        --outdir /tmp/character_previews
"""

import os
import sys

import bpy


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []

    def get(flag, default):
        return args[args.index(flag) + 1] if flag in args else default

    return get("--input", "assets/characters/base_mesh_placeholder.glb"), get("--outdir", "/tmp/character_previews")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def setup_scene():
    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in dir(bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items) else "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 768
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)

    import math

    camera_data = bpy.data.cameras.new("PreviewCam")
    camera_data.lens = 35
    camera_data.sensor_fit = "VERTICAL"
    camera_data.sensor_height = 36
    camera_obj = bpy.data.objects.new("PreviewCam", camera_data)
    camera_obj.location = (0, -3.4, 0.9)
    camera_obj.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(camera_obj)
    bpy.context.scene.camera = camera_obj

    light_data = bpy.data.lights.new("KeyLight", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("KeyLight", light_data)
    light_obj.location = (2, -3, 4)
    light_obj.rotation_euler = (0.9, 0, 0.6)
    bpy.context.collection.objects.link(light_obj)

    fill_data = bpy.data.lights.new("FillLight", type="SUN")
    fill_data.energy = 1.0
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    fill_obj.location = (-2, -2, 2)
    fill_obj.rotation_euler = (1.1, 0, -0.8)
    bpy.context.collection.objects.link(fill_obj)


def find_mesh_object():
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            return obj
    raise RuntimeError("No mesh object found after import")


def set_shape_keys(mesh_obj, values: dict):
    keys = mesh_obj.data.shape_keys
    if not keys:
        return
    for block in keys.key_blocks:
        block.value = values.get(block.name, 0.0)


def render(outpath):
    bpy.context.scene.render.filepath = outpath
    bpy.ops.render.render(write_still=True)


def main():
    input_path, outdir = parse_args()
    os.makedirs(outdir, exist_ok=True)

    clear_scene()
    setup_scene()
    bpy.ops.import_scene.gltf(filepath=input_path)
    mesh_obj = find_mesh_object()

    set_shape_keys(mesh_obj, {})
    render(os.path.join(outdir, "default.png"))

    set_shape_keys(mesh_obj, {"body_muscle": 0.8, "body_fat": 0.6, "shoulder_wide": 1.0})
    render(os.path.join(outdir, "stress_combo.png"))

    set_shape_keys(mesh_obj, {"body_thin": 1.0, "height_tall": 1.0})
    render(os.path.join(outdir, "thin_tall.png"))

    print(f"Wrote previews to {outdir}")


if __name__ == "__main__":
    main()
