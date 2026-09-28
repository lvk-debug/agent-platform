/**
 * 透明标注画布
 *
 * 浮在文档页之上的 Konva Stage：
 * - 默认 `pointer-events: none`，只有进入标注模式才接管指针
 * - 坐标一律用 0~1 归一化存储，渲染时乘以当前页面尺寸，缩放/换设备都不错位
 * - 手掌防误触：`allowFingerDraw=false` 时只接受手写笔（pointerType === 'pen'）
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage, Layer, Line, Arrow, Rect, Ellipse, Text, Group, Transformer } from 'react-konva'
import Konva from 'konva'
import type { AnnotationShape, AnnotationTool, CanvasMode } from '../../types/learning'

/** 文本标注的字号：由归一化线宽换算，保证与笔迹粗细同步缩放 */
export const textFontSize = (strokeWidth: number, width: number): number =>
  Math.max(strokeWidth * width * 5, 14)

/**
 * 点击与拖动的位移分界（px）。
 * 超过该距离一律视为拖动：拖动已有贴纸、或按下后滑动页面，抬手都不应新建贴纸。
 */
const CLICK_MOVE_TOLERANCE = 6

/**
 * 取事件的视口坐标。
 * 主流环境都是 PointerEvent；个别旧 WebView 只发 TouchEvent（只有 changedTouches），
 * 直接读 clientX 会得到 undefined 并让位移比较变成 NaN，故统一在这里兼容。
 */
const viewportPoint = (evt: Event): { x: number; y: number } | null => {
  const native = evt as TouchEvent & PointerEvent
  const touch = native.changedTouches?.[0] ?? native.touches?.[0]
  if (touch) return { x: touch.clientX, y: touch.clientY }
  if (typeof native.clientX === 'number') return { x: native.clientX, y: native.clientY }
  return null
}

/**
 * 贴纸文字色：按背景的感知亮度自动切换深/浅字，
 * 否则黄、青绿这类亮色底上的白字会糊成一片。
 */
const TEXT_FONT = 'Poppins, -apple-system, Segoe UI, sans-serif'
/** 贴纸行高：多行文本时不至于挤在一起 */
const STICKER_LINE_HEIGHT = 1.4

/**
 * 同步测量贴纸尺寸。
 *
 * 底板（Rect）必须与文字实际占位等大，否则会出现"底色块比字小/比字大"的错位。
 * 这里用一个临时 Konva.Text 量出宽高后立刻销毁——比依赖 Konva.Label 可靠：
 * Label 的 Tag 不会随文字变化自动重算尺寸，是之前贴纸效果不对的根因。
 */
const measureSticker = (
  text: string,
  fontSize: number,
  padding: number
): { width: number; height: number } => {
  const probe = new Konva.Text({
    text,
    fontSize,
    fontFamily: TEXT_FONT,
    padding,
    lineHeight: STICKER_LINE_HEIGHT,
  })
  const size = { width: probe.width(), height: probe.height() }
  probe.destroy()
  return size
}

export const readableTextColor = (background: string): string => {
  const hex = background.replace('#', '')
  if (hex.length !== 6) return '#FFFFFF'
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return '#FFFFFF'
  return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? '#1E293B' : '#FFFFFF'
}

export interface AnnotationCanvasProps {
  width: number
  height: number
  shapes: AnnotationShape[]
  /** 正在绘制中的图形（实时笔迹） */
  draft: AnnotationShape | null
  active: boolean
  /** 当前交互模式：决定按下/抬手的语义（新建贴纸 vs 绘制 vs 什么都不做） */
  mode: CanvasMode
  tool: AnnotationTool
  color: string
  strokeWidth: number
  /** 是否允许手指绘制（关闭时仅手写笔/鼠标可绘制，手指留给平移手势） */
  allowFingerDraw: boolean
  onDrawStart: (x: number, y: number, pressure: number) => void
  onDrawMove: (x: number, y: number) => void
  onDrawEnd: () => void
  /** 文本标注输入完成时回调（点击画布 → 输入 → 确认） */
  onTextCommit?: (shape: AnnotationShape) => void
  /** 贴纸拖动结束：回传归一化后的新锚点 */
  onShapeMove?: (id: string, x: number, y: number) => void
  /** 贴纸旋转/缩放结束：回传新的锚点、角度与缩放 */
  onShapeTransform?: (
    id: string,
    transform: { x: number; y: number; rotation: number; scaleX: number; scaleY: number }
  ) => void
  onStageReady?: (stage: Konva.Stage | null) => void
}

