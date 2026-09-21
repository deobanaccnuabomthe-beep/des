# AI Character Pipeline v2

**Every output of this pipeline is `PROTOTYPE` / `PROCEDURAL_GENERATED` / `NOT_PRODUCTION_APPROVED`.**

> Label note: `PROCEDURAL_GENERATED`, not `AI_GENERATED` — this iteration uses a local
> deterministic procedural generator, not an external AI model.

There is no human 3D artist and the project does not block on one. This pipeline produces
a parametric human base, normalizes and validates it through Blender, and generates three
body variants (lean / average / fat) plus a full morph + QA pass — all offline and
deterministic. When an external AI mesh service or a parametric-human addon becomes
available it slots in at the import step without changing anything downstream.

## Files

| File | Role |
|---|---|
| `tools/blender/ai_character_pipeline.py` | Generate lean/average/fat GLBs from one parametric topology |
| `tools/blender/validate_glb.py` | Post-export GLB QA gate (pure Python, CI-friendly) |
| `tools/blender/render_character_qa.py` | Morph sweeps, combos, contact sheet, QA JSON |
| `AI_PIPELINE_MANIFEST.json` | Source method, tooling, params, dims, morphs, bones, validator result, limitations |
| `docs/PLUGIN_STATUS.md` | Plugin/service availability + why the local fallback |
| `assets/characters/ai_prototype/{lean,average,fat}.glb` | The three variants |
| `assets/characters/ai_prototype/qa/` | Validation JSON, QA reports, contact sheets, renders |

## Run it

```
# 1. Generate the three variants (one consistent topology)
blender --background --python tools/blender/ai_character_pipeline.py -- \
    --outdir assets/characters/ai_prototype

# 2. Validate each GLB (exit non-zero on any required failure)
python3 tools/blender/validate_glb.py assets/characters/ai_prototype/fat.glb \
    --profile body --json assets/characters/ai_prototype/qa/fat_validation.json

# 3. Morph + variant QA (renders + contact sheet + report)
blender --background --python tools/blender/render_character_qa.py -- \
    --input assets/characters/ai_prototype/fat.glb \
    --outdir assets/characters/ai_prototype/qa
```

## How the procedural human works (watertight rebuild)

The first v2 attempt built the body from separate cross-section tubes; a topology review
found that gave **80 boundary edges and 5 disconnected shells** with visible seams and a
shoulder spike. That approach is abandoned.

The body is now built **once** with Blender's **Skin modifier** on a connected, branching
skeleton (spine with belly/waist/chest nodes, plus arm and leg chains, with elliptical
radii for real torso volume). The Skin modifier welds the arms and legs into the torso as
a **single watertight manifold surface**: 0 boundary edges, 0 non-manifold edges, 1
connected component, no seams. That frozen mesh `M` (its vertices + faces) is the one
canonical topology.

- `average.glb` = `M` (canonical neutral base) + the 10 body morphs.
- `lean.glb` / `fat.glb` = the **same topology** `M` with a thin / fat displacement field
  baked into the basis — comparison outputs, not separate progression bases.

Every variant basis and every shape key is an **analytic displacement of the same frozen
`M` vertex list** (radial-falloff pushes for girth, a Z-scale about the ground for
height), so topology is identical across all of them and all morphs preserve it. The
`shoulder_wide` morph uses a broad, smoothly-falling-off region push (not a single-ring
scale), so there is no needle/spike at any value.

Rig: a hand-built armature using the exact spec bone names, with branch bones
(`chest->shoulder`, `hips->thigh`) intentionally unconnected. Rigify is available but its
naming does not match the required convention (see `PLUGIN_STATUS.md`).

## Honest status — read this before trusting any output

### 1. What is technically validated (measured, not eyeballed)
- **Watertight manifold**: 0 boundary edges, 0 non-manifold edges, 0 loose vertices, 1 connected component (checked by welding the GLB indices by position). Confirmed on all three variants and, via the render QA, at every morph value and stress combo.
- **Topology preserved by every morph**: vertex count is constant (2700) across all morph states; identical topology (2700 verts / 5392 tris) across lean/average/fat.
- Bounds: exactly 1.75 m tall, feet at Z=0 (min_Y=0.0000 in the Y-up GLB), origin between feet.
- Axis: Blender Z-up source exported as glTF Y-up; mesh node transforms are identity.
- Skin: `JOINTS_0`/`WEIGHTS_0` present, weight sums ~1.0, max 4 influences, zero zero-weight verts.
- All 21 required bones are **actual members of the exported skin** (not just scene nodes), with the spec parent→child chains intact and shoulder/thigh not snapped to the centerline.
- 10 body morph names + count exact; 3 animation clips with correct durations.
- Height morphs keep feet on the ground at value 1.0 (checked from the exported morph deltas).
- All three variants pass the validator with zero required failures (UV absence is a WARN).

### 2. What is visually plausible (looks right, not proven)
- Three clearly distinct, seamless body types; the fat variant reads as fuller in abdomen, waist, chest, hips and face, with a rounder silhouette (see `qa/*_contact_sheet.png` and the 3-up variant render).
- Each morph sweeps smoothly across 0.25/0.5/0.75 with no spike (including `shoulder_wide`), and the three stress combos hold together.
- These are visual judgements on a low-poly prototype; smoothness/anatomical quality is not claimed to be production grade.

### 3. What is still only a placeholder
- Procedural Skin-modifier surface — watertight and manifold, but NOT a sculpted production base mesh: no deliberate facial edge flow, minimal hands/feet, generic flow from the Skin modifier.
- UV is an auto Smart-UV-Project set (TEXCOORD_0 present, tint workflow unblocked), not a hand-laid production UV; no texture maps yet.
- Auto envelope skin weights, not hand-painted (deformation QA confirms they hold under posing+morphs, but they are not production-tuned).
- No facial morphs on the procedural body (face is out of scope — see item 4).
- `NOT_PRODUCTION_APPROVED` — use for pipeline validation and proportion prototyping only.

### 4. What requires a future face-specific experiment (V3)
- Facial identity preservation is **not** claimed here. v2 face scope is limited to head shape and approximate face width.
- Eye landmarks are a separate proxy (see `docs/stylization-prototype-v1.1.md`), not real facial topology.
- A V3 face pass (licensed face-generation or multi-view reconstruction) must live behind a separate adapter with explicit privacy + license confirmation, and must never upload personal face photos without confirmation.
