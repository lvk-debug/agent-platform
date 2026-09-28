/**
 * EPUB 章节渲染器
 *
 * 后端已做过一次 HTML 净化（去 script/外链），这里再用 DOMPurify 兜一层，
 * 双保险防止第三方书籍内容带来的 XSS。
 */

import React, { useMemo } from 'react'
import DOMPurify from 'dompurify'
import { useAuthedHtml } from '../../../hooks/useAssetUrl'

interface EpubChapterRendererProps {
  html: string
  width: number
}

const EpubChapterRenderer: React.FC<EpubChapterRendererProps> = ({ html, width }) => {
  const sanitized = useMemo(() => DOMPurify.sanitize(html, { USE_PROFILES: { html: true } }), [html])
  // 内联图片指向需鉴权的 /api/v1/learning/assets/**，<img src> 直连会 401，先换成 blob URL
  const authedHtml = useAuthedHtml(sanitized)

  return (
    <div
      className="epub-content bg-white px-[8%] py-10 text-[15px] leading-7 text-slate-800"
      style={{ width }}
    >
      <div dangerouslySetInnerHTML={{ __html: authedHtml }} />
    </div>
  )
}

export default EpubChapterRenderer
