/**
 * 带鉴权的图片
 *
 * 文档内联图片地址为 `/api/v1/learning/assets/**`，需要 Authorization 头，
 * 直接用 <img src> 会被后端拒绝（401）。这里先换成 blob URL 再渲染，
 * 未就绪时占住同样的位置，避免图片加载导致的布局跳动。
 */

import React from 'react'
import { useAssetUrl } from '../../hooks/useAssetUrl'

interface AuthImageProps {
  src?: string
  alt?: string
  className?: string
  style?: React.CSSProperties
  loading?: 'lazy' | 'eager'
}

const AuthImage: React.FC<AuthImageProps> = ({ src, alt = '', className, style, loading }) => {
  const url = useAssetUrl(src)

  if (!url) {
    return (
      <div
        className={className}
        style={{ ...style, backgroundColor: '#F1F5F9' }}
        aria-hidden
      />
    )
  }

  return <img src={url} alt={alt} className={className} style={style} loading={loading} />
}

export default AuthImage
