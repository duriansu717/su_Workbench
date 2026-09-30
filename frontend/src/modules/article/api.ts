import api from '@/core/api'

/**
 * 文章模块的后端接口（A1~A16）。
 *
 * 只调用 /api/article/* —— 本模块不碰别的模块的接口，别的模块也不碰这里的。
 * **所有路径集中在这个文件里**，组件不要直接写 axios.get('/article/articles')，
 * 改路径时才能只动一处。
 *
 * 字段名一律 snake_case，和后端保持一致，不做驼峰转换。
 */

// ============================ 类型 ============================

export interface Category {
  id: number
  name: string
  sort_order: number
  article_count: number
}

export interface Tag {
  id: number
  name: string
  article_count: number
}

/** 列表页的一项。**不含正文**。 */
export interface ArticleListItem {
  id: number
  title: string
  excerpt: string
  category: { id: number; name: string }
  tags: { id: number; name: string }[]
  status: string
  /** 带 Z 的 ISO 8601，如 2026-09-29T15:30:00Z */
  created_at: string
  updated_at: string
}

export interface ArticleDetail extends ArticleListItem {
  content_html: string
  deleted_at: string | null
}

export interface ArticlePage {
  items: ArticleListItem[]
  total: number
  page: number
  page_size: number
}

export interface ArticleInput {
  title: string
  content_html: string
  category_id: number
  tag_ids: number[]
}

export interface ArticleQuery {
  page?: number
  page_size?: number
  keyword?: string
  category_id?: number
  tag_id?: number
  status?: 'published' | 'deleted'
}

export interface UploadResult {
  url: string
  size: number
}

// ============================ 接口 ============================

export const articleApi = {
  categories: {
    list: () => api.get<Category[]>('/article/categories'),

    create: (name: string, sort_order = 0) =>
      api.post<Category>('/article/categories', { name, sort_order }),

    update: (id: number, payload: { name?: string; sort_order?: number }) =>
      api.put<Category>(`/article/categories/${id}`, payload),

    /** 分类下还有文章时后端会返回 409，错误信息可以直接显示给用户 */
    remove: (id: number) => api.delete(`/article/categories/${id}`),
  },

  tags: {
    list: () => api.get<Tag[]>('/article/tags'),

    create: (name: string) => api.post<Tag>('/article/tags', { name }),

    update: (id: number, name: string) => api.put<Tag>(`/article/tags/${id}`, { name }),

    /** 删标签不需要先检查引用，后端会把它从所有文章上摘掉 */
    remove: (id: number) => api.delete(`/article/tags/${id}`),
  },

  articles: {
    list: (params: ArticleQuery = {}) =>
      api.get<ArticlePage>('/article/articles', { params }),

    get: (id: number) => api.get<ArticleDetail>(`/article/articles/${id}`),

    create: (payload: ArticleInput) =>
      api.post<ArticleDetail>('/article/articles', payload),

    update: (id: number, payload: ArticleInput) =>
      api.put<ArticleDetail>(`/article/articles/${id}`, payload),

    /** 移入回收站（软删除），可以还原 */
    remove: (id: number) => api.delete(`/article/articles/${id}`),

    restore: (id: number) => api.post<ArticleDetail>(`/article/articles/${id}/restore`),

    /** 彻底删除，**不可恢复** */
    forceRemove: (id: number) => api.delete(`/article/articles/${id}/force`),
  },

  uploads: {
    /** 上传正文插图。用 FormData，不要手动设 Content-Type —— axios 要自己填 boundary */
    image: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<UploadResult>('/article/uploads/images', form)
    },
  },
}

export default articleApi
