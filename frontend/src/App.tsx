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
      </Route>

      {/* 404路由 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
