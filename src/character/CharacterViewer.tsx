import { useGLTF } from '@react-three/drei/native';
import { useFrame } from '@react-three/fiber';
import React, { useEffect, useRef } from 'react';
import { Color, type Group, type Mesh, type MeshStandardMaterial } from 'three';
import { AnimationController } from './AnimationController';
import { ANIMATION_CLIPS, type AnimationClipName } from './constants';
import type { BlendShapeValues, ClothingItemDef } from './types';
import { useBlendShapes } from './useBlendShapes';

interface CharacterViewerProps {
  baseMeshUri: string;
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
  const base = useGLTF(baseMeshUri);
  const animationControllerRef = useRef<AnimationController | null>(null);

  useBlendShapes(groupRef.current, blendShapeValues);

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
    if (!skinTint) return;
    applyTint(base.scene, 'skin', skinTint);
  }, [base.scene, skinTint]);

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

  useBlendShapes(ref.current, blendShapeValues);

  useEffect(() => {
    if (!item.tintColor) return;
    applyTint(gltf.scene, 'clothing', item.tintColor);
  }, [gltf.scene, item.tintColor]);

  return (
    <group ref={ref}>
      <primitive object={gltf.scene} />
    </group>
  );
}

/**
 * Spec section 7: the artist ships one neutral base color map per material slot, and
 * the app tints it in-shader by multiplying the material color instead of asking for
 * pre-painted color variants.
 */
function applyTint(root: Group, materialNameHint: string, hexColor: string) {
  const color = new Color(hexColor);
  root.traverse((child) => {
    const mesh = child as Mesh;
    const material = mesh.material as MeshStandardMaterial | undefined;
    if (material?.name?.toLowerCase().includes(materialNameHint)) {
      material.color.copy(color);
    }
  });
}
