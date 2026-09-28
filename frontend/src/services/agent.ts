/**
 * Agent API 服务 - 使用 LangGraph create_react_agent
 */
import api from './api';
import { useAuthStore } from '@/stores/auth';
import {
  ChatbotVariable,
  KnowledgeBaseConfig,
  ModelParameters,
} from './chatbot';

// 类型定义
export interface AgentPromptConfig {
  system_prompt?: string;
}

export interface ToolConfig {
  tool_id: number;
  name: string;
  enabled: boolean;
  config?: Record<string, any>;
}

export interface AgentConfig {
  prompt: AgentPromptConfig;
  variables: ChatbotVariable[];
  model_id?: number;
  model_name?: string;
  model_parameters: ModelParameters;
  knowledge_bases: KnowledgeBaseConfig[];
  metadata_filter_enabled: boolean;
  tools: ToolConfig[];
  memory_enabled: boolean;
  memory_window: number;
  max_iterations: number;
}

export interface AgentConfigResponse {
  app_id: number;
  app_name: string;
  config: AgentConfig;
}

export interface AgentChatRequest {
  query: string;
  conversation_id?: number;
  inputs?: Record<string, string>;
  response_mode?: 'blocking' | 'streaming';
}

export interface AgentChatResponse {
  answer: string;
  conversation_id: number;
  message_id: number;
  // Agent 运行日志 -用于调试查看工具调用详情
  intermediate_steps?: Array<{
    tool: string;
    input: string;
    output: string;
    thought?: string;
    status?: 'success' | 'error' | 'running';
    duration?: number;
  }>;
  metadata?: Record<string, any>;
}

// API 方法
export const agentApi = {
  /**
   * 获取 Agent 配置
   */
  getConfig: async (appId: number): Promise<AgentConfigResponse> => {
    const response = await api.get(`/agent/${appId}/config`);
    return response.data;
  },

  /**
   * 更新 Agent 配置
   */
  updateConfig: async (appId: number, config: AgentConfig): Promise<void> => {
    await api.put(`/agent/${appId}/config`, config);
  },

  /**
   * 发送聊天消息（超时时间更长，Agent 需要执行工具调用）
   */
  chat: async (appId: number, request: AgentChatRequest): Promise<AgentChatResponse> => {
    const response = await api.post(`/agent/${appId}/chat`, request, { timeout: 180000 });  // 3分钟超时
    return response.data;
  },

  /**
   * 流式发送聊天消息 (SSE)
   * 返回异步迭代器，逐步 yield 事件
   */
  chatStream: async function* (appId: number, request: AgentChatRequest) {
    const token = useAuthStore.getState().token;
    const response = await fetch(`/api/v1/agent/${appId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '请求失败' }));
      yield { event: 'error', data: { message: error.detail || '请求失败' } };
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    let eventType = '';
    let eventData = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // 解析 SSE 事件
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';  // 保留未完成的行

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          eventData = line.slice(6);
        } else if (line === '' && eventType && eventData) {
          // 空行表示事件结束
          try {
            const data = JSON.parse(eventData);
            yield { event: eventType, data };
          } catch (e) {
            console.error('SSE 解析失败:', e, eventData);
          }
          eventType = '';
          eventData = '';
        }
      }
    }

    // 处理 buffer 中剩余的数据
    if (eventType && eventData) {
      try {
        const data = JSON.parse(eventData);
        yield { event: eventType, data };
      } catch (e) {
        console.error('SSE 解析失败:', e, eventData);
      }
    }
  },

  /**
   * 调试：获取原始配置
   */
  debugConfig: async (appId: number) => {
    const response = await api.get(`/agent/${appId}/debug/config`);
    return response.data;
  },

  /**
   * 调试：测试模型加载
   */
  debugModel: async (appId: number) => {
    const response = await api.get(`/agent/${appId}/debug/model`);
    return response.data;
  },
};

export default agentApi;
