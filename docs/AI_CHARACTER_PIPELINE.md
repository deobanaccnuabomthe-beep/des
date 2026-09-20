# AI Character Pipeline v2

**Every output of this pipeline is `PROTOTYPE` / `AI_GENERATED` / `NOT_PRODUCTION_APPROVED`.**

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

## How the parametric human works

The body is built from **cross-section rings** (16 verts each) stacked into tubes:
torso+head as one tube, plus two leg tubes and two arm tubes. Each ring's width/depth
responds to body parameters (`fat`, `muscle`, `thin`, and the per-region morph params),
so a large `fat` value genuinely inflates belly, waist, hips, chest and face fullness —
which the capsule placeholder could not do.

Because `generate_vertices(params)` always emits the **same vertex order and faces**, the
three variants share one topology, and every shape key is a real
`generate_vertices(perturbed) - generate_vertices(base)` vertex delta. `height_tall` /
`height_short` scale the body about Z=0 so feet stay planted.

Rig: a hand-built armature using the exact spec bone names, with branch bones
(`chest->shoulder`, `hips->thigh`) intentionally unconnected. Rigify is available but its
naming does not match the required convention (see `PLUGIN_STATUS.md`).

## Honest status — read this before trusting any output

### 1. What is technically validated (measured, not eyeballed)
- Bounds: exactly 1.75 m tall, feet at Z=0 (min_Y=0.0000 in the Y-up GLB), origin between feet.
- Axis: Blender Z-up source exported as glTF Y-up; mesh node transforms are identity.
- Skin: `JOINTS_0`/`WEIGHTS_0` present, weight sums ~1.0, max 4 influences, zero zero-weight verts.
- All 21 required bones are **actual members of the exported skin** (not just scene nodes), with the spec parent→child chains intact and shoulder/thigh not snapped to the centerline.
- 10 body morph names + count exact; 3 animation clips with correct durations.
- Height morphs keep feet on the ground at value 1.0 (checked from the exported morph deltas).
- All three variants pass the validator with zero required failures (UV absence is a WARN).
- Consistent topology across variants: 533 vertices / 976 triangles each.

### 2. What is visually plausible (looks right, not proven)
- Three clearly distinct body types; the fat variant reads as fuller in abdomen, waist, chest, hips, face and silhouette (see `qa/*_contact_sheet.png` and the 3-up variant render).
- Each morph sweeps sensibly across 0.25/0.5/0.75, and the three stress combos hold together without exploding.
- These are heuristic/visual judgements on a low-poly prototype, not a guarantee of deformation quality.

### 3. What is still only a placeholder
- Tube/cross-section topology, not a sculpted production base mesh: no clean facial edge flow, minimal hands/feet, and overlapping tube seams at the shoulders/hips (expected self-intersection there).
- No UV and no texture.
- Auto envelope skin weights, not hand-painted.
- `NOT_PRODUCTION_APPROVED` — use for pipeline validation and proportion prototyping only.

### 4. What requires a future face-specific experiment (V3)
- Facial identity preservation is **not** claimed here. v2 face scope is limited to head shape and approximate face width.
- Eye landmarks are a separate proxy (see `docs/stylization-prototype-v1.1.md`), not real facial topology.
- A V3 face pass (licensed face-generation or multi-view reconstruction) must live behind a separate adapter with explicit privacy + license confirmation, and must never upload personal face photos without confirmation.
