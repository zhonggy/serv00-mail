import { reactive } from 'vue'
import api from './api'

export const state = reactive({ user: null, ready: false })

export async function initAuth() {
  const t = localStorage.getItem('sm_token')
  if (t) {
    try {
      const { data } = await api.get('/auth/me')
      state.user = data
    } catch (e) {
      const s = e?.response?.status
      if (s === 401 || s === 403) {
        // token 真的失效了：清掉，去登录页
        localStorage.removeItem('sm_token')
      } else {
        // 网络/服务端故障（比如后端重启中）：保留 token，先放行进应用；
        // 后续请求的 401 会由 api 拦截器统一处理（清 token 跳登录）
        state.user = { username: '', is_admin: false, can_send: true, _pending: true }
        // 后台静默重试一次，把真实用户信息补回来
        api.get('/auth/me').then(({ data }) => { state.user = data }).catch(() => {})
      }
    }
  }
  state.ready = true
}

export function logout() {
  localStorage.removeItem('sm_token')
  state.user = null
  location.hash = '#/login'
}
