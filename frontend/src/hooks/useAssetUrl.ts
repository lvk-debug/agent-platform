/**
 * 需鉴权的资源链接 → 可直接塞进 <img src> 的地址
 *
 * 文档正文（PPTX/EPUB/Markdown）里的图片地址是后端拼好的
 * `/api/v1/learning/assets/{resource_id}/{name}`，该端点依赖 Authorization 头。
 * 但 <img src> 由浏览器直连发起，不带任何自定义头，必然 401。
 * 所以统一走 axios（带鉴权头）取回字节流，再转成同源 blob URL 交给 <img>。
 */

import { useEffect, useState } from 'react'
import learningApi from '../services/learning'

const AUTHED_PREFIX = '/api/v1/learning/assets/'

/** url → blobURL 缓存：翻页来回切换时同一张图不重复下载 */
const cache = new Map<string, string>()
const inflight = new Map<string, Promise<string>>()

export const isAuthedAsset = (url?: string | null): boolean =>
  Boolean(url && url.includes(AUTHED_PREFIX))

/** 取回可直接在 <img> 上使用的地址（带缓存与并发去重） */
export const resolveAssetUrl = (url: string): Promise<string> => {
  const cached = cache.get(url)
  if (cached) return Promise.resolve(cached)

  const running = inflight.get(url)
  if (running) return running

  const task = learningApi
    .fetchAssetByUrl(url)
    .then((blobUrl) => {
      cache.set(url, blobUrl)
      return blobUrl
    })
    .finally(() => {
      inflight.delete(url)
    })

  inflight.set(url, task)
  return task
}

/** 单张图：普通外链原样返回，需鉴权的转 blob URL（未就绪时为 null） */
export const useAssetUrl = (src?: string | null): string | null => {
  const [url, setUrl] = useState<string | null>(() =>
    src && !isAuthedAsset(src) ? src : null
  )

  useEffect(() => {
    if (!src || !isAuthedAsset(src)) {
      setUrl(src ?? null)
      return
    }

    const cached = cache.get(src)
    if (cached) {
      setUrl(cached)
      return
    }

    let alive = true
    setUrl(null)
    resolveAssetUrl(src)
      .then((blobUrl) => {
        if (alive) setUrl(blobUrl)
      })
      .catch(() => {
        if (alive) setUrl(null)
      })

    return () => {
      alive = false
    }
  }, [src])

  return url
}

const ASSET_URL_RE = /(?:src|href)=["']([^"']*\/api\/v1\/learning\/assets\/[^"']+)["']/g

/** 从 HTML 片段中抽出所有需鉴权的资源链接 */
export const collectAssetUrls = (html: string): string[] => {
  const found = new Set<string>()
  for (const match of html.matchAll(ASSET_URL_RE)) found.add(match[1])
  return [...found]
}

/** 1x1 透明 GIF：blob URL 就绪前的占位，避免先发出一次必然 401 的直连请求 */
const TRANSPARENT_GIF =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

/** 把 HTML 里的鉴权图片地址替换成占位图 */
export const maskAssetUrls = (html: string): string => {
  let next = html
  for (const url of collectAssetUrls(html)) next = next.split(url).join(TRANSPARENT_GIF)
  return next
}

/**
 * 整段 HTML：把其中的鉴权图片地址替换成 blob URL
 *
 * EPUB 章节走 dangerouslySetInnerHTML，没法直接插组件，只能在字符串层面替换。
 * 首帧先渲染占位图，否则浏览器会先用原始地址发一次请求（401）才等到替换。
 */
export const useAuthedHtml = (html: string): string => {
  const [output, setOutput] = useState(() => maskAssetUrls(html))

  useEffect(() => {
    const urls = collectAssetUrls(html)
    if (urls.length === 0) {
      setOutput(html)
      return
    }

    let alive = true
    setOutput(maskAssetUrls(html))
    Promise.all(urls.map((url) => resolveAssetUrl(url).catch(() => null))).then((resolved) => {
      if (!alive) return
      let next = html
      urls.forEach((url, index) => {
        const blobUrl = resolved[index]
        if (blobUrl) next = next.split(url).join(blobUrl)
      })
      setOutput(next)
    })

    return () => {
      alive = false
    }
  }, [html])

  return output
}

export default useAssetUrl
