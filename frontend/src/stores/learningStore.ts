/**
 * 学习助手状态
 *
 * 只存跨组件共享的数据：资源列表与分页游标、当前资源、字幕、文档页缓存。
 * 标注画布的临时状态留在组件内（高频更新，进 store 会拖慢绘制）。
 */

import { create } from 'zustand'
import learningApi from '../services/learning'
import type {
  AnnotationShape,
  DocumentPage,
  LearningResource,
  ResourceType,
  TranscriptCue,
} from '../types/learning'

export interface ResourceFilters {
  type: ResourceType | 'all'
  keyword: string
  sort: 'recent_studied' | 'recent_created' | 'progress'
}

interface LearningState {
  resources: LearningResource[]
  cursor: number | null
  hasMore: boolean
  loading: boolean
  filters: ResourceFilters

  currentResource: LearningResource | null
  cues: TranscriptCue[]
  /** 文档页缓存：key 为 pageIndex，翻页回看不必重新请求 */
  pageCache: Record<number, DocumentPage>
  /** 每页的矢量标注缓存 */
  shapeCache: Record<number, AnnotationShape[]>

  loadResources: (reset?: boolean) => Promise<void>
  loadMore: () => Promise<void>
  setFilters: (patch: Partial<ResourceFilters>) => Promise<void>

  setCurrentResource: (resource: LearningResource | null) => void
  appendResource: (resource: LearningResource) => void
  removeResource: (resourceId: number) => void
  replaceResource: (resource: LearningResource) => void

  setCues: (cues: TranscriptCue[]) => void
  cachePage: (pageIndex: number, page: DocumentPage) => void
  cacheShapes: (pageIndex: number, shapes: AnnotationShape[]) => void
  resetStudio: () => void
}

const DEFAULT_FILTERS: ResourceFilters = {
  type: 'all',
  keyword: '',
  sort: 'recent_studied',
}

export const useLearningStore = create<LearningState>((set, get) => ({
  resources: [],
  cursor: null,
  hasMore: false,
  loading: false,
  filters: DEFAULT_FILTERS,

  currentResource: null,
  cues: [],
  pageCache: {},
  shapeCache: {},

  loadResources: async (reset = true) => {
    const { filters, loading } = get()
    if (loading) return

    set({ loading: true })
    try {
      const result = await learningApi.listResources({
        type: filters.type === 'all' ? undefined : filters.type,
        keyword: filters.keyword || undefined,
        sort: filters.sort,
        cursor: reset ? null : get().cursor,
        limit: 24,
      })
      set((state) => ({
        resources: reset ? result.items : [...state.resources, ...result.items],
        cursor: result.next_cursor,
        hasMore: result.has_more,
      }))
    } catch (error) {
      console.error('加载学习资源失败', error)
    } finally {
      set({ loading: false })
    }
  },

  loadMore: async () => {
    const { hasMore, loading } = get()
    if (!hasMore || loading) return
    await get().loadResources(false)
  },

  setFilters: async (patch) => {
    set((state) => ({ filters: { ...state.filters, ...patch } }))
    await get().loadResources(true)
  },

  setCurrentResource: (resource) => set({ currentResource: resource }),

  appendResource: (resource) =>
    set((state) => ({ resources: [resource, ...state.resources] })),

  removeResource: (resourceId) =>
    set((state) => ({
      resources: state.resources.filter((item) => item.id !== resourceId),
      currentResource:
        state.currentResource?.id === resourceId ? null : state.currentResource,
    })),

  replaceResource: (resource) =>
    set((state) => ({
      resources: state.resources.map((item) => (item.id === resource.id ? resource : item)),
      currentResource:
        state.currentResource?.id === resource.id ? resource : state.currentResource,
    })),

  setCues: (cues) => set({ cues }),

  cachePage: (pageIndex, page) =>
    set((state) => ({ pageCache: { ...state.pageCache, [pageIndex]: page } })),

  cacheShapes: (pageIndex, shapes) =>
    set((state) => ({ shapeCache: { ...state.shapeCache, [pageIndex]: shapes } })),

  resetStudio: () => set({ currentResource: null, cues: [], pageCache: {}, shapeCache: {} }),
}))

export default useLearningStore
