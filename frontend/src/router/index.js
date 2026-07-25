import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'browser', component: () => import('../views/DocumentBrowserView.vue') },
  {
    path: '/documents/:id',
    name: 'document-detail',
    component: () => import('../views/DocumentDetailView.vue'),
    props: true,
  },
  { path: '/reviews', name: 'reviews', component: () => import('../views/ReviewInboxView.vue') },
  {
    path: '/admin/dashboard',
    name: 'admin-dashboard',
    component: () => import('../views/AdminDashboardView.vue'),
    meta: { adminOnly: true },
  },
  {
    path: '/admin/audit',
    name: 'admin-audit',
    component: () => import('../views/AuditLogView.vue'),
    meta: { adminOnly: true },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('../views/UserManagementView.vue'),
    meta: { adminOnly: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'browser' }
  }
  if (to.meta.adminOnly && !auth.isAdmin) {
    return { name: 'browser' }
  }
  return true
})

export default router
