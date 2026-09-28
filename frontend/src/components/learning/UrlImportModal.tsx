/**
 * URL 导入弹窗
 *
 * 后端抓取是后台任务，这里导入后轮询资源状态直到就绪，
 * 让用户「看着它转完」而不是拿到一个还在 pending 的卡片。
 */

import React, { useEffect, useRef, useState } from 'react'
import { Modal, Input, Select, Button, Alert } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import learningApi from '../../services/learning'
import type { LearningResource } from '../../types/learning'

interface UrlImportModalProps {
  open: boolean
  onClose: () => void
  onImported: (resource: LearningResource) => void
}

const LANGUAGE_OPTIONS = [
  { value: 'zh-Hans', label: '中文（简体）' },
  { value: 'zh-TW', label: '中文（繁体）' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
]

const POLL_INTERVAL_MS = 2000
const POLL_MAX_TIMES = 60

const detectPlatformLabel = (url: string): string => {
  const lower = url.toLowerCase()
  if (lower.includes('bilibili.com') || lower.includes('b23.tv') || /^bv[0-9a-z]{10}$/i.test(url.trim())) {
    return '哔哩哔哩'
  }
  if (lower.includes('youtu.be') || lower.includes('youtube.com')) return 'YouTube'
  return ''
}

const UrlImportModal: React.FC<UrlImportModalProps> = ({ open, onClose, onImported }) => {
  const [url, setUrl] = useState('')
  const [languages, setLanguages] = useState<string[]>(['zh-Hans', 'zh-TW', 'en'])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollTimer = useRef<number | null>(null)

  const stopPolling = () => {
    if (pollTimer.current !== null) {
      window.clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }

  useEffect(() => stopPolling, [])

  const pollUntilReady = (resourceId: number) => {
    let attempts = 0
    pollTimer.current = window.setInterval(async () => {
      attempts += 1
      try {
        const latest = await learningApi.getResource(resourceId)
        if (latest.status !== 'pending') {
          stopPolling()
          setSubmitting(false)
          onImported(latest)
          onClose()
          setUrl('')
          return
        }
        if (attempts >= POLL_MAX_TIMES) {
          stopPolling()
          setSubmitting(false)
          setError('解析超时，资源仍在后台处理中，稍后可在列表中查看')
        }
      } catch (pollError) {
        console.error('轮询资源状态失败', pollError)
      }
    }, POLL_INTERVAL_MS)
  }

  const handleSubmit = async () => {
    const trimmed = url.trim()
    if (!trimmed) {
      setError('请先粘贴视频链接')
      return
    }

    setError(null)
    setSubmitting(true)
    try {
      const resource = await learningApi.importUrl(trimmed, languages)
      if (resource.status === 'pending') {
        pollUntilReady(resource.id)
      } else {
        setSubmitting(false)
        onImported(resource)
        onClose()
        setUrl('')
      }
    } catch (submitError: any) {
      console.error('导入视频链接失败', submitError)
      const detail = submitError?.response?.data?.detail
      setError(detail ?? '导入失败，请确认链接有效且服务端已安装 yt-dlp')
      setSubmitting(false)
    }
  }

  const platformLabel = detectPlatformLabel(url)

  return (
    <Modal
      open={open}
      title={
        <span className="flex items-center gap-2 text-base font-semibold">
          <LinkOutlined className="text-indigo-500" />
          导入视频链接
        </span>
      }
      onCancel={() => {
        if (!submitting) {
          stopPolling()
          onClose()
        }
      }}
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button
            type="primary"
            loading={submitting}
            onClick={() => void handleSubmit()}
            className="bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] border-0"
          >
            {submitting ? '解析中…' : '开始导入'}
          </Button>
        </div>
      }
      maskClosable={!submitting}
      width={560}
    >
      <div className="space-y-4 py-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">视频链接</label>
          <Input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="粘贴 YouTube 或哔哩哔哩视频链接"
            size="large"
            allowClear
            onPressEnter={() => void handleSubmit()}
            className="!rounded-xl"
          />
          {platformLabel && (
            <p className="mt-1.5 text-xs text-indigo-500">已识别为 {platformLabel} 视频</p>
          )}
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">
            字幕语言优先级
          </label>
          <Select
            mode="multiple"
            value={languages}
            onChange={setLanguages}
            options={LANGUAGE_OPTIONS}
            placeholder="按优先级选择字幕语言"
            className="w-full"
            size="large"
            maxTagCount="responsive"
          />
        </div>

        {submitting && (
          <Alert
            type="info"
            showIcon
            message="正在抓取视频信息与字幕"
            description="长视频可能需要十几秒，请保持页面开启。若平台未提供字幕，导入后仍可播放，并支持手动上传字幕文件。"
          />
        )}

        {error && <Alert type="error" showIcon message={error} closable onClose={() => setError(null)} />}
      </div>
    </Modal>
  )
}

export default UrlImportModal
