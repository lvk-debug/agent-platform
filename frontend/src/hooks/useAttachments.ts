/**
 * useAttachments - 附件上传队列状态机
 *
 * 职责：
 * 1. 管理待发送附件的本地队列（pending / uploading / success / error）
 * 2. 逐个调用后端 /attachments 上传，拿到 attachment_id
 * 3. 发送时由调用方取 attachmentIds 注入 chatStream
 * 4. 删除时同步调用后端删除（未发送的不会有 attachment）
 *
 * 设计要点：
 * - 每个文件有本地 localId 作为 React key 与去重依据
 * - 上传失败仅标记 error，不影响其它文件与最终发送（发送仍可进行，只是少一个附件）
 * - 不在此处弹 UI 错误提示，由组件根据 item.status 自行渲染
 */

import { useCallback, useRef, useState } from 'react'
import {
  deleteAttachment,
  uploadAttachment,
  type HermesAttachment,
} from '@/services/hermes'

export type AttachmentStatus = 'uploading' | 'success' | 'error'

export interface UploadItem {
  /** 本地临时 key（React list key + 去重） */
  localId: string
  file: File
  /** 上传成功后由后端返回 */
  attachment?: HermesAttachment
  status: AttachmentStatus
  error?: string
  /** 展示用进度（小文件通常瞬间完成） */
  percent: number
}

export interface UseAttachmentsReturn {
  items: UploadItem[]
  addFiles: (files: FileList | File[]) => Promise<void>
  removeItem: (localId: string) => Promise<void>
  /** 已成功上传的附件 ID（发送时注入 chatStream） */
  attachmentIds: number[]
  /** 是否仍有正在上传或失败的（可用于禁用发送按钮） */
  hasPending: boolean
  clear: () => void
}

let uid = 0

export function useAttachments(): UseAttachmentsReturn {
  const [items, setItems] = useState<UploadItem[]>([])
  const itemsRef = useRef<UploadItem[]>(items)
  itemsRef.current = items

  const update = useCallback((localId: string, patch: Partial<UploadItem>) => {
    setItems((prev) =>
      prev.map((it) => (it.localId === localId ? { ...it, ...patch } : it))
    )
  }, [])

  const addFiles = useCallback(
    async (files: FileList | File[]) => {
      const list = Array.from(files)
      for (const file of list) {
        const localId = `att_${Date.now()}_${uid++}`
        setItems((prev) => [
          ...prev,
          { localId, file, status: 'uploading', percent: 0 },
        ])
        try {
          const attachment = await uploadAttachment(file)
          update(localId, { attachment, status: 'success', percent: 100 })
        } catch (e: any) {
          update(localId, {
            status: 'error',
            error: e?.response?.data?.detail || e?.message || '上传失败',
          })
        }
      }
    },
    [update]
  )

  const removeItem = useCallback(async (localId: string) => {
    const target = itemsRef.current.find((it) => it.localId === localId)
    if (target?.attachment) {
      try {
        await deleteAttachment(target.attachment.id)
      } catch (e) {
        console.error('删除附件失败', e)
      }
    }
    setItems((prev) => prev.filter((it) => it.localId !== localId))
  }, [])

  const clear = useCallback(() => setItems([]), [])

  const attachmentIds = items
    .filter((it) => it.status === 'success' && it.attachment)
    .map((it) => it.attachment!.id)

  const hasPending = items.some(
    (it) => it.status === 'uploading' || it.status === 'error'
  )

  return { items, addFiles, removeItem, attachmentIds, hasPending, clear }
}
