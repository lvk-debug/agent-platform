/**
 * 标注工具条
 *
 * 所有按钮命中区域 ≥44px。平板竖屏时改为底部横向条（vertical=false）。
 */

import React from 'react'
import { Popover } from 'antd'
import {
  ArrowUpRight,
  Circle,
  Download,
  EyeOff,
  Hand,
  Highlighter,
  Pen,
  PenLine,
  Redo2,
  Square,
  Trash2,
  Type,
  Undo2,
} from 'lucide-react'
import type { AnnotationTool, CanvasMode } from '../../types/learning'

/** 画布交互模式定义在公共类型里，画布与工具栏共用一份，避免循环依赖 */
export type { CanvasMode } from '../../types/learning'

/** 画笔模式下可用的工具（文本已独立为模式，不在此列） */
const TOOLS: Array<{ key: AnnotationTool; label: string; icon: React.ReactNode }> = [
  { key: 'pen', label: '画笔', icon: <Pen size={20} /> },
  { key: 'highlighter', label: '荧光笔', icon: <Highlighter size={20} /> },
  { key: 'arrow', label: '箭头', icon: <ArrowUpRight size={20} /> },
  { key: 'rect', label: '矩形', icon: <Square size={20} /> },
  { key: 'ellipse', label: '圆形', icon: <Circle size={20} /> },
]

const MODE_BUTTONS: Array<{
  key: CanvasMode
  label: string
  icon: React.ReactNode
}> = [
  { key: 'browse', label: '预览模式', icon: <Hand size={20} /> },
  { key: 'draw', label: '画笔模式', icon: <Pen size={20} /> },
  { key: 'text', label: '文本贴纸模式', icon: <Type size={20} /> },
]

/** 收进 Popover 后可以放心多给几个色值，不再挤占工具栏空间 */
export const CANVAS_COLORS = [
  '#EF4444',
  '#F97316',
  '#F59E0B',
  '#10B981',
  '#14B8A6',
  '#3B82F6',
  '#6366F1',
  '#8B5CF6',
  '#EC4899',
  '#1E293B',
]

const WIDTH_OPTIONS = [
  { value: 0.002, label: '细' },
  { value: 0.004, label: '中' },
  { value: 0.007, label: '粗' },
]

interface AnnotationToolbarProps {
  /** 画布总开关。关闭时工具栏只保留开关本身，文档处于纯阅读态 */
  canvasEnabled: boolean
  mode: CanvasMode
  tool: AnnotationTool
  color: string
  strokeWidth: number
  allowFingerDraw: boolean
  canUndo: boolean
  canRedo: boolean
  vertical?: boolean
  onToggleCanvas: () => void
  onModeChange: (mode: CanvasMode) => void
  onToolChange: (tool: AnnotationTool) => void
  onColorChange: (color: string) => void
  onStrokeWidthChange: (width: number) => void
  onToggleFingerDraw: () => void
  onUndo: () => void
  onRedo: () => void
  onClear: () => void
  onExport: () => void
}

