<template>
  <div>
    <!-- Charts Grid -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 1.5rem;">
      <!-- Dependencies by Ecosystem -->
      <div class="card chart-container">
        <h3 style="margin-bottom: 1rem; font-size: 1.125rem;">Dependencies by Ecosystem</h3>
        <Pie :data="ecosystemChartData" :options="chartOptions" />
      </div>

      <!-- Coverage by Ecosystem -->
      <div v-if="data.coverage_analysis" class="card chart-container">
        <h3 style="margin-bottom: 1rem; font-size: 1.125rem;">Coverage Percentage</h3>
        <Bar :data="coverageChartData" :options="barChartOptions" />
      </div>

      <!-- Top Dependencies -->
      <div class="card chart-container" style="grid-column: 1 / -1;">
        <h3 style="margin-bottom: 1rem; font-size: 1.125rem;">Top Dependencies</h3>
        <Bar :data="topDependenciesData" :options="horizontalBarOptions" />
      </div>
    </div>

    <!-- Adoption Indicators -->
    <div v-if="adoptionIndicators.length > 0" class="card" style="margin-top: 1.5rem;">
      <h3 style="margin-bottom: 1rem; font-size: 1.125rem;">Chainguard Adoption Indicators</h3>
      <div v-for="indicator in adoptionIndicators" :key="indicator.project" style="margin-bottom: 0.75rem;">
        <strong>{{ indicator.project }}</strong>
        <ul style="margin-left: 1.5rem; margin-top: 0.25rem; color: #6b7280;">
          <li v-for="(item, idx) in indicator.indicators" :key="idx">{{ item }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue'
import { Pie, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend)

export default {
  name: 'Stats',
  components: { Pie, Bar },
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const ecosystemChartData = computed(() => {
      const ecosystems = props.data.ecosystems_breakdown
      return {
        labels: Object.keys(ecosystems).map(e => e.toUpperCase()),
        datasets: [{
          data: Object.values(ecosystems).map(e => e.total_dependencies),
          backgroundColor: ['#3b82f6', '#f59e0b', '#ec4899', '#10b981', '#8b5cf6']
        }]
      }
    })

    const coverageChartData = computed(() => {
      if (!props.data.coverage_analysis) return { labels: [], datasets: [] }
      
      const coverage = props.data.coverage_analysis
      const ecosystems = []
      const percentages = []
      
      for (const [ecosystem, data] of Object.entries(coverage)) {
        if (ecosystem !== 'adoption_indicators') {
          ecosystems.push(ecosystem.toUpperCase())
          percentages.push(data.percentage)
        }
      }
      
      return {
        labels: ecosystems,
        datasets: [{
          label: 'Coverage %',
          data: percentages,
          backgroundColor: '#3b82f6'
        }]
      }
    })

    const topDependenciesData = computed(() => {
      const depCounts = {}
      
      props.data.projects.forEach(project => {
        project.manifests.forEach(manifest => {
          manifest.dependencies.forEach(dep => {
            const name = dep.name
            depCounts[name] = (depCounts[name] || 0) + 1
          })
        })
      })
      
      const sorted = Object.entries(depCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15)
      
      return {
        labels: sorted.map(([name]) => name),
        datasets: [{
          label: 'Usage Count',
          data: sorted.map(([, count]) => count),
          backgroundColor: '#10b981'
        }]
      }
    })

    const adoptionIndicators = computed(() => {
      if (!props.data.coverage_analysis?.adoption_indicators) return []
      
      return Object.entries(props.data.coverage_analysis.adoption_indicators).map(
        ([project, indicators]) => ({ project, indicators })
      )
    })

    const chartOptions = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom'
        }
      }
    }

    const barChartOptions = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 100
        }
      }
    }

    const horizontalBarOptions = {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: false
        }
      }
    }

    return {
      ecosystemChartData,
      coverageChartData,
      topDependenciesData,
      adoptionIndicators,
      chartOptions,
      barChartOptions,
      horizontalBarOptions
    }
  }
}
</script>
