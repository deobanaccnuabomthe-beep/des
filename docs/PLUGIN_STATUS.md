# PLUGIN_STATUS — AI Character Pipeline v2

Availability of the plugins/services named in the pipeline policy, probed in THIS
environment. Recorded because the pipeline rules require a local fallback + this file
whenever an external plugin/service is unavailable, and forbid silently installing paid
plugins or assuming API keys/accounts/licenses exist.

Probed: 2026-09-20. Blender 4.0.2.

| Tool | Role | Status here | Action taken |
|---|---|---|---|
| Blender glTF 2.0 exporter | GLB export | **Available** (built-in) | Used for all exports. |
| Blender Python API (bpy) | automation / validation | **Available** (built-in) | Used for generation, rig, QA. |
| Rigify | humanoid rigging | **Available but not used** (built-in addon, disabled) | See note below. |
| MPFB / MB-Lab | parametric human base | **Not installed** | Local parametric fallback used. |
| Tripo | AI-generated base mesh | **Unreachable** (no network: HTTP 000; no API key) | Local parametric fallback used. |
| Meshy | AI-generated base mesh | **Unreachable** (no network: HTTP 000; no API key) | Local parametric fallback used. |
| FaceBuilder | later face-identity experiment | **Not evaluated** (out of scope for v2) | Deferred to a V3 face adapter behind explicit privacy/license confirmation. |

## Why Rigify is available but not used

Rigify ships with Blender and can be enabled, but the rig it generates does NOT use the
bone names this project requires (`hips`, `spine`, `chest`, `neck`, `head`,
`shoulder/upper_arm/forearm/hand.L/R`, `thigh/shin/foot/toe.L/R`). Rigify uses its own
convention (`spine`, `spine.001`, `upper_arm.L`, plus `ORG-`/`DEF-`/`MCH-` prefixes and
control bones). Pipeline rule 7 allows "Rigify **or a corrected equivalent hierarchy**".

We use the corrected equivalent: a hand-built armature that emits the exact required
names, with branch bones (`chest->shoulder`, `hips->thigh`) intentionally NOT connected
(rule 8), verified by the validator (`joints_in_skin`, `bone_hierarchy`,
`shoulder_not_snapped`, `thigh_not_snapped`). Adopting Rigify later would require a
retarget/rename pass to this convention; that is deferred, not blocked.

## Why the local parametric fallback (no external AI mesh)

No external AI mesh service is reachable and no API keys exist in this environment, and
the rules forbid assuming they do or uploading anything without confirmation. Per rule 4,
the pipeline falls back to a **local parametric cross-section human generator**
(`tools/blender/ai_character_pipeline.py`) — deterministic, offline, no license or
account required. It produces genuinely different abdomen/waist/chest/hips/face volumes
across lean/average/fat (unlike the capsule regression placeholder).

When an AI mesh service or MPFB/MB-Lab becomes available (network + license confirmed),
it plugs in at the "import base mesh" step; the normalize/rig/morph/validate/QA stages
downstream are source-agnostic and unchanged. The import adapter is the only new piece.

## Licenses

All tools actually used here (Blender, its glTF exporter, bpy) are GPL/Blender-licensed
and already present. No paid plugin was installed. No external asset was downloaded. The
generated meshes are produced by our own script and carry no third-party asset license.
