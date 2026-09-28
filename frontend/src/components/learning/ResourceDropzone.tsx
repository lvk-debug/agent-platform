/**
 * 文档拖拽上传区
 *
 * - 桌面：拖拽文件到虚线框内上传
 * - 平板/触屏：点击虚线框唤起文件选择器（触控没有拖拽语义）
 */

import React, { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CloudUploadOutlined, FileAddOutlined, LoadingOutlined } from '@ant-design/icons'
import learningApi from '../../services/learning'
import type { LearningResource } from '../../types/learning'

const ACCEPTED: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'application/epub+zip': ['.epub'],
  'text/markdown': ['.md', '.markdown'],
}

export interface UploadingItem {
  id: string
  name: string
  percent: number
  failed?: boolean
}

interface ResourceDropzoneProps {
  onUploaded: (resource: LearningResource) => void
}

const MAX_SIZE_MB = 50

const ResourceDropzone: React.FC<ResourceDropzoneProps> = ({ onUploaded }) => {
  const [queue, setQueue] = useState<UploadingItem[]>([])

  const handleFiles = async (files: File[]) => {
    const accepted = files.filter((file) => file.size <= MAX_SIZE_MB * 1024 * 1024)
    if (accepted.length === 0) {
      window.alert(`单个文档不能超过 ${MAX_SIZE_MB}MB`)
      return
    }

    const items: UploadingItem[] = accepted.map((file) => ({
      id: `${file.name}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: file.name,
      percent: 0,
    }))
    setQueue((prev) => [...prev, ...items])

    for (let index = 0; index < accepted.length; index += 1) {
      const file = accepted[index]
      const itemId = items[index].id
      try {
        const resource = await learningApi.uploadDocument(file, (percent) => {
          setQueue((prev) =>
            prev.map((item) => (item.id === itemId ? { ...item, percent } : item))
          )
        })
        onUploaded(resource)
        setQueue((prev) => prev.filter((item) => item.id !== itemId))
      } catch (error) {
        console.error(`上传 ${file.name} 失败`, error)
        setQueue((prev) =>
          prev.map((item) => (item.id === itemId ? { ...item, failed: true } : item))
        )
      }
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => void handleFiles(files),
    accept: ACCEPTED,
    multiple: true,
    noClick: false,
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`flex min-h-[168px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] ${
          isDragActive
            ? 'border-indigo-500 bg-indigo-50/70 shadow-[inset_0_0_32px_rgba(99,102,241,0.16)]'
            : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50/70'
        }`}
      >
        <input {...getInputProps()} />
        <span
          className={`flex h-14 w-14 items-center justify-center rounded-full text-2xl transition-transform duration-200 ${
            isDragActive
              ? 'scale-110 bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white'
              : 'bg-slate-100 text-slate-400'
          }`}
        >
          <CloudUploadOutlined />
        </span>
        <p className="text-sm font-medium text-slate-700">
          {isDragActive ? '松开即可导入' : '拖拽文档到此处，或点击选择文件'}
        </p>
        <p className="text-xs text-slate-400">支持 PDF、PPTX、EPUB、Markdown，单个不超过 {MAX_SIZE_MB}MB</p>
      </div>

      {queue.length > 0 && (
        <ul className="space-y-2">
          {queue.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2"
            >
              <FileAddOutlined className="text-indigo-500" />
              <span className="flex-1 truncate text-sm text-slate-700">{item.name}</span>
              {item.failed ? (
                <span className="text-xs font-medium text-red-500">导入失败</span>
              ) : (
                <>
                  <div className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,#6366F1_0%,#8B5CF6_100%)] transition-[width] duration-200"
                      style={{ width: `${item.percent}%` }}
                    />
                  </div>
                  <LoadingOutlined className="text-xs text-slate-400" />
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default ResourceDropzone
