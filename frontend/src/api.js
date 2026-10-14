import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('sm_token')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && location.hash !== '#/login') {
      localStorage.removeItem('sm_token')
      location.hash = '#/login'
    }
    return Promise.reject(err)
  },
)

export function errMsg(err, fallback = '请求失败') {
  const d = err?.response?.data?.detail
  if (!d) return fallback
  return typeof d === 'string' ? d : JSON.stringify(d)
}

export default api
