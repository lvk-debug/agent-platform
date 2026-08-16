import React, { useEffect, useState } from 'react'
import { Drawer, List, Tag, Typography, Spin, Empty, Collapse, Button } from 'antd'
import { FileTextOutlined, DownOutlined } from '@ant-design/icons'
import { knowledgeApi, DocumentSegmentData } from '../services/knowledge'

const { Text, Paragraph } = Typography

interface SegmentDrawerProps {
  visible: boolean
  onClose: () => void
  kbId: number
  docId: number
  docName: string
}

const SegmentDrawer: React.FC<SegmentDrawerProps> = ({
  visible,
  onClose,
  kbId,
  docId,
  docName,
}) => {
  const [segments, setSegments] = useState<DocumentSegmentData[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<number | null>(null)

  useEffect(() => {
    if (visible && docId) {
      setSegments([])
      setNextCursor(null)
      setHasMore(false)
      fetchSegments(true)
    }
  }, [visible, docId])

  const fetchSegments = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? undefined : nextCursor ?? undefined
      const response = await knowledgeApi.getSegments(kbId, docId, {
        cursor,
        limit: 50,
      })
      const { items, next_cursor, has_more } = response.data
      if (reset) {
        setSegments(items)
      } else {
        setSegments((prev) => [...prev, ...items])
      }
      setNextCursor(next_cursor)
      setHasMore(has_more)
    } catch {
      if (reset) setSegments([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <Drawer
      title={`文档分段 — ${docName}`}
      placement="right"
      width={640}
      onClose={onClose}
      open={visible}
    >
      {loading && segments.length === 0 ? (
        <div className="text-center p-10">
          <Spin tip="加载分段中..." />
        </div>
      ) : segments.length === 0 ? (
        <Empty description="暂无分段数据" />
      ) : (
        <div>
          <Text type="secondary" className="mb-4 block">
            已加载 {segments.length} 个分段
          </Text>
          <Collapse accordion>
            {segments.map((seg, index) => (
              <Collapse.Panel
                key={seg.id}
                header={
                  <span>
                    <Tag color="blue">#{index + 1}</Tag>
                    <Text ellipsis className="max-w-[360px]">
                      {seg.content.slice(0, 80)}...
                    </Text>
                    {seg.token_count && (
                      <Tag className="ml-2">{seg.token_count} 字符</Tag>
                    )}
                  </span>
                }
              >
                <div className="mb-2">
                  {seg.metadata_?.header_path && (
                    <Tag color="purple">{seg.metadata_.header_path}</Tag>
                  )}
                  {seg.metadata_?.has_table && <Tag color="orange">含表格</Tag>}
                </div>
                <Paragraph className="whitespace-pre-wrap bg-page p-3 rounded-md max-h-[400px] overflow-auto">
                  {seg.content}
                </Paragraph>
              </Collapse.Panel>
            ))}
          </Collapse>
          {hasMore && (
            <div className="text-center mt-4">
              <Button
                icon={<DownOutlined />}
                loading={loading}
                onClick={() => fetchSegments(false)}
              >
                加载更多
              </Button>
            </div>
          )}
        </div>
      )}
    </Drawer>
  )
}

export default SegmentDrawer
