import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../pages/LoginPage.vue'), meta: { public: true } },
  { path: '/', redirect: '/features' },
  { path: '/features', name: 'features', component: () => import('../pages/FeaturesPage.vue') },
  { path: '/features/:id/versions', name: 'feature-versions', component: () => import('../pages/FeatureVersionsPage.vue') },
  { path: '/samples/new', name: 'sample-new', component: () => import('../pages/SampleNewPage.vue') },
  { path: '/samples/:id', name: 'sample-detail', component: () => import('../pages/SampleDetailPage.vue') },
  { path: '/backfills', name: 'backfills', component: () => import('../pages/BackfillsPage.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/features' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'features' }
  }
  return true
})

export default router
