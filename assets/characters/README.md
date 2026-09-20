Place delivered assets here, matching the file list in the spec (section 8):

- `base_mesh.glb` — base mesh, rig, all blend shapes, animation clips, embedded textures
- `clothing/<item_id>.glb` — one file per clothing item, blend shapes named identically to the base mesh

`base_mesh_placeholder.glb` referenced by `App.tsx` does not exist yet — swap in the real
delivered file and update the `require(...)` path once the artist hands off the first draft.
