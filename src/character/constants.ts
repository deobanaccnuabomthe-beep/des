// Blend shape names must match the .glb morph target names exactly (case-sensitive) — spec section 4/4b.

export const BODY_BLEND_SHAPES = [
  'body_muscle',
  'body_fat',
  'body_thin',
  'shoulder_wide',
  'waist_narrow',
  'chest_thick',
  'arm_mass',
  'leg_mass',
  'height_tall',
  'height_short',
] as const;

export const FACE_BLEND_SHAPES = [
  'face_wide',
  'face_narrow',
  'jaw_square',
  'jaw_round',
  'eyes_wide_set',
  'eyes_close_set',
  'nose_wide',
  'nose_narrow',
] as const;

export const ALL_BLEND_SHAPES = [...BODY_BLEND_SHAPES, ...FACE_BLEND_SHAPES] as const;

export type BodyBlendShape = (typeof BODY_BLEND_SHAPES)[number];
export type FaceBlendShape = (typeof FACE_BLEND_SHAPES)[number];
export type BlendShapeName = (typeof ALL_BLEND_SHAPES)[number];

// Spec 4/4c: these are two independent shapes, never a single bidirectional slider —
// only one side of a pair may be non-zero at a time.
export const OPPOSING_PAIRS: ReadonlyArray<readonly [BlendShapeName, BlendShapeName]> = [
  ['body_fat', 'body_thin'],
  ['height_tall', 'height_short'],
  ['face_wide', 'face_narrow'],
  ['jaw_square', 'jaw_round'],
  ['eyes_wide_set', 'eyes_close_set'],
  ['nose_wide', 'nose_narrow'],
];

// Spec 9: minimal package to prove the concept, in case the full body set ships later.
export const MVP_BODY_BLEND_SHAPES: readonly BodyBlendShape[] = [
  'body_muscle',
  'body_fat',
  'body_thin',
  'shoulder_wide',
];

// Spec 6: mesh is split into groups so clothing can hide the covered body part.
export const BODY_PART_GROUPS = ['torso_upper', 'torso_lower', 'arms', 'legs'] as const;
export type BodyPartGroup = (typeof BODY_PART_GROUPS)[number];

// Spec 5: animation clips shipped in the same file as the base mesh.
export const ANIMATION_CLIPS = {
  idle: 'idle',
  celebrate: 'celebrate',
  showcase: 'showcase',
} as const;
export type AnimationClipName = (typeof ANIMATION_CLIPS)[keyof typeof ANIMATION_CLIPS];