/** 正在编辑的文本标注草稿 */
interface TextDraft {
  x: number
  y: number
  value: string
}

/** 归一化点 → 舞台绝对坐标 */
const toAbsolute = (shape: AnnotationShape, width: number, height: number): number[] => {
  const flat: number[] = []
  shape.points.forEach((point) => {
    flat.push(point.x * width, point.y * height)
  })
  return flat
}

const ShapeNode: React.FC<{
  shape: AnnotationShape
  width: number
  height: number
  isDraft: boolean
}> = ({ shape, width, height, isDraft }) => {
  // 矩形/箭头/椭圆必须两点成形，点不足时直接不画：
  // 否则末点会被当成原点 (0,0)，落笔瞬间甩出一个贯穿整页的图形（表现为"闪一下"）。
  // 文本标注只靠一个锚点定位，需单独放行。
  // 文本贴纸由 StickerNode 单独渲染（要挂选中框与变换器），这里不处理
  if (shape.tool === 'text') return null
  if (shape.points.length === 0) return null
  const isFreehand = shape.tool === 'pen' || shape.tool === 'highlighter'
  if (shape.points.length < 2 && !isFreehand) {
    return null
  }

  const points = toAbsolute(shape, width, height)
  const strokeWidthPx = Math.max(shape.strokeWidth * width, 1)
  // 手指命中区域远大于鼠标，加宽 hit 区域提升选中/擦除手感
  const hitStrokeWidth = Math.max(strokeWidthPx, 20)

  if (shape.tool === 'pen' || shape.tool === 'highlighter') {
    return (
      <Line
        points={points}
        stroke={shape.color}
        strokeWidth={shape.tool === 'highlighter' ? strokeWidthPx * 3 : strokeWidthPx}
        opacity={shape.tool === 'highlighter' ? shape.opacity * 0.35 : shape.opacity}
        tension={0.35}
        lineCap="round"
        lineJoin="round"
        hitStrokeWidth={hitStrokeWidth}
        globalCompositeOperation={shape.tool === 'highlighter' ? 'multiply' : 'source-over'}
        listening={!isDraft}
      />
    )
  }

  if (shape.tool === 'arrow') {
    const [x1, y1, x2, y2] = points
    return (
      <Arrow
        points={[x1 ?? 0, y1 ?? 0, x2 ?? 0, y2 ?? 0]}
        stroke={shape.color}
        fill={shape.color}
        strokeWidth={strokeWidthPx}
        opacity={shape.opacity}
        pointerLength={strokeWidthPx * 2.5}
        pointerWidth={strokeWidthPx * 2.5}
        hitStrokeWidth={hitStrokeWidth}
        listening={!isDraft}
      />
    )
  }

  if (shape.tool === 'rect') {
    const [x1, y1, x2, y2] = points
    return (
      <Rect
        x={Math.min(x1 ?? 0, x2 ?? 0)}
        y={Math.min(y1 ?? 0, y2 ?? 0)}
        width={Math.abs((x2 ?? 0) - (x1 ?? 0))}
        height={Math.abs((y2 ?? 0) - (y1 ?? 0))}
        stroke={shape.color}
        strokeWidth={strokeWidthPx}
        opacity={shape.opacity}
        hitStrokeWidth={hitStrokeWidth}
        listening={!isDraft}
      />
    )
  }

  const [x1, y1, x2, y2] = points
  return (
    <Ellipse
      x={((x1 ?? 0) + (x2 ?? 0)) / 2}
      y={((y1 ?? 0) + (y2 ?? 0)) / 2}
      radiusX={Math.abs((x2 ?? 0) - (x1 ?? 0)) / 2}
      radiusY={Math.abs((y2 ?? 0) - (y1 ?? 0)) / 2}
      stroke={shape.color}
      strokeWidth={strokeWidthPx}
      opacity={shape.opacity}
      hitStrokeWidth={hitStrokeWidth}
      listening={!isDraft}
    />
  )
}

