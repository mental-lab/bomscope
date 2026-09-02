import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import OverviewPage from './pages/OverviewPage.vue'
import ReposPage from './pages/ReposPage.vue'
import RepoDetailPage from './pages/RepoDetailPage.vue'
import DependenciesPage from './pages/DependenciesPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import LoginPage from './pages/LoginPage.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewPage },
    { path: '/repositories', name: 'repos', component: ReposPage },
    { path: '/repositories/:fullName(.*)', name: 'repo-detail', component: RepoDetailPage },
    { path: '/dependencies', name: 'dependencies', component: DependenciesPage },
    { path: '/settings', name: 'settings', component: SettingsPage },
    { path: '/login', name: 'login', component: LoginPage },
  ]
})

createApp(App).use(router).mount('#app')
