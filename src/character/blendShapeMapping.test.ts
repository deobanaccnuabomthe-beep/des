import assert from 'node:assert/strict';
import test from 'node:test';
import { computeBlendShapeValues } from './blendShapeMapping';
import type { UserCharacterStats } from './types';

function stats(over: Partial<UserCharacterStats['body']> = {},
               workout: Partial<UserCharacterStats['workout']> = {}): UserCharacterStats {
  return {
    workout: { trainingConsistency: 0, upperBodyVolume: 0, chestVolume: 0, armVolume: 0, legVolume: 0, ...workout },
    body: { heightCm: 175, weightKg: 70, referenceHeightCm: 175, compositionRatio: 0.5, ...over },
    face: null,
  };
}

const approx = (a: number | undefined, b: number, eps = 1e-6) =>
  assert.ok(Math.abs((a ?? 0) - b) <= eps, `expected ${a} ≈ ${b}`);

// compositionRatio contract: 0 lean -> body_thin=1, 0.5 neutral -> 0/0, 1 heavy -> body_fat=1
test('compositionRatio = 0.0 -> fully thin, no fat, full waist_narrow', () => {
  const v = computeBlendShapeValues(stats({ compositionRatio: 0.0 }));
  approx(v.body_thin, 1.0);
  approx(v.body_fat, 0.0);
  approx(v.waist_narrow, 1.0);
});

test('compositionRatio = 0.25 -> partial thin, no fat', () => {
  const v = computeBlendShapeValues(stats({ compositionRatio: 0.25 }));
  approx(v.body_thin, 0.5);
  approx(v.body_fat, 0.0);
  approx(v.waist_narrow, 0.5);
});

test('compositionRatio = 0.5 -> neutral (no fat/thin/waist morph)', () => {
  const v = computeBlendShapeValues(stats({ compositionRatio: 0.5 }));
  approx(v.body_fat, 0.0);
  approx(v.body_thin, 0.0);
  approx(v.waist_narrow, 0.0);
});

test('compositionRatio = 0.75 -> partial fat, no thin', () => {
  const v = computeBlendShapeValues(stats({ compositionRatio: 0.75 }));
  approx(v.body_fat, 0.5);
  approx(v.body_thin, 0.0);
  approx(v.waist_narrow, 0.0);
});

test('compositionRatio = 1.0 -> fully fat, no thin', () => {
  const v = computeBlendShapeValues(stats({ compositionRatio: 1.0 }));
  approx(v.body_fat, 1.0);
  approx(v.body_thin, 0.0);
  approx(v.waist_narrow, 0.0);
});

test('opposing pairs are mutually exclusive at every composition value', () => {
  for (const c of [0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0]) {
    const v = computeBlendShapeValues(stats({ compositionRatio: c }));
    assert.ok(!((v.body_fat ?? 0) > 0 && (v.body_thin ?? 0) > 0),
      `body_fat and body_thin both > 0 at compositionRatio=${c}`);
  }
});

test('height maps around reference: taller -> height_tall, shorter -> height_short', () => {
  const tall = computeBlendShapeValues(stats({ heightCm: 205 }));
  approx(tall.height_short, 0.0);
  assert.ok((tall.height_tall ?? 0) > 0.9, 'expected near-max height_tall at +30cm');
  const short = computeBlendShapeValues(stats({ heightCm: 145 }));
  approx(short.height_tall, 0.0);
  assert.ok((short.height_short ?? 0) > 0.9, 'expected near-max height_short at -30cm');
});

test('workout signals drive their morphs directly', () => {
  const v = computeBlendShapeValues(stats({}, { upperBodyVolume: 0.8, armVolume: 0.7, legVolume: 0.6, chestVolume: 0.5, trainingConsistency: 0.9 }));
  approx(v.shoulder_wide, 0.8);
  approx(v.arm_mass, 0.7);
  approx(v.leg_mass, 0.6);
  approx(v.chest_thick, 0.5);
  approx(v.body_muscle, 0.9);
});
