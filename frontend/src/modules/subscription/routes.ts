import type { RouteRecordRaw } from 'vue-router'

const SubscriptionLayout = () => import('./layout/SubscriptionLayout.vue')
const SourcesPage = () => import('./pages/SourcesPage.vue')
const PluginsPage = () => import('./pages/PluginsPage.vue')
const ArticlesPage = () => import('./pages/ArticlesPage.vue')
const ArticleDetailPage = () => import('./pages/ArticleDetailPage.vue')

export const subscriptionRoutes: RouteRecordRaw[] = [
  {
    path: 'subscription',
    component: SubscriptionLayout,
    children: [
      { path: '', name: 'subscription-sources', component: SourcesPage },
      { path: 'plugins', name: 'subscription-plugins', component: PluginsPage },
      { path: 'articles', name: 'subscription-articles', component: ArticlesPage },
      { path: 'articles/:id', name: 'subscription-article', component: ArticleDetailPage },
    ],
  },
]
