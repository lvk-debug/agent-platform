/**
 * 技能管理页
 *
 * 管理工作助理可选的技能（Hermes Skill）：
 * 新建 / 编辑 / 停用 / 删除，选中后在工作助理对话中作为 system 指令注入。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  App as AntApp,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  HermesSkill,
  HermesSkillInput,
  createSkill,
  deleteSkill,
  getSkills,
  updateSkill,
} from '@/services/hermes'

const { Title, Text } = Typography
const { TextArea } = Input

const HermesSkills: React.FC = () => {
  const { message } = AntApp.useApp()
  const [skills, setSkills] = useState<HermesSkill[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [editing, setEditing] = useState<HermesSkill | null>(null)
  const [modalVisible, setModalVisible] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm<HermesSkillInput>()

  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSkills({ keyword: keyword || undefined })
      setSkills(data)
    } catch {
      message.error('加载技能列表失败')
    } finally {
      setLoading(false)
    }
  }, [keyword, message])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  const stats = useMemo(() => {
    const enabled = skills.filter((s) => s.enabled).length
    return { total: skills.length, enabled, disabled: skills.length - enabled }
  }, [skills])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ enabled: true, sort_order: 0, icon: '🧩' })
    setModalVisible(true)
  }

  const openEdit = (skill: HermesSkill) => {
    setEditing(skill)
    form.setFieldsValue({
      name: skill.name,
      slug: skill.slug,
      description: skill.description,
      instruction: skill.instruction,
      icon: skill.icon,
      enabled: skill.enabled,
      sort_order: skill.sort_order,
    })
    setModalVisible(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (editing) {
        await updateSkill(editing.id, values)
        message.success('技能已更新')
      } else {
        await createSkill(values)
        message.success('技能已创建')
      }
      setModalVisible(false)
      await loadSkills()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || '保存失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (skillId: string) => {
    try {
      await deleteSkill(skillId)
      message.success('技能已删除')
      await loadSkills()
    } catch {
      message.error('删除失败')
    }
  }

  const handleToggle = async (skill: HermesSkill, enabled: boolean) => {
    try {
      await updateSkill(skill.id, { enabled })
      setSkills((prev) =>
        prev.map((item) => (item.id === skill.id ? { ...item, enabled } : item))
      )
    } catch {
      message.error('状态更新失败')
    }
  }

  const columns: ColumnsType<HermesSkill> = [
    {
      title: '技能',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Space>
          <span className="text-lg">{record.icon || '🧩'}</span>
          <div>
            <div className="font-medium text-gray-800">{name}</div>
            <Text type="secondary" className="text-xs">
              {record.slug}
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => <span className="text-gray-600">{text || '—'}</span>,
    },
    {
      title: '注入指令',
      dataIndex: 'instruction',
      key: 'instruction',
      ellipsis: true,
      render: (text: string) => (
        <Text type="secondary" className="text-xs">
          {text || '—'}
        </Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean, record) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={(checked) => handleToggle(record, checked)}
        />
      ),
    },
    {
      title: '排序',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 80,
      render: (order: number) => <Tag>{order ?? 0}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 110,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          />
          <Popconfirm
            title="确定删除该技能？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Title level={4} className="!mb-1">
            技能管理
          </Title>
          <Text type="secondary">
            管理工作助理可勾选的技能，选中后以系统指令形式注入对话，不影响 Hermes 内置能力
          </Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建技能
        </Button>
      </div>

      <Row gutter={16} className="mb-4">
        <Col span={8}>
          <Card size="small">
            <Statistic title="技能总数" value={stats.total} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="启用中" value={stats.enabled} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="已停用" value={stats.disabled} valueStyle={{ color: '#9ca3af' }} />
          </Card>
        </Col>
      </Row>

      <Card>
        <Input.Search
          placeholder="搜索技能名称 / 标识 / 描述"
          allowClear
          style={{ maxWidth: 320, marginBottom: 16 }}
          onSearch={(value) => setKeyword(value.trim())}
        />

        <Spin spinning={loading}>
          {skills.length === 0 && !loading ? (
            <Empty description="暂无技能，点击右上角新建">
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
                新建技能
              </Button>
            </Empty>
          ) : (
            <Table
              rowKey="id"
              columns={columns}
              dataSource={skills}
              pagination={false}
              size="middle"
            />
          )}
        </Spin>
      </Card>

      <Modal
        title={editing ? '编辑技能' : '新建技能'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ enabled: true, sort_order: 0 }}>
          <Form.Item
            name="name"
            label="技能名称"
            rules={[{ required: true, message: '请输入技能名称' }]}
          >
            <Input placeholder="如：代码助手" maxLength={100} />
          </Form.Item>
          <Form.Item
            name="slug"
            label="唯一标识"
            extra="用于注入与存储的英文标识，不可重复"
            rules={[
              { required: true, message: '请输入唯一标识' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持字母、数字、下划线与中划线' },
            ]}
          >
            <Input placeholder="如：coding" maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="技能描述">
            <TextArea rows={2} placeholder="一句话说明这个技能适合什么场景" />
          </Form.Item>
          <Form.Item
            name="instruction"
            label="注入指令"
            extra="勾选该技能后追加到 system 指令中的内容"
          >
            <TextArea rows={4} placeholder="如：请以资深工程师标准作答，给出完整可运行代码……" />
          </Form.Item>
          <div className="flex gap-4">
            <Form.Item name="icon" label="图标" className="flex-1">
              <Input placeholder="🧩" maxLength={20} />
            </Form.Item>
            <Form.Item name="sort_order" label="排序" className="flex-1">
              <InputNumber min={0} max={9999} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default HermesSkills
