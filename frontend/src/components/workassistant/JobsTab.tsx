/**
 * 能力设置抽屉 - 后台任务 Tab
 *
 * 代理 Hermes Jobs API：列表 / 新建 / 编辑 / 删除 / 暂停 / 恢复 / 立即执行。
 * 上游不支持时给出友好提示，不弹错误。
 */
import React, { useState } from 'react'
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  App as AntApp,
} from 'antd'
import { DeleteOutlined, PauseCircleOutlined, PlayCircleOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  HermesJob,
  HermesSkill,
  controlJob,
  createJob,
  deleteJob,
  getJobs,
  updateJob,
} from '@/services/hermes'

const { Text } = Typography
const { TextArea } = Input

interface JobsTabProps {
  skills: HermesSkill[]
  supported: boolean
  onUnsupported?: () => void
}

const JobsTab: React.FC<JobsTabProps> = ({ skills }) => {
  const { message } = AntApp.useApp()
  const [jobs, setJobs] = useState<HermesJob[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [modalVisible, setModalVisible] = useState(false)
  const [editing, setEditing] = useState<HermesJob | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm<{ prompt: string; schedule: string; skills?: string[] }>()

  const loadJobs = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await getJobs()
      setJobs(data)
      setError('')
    } catch {
      setError('当前 Hermes 版本不支持后台任务，或任务服务不可用')
    } finally {
      setLoading(false)
      setLoaded(true)
    }
  }, [])

  React.useEffect(() => {
    if (!loaded) loadJobs()
  }, [loaded, loadJobs])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalVisible(true)
  }

  const openEdit = (job: HermesJob) => {
    setEditing(job)
    const scheduleStr =
      typeof job.schedule === 'string'
        ? job.schedule
        : (job.schedule as any)?.expr || ''
    form.setFieldsValue({
      prompt: job.prompt || '',
      schedule: scheduleStr,
      skills: job.skills || [],
    })
    setModalVisible(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (editing) {
        await updateJob(editing.id, values)
        message.success('任务已更新')
      } else {
        await createJob(values)
        message.success('任务已创建')
      }
      setModalVisible(false)
      await loadJobs()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleControl = async (job: HermesJob, action: 'pause' | 'resume' | 'run') => {
    try {
      await controlJob(job.id, action)
      const text = action === 'run' ? '已触发执行' : action === 'pause' ? '已暂停' : '已恢复'
      message.success(text)
      await loadJobs()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (jobId: string) => {
    try {
      await deleteJob(jobId)
      message.success('任务已删除')
      await loadJobs()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败')
    }
  }

  const columns: ColumnsType<HermesJob> = [
    {
      title: '任务',
      dataIndex: 'prompt',
      key: 'prompt',
      render: (text: string, record) => {
        const scheduleStr =
          typeof record.schedule === 'string'
            ? record.schedule
            : (record.schedule as any)?.display ||
              (record.schedule as any)?.expr ||
              JSON.stringify(record.schedule)
        return (
          <div className="min-w-0">
            <div className="text-sm text-gray-800 line-clamp-2">{record.name || text}</div>
            <Text type="secondary" className="text-xs">
              {scheduleStr || '未设置周期'}
            </Text>
          </div>
        )
      },
    },
    {
      title: '技能',
      dataIndex: 'skills',
      key: 'skills',
      width: 140,
      render: (list?: string[]) =>
        list && list.length ? (
          <Space size={4} wrap>
            {list.map((s) => (
              <Tag key={s}>{s}</Tag>
            ))}
          </Space>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status?: string, record?: HermesJob) => (
        <Tag color={record?.paused ? 'orange' : status === 'error' ? 'red' : 'green'}>
          {record?.paused ? '已暂停' : status || '运行中'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      render: (_, record) => (
        <Space size={4}>
          <Button type="text" size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            type="text"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleControl(record, 'run')}
          >
            执行
          </Button>
          <Button
            type="text"
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={() => handleControl(record, record.paused ? 'resume' : 'pause')}
          >
            {record.paused ? '恢复' : '暂停'}
          </Button>
          <Popconfirm title="确定删除该任务？" okText="删除" cancelText="取消" onConfirm={() => handleDelete(record.id)}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <Text type="secondary" className="text-xs">
          管理 Hermes 后台计划任务（prompt + 周期 + 技能）
        </Text>
        <Space>
          <Button size="small" onClick={loadJobs} loading={loading}>
            刷新
          </Button>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建任务
          </Button>
        </Space>
      </div>

      {error && <Alert type="warning" showIcon message={error} className="mb-3" />}

      <Spin spinning={loading}>
        {jobs.length === 0 && !loading ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={error ? '暂不可用' : '暂无后台任务'}
          />
        ) : (
          <Table
            rowKey="id"
            size="small"
            columns={columns}
            dataSource={jobs}
            pagination={false}
          />
        )}
      </Spin>

      <Modal
        title={editing ? '编辑任务' : '新建任务'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="schedule"
            label="执行周期"
            extra="cron 表达式，如 0 9 * * 1（每周一 9:00）"
            rules={[{ required: true, message: '请输入执行周期' }]}
          >
            <Input placeholder="0 9 * * 1" />
          </Form.Item>
          <Form.Item
            name="prompt"
            label="任务提示词"
            rules={[{ required: true, message: '请输入任务提示词' }]}
          >
            <TextArea rows={4} placeholder="如：汇总本周项目进展并生成周报" />
          </Form.Item>
          <Form.Item name="skills" label="关联技能">
            <Select
              mode="multiple"
              allowClear
              placeholder="可选，关联工作助理技能"
              options={skills.map((s) => ({ value: s.slug, label: s.name }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default JobsTab
