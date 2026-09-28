import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Apps from './pages/Apps'
import Knowledge from './pages/Knowledge'
import KnowledgeDetail from './pages/KnowledgeDetail'
import Models from './pages/Models'
import ModelDetail from './pages/ModelDetail'
import Tools from './pages/Tools'
import ChatbotOrchestration from './pages/ChatbotOrchestration'
import ChatbotDebug from './pages/ChatbotDebug'
import WorkflowOrchestration from './pages/WorkflowOrchestration'
import PublishManagement from './pages/PublishManagement'
import AgentOrchestration from './pages/AgentOrchestration'
import AgentDebug from './pages/AgentDebug'
import AppRunner from './pages/AppRunner'
import EvaluationLayout from './pages/Evaluation/EvaluationLayout'
import AnalyticsDashboard from './pages/Evaluation/AnalyticsDashboard'
import DatasetManagement from './pages/Evaluation/DatasetManagement'
import EvaluatorManagement from './pages/Evaluation/EvaluatorManagement'
import EvaluationList from './pages/Evaluation/EvaluationList'
import CreateEvaluation from './pages/Evaluation/CreateEvaluation'
import EvaluationReport from './pages/Evaluation/EvaluationReport'
import WorkAssistant from './pages/WorkAssistant'
import HermesSkills from './pages/HermesSkills'
import ResourceLibrary from './pages/learning/ResourceLibrary'
import LearningStudio from './pages/learning/LearningStudio'
import LearningRecords from './pages/learning/LearningRecords'
import AgentWorkspace from './pages/support/AgentWorkspace'
import TicketCenter from './pages/support/TicketCenter'
import SupportAnalytics from './pages/support/SupportAnalytics'
import BotSettings from './pages/support/BotSettings'
import SupportQuality from './pages/support/SupportQuality'
import SupportCustomers from './pages/support/Customers'

// 受保护的路由组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

const App: React.FC = () => {
  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* 受保护的路由 */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="apps" element={<Apps />} />
        <Route path="apps/:appId/chatbot" element={<ChatbotOrchestration />} />
        <Route path="apps/:appId/chatbot/debug" element={<ChatbotDebug />} />
        <Route path="apps/:appId/workflow" element={<WorkflowOrchestration />} />
        <Route path="apps/:appId/agent" element={<AgentOrchestration />} />
        <Route path="apps/:appId/agent/debug" element={<AgentDebug />} />
        <Route path="apps/:appId/publish" element={<PublishManagement />} />
        <Route path="apps/:appId/run" element={<AppRunner />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/:id" element={<KnowledgeDetail />} />
        <Route path="models" element={<Models />} />
        <Route path="models/:providerId" element={<ModelDetail />} />
        <Route path="tools" element={<Tools />} />
        {/* 学习助手：详情页 hasPadding 为 false，走沉浸式全屏 */}
        <Route path="learning" element={<ResourceLibrary />} />
        <Route path="learning/records" element={<LearningRecords />} />
        <Route path="learning/:id" element={<LearningStudio />} />
        {/* 智能客服：工作台走沉浸式全屏，其余页面保留上下间距 */}
        <Route path="support" element={<AgentWorkspace />} />
        <Route path="support/tickets" element={<TicketCenter />} />
        <Route path="support/analytics" element={<SupportAnalytics />} />
        <Route path="support/quality" element={<SupportQuality />} />
        <Route path="support/settings" element={<BotSettings />} />
        <Route path="support/customers" element={<SupportCustomers />} />
        <Route path="work-assistant" element={<WorkAssistant />} />
        <Route path="hermes-skills" element={<HermesSkills />} />

        {/* 评估模块路由 */}
        <Route path="evaluation" element={<EvaluationLayout />}>
          <Route index element={<AnalyticsDashboard />} />
          <Route path="datasets" element={<DatasetManagement />} />
          <Route path="evaluators" element={<EvaluatorManagement />} />
          <Route path="tasks" element={<EvaluationList />} />
          <Route path="tasks/create" element={<CreateEvaluation />} />
          <Route path="tasks/:evalId" element={<EvaluationReport />} />
          <Route path="tasks/:evalId/report" element={<EvaluationReport />} />
        </Route>
      </Route>

      {/* 404路由 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
