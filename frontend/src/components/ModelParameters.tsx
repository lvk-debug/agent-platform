import React from 'react'
import { Modal, Form, InputNumber, Slider, Switch, Space, Tooltip } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { ModelParameters as ModelParametersType } from '../services/chatbot'

interface ModelParametersProps {
  open: boolean
  parameters: ModelParametersType
  onOk: (parameters: ModelParametersType) => void
  onCancel: () => void
}

const ModelParametersModal: React.FC<ModelParametersProps> = ({
  open,
  parameters,
  onOk,
  onCancel
}) => {
  const [form] = Form.useForm()

  React.useEffect(() => {
    if (open) {
      form.setFieldsValue(parameters)
    }
  }, [open, parameters, form])

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      onOk(values)
    } catch (error) {
      console.error('Validation failed:', error)
    }
  }

  return (
    <Modal
      title="模型设置"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      width={480}
      okText="确定"
      cancelText="取消"
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={parameters}
      >
        <Form.Item label={
          <Space>
            <span>温度</span>
            <Tooltip title="较高的值会使输出更加随机，较低的值会使其更加集中和确定">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="temperature" noStyle>
              <Slider min={0} max={2} step={0.1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="temperature" noStyle>
              <InputNumber min={0} max={2} step={0.1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>Top P</span>
            <Tooltip title="与温度一起调整，建议只修改其中一个">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="top_p" noStyle>
              <Slider min={0} max={1} step={0.1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="top_p" noStyle>
              <InputNumber min={0} max={1} step={0.1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>Top K</span>
            <Tooltip title="从概率最高的K个词中采样">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="top_k" noStyle>
              <Slider min={1} max={100} step={1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="top_k" noStyle>
              <InputNumber min={1} max={100} step={1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>存在惩罚</span>
            <Tooltip title="根据新词是否出现在原文中进行惩罚">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="presence_penalty" noStyle>
              <Slider min={-2} max={2} step={0.1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="presence_penalty" noStyle>
              <InputNumber min={-2} max={2} step={0.1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>频率惩罚</span>
            <Tooltip title="根据新词在原文中出现的频率进行惩罚">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="frequency_penalty" noStyle>
              <Slider min={-2} max={2} step={0.1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="frequency_penalty" noStyle>
              <InputNumber min={-2} max={2} step={0.1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>最大生成长度</span>
            <Tooltip title="单次回复的最大Token数">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Space className="w-full">
            <Form.Item name="max_tokens" noStyle>
              <Slider min={1} max={8192} step={1} className="w-[200px]" />
            </Form.Item>
            <Form.Item name="max_tokens" noStyle>
              <InputNumber min={1} max={8192} step={1} className="w-[60px]" />
            </Form.Item>
          </Space>
        </Form.Item>

        <Form.Item label={
          <Space>
            <span>跳过内容审核</span>
            <Tooltip title="开启后将跳过内容安全检查">
              <QuestionCircleOutlined className="text-text-secondary" />
            </Tooltip>
          </Space>
        }>
          <Form.Item name="skip_content_review" valuePropName="checked" noStyle>
            <Switch />
          </Form.Item>
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default ModelParametersModal
