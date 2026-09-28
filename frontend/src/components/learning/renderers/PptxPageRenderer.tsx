/**
 * PPTX 页面渲染器
 *
 * 后端已把每页 shape 抽成结构化 JSON（坐标按 slide 宽高归一化），
 * 这里按原点比例绝对定位还原，视觉上接近原稿排版。
 */

import React from 'react'
import AuthImage from '../AuthImage'
import type { PageBlock } from '../../../types/learning'

interface PptxPageRendererProps {
  blocks: PageBlock[]
  width: number
  /** 页面宽高比（后端 slide 宽高），用于撑出正确的页面比例 */
  aspectRatio: number
}

const PptxPageRenderer: React.FC<PptxPageRendererProps> = ({
  blocks,
  width,
  aspectRatio,
}) => {
  const pageWidth = width
  const pageHeight = aspectRatio > 0 ? pageWidth / aspectRatio : pageWidth * 0.5625

  return (
    <div
      className="relative overflow-hidden bg-white"
      style={{ width: pageWidth, height: pageHeight }}
    >
      {blocks.map((block, index) => {
        const style: React.CSSProperties = {
          position: 'absolute',
          left: `${block.x * 100}%`,
          top: `${block.y * 100}%`,
          width: `${block.w * 100}%`,
          height: `${block.h * 100}%`,
          fontSize: block.style?.fontSize
            ? `${(block.style.fontSize as number) * pageHeight}px`
            : undefined,
          fontWeight: block.style?.bold ? 600 : undefined,
          color: block.style?.color,
          textAlign: (block.style?.align as React.CSSProperties['textAlign']) ?? undefined,
          whiteSpace: 'pre-wrap',
          overflow: 'hidden',
        }

        if (block.kind === 'image' && block.src) {
          return (
            <AuthImage
              key={block.src + index}
              src={block.src}
              style={{ ...style, objectFit: 'contain' }}
            />
          )
        }

        if (block.kind === 'table') {
          return (
            <div key={`table-${index}`} style={{ ...style, fontSize: `${pageHeight * 0.022}px` }}>
              {block.text?.split('\n').map((row, rowIndex) => (
                <div key={rowIndex} className="text-slate-700">
                  {row}
                </div>
              ))}
            </div>
          )
        }

        return (
          <div key={`text-${index}`} style={style} className="text-slate-800">
            {block.text}
          </div>
        )
      })}
    </div>
  )
}

export default PptxPageRenderer
