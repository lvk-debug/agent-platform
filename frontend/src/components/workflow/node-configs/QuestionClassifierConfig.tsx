/**
 * 问题分类节点配置 — 模型 / 输入变量 / 分类列表
 */
import React from 'react'
import {
  Form, Input, Select, Switch, Button, Typography, Tooltip,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, SettingOutlined, InfoCircleOutlined,
  CopyOutlined, FunctionOutlined,
} from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { ModelData } from '@/services/models'
import type { UpstreamNode } from '../shared/VarDropdown'

const { TextArea } = Input
const { Text } = Typography

interface QuestionClassifierConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
  availableModels: ModelData[]
  modelsLoading: boolean
}

const QuestionClassifierConfig: React.FC<QuestionClassifierConfigProps> = ({
  form, upstreamNodes, availableModels, modelsLoading,
}) => (
  <>
    {/* 模型 */}
    <div className="mb-5">
      <div className="flex items-center gap-1 mb-2">
        <span className="text-red-500">*</span>
        <Text strong>模型</Text>
        <Tooltip title="选择用于分类的大语言模型">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <div className="flex gap-2">
        <Form.Item name="model_id" noStyle>
          <Select
            placeholder={modelsLoading ? "加载中..." : "选择模型"}
            className="flex-1"
            allowClear
            showSearch
            optionFilterProp="label"
            loading={modelsLoading}
            notFoundContent={modelsLoading ? "加载中..." : "暂无可用模型"}
          >
            {availableModels.filter(m => m.is_active).map((model) => (
              <Select.Option key={model.id} value={model.id} label={model.name}>
                <div className="flex items-center justify-between">
                  <span>{model.name}</span>
                  <span className="text-xs text-gray-400">{model.model_id}</span>
                </div>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Tooltip title="模型设置">
          <Button icon={<SettingOutlined />} />
        </Tooltip>
      </div>
    </div>

    {/* 输入变量 */}
    <div className="mb-5">
      <div className="flex items-center gap-1 mb-2">
        <span className="text-red-500">*</span>
        <Text strong>输入变量</Text>
        <Tooltip title="选择要分类的输入文本变量">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <Form.Item name="input_variable" noStyle>
        <Select placeholder="选择变量" allowClear showSearch>
          {upstreamNodes.map((n) => (
            <Select.Option key={n.id} value={`${n.id}.output`}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace', background: '#f5f5f5', padding: '1px 4px', borderRadius: 3 }}>{'{x}'}</span>
                {n.data?.label || n.id} . output
              </span>
            </Select.Option>
          ))}
        </Select>
      </Form.Item>
    </div>

    {/* 视觉 */}
    <div className="mb-5 flex items-center justify-between">
      <div className="flex items-center gap-1">
        <Text strong>视觉</Text>
        <Tooltip title="启用后可以处理图片输入">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <Form.Item name="vision" valuePropName="checked" noStyle>
        <Switch size="small" />
      </Form.Item>
    </div>

    {/* 分类 */}
    <div className="mb-5">
      <div className="flex items-center gap-1 mb-3">
        <span className="text-red-500">*</span>
        <Text strong>分类</Text>
        <Tooltip title="定义问题的分类类别，每个类别对应一个输出分支">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <Form.List
        name="categories"
        initialValue={[
          { id: '1', name: 'CLASS 1', description: '' },
          { id: '2', name: 'CLASS 2', description: '' },
        ]}
      >
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }) => (
              <div key={key} className="border border-gray-200 rounded-lg mb-3 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2" style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                  <Form.Item {...restField} name={[name, 'name']} noStyle>
                    <Input placeholder="CLASS" size="small" style={{ width: 140, fontWeight: 600, fontSize: 13 }} />
                  </Form.Item>
                  <div className="flex items-center gap-1">
                    <Tooltip title="变量">
                      <FunctionOutlined className="text-gray-400 text-sm cursor-pointer" />
                    </Tooltip>
                    <Tooltip title="复制">
                      <Button
                        type="text" size="small" icon={<CopyOutlined />}
                        onClick={() => {
                          const current = form.getFieldValue(['categories', name])
                          add({ ...current, id: Date.now().toString() }, name + 1)
                        }}
                      />
                    </Tooltip>
                    {fields.length > 1 && (
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(name)} />
                    )}
                  </div>
                </div>
                <div className="p-3">
                  <Form.Item {...restField} name={[name, 'description']} noStyle>
                    <TextArea rows={2} placeholder="在这里输入你的主题内容" style={{ fontSize: 13 }} />
                  </Form.Item>
                </div>
              </div>
            ))}
            <Button type="dashed" onClick={() => add({ id: Date.now().toString(), name: `CLASS ${fields.length + 1}`, description: '' })} icon={<PlusOutlined />} block>
              添加分类
            </Button>
          </>
        )}
      </Form.List>
    </div>

    {/* 高级设置 */}
    <div className="mb-5">
      <Text strong className="text-gray-500">高级设置</Text>
    </div>

    {/* 输出变量 */}
    <div className="mb-5">
      <Text strong className="text-gray-500">输出变量</Text>
      <div className="mt-2 text-xs text-gray-400">输出分类结果到下一个节点</div>
    </div>

    <Form.Item name="output_key" label="输出键名" initialValue="classification" hidden>
      <Input />
    </Form.Item>
  </>
)

export default QuestionClassifierConfig
