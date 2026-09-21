import { useFrame } from '@react-three/fiber';
import { useRef, type RefObject } from 'react';
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
 * Applies named blend shape values (0..1) to every morph-target mesh under the group
 * `rootRef` points at, matching by exact name (spec section 4), easing toward new
 * values each frame instead of snapping.
 *
 * Takes the ref OBJECT, not `ref.current`: on the first render the group is not
 * mounted yet (current === null), and a later mount does not re-render this hook, so
 * reading `ref.current` at render time would capture null forever. Instead the meshes
 * are collected inside useFrame — which runs every frame — and re-collected until the
 * morph-target meshes (the GLTF primitive attaches a frame or two after mount) appear.
 */
export function useBlendShapes(
  rootRef: RefObject<Object3D | null>,
  targetValues: BlendShapeValues,
) {
  const meshesRef = useRef<Mesh[]>([]);
  const collectedFrom = useRef<Object3D | null>(null);

  useFrame((_, delta) => {
    const root = rootRef.current;
    if (!root) return;

    // (Re)collect when the group instance changes, or while no morph meshes have been
    // found yet (children mount asynchronously after the group itself).
    if (root !== collectedFrom.current || meshesRef.current.length === 0) {
      const found = collectMorphMeshes(root);
      if (found.length > 0) {
        meshesRef.current = found;
        collectedFrom.current = root;
      }
    }

    const meshes = meshesRef.current;
    if (meshes.length === 0) return;
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
