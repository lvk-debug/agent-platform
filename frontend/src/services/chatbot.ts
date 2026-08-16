/**
 * 聊天助手 API 服务
 */
import api from './api';

// 类型定义
export interface ChatbotVariable {
  key: string;
  name: string;
  type: 'text_input' | 'paragraph' | 'select';
  required: boolean;
  default?: string;
  options?: Array<{ value: string; label: string }>;
  description?: string;
}

export interface KnowledgeBaseConfig {
  knowledge_base_id: number;
  name: string;
  enabled: boolean;
  score_threshold: number;
  top_k: number;
  show_citation: boolean;
}

export interface ChatbotPromptConfig {
  system_prompt?: string;
  opening_statement?: string;
  suggested_questions?: string[];
}

export interface ModelParameters {
  temperature: number;
  top_p: number;
  top_k: number;
  presence_penalty: number;
  frequency_penalty: number;
  max_tokens: number;
  skip_content_review: boolean;
}

export interface ChatbotConfig {
  prompt: ChatbotPromptConfig;
  variables: ChatbotVariable[];
  knowledge_bases: KnowledgeBaseConfig[];
  model_id?: number;
  model_name?: string;
  model_parameters: ModelParameters;
  memory_enabled: boolean;
  memory_window: number;
  metadata_filter_enabled: boolean;
}

export interface ChatRequest {
  query: string;
  conversation_id?: number;
  inputs?: Record<string, string>;
  response_mode?: 'blocking' | 'streaming';
}

export interface ChatResponse {
  answer: string;
  conversation_id: number;
  message_id: number;
  metadata?: Record<string, any>;
}

export interface Conversation {
  id: number;
  app_id: number;
  title?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: Record<string, any>;
  created_at: string;
}

// API 方法
export const chatbotApi = {
  /**
   * 获取聊天助手配置
   */
  getConfig: async (appId: number): Promise<ChatbotConfig> => {
    const response = await api.get(`/chatbot/${appId}/config`);
    return response.data;
  },

  /**
   * 更新聊天助手配置
   */
  updateConfig: async (appId: number, config: ChatbotConfig): Promise<void> => {
    await api.put(`/chatbot/${appId}/config`, config);
  },

  /**
   * 发送聊天消息
   */
  chat: async (appId: number, request: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post(`/chatbot/${appId}/chat`, request);
    return response.data;
  },

  /**
   * 获取会话列表
   */
  getConversations: async (
    appId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<Conversation[]> => {
    const response = await api.get(`/chatbot/${appId}/conversations`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * 获取会话消息列表
   */
  getMessages: async (
    appId: number,
    conversationId: number,
    limit: number = 50
  ): Promise<Message[]> => {
    const response = await api.get(
      `/chatbot/${appId}/conversations/${conversationId}/messages`,
      { params: { limit } }
    );
    return response.data;
  },

  /**
   * 删除会话
   */
  deleteConversation: async (
    appId: number,
    conversationId: number
  ): Promise<void> => {
    await api.delete(`/chatbot/${appId}/conversations/${conversationId}`);
  },
};

export default chatbotApi;
