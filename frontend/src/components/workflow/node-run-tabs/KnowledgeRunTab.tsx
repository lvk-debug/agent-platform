/**
 * 知识检索运行调试 Tab — 查询输入 / 运行按钮 / 结果列表
 */
import React from 'react'
import { Input, Button, Typography, Tag } from 'antd'
import { CaretRightOutlined } from '@ant-design/icons'

const { Text } = Typography

interface KnowledgeRunTabProps {
  lastRunQuery: string
  onQueryChange: (value: string) => void
  lastRunResults: any
  lastRunLoading: boolean
  onRun: () => void
}

const KnowledgeRunTab: React.FC<KnowledgeRunTabProps> = ({
  lastRunQuery, onQueryChange, lastRunResults, lastRunLoading, onRun,
}) => (
  <div className="mt-2">
    {/* 查询输入 */}
    <div className="mb-4">
      <Text strong className="block mb-2">查询文本</Text>
      <Input.TextArea
        value={lastRunQuery}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={'支持单条或多条查询，多条请换行输入，例如：\n什么是机器学习？\n如何训练深度学习模型？\n神经网络的基本原理'}
        autoSize={{ minRows: 3, maxRows: 8 }}
        style={{ fontFamily: 'monospace', fontSize: 13 }}
      />
      <div className="text-xs text-gray-400 mt-1">每行一条查询，将分别检索后合并去重</div>
    </div>

    {/* 运行按钮 */}
    <div className="mb-4">
      <Button type="primary" icon={<CaretRightOutlined />} loading={lastRunLoading} onClick={onRun} block>
        运行
      </Button>
    </div>

    {/* 运行结果 */}
    {lastRunResults ? (
      <div>
        <div className="text-xs text-gray-500 mb-2">
          {lastRunResults.queries && lastRunResults.queries.length > 1 ? (
            <>批量查询 <code>{lastRunResults.queries.length}</code> 条 · </>
          ) : (
            <>查询: <code>{lastRunResults.queries?.[0] || lastRunResults.query}</code> · </>
          )}
          共 {lastRunResults.total} 条结果
        </div>
        {lastRunResults.results.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-xs">无匹配结果</div>
        ) : (
          <div className="space-y-2">
            {lastRunResults.results.map((item: any, idx: number) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-gray-700 truncate">{item.document_name}</span>
                  <Tag color={item.score >= 0.8 ? 'green' : item.score >= 0.5 ? 'orange' : 'default'} style={{ marginRight: 0 }}>
                    {(item.score * 100).toFixed(1)}%
                  </Tag>
                </div>
                <div className="text-gray-500" style={{ fontSize: 12, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {item.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    ) : (
      <div className="text-center py-8 text-gray-400">暂无运行记录</div>
    )}
  </div>
)

export default KnowledgeRunTab
