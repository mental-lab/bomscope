<template>
  <div class="app-shell">
    <aside class="sidebar">
      <router-link to="/" class="brand">
        <img class="brand-mark" src="/logo.svg" alt="bomscope" width="24" height="24" />
        bom<span class="brand-accent">scope</span>
      </router-link>

      <div class="org-select" v-if="org">
        <span class="org-select-label">Organization</span>
        <span class="org-select-value mono">{{ org }}</span>
      </div>

      <nav class="side-nav">
        <span class="nav-section">Analyze</span>
        <router-link to="/" exact-active-class="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="1.5" width="5" height="5" rx="1"/><rect x="9.5" y="1.5" width="5" height="5" rx="1"/><rect x="1.5" y="9.5" width="5" height="5" rx="1"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/></svg>
          Overview
        </router-link>
        <router-link to="/repositories" active-class="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 4.5L8 1.5l6 3v7l-6 3-6-3v-7z"/><path d="M2 4.5l6 3 6-3M8 7.5v7"/></svg>
          Repositories
        </router-link>
        <router-link to="/dependencies" active-class="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="3" cy="3" r="1.75"/><circle cx="13" cy="3" r="1.75"/><circle cx="8" cy="13" r="1.75"/><path d="M4.2 4.4l3 6.8M11.8 4.4l-3 6.8M4.75 3h6.5"/></svg>
          Dependencies
        </router-link>

        <span class="nav-section">Configure</span>
        <router-link v-if="auth.role !== 'viewer'" to="/settings" active-class="active" class="nav-item">
          <svg class="nav-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="2.25"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4"/></svg>
          Settings
        </router-link>
      </nav>

      <div v-if="auth.token" class="sidebar-auth">
        <span class="badge accent mono">{{ auth.role }}</span>
        <a class="nav-item" @click="logout" style="cursor: pointer">Sign out</a>
      </div>

      <div class="sidebar-footer mono">bomscope &middot; self-managed</div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script>
import { ref, provide } from 'vue'
import { apiFetch, auth, clearToken } from './api'

const DEFAULT_ADOPTION = {
  label: 'Trusted',
  patterns: ''
}

export default {
  name: 'App',
  setup() {
    const org = ref(null)
    const adoption = ref(DEFAULT_ADOPTION)

    // Adoption config comes from the server (Settings page writes to
    // /api/config) — shared across browsers, not localStorage.
    apiFetch('/api/config')
      .then(r => r.ok ? r.json() : null)
      .then(cfg => {
        if (!cfg) return
        if (cfg.organization) org.value = cfg.organization
        if (cfg.adoption) adoption.value = cfg.adoption
      })
      .catch(() => {})

    provide('org', org)
    provide('adoption', adoption)

    const logout = () => {
      clearToken()
      window.location.href = '/login'
    }

    return { org, auth, logout }
  }
}
</script>
