import axios from 'axios'

/**
 * 全局 axios 实例。所有模块调后端都必须用它，不要自己 new。
 *
 * baseURL 用相对路径 /api：开发时由 Vite 代理转发到 8000 端口，
 * 日常使用时前端由 FastAPI 同源托管 —— 两种环境下路径完全一致，代码不用改。
 *
 * withCredentials 打开才会带上 httpOnly Cookie 里的登录凭证。
 */
export const api = axios.create({
  baseURL: '/api',
  timeout: 20000,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // TODO 登录页建好后，这里负责跳转到 /login
    }
    return Promise.reject(error)
  },
)

export default api