/**
 * 文本贴纸：Group = Rect 底板 + Text 文字
 *
 * - 底板尺寸来自 measureSticker 实测，与单行/多行文字严格等大
 * - 鼠标与触摸均可拖拽（Konva draggable 内部统一走 pointer 事件）
 * - 选中后由外层 Transformer 提供旋转与缩放手柄
 */
const StickerNode: React.FC<{
  shape: AnnotationShape
  width: number
  height: number
  draggable: boolean
  selected: boolean
  onSelect: (id: string) => void
  onDragEnd: (id: string, x: number, y: number) => void
}> = ({ shape, width, height, draggable, selected, onSelect, onDragEnd }) => {
  const fontSize = textFontSize(shape.strokeWidth, width)
  const padding = Math.max(Math.round(fontSize * 0.5), 6)
  const size = useMemo(
    () => measureSticker(shape.text || '', fontSize, padding),
    [shape.text, fontSize, padding]
  )

  const anchor = shape.points[0] ?? { x: 0, y: 0 }
  const radius = Math.min(fontSize * 0.5, 10)

  return (
    <Group
      id={shape.id}
      x={anchor.x * width}
      y={anchor.y * height}
      rotation={shape.rotation ?? 0}
      scaleX={shape.scaleX ?? 1}
      scaleY={shape.scaleY ?? 1}
      draggable={draggable}
      onMouseDown={() => onSelect(shape.id)}
      onTouchStart={() => onSelect(shape.id)}
      onDragEnd={(event) => {
        const node = event.target
        onDragEnd(shape.id, node.x() / width, node.y() / height)
      }}
    >
      {/* 选中时用虚线描边提示，避免与底板同色时看不出选中态 */}
      {selected && (
        <Rect
          width={size.width}
          height={size.height}
          stroke="#6366F1"
          strokeWidth={1.5}
          dash={[4, 3]}
          cornerRadius={radius}
        />
      )}
      <Rect
        width={size.width}
        height={size.height}
        fill={shape.color}
        cornerRadius={radius}
        shadowColor="rgba(15,17,23,0.35)"
        shadowBlur={8}
        shadowOffsetY={3}
      />
      <Text
        text={shape.text || ''}
        fontFamily={TEXT_FONT}
        fontSize={fontSize}
        fill={readableTextColor(shape.color)}
        padding={padding}
        lineHeight={STICKER_LINE_HEIGHT}
        listening={false}
      />
    </Group>
  )
}

