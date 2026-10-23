/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Launcher options for `/api/run` (`verification_level`, `explorer_mode`).
 * Keep ids in sync with `VERIFICATION_LEVEL_PRESETS` in `artemis/config/agent.py`
 * and `EXPLORER_TIERS` in `artemis/agents/explorer/tiers.py`.
 */

export type VerificationLevelId = 'off' | 'final' | 'checkpoints' | 'strict';
export type ExplorerModeId = 'flash' | 'pro' | 'ultra';

/** One notch on a tuning slider. */
export interface TuningLevel<TId extends string = string> {
  /** Wire value sent to the backend. */
  id: TId;
  /** Short name shown next to the slider title and as the hover card heading. */
  label: string;
  /** One-sentence summary shown in the hover card. */
  tagline: string;
  /** Plain-language time cost, e.g. "no extra time". */
  latency: string;
  /** Checks or searches performed at this level. */
  runs: string[];
  /** Checks or searches omitted at this level. */
  skips?: string[];
  /** When to pick this level. */
  bestFor: string;
}

export const VERIFICATION_LEVELS: readonly TuningLevel<VerificationLevelId>[] = [
  {
    id: 'off',
    label: '关闭',
    tagline: '不做任何检查，任务看起来完成即结束。',
    latency: '不增加耗时',
    runs: [
      '每一步执行完即视为完成。',
      '保留完整操作轨迹，但不给出通过/失败判定。'
    ],
    skips: ['不复查、不重试。'],
    bestFor: '快速尝试与演示，只想看过程、不要判定。'
  },
  {
    id: 'final',
    label: '结尾检查',
    tagline: '任务结束后对照目标检查一次结果。这是默认档位。',
    latency: '结尾增加约 20–60 秒',
    runs: [
      '任务结束时，将最终画面、步骤历史与设备状态对照你的要求逐项检查。',
      '结果不符时自动回退修复，最多重试 3 次。'
    ],
    skips: ['执行过程中不检查。'],
    bestFor: '日常任务：不拖慢执行速度地拿到可靠的通过/失败结论。'
  },
  {
    id: 'checkpoints',
    label: '每步检查',
    tagline: '每一步完成后立即检查，外加结尾检查。',
    latency: '每步后台快速检查',
    runs: [
      '每步完成后立即用当时的截图检查。',
      '某步出错会先修复再继续（每步最多 2 次）。',
      '失败条件会被记录，任务继续执行。',
      '结尾仍会执行最终检查。'
    ],
    bestFor: '长任务：前期一个错误会毁掉后续全部工作。'
  },
  {
    id: 'strict',
    label: '严格',
    tagline: '每步都检查且重试更多；首个失败条件立即终止运行。',
    latency: '最慢：检查与重试最多',
    runs: [
      '每次检查耗时更长、尝试更多：每步修复 4 次、结尾 5 次。',
      '首个失败条件立即终止运行，并附带证据。'
    ],
    bestFor: '发布检查与回归运行：绝不容忍误判通过。'
  }
];

export const EXPLORER_MODES: readonly TuningLevel<ExplorerModeId>[] = [
  {
    id: 'flash',
    label: '快速一瞥',
    tagline: '一次扫描即可找到屏幕上的按钮与文字。',
    latency: '每次搜索 1 次扫描',
    runs: [
      '按名称、图标或颜色询问屏幕元素，位置立即返回。',
      '可同时查找多个元素。'
    ],
    skips: ['不放大、不二次尝试。'],
    bestFor: '按钮、图标、文字标注清晰的普通应用。'
  },
  {
    id: 'pro',
    label: '反复确认',
    tagline: '最多扫描 3 次，中间加入推理后再回答。',
    latency: '每次搜索最多 3 次扫描',
    runs: [
      '先读取屏幕布局，再在画面中定位。',
      '首次未命中会在 3 次扫描内换思路重试。'
    ],
    skips: ['仍不放大局部区域，保持搜索快速。'],
    bestFor: '按位置描述的元素（“Wi-Fi 旁边的开关”）或标注不清的元素。'
  },
  {
    id: 'ultra',
    label: '局部放大',
    tagline: '放大屏幕局部，最多扫描 8 次。',
    latency: '每次搜索最多 8 次扫描（最慢）',
    runs: [
      '可裁剪放大屏幕局部，逐块读取小字与拥挤布局。',
      '后续扫描复用早前结果，实际耗时比听起来低。'
    ],
    bestFor: '拥挤界面、极小目标、图表绘图，以及对位置精确度有要求的检查。'
  }
];

/** Per-run tuning sent with `/api/run` for the Pro profile. */
export interface ProTuningOptions {
  verificationLevel?: VerificationLevelId | string;
  explorerMode?: ExplorerModeId | string;
}

/** Effective defaults reported by `GET /api/run/defaults`. */
export interface ProTuningDefaults {
  verification_level?: string | null;
  explorer_mode?: string | null;
}

export const DEFAULT_VERIFICATION_LEVEL: VerificationLevelId = 'final';
export const DEFAULT_EXPLORER_MODE: ExplorerModeId = 'flash';

/** Index of a level id within its ladder; falls back to the default when unknown. */
export function levelIndex<TId extends string>(
  ladder: readonly TuningLevel<TId>[],
  id: string | null | undefined,
  fallback: TId
): number {
  const wanted = String(id ?? '').trim().toLowerCase();
  const idx = ladder.findIndex((l) => l.id === wanted);
  if (idx >= 0) return idx;
  return Math.max(0, ladder.findIndex((l) => l.id === fallback));
}

/** Slider fill percentage for a notch index on a ladder of `count` notches. */
export function notchPercent(index: number, count: number): number {
  if (count <= 1) return 0;
  const clamped = Math.min(Math.max(index, 0), count - 1);
  return (clamped / (count - 1)) * 100;
}
