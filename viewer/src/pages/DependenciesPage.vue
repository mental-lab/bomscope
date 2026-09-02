<template>
  <div>
    <h1 class="page-title">Dependencies</h1>
    <p class="page-sub">Search across all repositories — "where do we use X?"</p>

    <div class="filters">
      <input class="input" v-model="search" placeholder="package name… (e.g. lodash)" @keyup.enter="runSearch" />
      <select class="select" v-model="ecoFilter" @change="runSearch">
        <option value="">all ecosystems</option>
        <option v-for="e in ecosystems" :key="e" :value="e">{{ e }}</option>
      </select>
      <input class="input" v-model="repoFilter" placeholder="repository name… (e.g. opentelemetry-demo)" @keyup.enter="runSearch" />
    </div>

    <div v-if="loading" class="loading">loading…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="!deps.length" class="empty">no dependencies found</div>

    <div v-else class="panel" style="padding: 8px 0;">
      <table class="table">
        <thead>
          <tr><th>Package</th><th>Version</th><th>Ecosystem</th><th>Used In</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in deps" :key="d.repo_full_name + d.package_name + d.version" @click="$router.push('/repositories/' + d.repo_full_name)">
            <td class="mono">{{ d.package_name }}</td>
            <td class="mono">{{ d.version || '—' }}</td>
            <td><span class="badge accent">{{ d.ecosystem }}</span></td>
            <td class="mono">{{ shortName(d.repo_full_name) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { apiFetch } from '../api'

export default {
  name: 'DependenciesPage',
  setup() {
    const deps = ref([])
    const ecosystems = ref([])
    const loading = ref(true)
    const error = ref(null)
    const search = ref('')
    const ecoFilter = ref('')
    const repoFilter = ref('')

    const runSearch = async () => {
      loading.value = true
      error.value = null
      try {
        const params = new URLSearchParams({ limit: '1000' })
        if (search.value) params.set('package_name', search.value)
        if (ecoFilter.value) params.set('ecosystem', ecoFilter.value)
        if (repoFilter.value) params.set('repo', repoFilter.value)
        const res = await apiFetch('/api/dependencies?' + params)
        if (!res.ok) throw new Error('request failed')
        deps.value = await res.json()
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    }

    const shortName = (full) => full.split('/').slice(-1)[0]

    onMounted(async () => {
      try {
        const res = await apiFetch('/api/stats/overview')
        if (res.ok) {
          const stats = await res.json()
          ecosystems.value = Object.keys(stats.ecosystems).sort()
        }
      } catch (e) { /* non-fatal */ }
      await runSearch()
    })

    return { deps, ecosystems, loading, error, search, ecoFilter, repoFilter, runSearch, shortName }
  }
}
</script>
