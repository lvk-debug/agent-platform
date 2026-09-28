/**
 * ComposerInput - 输入区（常驻底部）
 *
 * 整合：
 * - 左侧「+」上传按钮（Upload beforeUpload 阻止自动上传，改为状态机托管）
 * - 拖拽 / 粘贴图片添加附件
 * - 附件 chips（见 AttachmentChips）
 * - 左下「快捷指令」入口 → 打开 QuickPromptPanel
 * - 右下发送 / 停止
 *
 * 纯展示 + 交互，附件上传状态由父级 useAttachments 托管，
 * 发送时父级从 props 读取 attachmentIds 注入 chatStream。
 */
import { useState, useRef, type DragEvent, type ClipboardEvent } from 'react'
import { Input, Button, Upload } from 'antd'
import {
  PlusOutlined,
  SendOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { QuickPrompt } from '@/services/hermes'
import type { UploadItem } from '@/hooks/useAttachments'
import AttachmentChips from './AttachmentChips'
import QuickPromptPanel from './QuickPromptPanel'

const { TextArea } = Input

export interface ComposerInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  loading: boolean
  token: string | null
  attachmentItems: UploadItem[]
  onAddFiles: (files: FileList | File[]) => void
  onRemoveAttachment: (localId: string) => void
  quickPrompts: QuickPrompt[]
  quickPromptsLoading: boolean
  onSelectQuickPrompt: (p: QuickPrompt) => void
  disabled?: boolean
}

const ACCEPT =
  'image/*,.pdf,.doc,.docx,.xls,.xlsx,.md,.txt,.html,.htm,.epub'

export default function ComposerInput({
  value,
  onChange,
  onSend,
  onStop,
  loading,
  token,
  attachmentItems,
  onAddFiles,
  onRemoveAttachment,
  quickPrompts,
  quickPromptsLoading,
  onSelectQuickPrompt,
  disabled,
}: ComposerInputProps) {
  const [dragOver, setDragOver] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const inputRef = useRef<any>(null)

  const handleBeforeUpload = (file: File) => {
    onAddFiles([file])
    return false // 阻止 antd 自动上传
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files?.length) {
      onAddFiles(e.dataTransfer.files)
    }
  }

  const handlePaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items
    if (!items) return
    const files: File[] = []
    for (const it of items) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        const f = it.getAsFile()
        if (f) files.push(f)
      }
    }
    if (files.length) {
      e.preventDefault()
      onAddFiles(files)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!loading && value.trim()) onSend()
    }
  }

  const canSend = value.trim().length > 0 && !loading && !disabled

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="max-w-3xl mx-auto">
        <div
          className={`rounded-2xl border bg-white px-3 py-2 transition-all duration-200 ${
            dragOver
              ? 'border-blue-400 shadow-[0_0_0_3px_rgba(22,119,255,0.12)]'
              : 'border-gray-200'
          }`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {/* 附件 chips */}
          <AttachmentChips
            items={attachmentItems}
            token={token}
            onRemove={onRemoveAttachment}
          />

          <div className="flex items-end gap-2">
            {/* 左侧 + 上传 */}
            <Upload
              beforeUpload={handleBeforeUpload}
              showUploadList={false}
              multiple
              accept={ACCEPT}
            >
              <Button
                type="text"
                shape="circle"
                icon={<PlusOutlined />}
                disabled={loading}
                aria-label="添加附件"
              />
            </Upload>

            {/* 输入框 */}
            <TextArea
              ref={inputRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder="发送消息，或拖拽 / 粘贴文件…"
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={loading || disabled}
              bordered={false}
              className="flex-1 resize-none"
            />

            {/* 快捷指令 */}
            <Button
              type="text"
              icon={<ThunderboltOutlined />}
              onClick={() => setPanelOpen(true)}
              disabled={loading}
            >
              快捷指令
            </Button>

            {/* 发送 / 停止 */}
            {loading ? (
              <Button type="primary" danger icon={<StopOutlined />} onClick={onStop}>
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={onSend}
                disabled={!canSend}
              >
                发送
              </Button>
            )}
          </div>
        </div>
        <div className="mt-1.5 text-center">
          <span className="text-xs text-gray-400">
            Enter 发送，Shift+Enter 换行
          </span>
        </div>
      </div>

      <QuickPromptPanel
        open={panelOpen}
        prompts={quickPrompts}
        loading={quickPromptsLoading}
        onClose={() => setPanelOpen(false)}
        onSelect={(p) => {
          onSelectQuickPrompt(p)
          setPanelOpen(false)
          inputRef.current?.focus()
        }}
      />
    </div>
  )
}
