import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import type { Mesh, Object3D } from 'three';
import type { BlendShapeValues } from './types';

const LERP_SPEED = 4; // higher = snappier response to new stats, in units/sec

function collectMorphMeshes(root: Object3D): Mesh[] {
  const meshes: Mesh[] = [];
  root.traverse((child) => {
    const mesh = child as Mesh;
    if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) meshes.push(mesh);
  });
  return meshes;
}

/**
 * Applies named blend shape values (0..1) to every morph-target mesh under `root`,
 * matching by exact name as required by spec section 4 ("code sẽ tìm theo tên"),
 * and smoothly eases toward new values each frame instead of snapping.
 */
export function useBlendShapes(root: Object3D | null, targetValues: BlendShapeValues) {
  const meshesRef = useRef<Mesh[] | null>(null);
  const rootRef = useRef<Object3D | null>(null);

  if (root !== rootRef.current) {
    rootRef.current = root;
    meshesRef.current = root ? collectMorphMeshes(root) : null;
  }

  useFrame((_, delta) => {
    const meshes = meshesRef.current;
    if (!meshes) return;
    const t = Math.min(1, delta * LERP_SPEED);

    for (const mesh of meshes) {
      const dict = mesh.morphTargetDictionary!;
      const influences = mesh.morphTargetInfluences!;
      for (const name in dict) {
        const index = dict[name];
        const target = targetValues[name as keyof BlendShapeValues] ?? 0;
        influences[index] += (target - influences[index]) * t;
      }
    }
  });
}
