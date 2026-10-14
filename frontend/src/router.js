import { createRouter, createWebHashHistory } from 'vue-router'
import Login from './views/Login.vue'
import Layout from './views/Layout.vue'
import Mailboxes from './views/Mailboxes.vue'
import Compose from './views/Compose.vue'
import Sent from './views/Sent.vue'
import Drafts from './views/Drafts.vue'
import Stars from './views/Stars.vue'
import Profile from './views/Profile.vue'
import Admin from './views/Admin.vue'
import { state } from './store'

const router = createRouter({
  // hash 路由：纯静态托管（serv00 public_html）无需 rewrite 规则
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/mailboxes',
      children: [
        { path: 'mailboxes', component: Mailboxes },
        { path: 'compose', component: Compose },
        { path: 'sent', component: Sent },
        { path: 'drafts', component: Drafts },
        { path: 'stars', component: Stars },
        { path: 'profile', component: Profile },
        { path: 'admin', component: Admin, meta: { admin: true } },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.path === '/login') return true
  if (!state.user) return '/login'
  if (to.meta.admin && !state.user.is_admin) return '/mailboxes'
  return true
})

export default router
