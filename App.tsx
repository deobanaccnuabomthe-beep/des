import { Canvas } from '@react-three/fiber/native';
import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { computeBlendShapeValues } from './src/character/blendShapeMapping';
import { CharacterViewer } from './src/character/CharacterViewer';
import { ANIMATION_CLIPS } from './src/character/constants';
import type { UserCharacterStats } from './src/character/types';

// Set once the artist delivers the base mesh (spec section 8), e.g.
// require('./assets/characters/base_mesh.glb'). Left null so the app runs before
// any asset exists — see assets/characters/README.md.
const BASE_MESH_URI: string | null = null;

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
    fatRatio: 0.35,
  },
  face: null,
};

export default function App() {
  const blendShapeValues = useMemo(() => computeBlendShapeValues(MOCK_STATS), []);

  if (!BASE_MESH_URI) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Text style={styles.placeholderText}>
          Waiting on base_mesh.glb from the character artist. See
          assets/characters/README.md.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Canvas camera={{ position: [0, 1.6, 3], fov: 40 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 4, 3]} intensity={1.2} />
        <CharacterViewer
          baseMeshUri={BASE_MESH_URI}
          blendShapeValues={blendShapeValues}
          animation={ANIMATION_CLIPS.idle}
        />
      </Canvas>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  centered: { alignItems: 'center', justifyContent: 'center', padding: 24 },
  placeholderText: { color: '#ccc', textAlign: 'center' },
});
