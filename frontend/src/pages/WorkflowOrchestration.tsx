/**
 * 工作流编排页面 — 可视化编辑工作流
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  Connection,
  Edge,
  Node,
  ReactFlowInstance,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Button, Space, Breadcrumb, message, Spin, Modal, Input } from 'antd'
import {
  SaveOutlined,
  ExportOutlined,
  ImportOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { useParams, Link } from 'react-router-dom'

import NodePanel from '../components/workflow/NodePanel'
import NodeConfigDrawer from '../components/workflow/NodeConfigDrawer'
import DSLImportModal from '../components/workflow/DSLImportModal'
import StartNode from '../components/workflow/nodes/StartNode'
import EndNode from '../components/workflow/nodes/EndNode'
import LLMNode from '../components/workflow/nodes/LLMNode'
import KnowledgeNode from '../components/workflow/nodes/KnowledgeNode'
import ConditionNode from '../components/workflow/nodes/ConditionNode'
import CodeNode from '../components/workflow/nodes/CodeNode'
import HTTPNode from '../components/workflow/nodes/HTTPNode'
import ToolNode from '../components/workflow/nodes/ToolNode'
import HumanInterventionNode from '../components/workflow/nodes/HumanInterventionNode'
import QuestionClassifierNode from '../components/workflow/nodes/QuestionClassifierNode'

import {
  workflowApi,
  WorkflowNode as WFNode,
  WorkflowEdge as WFEdge,
  WorkflowConfig,
  DSLData,
} from '../services/workflow'

// ------------------------------------------------------------------
// 自定义节点类型映射
// ------------------------------------------------------------------

const nodeTypes = {
  start: StartNode,
  end: EndNode,
  llm: LLMNode,
  knowledge_retrieval: KnowledgeNode,
  condition: ConditionNode,
  question_classifier: QuestionClassifierNode,
  code: CodeNode,
  http: HTTPNode,
  tool: ToolNode,
  human_intervention: HumanInterventionNode,
}

// ------------------------------------------------------------------
// 内部组件（需要在 ReactFlowProvider 内部）
// ------------------------------------------------------------------

let nodeIdCounter = 0
const getNodeId = (type: string) => `${type}_${++nodeIdCounter}`

const WorkflowEditor: React.FC = () => {
  const { appId } = useParams<{ appId: string }>()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selectedNode, setSelectedNode] = useState<WFNode | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [dslImportOpen, setDslImportOpen] = useState(false)
  const [runModalOpen, setRunModalOpen] = useState(false)
  const [runInputs, setRunInputs] = useState('{}')
  const [running, setRunning] = useState(false)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // ------------------------------------------------------------------
  // 加载配置
  // ------------------------------------------------------------------

  useEffect(() => {
    fetchConfig()
  }, [appId])

  const fetchConfig = async () => {
    if (!appId) return
    setLoading(true)
    try {
      const config = await workflowApi.getConfig(Number(appId))
      if (config.graph) {
        const rfNodes: Node[] = config.graph.nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: { ...n.data, nodeType: n.type },
        }))
        const rfEdges: Edge[] = config.graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
          label: e.label,
          type: 'smoothstep',
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
        }))
        setNodes(rfNodes)
        setEdges(rfEdges)
        // 更新计数器
        const maxId = config.graph.nodes.reduce((max, n) => {
          const match = n.id.match(/_(\d+)$/)
          return match ? Math.max(max, parseInt(match[1])) : max
        }, 0)
        nodeIdCounter = maxId
      }
    } catch (error) {
      console.error('加载工作流配置失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // ------------------------------------------------------------------
  // 保存
  // ------------------------------------------------------------------

  const handleSave = async () => {
    if (!appId) return
    setSaving(true)
    try {
      const graphNodes: WFNode[] = nodes.map((n) => ({
        id: n.id,
        type: (n.type || 'llm') as any,
        position: n.position,
        data: {
          label: n.data.label || '',
          description: n.data.description,
          config: n.data.config || {},
        },
      }))
      const graphEdges: WFEdge[] = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle || undefined,
        targetHandle: e.targetHandle || undefined,
        label: e.label ? String(e.label) : undefined,
      }))

      const config: WorkflowConfig = {
        graph: { nodes: graphNodes, edges: graphEdges },
        version: 1,
      }
      await workflowApi.updateConfig(Number(appId), config)
      message.success('保存成功')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  // ------------------------------------------------------------------
  // 连线
  // ------------------------------------------------------------------

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            type: 'smoothstep',
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed },
          },
          eds,
        ),
      )
    },
    [setEdges],
  )

  // ------------------------------------------------------------------
  // 拖拽放置
  // ------------------------------------------------------------------

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const type = event.dataTransfer.getData('application/reactflow')
      if (!type || !reactFlowInstance || !reactFlowWrapper.current) return

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      const newNode: Node = {
        id: getNodeId(type),
        type,
        position,
        data: { label: type, nodeType: type, config: {} },
      }

      setNodes((nds) => nds.concat(newNode))
    },
    [reactFlowInstance, setNodes],
  )

  // ------------------------------------------------------------------
  // 节点点击
  // ------------------------------------------------------------------

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const wfNode: WFNode = {
        id: node.id,
        type: (node.type || 'llm') as any,
        position: node.position,
        data: {
          label: node.data.label || '',
          description: node.data.description,
          config: node.data.config || {},
        },
      }
      setSelectedNode(wfNode)
      setDrawerOpen(true)
    },
    [],
  )

  const handleNodeConfigSave = useCallback(
    (nodeId: string, data: { label: string; config: Record<string, any> }) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === nodeId) {
            return {
              ...n,
              data: { ...n.data, label: data.label, config: data.config },
            }
          }
          return n
        }),
      )
    },
    [setNodes],
  )

  // ------------------------------------------------------------------
  // 删除选中
  // ------------------------------------------------------------------

  const onNodesDelete = useCallback(
    (_deleted: Node[]) => {
      setDrawerOpen(false)
      setSelectedNode(null)
    },
    [],
  )

  // ------------------------------------------------------------------
  // DSL 导入导出
  // ------------------------------------------------------------------

  const handleExportDSL = async () => {
    if (!appId) return
    try {
      const dsl = await workflowApi.exportDSL(Number(appId))
      const blob = new Blob([JSON.stringify(dsl, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `workflow_${appId}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('DSL 已导出')
    } catch (error) {
      // 如果后端没有保存过，直接从当前画布导出
      const dsl: DSLData = {
        version: 1,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: (n.type || 'llm') as any,
          position: n.position,
          data: { label: n.data.label || '', config: n.data.config || {} },
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle || undefined,
          targetHandle: e.targetHandle || undefined,
          label: e.label ? String(e.label) : undefined,
        })),
      }
      const blob = new Blob([JSON.stringify(dsl, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `workflow_${appId}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('DSL 已导出（从画布）')
    }
  }

  const handleImportDSL = (dsl: DSLData) => {
    const rfNodes: Node[] = dsl.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: { ...n.data, nodeType: n.type },
    }))
    const rfEdges: Edge[] = dsl.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      label: e.label,
      type: 'smoothstep',
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed },
    }))
    setNodes(rfNodes)
    setEdges(rfEdges)
    message.success('DSL 已导入')
  }

  // ------------------------------------------------------------------
  // 执行工作流
  // ------------------------------------------------------------------

  const handleRun = async () => {
    if (!appId) return
    setRunning(true)
    try {
      const inputs = JSON.parse(runInputs)
      const result = await workflowApi.run(Number(appId), { inputs })
      message.success(`执行完成，运行 ID: ${result.run_id}`)
      setRunModalOpen(false)
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        message.error('输入 JSON 格式错误')
      } else {
        message.error(`执行失败: ${error.response?.data?.detail || error.message}`)
      }
    } finally {
      setRunning(false)
    }
  }

  // ------------------------------------------------------------------
  // 渲染
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <div className="text-center py-25">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      {/* 顶部工具栏 */}
      <div className="px-4 py-2 border-b border-border bg-white flex items-center justify-between ">
        <Breadcrumb
          items={[
            { title: <Link to="/apps">应用</Link> },
            { title: '工作流编排' },
          ]}
        />
        <Space>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => setRunModalOpen(true)}
          >
            运行
          </Button>
          <Button icon={<ImportOutlined />} onClick={() => setDslImportOpen(true)}>
            导入 DSL
          </Button>
          <Button icon={<ExportOutlined />} onClick={handleExportDSL}>
            导出 DSL
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
          >
            保存
          </Button>
        </Space>
      </div>

      {/* 主体区域 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧节点面板 */}
        <NodePanel />

        {/* 中间画布 */}
        <div className="flex-1" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeClick={onNodeClick}
            onNodesDelete={onNodesDelete}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            deleteKeyCode={['Backspace', 'Delete']}
          >
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
            />
            <Background gap={15} size={1} />
          </ReactFlow>
        </div>
      </div>

      {/* 节点配置抽屉 */}
      <NodeConfigDrawer
        node={selectedNode}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedNode(null)
        }}
        onSave={handleNodeConfigSave}
        upstreamNodes={(() => {
          if (!selectedNode) return []
          const upstreamIds = edges
            .filter((e) => e.target === selectedNode.id)
            .map((e) => e.source)
          return nodes.filter((n) => upstreamIds.includes(n.id))
        })()}
      />

      {/* DSL 导入弹窗 */}
      <DSLImportModal
        open={dslImportOpen}
        onClose={() => setDslImportOpen(false)}
        onImport={handleImportDSL}
      />

      {/* 运行弹窗 */}
      <Modal
        title="运行工作流"
        open={runModalOpen}
        onCancel={() => setRunModalOpen(false)}
        onOk={handleRun}
        confirmLoading={running}
        okText="执行"
      >
        <div className="mb-2 text-sm text-text-secondary">
          输入 JSON 格式的变量：
        </div>
        <Input.TextArea
          value={runInputs}
          onChange={(e) => setRunInputs(e.target.value)}
          rows={6}
          placeholder='{"query": "你好"}'
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>
    </div>
  )
}

// ------------------------------------------------------------------
// 外层包装（ReactFlowProvider）
// ------------------------------------------------------------------

const WorkflowOrchestration: React.FC = () => {
  return (
    <ReactFlowProvider>
      <WorkflowEditor />
    </ReactFlowProvider>
  )
}

export default WorkflowOrchestration