const AnnotationToolbar: React.FC<AnnotationToolbarProps> = ({
  canvasEnabled,
  mode,
  tool,
  color,
  strokeWidth,
  allowFingerDraw,
  canUndo,
  canRedo,
  vertical = true,
  onToggleCanvas,
  onModeChange,
  onToolChange,
  onColorChange,
  onStrokeWidthChange,
  onToggleFingerDraw,
  onUndo,
  onRedo,
  onClear,
  onExport,
}) => {
  // 水平态用 max-w-full 让宽度随工具数量自适应，占满整行会显得空旷
  const containerClass = vertical
    ? 'flex w-14 flex-col items-center gap-1.5 rounded-2xl border border-slate-200/80 bg-white/95 p-1.5 shadow-xl backdrop-blur'
    : 'flex max-w-full items-center gap-1.5 overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/95 p-1.5 shadow-lg backdrop-blur'

  const buttonBase =
    'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-slate-500 transition-all duration-150 hover:bg-slate-100 hover:text-indigo-600 active:scale-[0.94] disabled:cursor-not-allowed disabled:opacity-40'
  const activeClass = 'bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white shadow-md hover:text-white'

  return (
    <div className={containerClass}>
      {/* 画布总开关：默认关闭，让文档处于纯阅读态；打开后才显示标注工具 */}
      <button
        type="button"
        title={canvasEnabled ? '关闭画布' : '打开画布'}
        aria-label={canvasEnabled ? '关闭画布' : '打开画布'}
        onClick={onToggleCanvas}
        className={`${buttonBase} ${canvasEnabled ? activeClass : 'text-indigo-500'}`}
      >
        {canvasEnabled ? <EyeOff size={20} /> : <PenLine size={20} />}
      </button>

      {!canvasEnabled ? null : (
        <>
      {/* 模式切换：预览 / 画笔 / 文本贴纸，三选一 */}
      {MODE_BUTTONS.map((item) => (
        <button
          key={item.key}
          type="button"
          title={item.label}
          aria-label={item.label}
          onClick={() => onModeChange(item.key)}
          className={`${buttonBase} ${mode === item.key ? activeClass : ''}`}
        >
          {item.icon}
        </button>
      ))}

      <span className={vertical ? 'my-1 h-px w-8 bg-slate-200' : 'mx-1 h-8 w-px bg-slate-200'} />

      {/* 画笔工具：仅画笔模式下可用 */}
      {mode === 'draw' &&
        TOOLS.map((item) => (
          <button
            key={item.key}
            type="button"
            title={item.label}
            aria-label={item.label}
            onClick={() => onToolChange(item.key)}
            className={`${buttonBase} ${tool === item.key ? activeClass : ''}`}
          >
            {item.icon}
          </button>
        ))}

      <span className={vertical ? 'my-1 h-px w-8 bg-slate-200' : 'mx-1 h-8 w-px bg-slate-200'} />

      {/* 颜色：收进 Popover，点开再选，避免竖排工具栏被色块撑长 */}
      <Popover
        trigger="click"
        placement={vertical ? 'left' : 'top'}
        content={
          <div className="grid w-[152px] grid-cols-5 gap-2 p-1">
            {CANVAS_COLORS.map((option) => (
              <button
                key={option}
                type="button"
                aria-label={`颜色 ${option}`}
                onClick={() => onColorChange(option)}
                className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
                  color === option ? 'border-slate-800' : 'border-white'
                }`}
                style={{ backgroundColor: option }}
              />
            ))}
          </div>
        }
      >
        <button type="button" title="颜色" aria-label="选择颜色" className={buttonBase}>
          <span
            className="h-5 w-5 rounded-full border border-white/70 shadow-sm"
            style={{ backgroundColor: color }}
          />
        </button>
      </Popover>

      {/* 线宽 */}
      <div className={vertical ? 'flex flex-col gap-1' : 'flex items-center gap-1'}>
        {WIDTH_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onStrokeWidthChange(option.value)}
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs transition-colors ${
              strokeWidth === option.value
                ? 'bg-indigo-50 text-indigo-600'
                : 'text-slate-400 hover:bg-slate-100'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <span className={vertical ? 'my-1 h-px w-8 bg-slate-200' : 'mx-1 h-8 w-px bg-slate-200'} />

      {/* 撤销 / 重做 / 清除 / 导出 */}
      <button
        type="button"
        title="撤销"
        aria-label="撤销"
        disabled={!canUndo}
        onClick={onUndo}
        className={buttonBase}
      >
        <Undo2 size={20} />
      </button>
      <button
        type="button"
        title="重做"
        aria-label="重做"
        disabled={!canRedo}
        onClick={onRedo}
        className={buttonBase}
      >
        <Redo2 size={20} />
      </button>
      <button type="button" title="清空本页" aria-label="清空本页" onClick={onClear} className={buttonBase}>
        <Trash2 size={20} />
      </button>
      <button type="button" title="导出截图" aria-label="导出截图" onClick={onExport} className={buttonBase}>
        <Download size={20} />
      </button>

      {/* 手掌防误触开关 */}
      <button
        type="button"
        title={allowFingerDraw ? '手指可绘制' : '仅手写笔绘制'}
        aria-label="切换手指绘制"
        onClick={onToggleFingerDraw}
        className={`${buttonBase} ${allowFingerDraw ? 'bg-indigo-50 text-indigo-600' : ''}`}
      >
        <Hand size={18} />
      </button>
        </>
      )}
    </div>
  )
}

export default AnnotationToolbar