const AnnotationCanvas: React.FC<AnnotationCanvasProps> = ({
  width,
  height,
  shapes,
  draft,
  active,
  mode,
  tool,
  color,
  strokeWidth,
  allowFingerDraw,
  onDrawStart,
  onDrawMove,
  onDrawEnd,
  onTextCommit,
  onShapeMove,
  onShapeTransform,
  onStageReady,
}) => {
  const [textDraft, setTextDraft] = useState<TextDraft | null>(null)

  /** 当前选中的贴纸：选中后 Transformer 才出现，可旋转/缩放 */
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const transformerRef = useRef<Konva.Transformer>(null)
  const layerRef = useRef<Konva.Layer>(null)
  /** 按下时的视口坐标：与抬手坐标比对，区分「点击」与「拖动已有贴纸」 */
  const downRef = useRef<{ x: number; y: number } | null>(null)

  // 选中项变化、或贴纸增删/改尺寸后，把变换框挂到对应节点上
  useEffect(() => {
    // 预览模式不留选中态，否则变换框会残留在不可交互的画布上
    if (mode === 'browse') {
      setSelectedId(null)
      return
    }
    const transformer = transformerRef.current
    const layer = layerRef.current
    if (!transformer || !layer) return
    const node = selectedId ? layer.findOne(`#${selectedId}`) : null
    transformer.nodes(node ? [node] : [])
  }, [selectedId, shapes, mode])

  const stageRef = useCallback(
    (node: Konva.Stage | null) => {
      onStageReady?.(node)
    },
    [onStageReady]
  )

  /** 文本输入确认：空内容直接丢弃，避免留下看不见的空节点 */
  const commitText = useCallback(() => {
    setTextDraft((current) => {
      if (current?.value.trim()) {
        onTextCommit?.({
          id:
            typeof crypto !== 'undefined' && 'randomUUID' in crypto
              ? crypto.randomUUID()
              : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          tool: 'text',
          color,
          strokeWidth,
          opacity: 1,
          points: [{ x: current.x, y: current.y }],
          text: current.value.trim(),
          createdAt: new Date().toISOString(),
        })
      }
      return null
    })
  }, [color, strokeWidth, onTextCommit])

  /** 旋转/缩放结束：把节点的实际变换换算回归一化坐标与角度后回传 */
  const handleTransformEnd = useCallback(() => {
    const node = selectedId ? layerRef.current?.findOne(`#${selectedId}`) : null
    if (!node || !selectedId) return
    onShapeTransform?.(selectedId, {
      x: node.x() / width,
      y: node.y() / height,
      rotation: node.rotation(),
      scaleX: node.scaleX(),
      scaleY: node.scaleY(),
    })
  }, [selectedId, width, height, onShapeTransform])

  // 手掌防误触：手指落笔直接放行给下层的平移手势
  const passesGuard = (event: Konva.KonvaEventObject<PointerEvent>): boolean => {
    const pointerType = event.evt?.pointerType ?? 'mouse'
    if (allowFingerDraw) return true
    return pointerType === 'pen' || pointerType === 'mouse'
  }

  const readPosition = (stage: Konva.Stage | null) => {
    const pointer = stage?.getPointerPosition()
    if (!pointer || width <= 0 || height <= 0) return null
    return {
      x: Math.min(Math.max(pointer.x / width, 0), 1),
      y: Math.min(Math.max(pointer.y / height, 0), 1),
    }
  }

  return (
    <div
      className="absolute left-0 top-0"
      style={{
        // 阅读态（预览模式 / 画布关闭）必须彻底让路：
        // 否则不仅点不到下层，touch-action: none 还会掐掉触屏的长按选词与滚动，
        // 表现为「文档里的文字选不中」。
        pointerEvents: active ? 'auto' : 'none',
        touchAction: active ? 'none' : 'auto',
      }}
    >
      <Stage
        ref={stageRef}
        width={width}
        height={height}
        style={{ cursor: active ? (tool === 'text' ? 'text' : 'crosshair') : 'default' }}
        onPointerDown={(event) => {
          downRef.current = viewportPoint(event.evt)
          // 点空白处：取消贴纸选中（收起旋转/缩放手柄）
          if (event.target === event.target.getStage()) setSelectedId(null)
          if (!active || !passesGuard(event)) return
          // 落在已有图形上：交给该图形自身处理（文本贴纸靠它拖动），不新建图形
          if (event.target !== event.target.getStage()) return
          const stage = event.target.getStage()
          const position = readPosition(stage)
          if (!position) return

          // 只有画笔模式才起笔。文本贴纸模式若在这里 start 绘制，
          // pointerup 又不会 end，会残留一个空草稿图形。
          if (mode !== 'draw') return

          // 手写笔用真实压感，鼠标/触摸给固定值
          const pressure =
            event.evt?.pointerType === 'pen' && event.evt.pressure > 0 ? event.evt.pressure : 0.5
          onDrawStart(position.x, position.y, pressure)
        }}
      onPointerMove={(event) => {
        if (!active || !passesGuard(event)) return
        const position = readPosition(event.target.getStage())
        if (!position) return
        onDrawMove(position.x, position.y)
      }}
      onPointerUp={(event) => {
        const down = downRef.current
        downRef.current = null
        if (!active) return

        // 拖动过就不算点击。仅凭 target === stage 判断不可靠：拖动贴纸时 Konva
        // 会让节点跟随指针，抬手瞬间命中目标可能回落到 stage，被误判成"点空白"
        // 而新建一个贴纸。加位移阈值后，拖动/滑动一律不新建。
        const up = viewportPoint(event.evt)
        const moved =
          !!down && !!up && Math.hypot(up.x - down.x, up.y - down.y) > CLICK_MOVE_TOLERANCE

        // 文本贴纸模式：**抬手后**、且点在空白处且没有拖动，才弹输入框新建。
        // 若放在 pointerdown 里挂载并 autoFocus，浏览器随后会把焦点还给舞台容器，
        // 触发 onBlur 提交空内容并立即关闭——表现就是"点了完全没反应"。
        if (mode === 'text') {
          if (!moved && event.target === event.target.getStage()) {
            const position = readPosition(event.target.getStage())
            if (position) setTextDraft({ x: position.x, y: position.y, value: '' })
          }
          return
        }
        if (mode === 'draw') onDrawEnd()
      }}
      onPointerLeave={() => {
        downRef.current = null
        if (!active) return
        onDrawEnd()
      }}
      onPointerCancel={() => {
        downRef.current = null
        if (!active) return
        onDrawEnd()
      }}
    >
      <Layer ref={layerRef}>
        {shapes
          .filter((shape) => shape.tool !== 'text')
          .map((shape) => (
            <ShapeNode key={shape.id} shape={shape} width={width} height={height} isDraft={false} />
          ))}

        {/* 文本贴纸：可拖动、可选中，选中后由 Transformer 提供旋转/缩放 */}
        {shapes
          .filter((shape) => shape.tool === 'text')
          .map((shape) => (
            <StickerNode
              key={shape.id}
              shape={shape}
              width={width}
              height={height}
              draggable={active}
              selected={selectedId === shape.id}
              onSelect={setSelectedId}
              onDragEnd={onShapeMove ?? (() => undefined)}
            />
          ))}

        <Transformer
          ref={transformerRef}
          rotateEnabled
          enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right']}
          anchorSize={12}
          anchorStroke="#6366F1"
          borderStroke="#6366F1"
          boundBoxFunc={(oldBox, newBox) =>
            Math.abs(newBox.width) < 24 || Math.abs(newBox.height) < 16 ? oldBox : newBox
          }
          onTransformEnd={handleTransformEnd}
        />

        {draft && (
          // 直接用 draft 自身的样式：落笔时的颜色/线宽（含压感）是什么样，
          // 抬笔落成正式图形后就是什么样，避免收笔瞬间线宽突变产生跳动
          <ShapeNode key={draft.id} shape={draft} width={width} height={height} isDraft />
        )}
        </Layer>
      </Stage>

      {/* 文本输入框：跟随点击位置，回车/失焦确认，Esc 取消 */}
      {textDraft && (
        <textarea
          ref={(node) => {
            // 延迟一拍再聚焦：同一轮事件内若被舞台容器抢回焦点，
            // 会立即触发 onBlur 提交空内容，输入框一闪就没了
            if (node) window.setTimeout(() => node.focus(), 0)
          }}
          value={textDraft.value}
          onChange={(event) =>
            setTextDraft((current) => (current ? { ...current, value: event.target.value } : current))
          }
          onBlur={commitText}
          onKeyDown={(event) => {
            // 多行文本：Enter 用于换行，Ctrl/⌘+Enter 才确认
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.preventDefault()
              commitText()
            } else if (event.key === 'Escape') {
              setTextDraft(null)
            }
          }}
          rows={2}
          placeholder="输入文字，Ctrl/⌘+回车确认，Esc 取消"
          className="z-20 min-w-[200px] resize-none rounded-lg border-2 border-indigo-400 bg-white px-2 py-1.5 text-sm shadow-lg outline-none"
          style={{
            position: 'absolute',
            left: textDraft.x * width,
            top: textDraft.y * height,
            color,
            fontSize: textFontSize(strokeWidth, width),
            lineHeight: 1.2,
          }}
        />
      )}
    </div>
  )
}

export default AnnotationCanvas
