/**
 * 客户管理
 *
 * 客户档案的增删改查；从客户卡片可看到其历史会话与工单数量，
 * 需要追溯时直接在工单中心按客户筛选。
 */

import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Input,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  message as antdMessage,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import CustomerFormModal from '../../components/support/CustomerFormModal'
import supportApi from '../../services/support'
import type { OptionItem, SupportCustomer } from '../../types/support'

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const Customers: React.FC = () => {
  const navigate = useNavigate()
  const [items, setItems] = useState<SupportCustomer[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const [keyword, setKeyword] = useState('')
  const [source, setSource] = useState<string | undefined>()
  const [sourceOptions, setSourceOptions] = useState<OptionItem[]>([])

  const [modal, setModal] = useState<{
    open: boolean
    mode: 'create' | 'edit'
    customerId: number | null
  }>({ open: false, mode: 'create', customerId: null })

  useEffect(() => {
    supportApi
      .options()
      .then((res) => setSourceOptions(res.customer_sources))
      .catch(() => undefined)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await supportApi.listCustomers({
        keyword: keyword || undefined,
        source,
        page,
        page_size: pageSize,
      })
      setItems(res.items || [])
      setTotal(res.meta?.total || 0)
    } catch (err) {
      console.error('加载客户列表失败:', err)
    } finally {
      setLoading(false)
    }
  }, [keyword, source, page])

  useEffect(() => {
    void load()
  }, [load])

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await supportApi.deleteCustomer(id)
        antdMessage.success('已删除')
        void load()
      } catch (err) {
        console.error('删除客户失败:', err)
        antdMessage.error('删除失败')
      }
    },
    [load]
  )

  const columns: ColumnsType<SupportCustomer> = [
    {
      title: '客户',
      dataIndex: 'name',
      render: (value: string, row) => (
        <div>
          <div className="font-medium text-slate-800">{value}</div>
          <div className="text-xs text-slate-400">
            {row.phone || '未留手机号'}
            {row.wechat ? ` · 微信 ${row.wechat}` : ''}
          </div>
        </div>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      width: 100,
      render: (value: string, row) => <Tag className="!m-0">{row.source_label || value}</Tag>,
    },
    {
      title: '咨询次数',
      dataIndex: 'session_count',
      width: 100,
    },
    {
      title: '工单数',
      dataIndex: 'ticket_count',
      width: 90,
      render: (value: number, row) => (
        <Button
          type="link"
          size="small"
          className="!px-0"
          disabled={value === 0}
          onClick={() => navigate(`/support/tickets?customer=${row.id}`)}
        >
          {value}
        </Button>
      ),
    },
    {
      title: '最近咨询',
      dataIndex: 'last_session_at',
      width: 150,
      render: (value: string) =>
        value ? (
          <span className="text-xs text-slate-500">
            {dayjs(value).format('YYYY-MM-DD HH:mm')}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        ),
    },
    {
      title: '操作',
      width: 130,
      render: (_, row) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            onClick={() => setModal({ open: true, mode: 'edit', customerId: row.id })}
          >
            编辑
          </Button>
          <Popconfirm title="确认删除该客户？" onConfirm={() => handleDelete(row.id)}>
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <Segmented
          value="/support/customers"
          options={NAV_ITEMS}
          onChange={(value) => navigate(value as string)}
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input.Search
            allowClear
            placeholder="姓名 / 手机号 / 微信"
            className="w-64"
            onSearch={(value) => {
              setKeyword(value)
              setPage(1)
            }}
          />
          <Select
            allowClear
            placeholder="来源渠道"
            className="w-36"
            value={source}
            onChange={(value) => {
              setSource(value)
              setPage(1)
            }}
            options={sourceOptions}
          />
          <Button
            type="primary"
            className="ml-auto"
            onClick={() => setModal({ open: true, mode: 'create', customerId: null })}
          >
            新建客户
          </Button>
        </div>

        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: setPage,
            showTotal: (count) => `共 ${count} 位客户`,
          }}
        />
      </div>

      <CustomerFormModal
        open={modal.open}
        mode={modal.mode}
        sessionId={null}
        customerId={modal.customerId}
        sourceOptions={sourceOptions}
        onCancel={() => setModal({ ...modal, open: false })}
        onDone={() => {
          setModal({ ...modal, open: false })
          void load()
        }}
      />
    </div>
  )
}

export default Customers
