import type { BlendShapeName, BodyPartGroup } from './constants';

// Raw signals the app already tracks (workouts, weight-ins, onboarding height, face scan).
// Spec section 4/4b "Nguồn dữ liệu trong app" column.
export interface WorkoutStats {
  /** 0–1, frequency + consistency over recent weeks. Drives body_muscle. */
  trainingConsistency: number;
  /** 0–1, relative upper-body training volume. Drives shoulder_wide. */
  upperBodyVolume: number;
  /** 0–1, relative chest training volume. Drives chest_thick. */
  chestVolume: number;
  /** 0–1, relative arm training volume. Drives arm_mass. */
  armVolume: number;
  /** 0–1, relative leg training volume. Drives leg_mass. */
  legVolume: number;
}

export interface BodyMetrics {
  heightCm: number;
  weightKg: number;
  /** Reference height for this user's chosen base mesh gender/build, from onboarding. */
  referenceHeightCm: number;
  /**
   * NORMALIZED body-composition signal, NOT an absolute body-fat percentage:
   *   0.0 = maximally lean   -> body_thin = 1
   *   0.5 = neutral          -> body_fat = body_thin = 0
   *   1.0 = maximally heavy   -> body_fat = 1
   * The app maps a user's body-fat estimate into this band (0.5 = middle of their
   * healthy band) before setting it here. body_fat/body_thin are an opposing pair, so
   * only one side is ever non-zero (spec 4c).
   */
  compositionRatio: number;
}

/** Normalized 0–1 landmark ratios from the on-device face-mesh extraction (spec 4b). */
export interface FaceLandmarkRatios {
  faceWidthRatio: number; // 0 = narrow, 1 = wide
  jawSquareness: number; // 0 = round, 1 = square
  eyeSpacingRatio: number; // 0 = close-set, 1 = wide-set
  noseWidthRatio: number; // 0 = narrow, 1 = wide
}

export interface UserCharacterStats {
  workout: WorkoutStats;
  body: BodyMetrics;
  face: FaceLandmarkRatios | null; // null until the user completes a face scan
}

export type BlendShapeValues = Partial<Record<BlendShapeName, number>>;

export interface ClothingItemDef {
  id: string;
  /** Body part groups this item covers, so the base mesh can hide them. */
  covers: readonly BodyPartGroup[];
  /** URI to the item's own .glb, which carries the same-named blend shapes as the base mesh. */
  modelUri: string;
  /** Multiplied over the neutral base color map in-shader (spec 7). */
  tintColor?: string;
}
