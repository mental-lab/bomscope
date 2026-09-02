<template>
  <div>
    <div v-if="loading" class="loading">loading…</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else-if="repo">
      <div class="detail-header">
        <h1 class="page-title mono">{{ repo.repo_full_name }}</h1>
        <span class="badge" :class="repo.uses_trusted ? 'green' : 'red'">
          {{ repo.uses_trusted ? 'trusted registry' : 'no trusted registry' }}
        </span>
      </div>
      <div class="detail-meta">
        <span v-if="repo.url"><a :href="repo.url" target="_blank">{{ repo.url }}</a></span>
        <span>branch: <span class="mono">{{ repo.default_branch }}</span></span>
        <span>scanned: {{ formatDate(repo.scanned_at) }}</span>
      </div>

      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Dependencies</div>
          <div class="stat-value">{{ repo.dependency_count }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Primary Ecosystem</div>
          <div class="stat-value accent" style="font-size: 18px;">{{ repo.primary_ecosystem || '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Language</div>
          <div class="stat-value" style="font-size: 18px;">{{ repo.language || '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Dockerfile</div>
          <div class="stat-value" :class="repo.has_dockerfile ? 'green' : 'yellow'" style="font-size: 18px;">
            {{ repo.has_dockerfile ? 'yes' : 'no' }}
          </div>
        </div>
      </div>

      <div class="panel" v-if="eolItems.length">
        <div class="panel-title">End-of-Life Status</div>
        <table class="table">
          <thead><tr><th>Component</th><th>Version</th><th>Status</th><th>EOL Date</th><th>Latest</th></tr></thead>
          <tbody>
            <tr v-for="item in eolItems" :key="(item.image || item.name)">
              <td class="mono">{{ item.image || item.name }}</td>
              <td class="mono">{{ item.cycle || item.version }}</td>
              <td><span class="badge" :class="item.status === 'eol' ? 'red' : 'yellow'">{{ item.status === 'eol' ? 'EOL' : 'EOL soon' }}</span></td>
              <td class="mono">{{ item.eol_date || '—' }}</td>
              <td class="mono">{{ item.latest || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel" v-if="repo.vulnerability_summary">
        <div class="panel-title">Vulnerabilities</div>
        <div class="stat-grid" style="margin-bottom: 16px;">
          <div class="stat-card"><div class="stat-label">Critical</div><div class="stat-value" :class="repo.vulnerability_summary.critical ? 'yellow' : 'green'">{{ repo.vulnerability_summary.critical }}</div></div>
          <div class="stat-card"><div class="stat-label">High</div><div class="stat-value" :class="repo.vulnerability_summary.high ? 'yellow' : 'green'">{{ repo.vulnerability_summary.high }}</div></div>
          <div class="stat-card"><div class="stat-label">Medium</div><div class="stat-value">{{ repo.vulnerability_summary.medium }}</div></div>
          <div class="stat-card"><div class="stat-label">Low</div><div class="stat-value">{{ repo.vulnerability_summary.low }}</div></div>
          <div class="stat-card"><div class="stat-label">Total</div><div class="stat-value">{{ repo.vulnerability_summary.total }}</div></div>
        </div>
        <table v-if="repo.vulnerability_summary.top_vulnerabilities.length" class="table">
          <thead><tr><th>CVE</th><th>Severity</th><th>Package</th><th>Fixed In</th></tr></thead>
          <tbody>
            <tr v-for="v in repo.vulnerability_summary.top_vulnerabilities" :key="v.id + v.package">
              <td class="mono">{{ v.id }}</td>
              <td><span class="badge" :class="v.severity === 'Critical' ? 'red' : 'yellow'">{{ v.severity }}</span></td>
              <td class="mono">{{ v.package }}@{{ v.version }}</td>
              <td class="mono">{{ v.fixed_in }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel" v-if="riskyImages.length">
        <div class="panel-title">Risky Base Images</div>
        <table class="table">
          <thead><tr><th>Image</th><th>File</th><th>Reason</th></tr></thead>
          <tbody>
            <tr v-for="img in riskyImages" :key="img.image + img.file">
              <td class="mono">{{ img.image }}</td>
              <td class="mono" style="color: var(--text-faint);">{{ img.file }}</td>
              <td>{{ img.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel" v-if="repo.license_summary && repo.license_summary.copyleft_count">
        <div class="panel-title">Copyleft Licenses ({{ repo.license_summary.copyleft_count }})</div>
        <table class="table">
          <thead><tr><th>Package</th><th>Version</th><th>License</th></tr></thead>
          <tbody>
            <tr v-for="p in repo.license_summary.copyleft_packages" :key="p.name + p.version + p.license">
              <td class="mono">{{ p.name }}</td>
              <td class="mono">{{ p.version }}</td>
              <td><span class="badge red">{{ p.license }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel" v-if="dockerImages.length">
        <div class="panel-title">Container Images</div>
        <table class="table">
          <thead><tr><th>Image</th><th>Trusted</th></tr></thead>
          <tbody>
            <tr v-for="img in dockerImages" :key="img.image + img.file">
              <td class="mono">{{ img.image }}</td>
              <td><span class="badge" :class="img.is_trusted ? 'green' : 'red'">{{ img.is_trusted ? 'yes' : 'no' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="panel-title">Dependencies ({{ repo.dependencies.length }})</div>
        <div class="filters">
          <input class="input" v-model="search" placeholder="filter dependencies…" />
        </div>
        <div v-if="!filteredDeps.length" class="empty" style="padding: 24px 0;">no dependencies match</div>
        <table v-else class="table">
          <thead><tr><th>Package</th><th>Version</th><th>Ecosystem</th></tr></thead>
          <tbody>
            <tr v-for="d in filteredDeps" :key="d.package_name + d.version">
              <td class="mono">{{ d.package_name }}</td>
              <td class="mono">{{ d.version || '—' }}</td>
              <td><span class="badge accent">{{ d.ecosystem }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { apiFetch } from '../api'
import { useRoute } from 'vue-router'

export default {
  name: 'RepoDetailPage',
  setup() {
    const route = useRoute()
    const repo = ref(null)
    const loading = ref(true)
    const error = ref(null)
    const search = ref('')

    const filteredDeps = computed(() => {
      if (!repo.value) return []
      if (!search.value) return repo.value.dependencies
      const q = search.value.toLowerCase()
      return repo.value.dependencies.filter(d => d.package_name.toLowerCase().includes(q))
    })

    const dockerImages = computed(() => {
      const adoption = repo.value?.dockerfile_adoption
      if (!adoption) return []
      const images = []
      for (const df of adoption.dockerfiles || []) {
        for (const img of df.trusted_images || []) {
          images.push({ image: img, is_trusted: true, file: df.path || '' })
        }
        for (const img of df.other_images || []) {
          images.push({ image: img, is_trusted: false, file: df.path || '' })
        }
      }
      return images
    })

    const riskyImages = computed(() =>
      repo.value?.dockerfile_adoption?.risky_images || []
    )

    const eolItems = computed(() => {
      const eol = repo.value?.eol_summary
      if (!eol) return []
      const flagged = (items) => (items || []).filter(i => i.status === 'eol' || i.status === 'approaching')
      return [...flagged(eol.images), ...flagged(eol.dependencies)]
    })

    const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '—'

    onMounted(async () => {
      try {
        const res = await apiFetch('/api/repositories/' + encodeURIComponent(route.params.fullName))
        if (!res.ok) throw new Error(res.status === 404 ? 'repository not found' : 'request failed')
        repo.value = await res.json()
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    })

    return { repo, loading, error, search, filteredDeps, dockerImages, riskyImages, eolItems, formatDate }
  }
}
</script>
