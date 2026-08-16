import React, { useState } from 'react'
import { Card, Input, Button, List, Tag, Typography, Empty, Spin, Space } from 'antd'
import { SearchOutlined, FileTextOutlined } from '@ant-design/icons'
import { knowledgeApi, SearchResultItem } from '../services/knowledge'

const { Text, Paragraph } = Typography
const { Search } = Input

interface SearchTestPanelProps {
  kbId: number
}

const SearchTestPanel: React.FC<SearchTestPanelProps> = ({ kbId }) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (value: string) => {
    if (!value.trim()) return

    setLoading(true)
    setSearched(true)
    try {
      const response = await knowledgeApi.searchKnowledgeBase(kbId, value, 5, 0)
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

  return (
    <Card
      title="检索测试"
      size="small"
      style={{ marginTop: 16 }}
    >
      <Search
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

      <div style={{ marginTop: 16 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
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
                <div style={{ marginBottom: 8 }}>
                  <Space>
                    <Tag color="blue">#{index + 1}</Tag>
                    <Tag color={getScoreColor(item.score)}>
                      相似度: {(item.score * 100).toFixed(1)}%
                    </Tag>
                    <Text type="secondary">
                      <FileTextOutlined /> {item.document_name}
                    </Text>
                  </Space>
                </div>
                <Paragraph
                  ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                  style={{ marginBottom: 0 }}
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
