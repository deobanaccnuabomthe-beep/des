# AI Pipeline v2c — response to the Technical Art Director review

Status of each of the 13 review items. "Fixed" means code changed + verified; "Blocked"
means it genuinely needs a sculpted production asset this environment cannot produce, and
is labeled rather than faked.

## App / runtime (TypeScript)

**1. useBlendShapes never ran (P0) — FIXED.** The hook took `groupRef.current` at render
time, which is null on first render and never re-collects after mount. It now takes the
ref object and collects morph meshes inside `useFrame`, re-collecting until the GLTF
primitive's morph meshes appear. Call sites pass the ref. Covered by `useBlendShapes.ts`
docstring + the runtime path (morphTargetInfluences are lerped every frame once meshes
resolve). Base mesh and clothing both use the fixed hook.

**2. App silently used the placeholder (P0) — FIXED.** New `src/character/characterAsset.ts`
registry: every asset declares `productionApproved`. `assertProductionReady()` throws in a
build that requires production (`EXPO_PUBLIC_REQUIRE_PRODUCTION_ASSET=1` or
`NODE_ENV=production`) when the active asset is not approved, and the app shows a persistent
"PROTOTYPE — NOT PRODUCTION APPROVED" banner otherwise. The placeholder's flag stays false.

**7. fatRatio contract conflict (P1) — FIXED.** Renamed `fatRatio` → `compositionRatio`
with an explicit contract: 0 = lean (body_thin=1), 0.5 = neutral (no morph), 1 = heavy
(body_fat=1) — a normalized composition signal, not absolute body-fat %. `waist_narrow`
now derives from leanness only (0 at/above neutral). Added `npm test` (tsx + node:test)
with unit tests at compositionRatio 0/0.25/0.5/0.75/1.0, opposing-pair exclusivity, height
mapping, and workout signals — 8 tests, all pass. `npm run typecheck` is clean.

**8. Clothing hiding not implemented (P1) — FIXED (app contract).** `applyClothingCoverage`
hides base-mesh child nodes whose name matches a covered `BodyPartGroup`, recomputed each
change so removing a garment re-shows the group. This is the correct app-side contract; it
is a no-op until the base mesh exposes named body-part group nodes (the procedural
prototype is a single shell — noted).

**9. applyTint wrong + array-unsafe (P1) — FIXED.** Now handles both a single material and
`Material[]`, caches the neutral color, and MULTIPLIES neutral × tint (color × map in
three.js) instead of replacing it, so a non-white neutral is preserved and repeated tinting
does not compound.

## Pipeline (Blender)

**4. shoulder_wide did nothing (P1) — FIXED.** Replaced the tiny torso push with a
deltoid/upper-arm-root region push (peak at shoulder height, smooth falloff, no spike).
`render_character_qa.py` now measures a LOCAL shoulder width (z~1.44) instead of whole-body
width (which the arms dominated). Measured gain: +0.04 m across 0→1, and the QA hard-flags
if shoulder_wide fails to widen.

**5. waist_narrow did nothing (P1) — FIXED.** Torso-only radial pull centred on the waist
station, strengthened. New torso-only waist-width metric (z~1.17, arms excluded). Measured:
0.263 m → 0.203 m across 0→1 (−0.06 m, clear V-taper); QA hard-flags if it fails to narrow.

**6. Body morphs weak / not anatomical (P1) — FIXED.** Generic radial pushes replaced with
region-aware ellipsoidal bumps: body_muscle = deltoid + pectoral + biceps + thigh + calf;
body_fat = front-heavy belly + hips + glute + fuller face; stronger arm/leg mass. All
smooth, topology preserved (0 QA flags), readable in the contact sheet at 0.25/0.5/0.75/1.0.

**10. showcase loop duplicate endpoint (P2) — FIXED.** The final keyframe now stops one
frame-step short of 360°, so frame n ≠ frame 1 and the loop has no hitch.

**11. No real deformation QA (P1) — FIXED.** `deformation_qa` poses the rig (shoulders +
hips rotated) with body_muscle=1.0 and waist_narrow=0.8, then checks vertex reach
(explosion), posed height (collapse) and non-manifold edges — hard flags. PASS on all
variants (reach ~1.75 m, height ~1.70 m, 0 non-manifold); a posed render is saved.

**12. No UV/texture (P1) — PARTIALLY FIXED.** Added Smart UV Project so TEXCOORD_0 exists
(validator `has_uv` now PASS), unblocking the tint/texture/UV-padding workflow. It is an
auto-unwrap, not a hand-laid production UV, and there are still no texture maps — labeled
as such in the manifest.

## Asset-quality items — acknowledged, NOT faked

**3. 8 facial morphs missing (full profile fails) — BLOCKED / by design.** The procedural
body has no facial topology, so the 8 face morphs are deliberately NOT added (faking them
on a smooth head would be exactly the "blob deformation is not facial validation" error the
review warns against). The body profile (10 morphs) is this iteration's target; the full
18-morph profile requires a real sculpted face and is a V3 experiment behind a separate,
privacy/license-gated adapter. Manifest states this explicitly.

**13. Stylization prototype ≠ facial identity — acknowledged.** Already labeled a proxy in
`docs/stylization-prototype-v1.1.md`; not used as evidence for any facial morph. Unchanged.

**Placeholder is still a placeholder.** Item 2's gate makes that explicit and unshippable
in production; the app renders it only as a clearly-banner-marked prototype.

## Verification
- `npm test` → 8 pass / 0 fail. `npm run typecheck` → clean.
- `validate_glb.py --profile body` → PASS on average/lean/fat (has_uv now PASS).
- `validate_glb.py --profile full` → still FAILS (8 facial morphs absent) — expected, see item 3.
- `render_character_qa.py` → 0 flags on all variants, incl. deformation pose + morph effectiveness.
