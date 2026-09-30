import type { TaskStatus } from './types'

/**
 * 任务状态色的唯一来源：列表 / 看板 / 手机卡芯片、日历事件、甘特条形与图例统一从这里取值。
 * done 文字色对齐 --color-success；蓝为 cyan 系浅底；待办中性灰；已取消灰 + 虚线。
 */
export interface StatusColor {
  background: string
  border: string
  text: string
  dashed?: boolean
}

export const statusPalette: Record<TaskStatus, StatusColor> = {
  todo: { background: '#f2f4f7', border: '#cbd5e1', text: '#475467' },
  in_progress: { background: '#eff6ff', border: '#93b4f5', text: '#1d4ed8' },
  done: { background: '#edf9f1', border: '#b4dfc9', text: '#16794b' },
  cancelled: { background: '#fbfcfd', border: '#d0d5dd', text: '#667085', dashed: true },
}

/** 甘特条形填充色：实心块比芯片底色略深一档，图例同源 */
export const ganttBarPalette: Record<TaskStatus, { fill: string; stroke: string; progress: string }> = {
  todo: { fill: '#dbeafe', stroke: '#93b4f5', progress: '#2563eb' },
  in_progress: { fill: '#dbeafe', stroke: '#93b4f5', progress: '#2563eb' },
  done: { fill: '#d9f0e3', stroke: '#8fd0af', progress: '#2e9c6b' },
  cancelled: { fill: '#eef1f5', stroke: '#cbd5e1', progress: '#b7c3d3' },
}

/** ChipSelect 触发器类：保持完整类名字面量，Tailwind v4 源码扫描才能命中 */
export const statusChipClass: Record<TaskStatus, string> = {
  todo: 'border-[#cbd5e1] bg-[#f2f4f7] text-text-secondary',
  in_progress: 'border-[#93b4f5] bg-[#eff6ff] text-[#1d4ed8]',
  done: 'border-[#b4dfc9] bg-[#edf9f1] text-[#16794b]',
  cancelled: 'bg-[#f2f4f7] text-muted-foreground',
}
