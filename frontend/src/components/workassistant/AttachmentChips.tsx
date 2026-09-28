/**
 * 附件 chips - 在输入框上方展示待发送 / 已发送附件
 *
 * - uploading: 进度条 + 旋转图标
 * - success:   图片显示缩略图（blob 方式加载，避免 token 进 URL），文档显示文件图标
 * - error:     红色提示 + 删除
 *
 * 图片预览走 loadAttachmentBlobUrl（fetch + Bearer → objectURL），
 * 因为 <img> 无法携带 Authorization header。
 */
import { useEffect, useState } from 'react'
import { Image, Progress, Tooltip } from 'antd'
import {
  LoadingOutlined,
  CloseOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { UploadItem } from '@/hooks/useAttachments'
import { getFileIcon } from '@/utils/fileIcons'
import { loadAttachmentBlobUrl } from '@/services/hermes'

export function AttachmentImage({ id, token }: { id: number; token: string | null }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!token) return
    let obj: string | undefined
    loadAttachmentBlobUrl(id, token)
      .then((u) => {
        obj = u
        setUrl(u)
      })
      .catch(() => undefined)
    return () => {
      if (obj) URL.revokeObjectURL(obj)
    }
  }, [id, token])
  if (!url) return <div className="w-9 h-9 rounded bg-gray-100 animate-pulse" />
  return (
    <Image
      src={url}
      width={36}
      height={36}
      preview={false}
      className="rounded object-cover"
    />
  )
}

export interface AttachmentChipsProps {
  items: UploadItem[]
  token: string | null
  onRemove: (localId: string) => void
}

export default function AttachmentChips({
  items,
  token,
  onRemove,
}: AttachmentChipsProps) {
  if (!items.length) return null
  return (
    <div className="flex flex-wrap gap-2 mb-2">
      {items.map((it) => {
        const isImage = it.file.type.startsWith('image/')
        const name = it.file.name

        if (it.status === 'uploading') {
          return (
            <div
              key={it.localId}
              className="flex items-center gap-2 px-2 py-1 bg-gray-50 border border-gray-200 rounded-lg"
            >
              <LoadingOutlined spin className="text-blue-500" />
              <span className="text-xs text-gray-500 max-w-[140px] truncate">
                {name}
              </span>
              <Progress
                percent={it.percent}
                size="small"
                showInfo={false}
                className="w-16"
              />
            </div>
          )
        }

        if (it.status === 'error') {
          return (
            <div
              key={it.localId}
              className="flex items-center gap-1 px-2 py-1 bg-red-50 border border-red-200 rounded-lg"
            >
              <CloseOutlined className="text-red-500" />
              <span className="text-xs text-red-600 max-w-[140px] truncate">
                {it.error || '上传失败'}
              </span>
              <Tooltip title="移除">
                <button
                  aria-label="移除失败附件"
                  onClick={() => onRemove(it.localId)}
                >
                  <DeleteOutlined />
                </button>
              </Tooltip>
            </div>
          )
        }

        // success
        return (
          <div
            key={it.localId}
            className="group relative flex items-center gap-2 px-2 py-1 bg-gray-50 border border-gray-200 rounded-lg hover:border-blue-400 transition-colors"
          >
            {isImage && it.attachment ? (
              <AttachmentImage id={it.attachment.id} token={token} />
            ) : (
              <span className="text-base text-blue-500">
                {getFileIcon(name)}
              </span>
            )}
            <span className="text-xs text-gray-700 max-w-[140px] truncate">
              {name}
            </span>
            <button
              onClick={() => onRemove(it.localId)}
              aria-label="删除附件"
              className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-500"
            >
              <CloseOutlined />
            </button>
          </div>
        )
      })}
    </div>
  )
}
