/**
 * BusinessDataPanel - 业务数据（Demo 示例）维护面板
 *
 * 展示客服 Tool Agent 查询的订单 / 商品 / 物流 / 退换货政策示例数据。
 * 首期为只读展示 + 「恢复示例」一键重置，便于演示与核对工具查询结果，
 * 后续可在此扩展行内编辑。
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Button, Card, Space, Spin, Table, message as antdMessage } from 'antd'
import { ReloadOutlined, BookOutlined } from '@ant-design/icons'
import supportApi from '../../services/support'
import type { BusinessData } from '../../types/support'

const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="text-xs font-medium text-slate-500 mb-2 mt-3 first:mt-0">{children}</div>
)

const BusinessDataPanel: React.FC = () => {
  const [data, setData] = useState<BusinessData | null>(null)
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await supportApi.getBusinessData())
    } catch (err) {
      console.error('加载业务数据失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleReset = async () => {
    setResetting(true)
    try {
      await supportApi.resetBusinessData()
      await load()
    } catch (err) {
      console.error('恢复示例失败:', err)
    } finally {
      setResetting(false)
    }
  }

  const handleGenerate = async () => {
    try {
      const res = await supportApi.generateKbDocs()
      antdMessage.success(res.message || '知识库文档已生成')
    } catch (err) {
      console.error('生成知识库文档失败:', err)
      antdMessage.error('生成知识库文档失败')
    }
  }

  return (
    <Card
      title="业务数据（Demo 示例）"
      extra={
        <Space size={4}>
          <Button size="small" icon={<BookOutlined />} onClick={handleGenerate}>
            生成知识库文档
          </Button>
          <Button size="small" icon={<ReloadOutlined />} loading={resetting} onClick={handleReset}>
            恢复示例
          </Button>
        </Space>
      }
    >
      {loading ? (
        <div className="text-center py-8">
          <Spin />
        </div>
      ) : (
        <div>
          <SectionTitle>订单</SectionTitle>
          <Table
            dataSource={data?.orders || []}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { title: '订单号', dataIndex: 'order_no' },
              { title: '客户', dataIndex: 'customer_name' },
              { title: '商品', dataIndex: 'product' },
              { title: '金额', dataIndex: 'amount', render: (v: number) => `¥${v}` },
              { title: '状态', dataIndex: 'status' },
            ]}
          />

          <SectionTitle>商品</SectionTitle>
          <Table
            dataSource={data?.products || []}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { title: '商品号', dataIndex: 'product_no' },
              { title: '名称', dataIndex: 'name' },
              { title: '价格', dataIndex: 'price', render: (v: number) => `¥${v}` },
              { title: '质保', dataIndex: 'warranty' },
              {
                title: '卖点',
                dataIndex: 'features',
                render: (v: string[]) => (v || []).join('、'),
              },
            ]}
          />

          <SectionTitle>物流</SectionTitle>
          <Table
            dataSource={data?.shipments || []}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { title: '订单号', dataIndex: 'order_no' },
              { title: '承运商', dataIndex: 'carrier' },
              { title: '运单号', dataIndex: 'tracking_no' },
              { title: '当前位置', dataIndex: 'current_location' },
              { title: '预计', dataIndex: 'estimated_text' },
            ]}
          />

          <SectionTitle>退换货政策</SectionTitle>
          <Table
            dataSource={data?.return_policies || []}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { title: '分类', dataIndex: 'category_label' },
              { title: '政策', dataIndex: 'policy_content' },
            ]}
          />

          <Space className="mt-3">
            <span className="text-[11px] text-slate-400">
              工具查询直接读这些示例数据；恢复示例可重置为初始状态。
            </span>
          </Space>
        </div>
      )}
    </Card>
  )
}

export default BusinessDataPanel
