import { OPPOSING_PAIRS } from './constants';
import type { BlendShapeValues, UserCharacterStats } from './types';

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

/**
 * Spec 4c: for an opposing pair, only the dominant side may be non-zero — a signed
 * ratio around a neutral midpoint splits into (positive side, negative side).
 */
function splitSigned(ratio: number, positiveKey: string, negativeKey: string, out: Record<string, number>) {
  const signed = clamp01(ratio) * 2 - 1; // ratio 0..1 -> signed -1..1
  out[positiveKey] = signed > 0 ? clamp01(signed) : 0;
  out[negativeKey] = signed < 0 ? clamp01(-signed) : 0;
}

export function computeBlendShapeValues(stats: UserCharacterStats): BlendShapeValues {
  const values: Record<string, number> = {};

  values.body_muscle = clamp01(stats.workout.trainingConsistency);
  // fatRatio is 0 (lean) .. 1 (high fat); split around the midpoint so only one of
  // body_fat/body_thin is ever non-zero, per spec section 4/4c.
  splitSigned(stats.body.fatRatio, 'body_fat', 'body_thin', values);

  values.shoulder_wide = clamp01(stats.workout.upperBodyVolume);
  values.waist_narrow = clamp01(1 - stats.body.fatRatio);
  values.chest_thick = clamp01(stats.workout.chestVolume);
  values.arm_mass = clamp01(stats.workout.armVolume);
  values.leg_mass = clamp01(stats.workout.legVolume);

  const heightDelta = stats.body.heightCm - stats.body.referenceHeightCm;
  const heightRatio = clamp01(heightDelta / 30 + 0.5); // ±30cm maps to the full 0..1 range
  splitSigned(heightRatio, 'height_tall', 'height_short', values);

  if (stats.face) {
    splitSigned(stats.face.faceWidthRatio, 'face_wide', 'face_narrow', values);
    splitSigned(stats.face.jawSquareness, 'jaw_square', 'jaw_round', values);
    splitSigned(stats.face.eyeSpacingRatio, 'eyes_wide_set', 'eyes_close_set', values);
    splitSigned(stats.face.noseWidthRatio, 'nose_wide', 'nose_narrow', values);
  }

  return assertMutuallyExclusivePairs(values);
}

/** Defensive guard: never let both sides of an opposing pair be non-zero (spec 4/4c). */
function assertMutuallyExclusivePairs(values: Record<string, number>): BlendShapeValues {
  for (const [a, b] of OPPOSING_PAIRS) {
    if ((values[a] ?? 0) > 0 && (values[b] ?? 0) > 0) {
      // Keep whichever side is larger; zero out the other rather than let the mesh blend both.
      if (values[a]! >= values[b]!) values[b] = 0;
      else values[a] = 0;
    }
  }
  return values;
}
