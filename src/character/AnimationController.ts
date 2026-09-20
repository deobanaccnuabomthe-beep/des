import { AnimationClip, AnimationMixer, LoopOnce, LoopRepeat, type Object3D } from 'three';
import { ANIMATION_CLIPS, type AnimationClipName } from './constants';

/**
 * Wraps a three.js AnimationMixer for the three clips the spec requires (section 5):
 * idle (looping), celebrate (one-shot), showcase (looping, used on the shop screen).
 */
export class AnimationController {
  private readonly mixer: AnimationMixer;
  private readonly actions = new Map<AnimationClipName, ReturnType<AnimationMixer['clipAction']>>();
  private current: AnimationClipName | null = null;

  constructor(root: Object3D, clips: AnimationClip[]) {
    this.mixer = new AnimationMixer(root);
    for (const clip of clips) {
      const name = clip.name as AnimationClipName;
      if (!(name in ANIMATION_CLIPS)) continue;
      const action = this.mixer.clipAction(clip);
      if (name === ANIMATION_CLIPS.celebrate) {
        action.setLoop(LoopOnce, 1);
        action.clampWhenFinished = true;
      } else {
        action.setLoop(LoopRepeat, Infinity);
      }
      this.actions.set(name, action);
    }
  }

  play(name: AnimationClipName, crossFadeSeconds = 0.3) {
    const next = this.actions.get(name);
    if (!next || this.current === name) return;

    const previous = this.current ? this.actions.get(this.current) : undefined;
    next.reset().play();
    if (previous) previous.crossFadeTo(next, crossFadeSeconds, false);
    this.current = name;

    if (name === ANIMATION_CLIPS.celebrate) {
      const idle = this.actions.get(ANIMATION_CLIPS.idle);
      if (idle) {
        const onFinished = () => {
          this.mixer.removeEventListener('finished', onFinished);
          this.play(ANIMATION_CLIPS.idle);
        };
        this.mixer.addEventListener('finished', onFinished);
      }
    }
  }

  update(deltaSeconds: number) {
    this.mixer.update(deltaSeconds);
  }

  dispose() {
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.mixer.getRoot());
  }
}
