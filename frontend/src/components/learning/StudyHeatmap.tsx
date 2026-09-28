/**
 * 学习热力图
 *
 * 按周分列、按星期分行的日历热力图，五档色阶表示当日学习时长。
 * hover 显示当日明细，底部给出连续学习天数。
 */

import React, { useMemo, useState } from 'react'
import type { HeatmapPoint } from '../../types/learning'
import { formatDuration } from '../../utils/format'

const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

/** 五档色阶：空 → 淡紫 → 深紫 */
const LEVEL_CLASS = [
  'bg-slate-100',
  'bg-indigo-200',
  'bg-indigo-300',
  'bg-indigo-500',
  'bg-violet-600',
]

const levelOf = (seconds: number): number => {
  if (seconds <= 0) return 0
  if (seconds < 900) return 1
  if (seconds < 1800) return 2
  if (seconds < 3600) return 3
  return 4
}

interface StudyHeatmapProps {
  heatmap: HeatmapPoint[]
  streakDays: number
}

const StudyHeatmap: React.FC<StudyHeatmapProps> = ({ heatmap, streakDays }) => {
  const [hovered, setHovered] = useState<HeatmapPoint | null>(null)

  const weeks = useMemo(() => {
    const result: Array<Array<HeatmapPoint | null>> = []
    if (heatmap.length === 0) return result

    // 第一列按首日的星期补齐前导空格，保证行与星期对齐
    const firstDate = new Date(heatmap[0].date)
    const leading = (firstDate.getDay() + 6) % 7
    let current: Array<HeatmapPoint | null> = Array.from({ length: leading }, () => null)

    heatmap.forEach((point) => {
      current.push(point)
      if (current.length === 7) {
        result.push(current)
        current = []
      }
    })
    if (current.length > 0) {
      while (current.length < 7) current.push(null)
      result.push(current)
    }
    return result
  }, [heatmap])

  if (heatmap.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">还没有学习记录，开始学习后这里会长出热力图</p>
    )
  }

  return (
    <div>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        <div className="flex shrink-0 flex-col gap-1 pr-1 pt-[18px]">
          {WEEKDAY_LABELS.map((label, index) => (
            <span key={label} className="h-3.5 text-[10px] leading-3.5 text-slate-400">
              {index % 2 === 0 ? label : ''}
            </span>
          ))}
        </div>

        {weeks.map((week, weekIndex) => (
          <div key={weekIndex} className="flex shrink-0 flex-col gap-1">
            <span className="h-[18px] text-[10px] leading-[18px] text-slate-400">
              {week[0] ? `${new Date(week[0].date).getMonth() + 1}月` : ''}
            </span>
            {week.map((point, dayIndex) => (
              <span
                key={dayIndex}
                onMouseEnter={() => point && setHovered(point)}
                onMouseLeave={() => setHovered(null)}
                className={`h-3.5 w-3.5 rounded-[3px] transition-transform duration-150 hover:scale-125 ${
                  point ? LEVEL_CLASS[levelOf(point.seconds)] : 'bg-transparent'
                }`}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span>少</span>
          {LEVEL_CLASS.map((className) => (
            <span key={className} className={`h-3 w-3 rounded-[3px] ${className}`} />
          ))}
          <span>多</span>
        </div>
        <span>
          {hovered
            ? `${hovered.date}　学习 ${formatDuration(hovered.seconds)}　${hovered.resource_count} 个资源　${hovered.note_count} 条笔记`
            : `连续学习 ${streakDays} 天`}
        </span>
      </div>
    </div>
  )
}

export default StudyHeatmap
