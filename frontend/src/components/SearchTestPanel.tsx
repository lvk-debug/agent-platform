import React, { useState } from 'react'
import { Card, Input, Button, List, Tag, Typography, Empty, Spin, Space, Segmented, Switch, Tooltip } from 'antd'
import { SearchOutlined, FileTextOutlined, SortAscendingOutlined } from '@ant-design/icons'
import { knowledgeApi, SearchResultItem, SearchMode } from '../services/knowledge'

const { Text, Paragraph } = Typography

interface SearchTestPanelProps {
  kbId: number
}

const MODE_OPTIONS = [
  { label: '向量检索', value: 'vector' },
  { label: 'BM25 检索', value: 'bm25' },
  { label: 'RRF 混合', value: 'rrf' },
]

const SearchTestPanel: React.FC<SearchTestPanelProps> = ({ kbId }) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [searchMode, setSearchMode] = useState<SearchMode>('rrf')
  const [enableRerank, setEnableRerank] = useState(false)

  const handleSearch = async (value: string) => {
    if (!value.trim()) return

    setLoading(true)
    setSearched(true)
    try {
      const response = await knowledgeApi.searchKnowledgeBase(kbId, value, 5, 0, searchMode, enableRerank)
      setResults(response.data.results)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return 'green'
    if (score >= 0.4) return 'orange'
    return 'red'
  }

  const renderScoreTags = (item: SearchResultItem, index: number) => {
    const tags = [
      <Tag key="rank" color="blue">#{index + 1}</Tag>,
      <Tag key="score" color={getScoreColor(item.score)}>
        score: {item.score.toFixed(4)}
      </Tag>,
    ]

    // 重排序分数
    if (enableRerank && item.rerank_score != null) {
      tags.push(
        <Tag key="rerank" color="gold">
          重排: {item.rerank_score.toFixed(4)}
        </Tag>
      )
    }

    // RRF 模式下展示子分数
    if (searchMode === 'rrf') {
      if (item.vector_score != null) {
        tags.push(
          <Tag key="vs" color="purple">
            向量: {item.vector_score.toFixed(4)}
          </Tag>
        )
      }
      if (item.bm25_score != null) {
        tags.push(
          <Tag key="bs" color="cyan">
            BM25: {item.bm25_score.toFixed(4)}
          </Tag>
        )
      }
    }

    return tags
  }

  return (
    <Card
      title="检索测试"
      size="small"
      className="mt-4"
    >
      <Space direction="vertical" className="w-full" size="middle">
        <Segmented
          options={MODE_OPTIONS}
          value={searchMode}
          onChange={(val) => setSearchMode(val as SearchMode)}
          block
        />

        <div className="flex items-center justify-between">
          <Tooltip title="使用 BAAI/bge-reranker-base 模型对检索结果进行二次排序，提升精度（首次加载较慢）">
            <Space>
              <SortAscendingOutlined />
              <span>重排序</span>
              <Switch
                size="small"
                checked={enableRerank}
                onChange={setEnableRerank}
                checkedChildren="开"
                unCheckedChildren="关"
              />
            </Space>
          </Tooltip>
        </div>

        <Input.Search
          placeholder="输入检索内容，测试知识库检索效果"
          enterButton={
            <span>
              <SearchOutlined /> 检索
            </span>
          }
          size="large"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onSearch={handleSearch}
          loading={loading}
        />
      </Space>

      <div className="mt-4">
        {loading ? (
          <div className="text-center p-6">
            <Spin tip="检索中..." />
          </div>
        ) : !searched ? (
          <Empty
            description="输入关键词测试检索效果"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : results.length === 0 ? (
          <Empty description="未找到匹配结果" />
        ) : (
          <List
            itemLayout="vertical"
            dataSource={results}
            renderItem={(item, index) => (
              <List.Item key={item.segment_id}>
                <div className="mb-2">
                  <Space wrap>
                    {renderScoreTags(item, index)}
                    {item.document_name && (
                      <Text type="secondary">
                        <FileTextOutlined /> {item.document_name}
                      </Text>
                    )}
                  </Space>
                </div>
                <Paragraph
                  ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                  className="mb-0"
                >
                  {item.content}
                </Paragraph>
              </List.Item>
            )}
          />
        )}
      </div>
    </Card>
  )
}

export default SearchTestPanel
