/**
 * 知识检索节点配置 — 查询变量 / 知识库选择 / 召回设置 / 输出变量
 */
import React from 'react'
import {
  Form, Input, Select, InputNumber, Switch, Tag, Button,
  Typography, Tooltip,
} from 'antd'
import {
  InfoCircleOutlined, PlusOutlined, SettingOutlined, BookOutlined,
} from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { KnowledgeBaseData } from '@/services/knowledge'
import type { UpstreamNode } from '../shared/VarDropdown'
import PromptEditor from '../shared/PromptEditor'

const { Text } = Typography

interface KnowledgeConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
  availableKBs: KnowledgeBaseData[]
  kbsLoading: boolean
}

const KnowledgeConfig: React.FC<KnowledgeConfigProps> = ({
  form, upstreamNodes, availableKBs, kbsLoading,
}) => (
  <>
    {/* 查询文本 */}
    <PromptEditor
      form={form}
      upstreamNodes={upstreamNodes}
      fieldName="query_variable"
      label="查询文本"
      placeholder="输入查询内容，按 { 插入变量，如 {{start.query}}"
      minRows={2}
    />

    {/* 知识库 */}
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1">
          <span className="text-red-500">*</span>
          <Text strong>知识库</Text>
        </div>
        <div className="flex items-center gap-2">
          <Button type="link" size="small" icon={<SettingOutlined />} className="text-xs px-0">召回设置</Button>
          <Button type="link" size="small" icon={<PlusOutlined />} className="text-xs px-0">添加</Button>
        </div>
      </div>
      <Form.Item name="knowledge_base_ids" noStyle>
        <Select
          mode="multiple"
          placeholder={kbsLoading ? "加载中..." : "选择知识库"}
          className="w-full"
          loading={kbsLoading}
          notFoundContent={kbsLoading ? "加载中..." : "暂无知识库"}
          optionFilterProp="label"
          tagRender={({ label, closable, onClose }) => (
            <Tag closable={closable} onClose={onClose} color="blue" style={{ margin: 2 }}>
              {label}
            </Tag>
          )}
        >
          {availableKBs.map((kb) => (
            <Select.Option key={kb.id} value={kb.id} label={kb.name}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOutlined className="text-purple-500" />
                  <span>{kb.name}</span>
                </div>
                <Tag color="blue" style={{ marginRight: 0, fontSize: 11 }}>
                  {kb.document_count} 文档
                </Tag>
              </div>
            </Select.Option>
          ))}
        </Select>
      </Form.Item>
    </div>

    {/* 召回设置 */}
    <div className="mb-5 p-3 bg-gray-50 rounded-lg">
      <Text strong className="block mb-3">召回设置</Text>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Text type="secondary" className="text-xs block mb-1">返回数量</Text>
          <Form.Item name="top_k" noStyle initialValue={5}>
            <InputNumber className="w-full" size="small" min={1} max={20} />
          </Form.Item>
        </div>
        <div>
          <Text type="secondary" className="text-xs block mb-1">相似度阈值</Text>
          <Form.Item name="score_threshold" noStyle initialValue={0.5}>
            <InputNumber className="w-full" size="small" min={0} max={1} step={0.05} />
          </Form.Item>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Text type="secondary" className="text-xs">启用重排序</Text>
        <Form.Item name="rerank_enabled" valuePropName="checked" noStyle initialValue={false}>
          <Switch size="small" />
        </Form.Item>
      </div>
      <Form.Item name="rerank_top_k" noStyle initialValue={3}>
        <div className="mt-2 flex items-center gap-2">
          <Text type="secondary" className="text-xs whitespace-nowrap">重排序 Top-K</Text>
          <InputNumber size="small" className="flex-1" min={1} max={20} />
        </div>
      </Form.Item>
    </div>

    {/* 元数据过滤 */}
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1">
          <Text strong>元数据过滤</Text>
          <Tooltip title="根据元数据条件过滤检索结果">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="metadata_filter_enabled" valuePropName="checked" noStyle>
          <Switch size="small" />
        </Form.Item>
      </div>
    </div>

    {/* 输出变量 */}
    <div className="mb-4">
      <div className="flex items-center gap-1 mb-2">
        <Text strong>输出变量</Text>
      </div>
      <div className="p-3 bg-gray-50 rounded-lg text-xs">
        <div className="mb-2">
          <span className="font-medium">result</span> <span className="text-gray-500">Array[Object]</span>
          <div className="text-gray-400 mt-0.5">召回的分段</div>
        </div>
        <div className="pl-4 space-y-1.5 text-gray-600">
          <div><code className="text-xs">content</code> <span className="text-gray-400">string</span> <span className="text-gray-400 ml-1">分段内容</span></div>
          <div><code className="text-xs">title</code> <span className="text-gray-400">string</span> <span className="text-gray-400 ml-1">分段标题</span></div>
          <div><code className="text-xs">url</code> <span className="text-gray-400">string</span> <span className="text-gray-400 ml-1">分段链接</span></div>
          <div><code className="text-xs">icon</code> <span className="text-gray-400">string</span> <span className="text-gray-400 ml-1">分段图标</span></div>
          <div><code className="text-xs">metadata</code> <span className="text-gray-400">object</span> <span className="text-gray-400 ml-1">其他元数据</span></div>
          <div><code className="text-xs">files</code> <span className="text-gray-400">Array[File]</span> <span className="text-gray-400 ml-1">召回的文件</span></div>
        </div>
      </div>
    </div>

    <Form.Item name="output_key" hidden initialValue="result">
      <Input />
    </Form.Item>
  </>
)

export default KnowledgeConfig
