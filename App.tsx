import { Canvas } from '@react-three/fiber/native';
import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { computeBlendShapeValues } from './src/character/blendShapeMapping';
import { ACTIVE_ASSET, assertProductionReady } from './src/character/characterAsset';
import { CharacterViewer } from './src/character/CharacterViewer';
import { ANIMATION_CLIPS } from './src/character/constants';
import type { UserCharacterStats } from './src/character/types';

// Fail fast if a production build somehow points at a non-approved (placeholder) asset.
assertProductionReady();

const MOCK_STATS: UserCharacterStats = {
  workout: {
    trainingConsistency: 0.6,
    upperBodyVolume: 0.4,
    chestVolume: 0.3,
    armVolume: 0.5,
    legVolume: 0.5,
  },
  body: {
    heightCm: 178,
    weightKg: 72,
    referenceHeightCm: 175,
    compositionRatio: 0.35,
  },
  face: null,
};

export default function App() {
  const blendShapeValues = useMemo(() => computeBlendShapeValues(MOCK_STATS), []);

  return (
    <View style={styles.container}>
      <Canvas camera={{ position: [0, 1.6, 3], fov: 40 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 4, 3]} intensity={1.2} />
        <CharacterViewer
          baseMeshUri={ACTIVE_ASSET.module}
          blendShapeValues={blendShapeValues}
          animation={ANIMATION_CLIPS.idle}
        />
      </Canvas>
      {!ACTIVE_ASSET.productionApproved && (
        <View style={styles.banner} pointerEvents="none">
          <Text style={styles.bannerText}>PROTOTYPE — NOT PRODUCTION APPROVED</Text>
          <Text style={styles.bannerSub}>{ACTIVE_ASSET.label}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  banner: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(180,90,20,0.85)',
    paddingVertical: 6,
    alignItems: 'center',
  },
  bannerText: { color: '#fff', fontWeight: 'bold', fontSize: 13 },
  bannerSub: { color: '#ffe', fontSize: 10 },
});
