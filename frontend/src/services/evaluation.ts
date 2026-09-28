/**
 * 评估系统 API 服务 (v2)
 *
 * 支持：数据集、测试用例、评估器、评估任务、执行轨迹
 */

import api from './api'

// ============================================================
// 类型定义
// ============================================================

export interface EvaluationDataset {
  id: number
  name: string
  description: string | null
  dataset_type: 'bfcl' | 'gaia' | 'custom'
  version: string
  total_cases: number
  metadata: Record<string, any> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DatasetDetail extends EvaluationDataset {
  test_cases_count: number
  evaluations_count: number
}

export interface TestCase {
  id: number
  dataset_id: number
  case_id: string
  category: string | null
  difficulty: 'easy' | 'medium' | 'hard' | null
  input_query: string
  input_context: Record<string, any> | null
  input_tools: Record<string, any>[] | null
  expected_answer: string | null
  expected_trajectory: Record<string, any>[] | null
  expected_tools: string[] | null
  tags: string[] | null
  metadata: Record<string, any> | null
  created_at: string
}

export interface Evaluator {
  id: number
  name: string
  description: string | null
  evaluator_type: 'heuristic' | 'llm_judge' | 'trajectory' | 'custom'
  config: Record<string, any> | null
  judge_model: string | null
  judge_prompt: string | null
  metric_type: string | null
  is_builtin: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Evaluation {
  id: number
  name: string
  description: string | null
  app_id: number
  dataset_id: number
  user_id: number
  evaluator_ids: number[] | null
  config: Record<string, any> | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  total_cases: number
  completed_cases: number
  success_cases: number
  overall_score: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface EvaluationDetail extends Evaluation {
  dataset_name: string | null
  app_name: string | null
  evaluators: Evaluator[] | null
  results_summary: {
    total: number
    passed: number
    avg_score: number
    avg_time: number
  } | null
}

export interface EvaluationResult {
  id: number
  evaluation_id: number
  test_case_id: number
  evaluator_id: number | null
  actual_answer: string | null
  actual_output: Record<string, any> | null
  actual_trajectory: Record<string, any>[] | null
  score: number | null
  score_details: Record<string, any> | null
  passed: boolean
  execution_time: number | null
  error_message: string | null
  diagnostics: Record<string, any> | null
  created_at: string
}

export interface EvaluationResultDetail extends EvaluationResult {
  test_case: TestCase | null
  evaluator: Evaluator | null
}

export interface Trace {
  id: number
  evaluation_result_id: number | null
  app_id: number
  conversation_id: number | null
  trace_type: 'agent' | 'workflow' | 'chatbot'
  status: 'running' | 'completed' | 'failed'
  steps: Record<string, any>[] | null
  total_steps: number
  total_llm_calls: number
  total_tool_calls: number
  total_time_ms: number
  total_tokens: number
  input_query: string | null
  output_answer: string | null
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export interface CategoryScore {
  category: string
  score: number
  total: number
  passed: number
}

export interface EvaluationReport {
  evaluation: Evaluation
  dataset_name: string
  app_name: string
  total_cases: number
  completed_cases: number
  success_cases: number
  overall_score: number
  duration: string | null
  evaluator_scores: Array<{
    evaluator_id: number
    evaluator_name: string
    avg_score: number
    pass_rate: number
    total: number
  }>
  category_scores: CategoryScore[]
  error_analysis: Record<string, any>
}

export interface AnalyticsOverview {
  total_evaluations: number
  total_datasets: number
  total_evaluators: number
  avg_score: number
  tool_accuracy: number
  completion_rate: number
}

export interface ComparisonResult {
  evaluations: Evaluation[]
  evaluator_comparison: Array<{
    evaluation_id: number
    evaluation_name: string
    evaluator_scores: Record<number, number>
  }>
  dimension_comparison: Array<Record<string, any>>
  category_comparison: Array<{
    evaluation_id: number
    evaluation_name: string
    categories: Record<string, {
      avg_score: number
      pass_rate: number
      total: number
    }>
  }>
  summary: Record<string, any>
}

export interface DatasetImportRequest {
  source: 'builtin' | 'huggingface' | 'custom'
  categories?: string[]
  max_cases?: number
}

export interface DatasetImportResponse {
  dataset_id: number
  imported_count: number
  skipped_count: number
  error_count: number
  message: string
}

// ============================================================
// 数据集 API
// ============================================================

export const datasetsApi = {
  getDatasets: (params?: { dataset_type?: string; is_active?: boolean }) => {
    return api.get<EvaluationDataset[]>('/evaluation/datasets', { params })
  },

  getDataset: (datasetId: number) => {
    return api.get<DatasetDetail>(`/evaluation/datasets/${datasetId}`)
  },

  createDataset: (data: {
    name: string
    description?: string
    dataset_type: string
    version?: string
    metadata?: Record<string, any>
  }) => {
    return api.post<EvaluationDataset>('/evaluation/datasets', data)
  },

  updateDataset: (
    datasetId: number,
    data: { name?: string; description?: string; metadata?: Record<string, any>; is_active?: boolean }
  ) => {
    return api.put<EvaluationDataset>(`/evaluation/datasets/${datasetId}`, data)
  },

  deleteDataset: (datasetId: number) => {
    return api.delete(`/evaluation/datasets/${datasetId}`)
  },

  getTestCases: (
    datasetId: number,
    params?: { page?: number; page_size?: number; category?: string; difficulty?: string }
  ) => {
    return api.get<{ items: TestCase[]; total: number; page: number; page_size: number }>(
      `/evaluation/datasets/${datasetId}/test-cases`,
      { params }
    )
  },

  createTestCase: (datasetId: number, data: {
    case_id: string
    category?: string
    difficulty?: string
    input_query: string
    input_context?: Record<string, any>
    input_tools?: Record<string, any>[]
    expected_answer?: string
    expected_trajectory?: Record<string, any>[]
    expected_tools?: string[]
    tags?: string[]
    metadata?: Record<string, any>
  }) => {
    return api.post<TestCase>(`/evaluation/datasets/${datasetId}/test-cases`, data)
  },

  importTestCases: (datasetId: number, data: DatasetImportRequest) => {
    return api.post<DatasetImportResponse>(`/evaluation/datasets/${datasetId}/import`, data)
  },
}

// ============================================================
// 评估器 API
// ============================================================

export const evaluatorsApi = {
  getEvaluators: (params?: {
    evaluator_type?: string
    is_builtin?: boolean
    is_active?: boolean
    page?: number
    page_size?: number
  }) => {
    return api.get<{ items: Evaluator[]; total: number; page: number; page_size: number }>(
      '/evaluation/evaluators',
      { params }
    )
  },

  getEvaluator: (evaluatorId: number) => {
    return api.get<Evaluator>(`/evaluation/evaluators/${evaluatorId}`)
  },

  createEvaluator: (data: {
    name: string
    description?: string
    evaluator_type: string
    config?: Record<string, any>
    judge_model?: string
    judge_prompt?: string
    metric_type?: string
    script_content?: string
  }) => {
    return api.post<Evaluator>('/evaluation/evaluators', data)
  },

  updateEvaluator: (evaluatorId: number, data: {
    name?: string
    description?: string
    config?: Record<string, any>
    judge_model?: string
    judge_prompt?: string
    is_active?: boolean
  }) => {
    return api.put<Evaluator>(`/evaluation/evaluators/${evaluatorId}`, data)
  },

  deleteEvaluator: (evaluatorId: number) => {
    return api.delete(`/evaluation/evaluators/${evaluatorId}`)
  },

  initBuiltin: () => {
    return api.post<{ message: string }>('/evaluation/evaluators/init-builtin')
  },
}

// ============================================================
// 评估任务 API
// ============================================================

export const evaluationsApi = {
  getEvaluations: (params?: {
    app_id?: number
    status?: string
    page?: number
    page_size?: number
  }) => {
    return api.get<{ items: Evaluation[]; total: number; page: number; page_size: number }>(
      '/evaluation/evaluations',
      { params }
    )
  },

  getEvaluation: (evalId: number) => {
    return api.get<EvaluationDetail>(`/evaluation/evaluations/${evalId}`)
  },

  createEvaluation: (data: {
    name: string
    description?: string
    app_id: number
    dataset_id: number
    evaluator_ids: number[]
    config?: Record<string, any>
  }) => {
    return api.post<Evaluation>('/evaluation/evaluations', data)
  },

  startEvaluation: (evalId: number) => {
    return api.post(`/evaluation/evaluations/${evalId}/start`)
  },

  cancelEvaluation: (evalId: number) => {
    return api.post(`/evaluation/evaluations/${evalId}/cancel`)
  },

  deleteEvaluation: (evalId: number) => {
    return api.delete(`/evaluation/evaluations/${evalId}`)
  },

  getResults: (
    evalId: number,
    params?: { page?: number; page_size?: number; passed?: boolean; evaluator_id?: number; category?: string }
  ) => {
    return api.get<{ items: EvaluationResult[]; total: number; page: number; page_size: number }>(
      `/evaluation/evaluations/${evalId}/results`,
      { params }
    )
  },

  getResult: (evalId: number, resultId: number) => {
    return api.get<EvaluationResultDetail>(`/evaluation/evaluations/${evalId}/results/${resultId}`)
  },

  getReport: (evalId: number) => {
    return api.get<EvaluationReport>(`/evaluation/evaluations/${evalId}/report`)
  },
}

// ============================================================
// 执行轨迹 API
// ============================================================

export const tracesApi = {
  getTraces: (params?: {
    app_id?: number
    trace_type?: string
    status?: string
    page?: number
    page_size?: number
  }) => {
    return api.get<{ items: Trace[]; total: number; page: number; page_size: number }>(
      '/evaluation/traces',
      { params }
    )
  },

  getTrace: (traceId: number) => {
    return api.get<Trace>(`/evaluation/traces/${traceId}`)
  },
}

// ============================================================
// 分析统计 API
// ============================================================

export const analyticsApi = {
  getOverview: (params?: { app_id?: number }) => {
    return api.get<AnalyticsOverview>('/evaluation/analytics/overview', { params })
  },

  compareEvaluations: (evalIds: number[]) => {
    return api.get<ComparisonResult>('/evaluation/analytics/comparison', {
      params: { eval_ids: evalIds.join(',') },
    })
  },
}
