import { defineStore } from 'pinia'
import { ref } from 'vue'

import api from '../api'

interface UserInfo {
  username: string
}

/**
 * 登录状态。
 *
 * **为什么住在 core 而不是某个模块里**：路由守卫在 core，它必须能读到登录态。
 * 如果这里属于某个模块，core 就要反向依赖模块 —— 违反架构设计第五章的依赖方向铁律。
 * 认证是基础设施，和后端的 security.py、deps.py 是一回事。
 */
export const useAuthStore = defineStore('auth', () => {
  const username = ref<string | null>(null)

  /** 是否已经向后端确认过登录状态。首次进入应用前是 false。 */
  const checked = ref(false)

  /** 问后端「我现在登录了吗」。token 在 httpOnly Cookie 里，前端读不到，只能问。 */
  async function fetchMe(): Promise<void> {
    try {
      const { data } = await api.get<UserInfo>('/auth/me')
      username.value = data.username
    } catch {
      username.value = null
    } finally {
      checked.value = true
    }
  }

  async function login(name: string, password: string): Promise<void> {
    const { data } = await api.post<UserInfo>('/auth/login', {
      username: name,
      password,
    })
    username.value = data.username
    checked.value = true
  }

  async function logout(): Promise<void> {
    try {
      await api.post('/auth/logout')
    } finally {
      // 就算请求失败也要清掉本地状态，否则界面会显示成还登录着，
      // 而实际 Cookie 可能已经失效 —— 那种状态最让人困惑
      username.value = null
    }
  }

  return { username, checked, fetchMe, login, logout }
})
