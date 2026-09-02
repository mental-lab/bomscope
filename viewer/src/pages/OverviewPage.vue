<template>
  <div>
    <h1 class="page-title">Overview</h1>
    <p class="page-sub">Repository supply-chain intelligence across your organization</p>

    <div v-if="loading" class="loading">loading…</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">Repositories</div>
          <div class="stat-value">{{ stats.total_repositories }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Dependencies</div>
          <div class="stat-value">{{ stats.total_dependencies.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">With Dockerfiles</div>
          <div class="stat-value accent">{{ stats.repositories_with_dockerfile }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Using {{ adoption.label }}</div>
          <div class="stat-value green">{{ stats.repositories_using_trusted }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ adoption.label }} Adoption</div>
          <div class="stat-value" :class="stats.trusted_adoption_pct >= 50 ? 'green' : 'yellow'">
            {{ stats.trusted_adoption_pct }}%
          </div>
        </div>
      </div>

      <div class="panel" v-if="trends.length > 1">
        <div class="panel-title">Trends</div>
        <div class="chart-box" style="height: 240px;">
          <Line :data="trendChart" :options="trendOptions" />
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-title">Dependencies by Ecosystem</div>
          <div class="chart-box" style="height: 280px;">
            <Doughnut :data="ecoChart" :options="doughnutOptions" />
          </div>
        </div>

        <div class="panel">
          <div class="panel-title">Attention Needed</div>
          <p v-if="!insights.length" class="empty" style="padding: 24px 0;">no issues found — nice</p>
          <div v-else class="insight-list">
            <div v-for="g in insights" :key="g.id" class="insight-group">
              <div class="insight-header" @click="toggleInsight(g.id)">
                <span class="badge" :class="severityClass(g.severity)">{{ g.severity }}</span>
                <span class="insight-title">{{ g.title }}</span>
                <span class="insight-desc">{{ g.description }}</span>
                <span class="insight-chevron">{{ expanded[g.id] ? '−' : '+' }}</span>
              </div>
              <table v-if="expanded[g.id]" class="table" style="margin-top: 8px;">
                <tbody>
                  <tr v-for="r in g.repos" :key="r.repo_full_name" @click="$router.push('/repositories/' + r.repo_full_name)">
                    <td class="mono">{{ shortName(r.repo_full_name) }}</td>
                    <td class="mono" style="text-align: right; color: var(--text-faint);">{{ detailFor(g.id, r) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, inject } from 'vue'
import { apiFetch } from '../api'
import { Line, Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, LineElement, PointElement, LinearScale, CategoryScale, ArcElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, ArcElement, Tooltip, Legend)

const PALETTE = ['#7aa2f7', '#9ece6a', '#e0af68', '#f7768e', '#bb9af7', '#73daca', '#ff9e64', '#b4f9f8', '#c0caf5', '#565f89']

export default {
  name: 'OverviewPage',
  components: { Line, Doughnut },
  setup() {
    const stats = ref(null)
    const trends = ref([])
    const insights = ref([])
    const loading = ref(true)
    const error = ref(null)
    const expanded = ref({})
    const adoption = inject('adoption')

    const toggleInsight = (id) => { expanded.value[id] = !expanded.value[id] }

    const severityClass = (sev) => ({ critical: 'red', high: 'red', medium: 'yellow', low: '' })[sev] || ''

    const detailFor = (groupId, r) => {
      if (groupId === 'eol') return `${r.eol_count} eol${r.eol_approaching_count ? ` / ${r.eol_approaching_count} soon` : ''}`
      if (groupId === 'eol-approaching') return `${r.eol_approaching_count} soon`
      if (groupId === 'critical-cves') return `${r.vuln_critical} crit / ${r.vuln_high} high`
      if (groupId === 'risky-images') return `${r.risky_image_count} images`
      if (groupId === 'copyleft') return `${r.copyleft_count} pkgs`
      if (groupId === 'stale-deps') return `${r.stale_count} stale`
      if (groupId === 'no-trusted') return `${r.dependency_count} deps`
      return ''
    }

    const trendChart = computed(() => ({
      labels: trends.value.map(t => new Date(t.scan_timestamp).toLocaleDateString()),
      datasets: [
        {
          label: `${adoption.value.label} adoption %`,
          data: trends.value.map(t => t.trusted_adoption_pct),
          borderColor: '#9ece6a',
          backgroundColor: 'rgba(158, 206, 106, 0.1)',
          yAxisID: 'y',
          tension: 0.3,
          fill: true
        },
        {
          label: 'Dependencies',
          data: trends.value.map(t => t.total_dependencies),
          borderColor: '#7aa2f7',
          backgroundColor: 'rgba(122, 162, 247, 0.1)',
          yAxisID: 'y1',
          tension: 0.3,
          fill: true
        }
      ]
    }))

    const trendOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#8b94a7', boxWidth: 12 } } },
      scales: {
        x: { ticks: { color: '#5a6376' }, grid: { color: '#232b3a' } },
        y: { position: 'left', ticks: { color: '#9ece6a' }, grid: { color: '#232b3a' }, max: 100 },
        y1: { position: 'right', ticks: { color: '#7aa2f7' }, grid: { display: false } }
      }
    }

    const ecoChart = computed(() => {
      const entries = Object.entries(stats.value.ecosystems).sort((a, b) => b[1] - a[1])
      return {
        labels: entries.map(e => e[0]),
        datasets: [{
          data: entries.map(e => e[1]),
          backgroundColor: entries.map((_, i) => PALETTE[i % PALETTE.length]),
          borderColor: '#0a0e14',
          borderWidth: 2
        }]
      }
    })

    const doughnutOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { color: '#8b94a7', boxWidth: 12 } } }
    }

    const shortName = (full) => full.split('/').slice(-1)[0]

    onMounted(async () => {
      try {
        const [statsRes, trendsRes, insightsRes] = await Promise.all([
          apiFetch('/api/stats/overview'),
          apiFetch('/api/trends'),
          apiFetch('/api/insights')
        ])
        if (!statsRes.ok) throw new Error('stats request failed')
        stats.value = await statsRes.json()
        trends.value = trendsRes.ok ? await trendsRes.json() : []
        if (insightsRes.ok) {
          const data = await insightsRes.json()
          insights.value = data.insights || []
        }
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    })

    return { stats, trends, insights, loading, error, expanded, adoption, toggleInsight, severityClass, detailFor, trendChart, trendOptions, ecoChart, doughnutOptions, shortName }
  }
}
</script>
