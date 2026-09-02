<template>
  <div>
    <h1 class="page-title">Repositories</h1>
    <p class="page-sub">All scanned repositories in {{ org || 'your organization' }}</p>

    <div class="filters">
      <input class="input" v-model="search" placeholder="search repositories…" />
      <select class="select" v-model="ecoFilter">
        <option value="">all ecosystems</option>
        <option v-for="e in ecosystems" :key="e" :value="e">{{ e }}</option>
      </select>
      <select class="select" v-model="trustedFilter">
        <option value="">trusted: any</option>
        <option value="true">using trusted registry</option>
        <option value="false">not using trusted registry</option>
      </select>
    </div>

    <div v-if="loading" class="loading">loading…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="!filtered.length" class="empty">no repositories match</div>

    <div v-else class="panel" style="padding: 8px 0;">
      <table class="table">
        <thead>
          <tr>
            <th>Repository</th>
            <th>Ecosystem</th>
            <th>Deps</th>
            <th>EOL</th>
            <th>Dockerfile</th>
            <th>Trusted</th>
            <th>Scanned</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filtered" :key="r.repo_full_name" @click="$router.push('/repositories/' + r.repo_full_name)">
            <td class="mono">{{ r.repo_full_name }}</td>
            <td><span class="badge accent">{{ r.primary_ecosystem || '—' }}</span></td>
            <td class="mono">{{ r.dependency_count }}</td>
            <td>
              <span v-if="r.eol_count > 0" class="badge red">{{ r.eol_count }} eol</span>
              <span v-else-if="r.eol_approaching_count > 0" class="badge yellow">{{ r.eol_approaching_count }} soon</span>
              <span v-else class="badge green">supported</span>
            </td>
            <td><span class="badge" :class="r.has_dockerfile ? 'green' : ''">{{ r.has_dockerfile ? 'yes' : 'no' }}</span></td>
            <td><span class="badge" :class="r.uses_trusted ? 'green' : 'red'">{{ r.uses_trusted ? 'yes' : 'no' }}</span></td>
            <td class="mono">{{ formatDate(r.scanned_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, inject } from 'vue'
import { apiFetch } from '../api'

export default {
  name: 'ReposPage',
  setup() {
    const org = inject('org')
    const repos = ref([])
    const loading = ref(true)
    const error = ref(null)
    const search = ref('')
    const ecoFilter = ref('')
    const trustedFilter = ref('')

    const ecosystems = computed(() =>
      [...new Set(repos.value.map(r => r.primary_ecosystem).filter(Boolean))].sort()
    )

    const filtered = computed(() => repos.value.filter(r => {
      if (search.value && !r.repo_full_name.toLowerCase().includes(search.value.toLowerCase())) return false
      if (ecoFilter.value && r.primary_ecosystem !== ecoFilter.value) return false
      if (trustedFilter.value === 'true' && !r.uses_trusted) return false
      if (trustedFilter.value === 'false' && r.uses_trusted) return false
      return true
    }))

    const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '—'

    onMounted(async () => {
      try {
        const res = await apiFetch('/api/repositories?limit=1000')
        if (!res.ok) throw new Error('request failed')
        repos.value = await res.json()
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    })

    return { org, repos, loading, error, search, ecoFilter, trustedFilter, ecosystems, filtered, formatDate }
  }
}
</script>
