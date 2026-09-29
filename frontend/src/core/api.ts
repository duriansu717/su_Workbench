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
    // 401 = 没登录或登录已过期，送回登录页。
    //
    // 这里用 window.location 而不是 router.push，是为了避开循环依赖：
    // router → 守卫 → auth store → 本文件 → router，转一圈又回来了。
    // 登录过期本来就是该重新加载应用的场景，整页跳转也不亏。
    //
    // 判断路径是为了不把「密码输错」也当成登录过期 ——
    // 登录接口失败时也返回 401，那时人已经在 /login 上了。
    if (
      error.response?.status === 401 &&
      !window.location.pathname.startsWith('/login')
    ) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default api
