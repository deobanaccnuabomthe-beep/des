import { useGLTF } from '@react-three/drei/native';
import { useFrame } from '@react-three/fiber';
import React, { useEffect, useRef } from 'react';
import { Color, type Group, type Material, type Mesh, type Object3D } from 'three';
import { AnimationController } from './AnimationController';
import { ANIMATION_CLIPS, BODY_PART_GROUPS, type AnimationClipName, type BodyPartGroup } from './constants';
import type { BlendShapeValues, ClothingItemDef } from './types';
import { useBlendShapes } from './useBlendShapes';

interface CharacterViewerProps {
  /** A remote URI, or a Metro `require(...)` asset id (number) for a bundled GLB. */
  baseMeshUri: string | number;
  blendShapeValues: BlendShapeValues;
  clothing?: ClothingItemDef[];
  skinTint?: string;
  animation?: AnimationClipName;
}

/**
 * Renders the base mesh plus any equipped clothing (spec section 6): every clothing
 * item is its own .glb sharing the base mesh's rig and blend shape names, so the same
 * `blendShapeValues` record drives body and clothing deformation together.
 */
export function CharacterViewer({
  baseMeshUri,
  blendShapeValues,
  clothing = [],
  skinTint,
  animation = ANIMATION_CLIPS.idle,
}: CharacterViewerProps) {
  const groupRef = useRef<Group>(null);
  // drei/native accepts a Metro require(...) asset id at runtime; its types only cover
  // string paths, so cast to satisfy the single-GLTF overload.
  const base = useGLTF(baseMeshUri as string);
  const animationControllerRef = useRef<AnimationController | null>(null);

  useBlendShapes(groupRef, blendShapeValues);

  useEffect(() => {
    if (!groupRef.current || base.animations.length === 0) return;
    const controller = new AnimationController(groupRef.current, base.animations);
    animationControllerRef.current = controller;
    return () => controller.dispose();
  }, [base.animations]);

  useEffect(() => {
    animationControllerRef.current?.play(animation);
  }, [animation]);

  useFrame((_, delta) => animationControllerRef.current?.update(delta));

  useEffect(() => {
    if (skinTint) applyTint(base.scene, 'skin', skinTint);
  }, [base.scene, skinTint]);

  // Spec section 6: hide the body-part groups a clothing item covers so the body does
  // not poke through the garment (and to save fill/vertex cost).
  useEffect(() => {
    applyClothingCoverage(base.scene, clothing);
  }, [base.scene, clothing]);

  return (
    <group ref={groupRef}>
      <primitive object={base.scene} />
      {clothing.map((item) => (
        <ClothingItemMesh key={item.id} item={item} blendShapeValues={blendShapeValues} />
      ))}
    </group>
  );
}

interface ClothingItemMeshProps {
  item: ClothingItemDef;
  blendShapeValues: BlendShapeValues;
}

function ClothingItemMesh({ item, blendShapeValues }: ClothingItemMeshProps) {
  const ref = useRef<Group>(null);
  const gltf = useGLTF(item.modelUri);

  useBlendShapes(ref, blendShapeValues);

  useEffect(() => {
    if (item.tintColor) applyTint(gltf.scene, 'clothing', item.tintColor);
  }, [gltf.scene, item.tintColor]);

  return (
    <group ref={ref}>
      <primitive object={gltf.scene} />
    </group>
  );
}

/**
 * Spec section 6: the base mesh exposes a child node per body-part group
 * (torso_upper, torso_lower, arms, legs). A clothing item's `covers` list hides the
 * matching nodes so the covered body does not intersect the garment. Recomputed from
 * scratch each call, so removing a garment re-shows its groups. This is a no-op on a
 * base mesh that does not yet split into named groups (e.g. the procedural prototype).
 */
function applyClothingCoverage(baseRoot: Object3D, clothing: readonly ClothingItemDef[]) {
  const covered = new Set<BodyPartGroup>();
  for (const item of clothing) for (const g of item.covers) covered.add(g);
  baseRoot.traverse((child) => {
    if ((BODY_PART_GROUPS as readonly string[]).includes(child.name)) {
      child.visible = !covered.has(child.name as BodyPartGroup);
    }
  });
}

const NEUTRAL_COLOR_KEY = '__neutralColor';

/**
 * Spec section 7: the artist ships one neutral base color map per material slot; the
 * app tints by MULTIPLYING the neutral material color by the chosen tint (color * map
 * in three.js), never by replacing it — so a non-white neutral is preserved. Handles
 * both a single material and a Material[] slot array, and caches the neutral color so
 * repeated tinting does not compound.
 */
function applyTint(root: Object3D, materialNameHint: string, hexColor: string) {
  const tint = new Color(hexColor);
  root.traverse((child) => {
    const mesh = child as Mesh;
    if (!mesh.material) return;
    const materials: Material[] = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      const colored = material as Material & { color?: Color; userData: Record<string, unknown> };
      if (!colored.color || !colored.name?.toLowerCase().includes(materialNameHint)) continue;
      let neutral = colored.userData[NEUTRAL_COLOR_KEY] as Color | undefined;
      if (!neutral) {
        neutral = colored.color.clone();
        colored.userData[NEUTRAL_COLOR_KEY] = neutral;
      }
      colored.color.copy(neutral).multiply(tint);
    }
  });
}
