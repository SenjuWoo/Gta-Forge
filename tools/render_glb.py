"""Render a .glb to a transparent PNG for the README (Blender, headless).

  blender -b -P tools/render_glb.py -- <in.glb> <out.png> [size] [yaw_degrees]

Used by tools/make_presentation.py on assets the forge extracted from the local game install
(ragekit rpf cat -> ragekit gltf). Three-point lighting, EEVEE, transparent film.
"""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
src, out = args[0], args[1]
size = int(args[2]) if len(args) > 2 else 1200
yaw = math.radians(float(args[3])) if len(args) > 3 else math.radians(35)

keep = {int(x) for x in args[4].split(",")} if len(args) > 4 and args[4] else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name)
if keep is not None:
    # a ped .ydd holds every component variant; keep one drawable per component (indices in file order)
    for i, o in enumerate(meshes):
        if i not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for i, o in enumerate(meshes) if i in keep]

# Hair and other card geometry carry coverage in the diffuse alpha; the export marks them opaque.
for o in meshes:
    for slot in o.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        img = next((n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image
                    and "_diff" in n.image.name.lower()), None)
        if bsdf and img and "hair" in (img.image.name + mat.name).lower() and not bsdf.inputs["Alpha"].links:
            mat.node_tree.links.new(img.outputs["Alpha"], bsdf.inputs["Alpha"])
            if hasattr(mat, "surface_render_method"):
                mat.surface_render_method = "DITHERED"
            elif hasattr(mat, "blend_method"):
                mat.blend_method = "HASHED"
pts =[o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center, extent = (lo + hi) / 2, (hi - lo)
radius = extent.length / 2

scene = bpy.context.scene
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 70
scene.collection.objects.link(cam)
dist = radius / math.tan(cam.data.angle / 2) * 1.08
cam.location = center + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, radius * 0.45))
cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam


def light(name, energy, loc, color=(1, 1, 1), size_=2.0):
    l = bpy.data.lights.new(name, "AREA")
    l.energy, l.color, l.size = energy, color, size_
    o = bpy.data.objects.new(name, l)
    o.location = center + Vector(loc) * radius
    o.rotation_euler = (center - o.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(o)


light("key", 900 * radius ** 2, (2.2, -2.4, 2.6), (1.0, 0.92, 0.85))
light("fill", 260 * radius ** 2, (-2.6, -1.6, 1.2), (0.75, 0.85, 1.0))
light("rim", 700 * radius ** 2, (0.4, 3.0, 2.2), (1.0, 0.35, 0.7))

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.015, 0.04, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = size
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX" if "AgX" in [t.name for t in []] else scene.view_settings.view_transform
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("RENDERED", out, scene.render.engine, len(meshes), "meshes")
