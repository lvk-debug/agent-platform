/**
 * 画布截图导出弹窗
 *
 * 预览合成结果 → 填写备注 → 确认导出。
 * 导出图会回传后端留档，随后可在「学习记录」中回看，同时本地下载一份。
 */

import React, { useEffect, useState } from 'react'
import { Modal, Button, Input, Radio, Alert, Spin } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'

export type ExportRange = 'current' | 'all'

interface ExportSnapshotDialogProps {
  open: boolean
  pageIndex: number
  pageCount: number
  onClose: () => void
  /** 预览当前页合成结果，返回 dataURL */
  onPreview: () => Promise<string>
  /** 执行导出（父层负责合成、上传、触发下载） */
  onExport: (range: ExportRange, note: string) => Promise<void>
}

const ExportSnapshotDialog: React.FC<ExportSnapshotDialogProps> = ({
  open,
  pageIndex,
  pageCount,
  onClose,
  onPreview,
  onExport,
}) => {
  const [range, setRange] = useState<ExportRange>('current')
  const [note, setNote] = useState('')
  const [preview, setPreview] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setPreview(null)
      setError(null)
      setNote('')
      return
    }
    setPreviewing(true)
    onPreview()
      .then(setPreview)
      .catch((previewError) => {
        console.error('生成导出预览失败', previewError)
        setError('生成预览失败，请确认文档已渲染完成')
      })
      .finally(() => setPreviewing(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, pageIndex])

  const handleExport = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await onExport(range, note)
      onClose()
    } catch (exportError) {
      console.error('导出失败', exportError)
      setError('导出失败，请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      title="导出画布截图"
      onCancel={() => !submitting && onClose()}
      width={620}
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={submitting}
            onClick={() => void handleExport()}
            className="!border-0 !bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)]"
          >
            {range === 'all' ? `导出全部 ${pageCount} 页` : '导出当前页'}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 py-2">
        <Radio.Group
          value={range}
          onChange={(event) => setRange(event.target.value)}
          className="!flex !gap-3"
        >
          <Radio.Button value="current">当前页（第 {pageIndex + 1} 页）</Radio.Button>
          <Radio.Button value="all">全部 {pageCount} 页</Radio.Button>
        </Radio.Group>

        <div className="flex min-h-[220px] items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
          {previewing ? (
            <Spin tip="正在合成…" />
          ) : preview ? (
            <img src={preview} alt="导出预览" className="max-h-[280px] w-auto object-contain" />
          ) : (
            <span className="text-sm text-slate-400">暂无预览</span>
          )}
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">备注（可选）</label>
          <Input.TextArea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            maxLength={200}
            placeholder="例如：第三章重点公式"
          />
        </div>

        {range === 'all' && pageCount > 12 && (
          <Alert
            type="warning"
            showIcon
            message={`共 ${pageCount} 页，逐页合成可能耗时较久，请保持页面开启`}
          />
        )}

        {error && <Alert type="error" showIcon message={error} />}
      </div>
    </Modal>
  )
}

export default ExportSnapshotDialog
