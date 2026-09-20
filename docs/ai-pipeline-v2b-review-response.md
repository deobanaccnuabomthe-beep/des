# AI Pipeline v2b — response to the "validator passes, visual body fails" review

The previous v2 body was built from separate cross-section tubes. The topology review was
right: it was open, disconnected, seamed, and spiked. This iteration replaces the mesh
foundation with a single watertight Skin-modifier surface and hardens the QA so those
failures can no longer pass. Evidence below is measured from the exported GLBs.

## Before vs after (measured)

| | tube v2 (fat.glb) | skin v2b (all variants) |
|---|---|---|
| boundary edges | **80** | **0** |
| non-manifold edges | 0 | 0 |
| connected components | **5** (torso + 2 arms + 2 legs) | **1** (watertight shell) |
| loose vertices | 0 | 0 |
| visible seams | yes (limb/torso) | none |
| shoulder_wide spike | yes | none |

## P0

1. **Topology QA added.** `validate_glb.py` welds the GLB indices by position and checks
   boundary edges, non-manifold edges, loose vertices and connected components — all as
   REQUIRED checks. `render_character_qa.py` additionally checks boundary/non-manifold
   (via bmesh) at every morph value and stress combo.
2. **Open tube boundaries closed.** The body is no longer tubes; the Skin modifier emits a
   single closed manifold. 0 boundary edges on all variants and at all morph states.
3. **Torso↔hip / torso↔shoulder transitions repaired.** These are now welded branch
   junctions produced by the Skin modifier from one connected skeleton — no seam in front,
   side or 3/4 views.
4. **shoulder_wide spike removed.** The morph is a broad region push with smooth quadratic
   falloff (not a single-ring width scale), so no needle vertices at 0.25/0.5/0.75/1.0.

## P1

5. **average.glb is the canonical neutral base** — built first, identity field.
6. **lean.glb / fat.glb are comparison outputs** — the same frozen `average` topology with
   a thin / fat displacement baked into the basis, not separate progression bases.
7. **Manifest label AI_GENERATED → PROCEDURAL_GENERATED** (local procedural generator, not
   an external AI model). `PROTOTYPE` and `NOT_PRODUCTION_APPROVED` kept.
8. **QA hardened.** The inward-normal fraction is now `..._INFO_ONLY` and never gates.
   Hard gates are: any boundary edge, any non-manifold edge, feet off ground, or a morph
   changing the vertex count (topology not preserved). A visual/topology break can no
   longer be hidden by a normal-heuristic baseline.

## Acceptance criteria — status

- no unintended boundary edges — **PASS** (0)
- no non-manifold edges — **PASS** (0)
- no torso/leg or shoulder seam in front/side/3-4 — **PASS** (watertight, visually seamless)
- no needle-like shoulder vertices — **PASS** (shoulder_wide smooth)
- body_fat visibly changes abdomen, waist, hips and face — **PASS** (see body_fat sweep + fat variant)
- all required morphs preserve topology — **PASS** (vertex count constant across all states)
- average.glb is the single neutral reference — **PASS**
- keep PROTOTYPE / NOT_PRODUCTION_APPROVED labels — **PASS**

## Still out of scope (unchanged)

Face customization is deliberately not started (the review said to fix the body first).
Face work stays a later V3 experiment behind a separate adapter with explicit privacy +
license confirmation. The surface is watertight and manifold but still a procedural
prototype, not a sculpted production base mesh (no UV/texture, generic edge flow).
