/**
 * Character base-mesh registry + production acceptance gate.
 *
 * The app must never silently ship the test-only placeholder as if it were the real
 * character. Each asset declares `productionApproved`. The active asset flows through
 * `assertProductionReady`, which throws when a build demands a production asset but the
 * active one is not approved — and the UI shows a persistent PROTOTYPE banner whenever
 * the active asset is not approved.
 */
export interface CharacterAsset {
  /** require(...)'d GLB module handle. */
  readonly module: number;
  readonly id: string;
  readonly label: string;
  /** false for test/prototype assets; only a real commissioned/accepted mesh is true. */
  readonly productionApproved: boolean;
  readonly note: string;
}

export const PLACEHOLDER_ASSET: CharacterAsset = {
  module: require('../../assets/characters/base_mesh_placeholder.glb'),
  id: 'base_mesh_placeholder',
  label: 'PROTOTYPE placeholder (test only)',
  productionApproved: false,
  note: 'Procedural/capsule test mesh — no face/hands/feet/clothing. See assets/characters/README.md.',
};

/**
 * The asset the app renders. Swap to a production-approved asset (productionApproved:
 * true) once a real base mesh is accepted; do NOT flip the placeholder's flag to true.
 */
export const ACTIVE_ASSET: CharacterAsset = PLACEHOLDER_ASSET;

/** True in builds that must refuse a non-production asset (set in production/CI). */
export function requiresProductionAsset(): boolean {
  const env = (typeof process !== 'undefined' && process.env) || ({} as Record<string, string | undefined>);
  return env.EXPO_PUBLIC_REQUIRE_PRODUCTION_ASSET === '1' || env.NODE_ENV === 'production';
}

/**
 * Fails fast if the active asset is not production-approved in a build that requires
 * one. Call at startup so a placeholder can never reach a production release unnoticed.
 */
export function assertProductionReady(asset: CharacterAsset = ACTIVE_ASSET): void {
  if (requiresProductionAsset() && !asset.productionApproved) {
    throw new Error(
      `[character] Refusing to run: active base mesh "${asset.id}" is not production-approved ` +
        `(${asset.label}). Provide a production-approved asset or unset ` +
        `EXPO_PUBLIC_REQUIRE_PRODUCTION_ASSET for prototype builds.`,
    );
  }
}
