<template>
  <div>
    <!-- Executive Summary Cards -->
    <div v-if="data.coverage_analysis" style="margin-bottom: 2rem;">
      <h2 style="margin-bottom: 1rem; font-size: 1.5rem; font-weight: 600;">Executive Summary</h2>
      <div class="stats-grid">
        <div class="stat-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
          <div class="stat-label" style="color: rgba(255,255,255,0.9);">Overall Coverage</div>
          <div class="stat-value" style="font-size: 2.5rem;">{{ overallCoverage }}%</div>
          <div style="margin-top: 0.5rem; font-size: 0.875rem; color: rgba(255,255,255,0.8);">
            {{ totalAvailable }}/{{ totalDependencies }} packages available
          </div>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
          <div class="stat-label" style="color: rgba(255,255,255,0.9);">Adoption Status</div>
          <div class="stat-value" style="font-size: 2.5rem;">{{ totalAdopted }}</div>
          <div style="margin-top: 0.5rem; font-size: 0.875rem; color: rgba(255,255,255,0.8);">
            {{ adoptionIndicatorCount }} projects with indicators
          </div>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
          <div class="stat-label" style="color: rgba(255,255,255,0.9);">Migration Opportunity</div>
          <div class="stat-value" style="font-size: 2.5rem;">{{ totalAvailable }}</div>
          <div style="margin-top: 0.5rem; font-size: 0.875rem; color: rgba(255,255,255,0.8);">
            packages ready to migrate
          </div>
        </div>
      </div>
    </div>

    <!-- Basic Info -->
    <h2 style="margin-bottom: 1rem; font-size: 1.5rem; font-weight: 600;">Analysis Overview</h2>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Organization</div>
        <div class="stat-value" style="font-size: 1.5rem;">{{ data.organization_name }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Platform</div>
        <div class="stat-value" style="font-size: 1.5rem; text-transform: uppercase;">{{ data.platform }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Projects</div>
        <div class="stat-value">{{ data.total_projects }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Analyzed Projects</div>
        <div class="stat-value">{{ data.analyzed_projects }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Dependencies</div>
        <div class="stat-value">{{ data.total_dependencies }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Analysis Date</div>
        <div class="stat-value" style="font-size: 1rem;">{{ formatDate(data.timestamp) }}</div>
      </div>
    </div>

    <!-- Ecosystems Breakdown -->
    <div class="card">
      <h2 style="margin-bottom: 1.5rem; font-size: 1.25rem;">Ecosystems Breakdown</h2>
      <div class="stats-grid">
        <div v-for="(ecosystem, name) in data.ecosystems_breakdown" :key="name" class="stat-card">
          <div class="stat-label">{{ name.toUpperCase() }}</div>
          <div class="stat-value" style="font-size: 1.5rem;">{{ ecosystem.total_dependencies }}</div>
          <div style="margin-top: 0.5rem; font-size: 0.875rem; color: #6b7280;">
            {{ ecosystem.total_projects }} projects
          </div>
        </div>
      </div>
    </div>

    <!-- Coverage by Ecosystem -->
    <div v-if="data.coverage_analysis" style="margin-top: 2rem;">
      <h2 style="margin-bottom: 1rem; font-size: 1.5rem; font-weight: 600;">Coverage by Ecosystem</h2>
      <div class="stats-grid">
        <div v-for="(coverage, ecosystem) in coverageData" :key="ecosystem" class="stat-card">
          <div class="stat-label">{{ ecosystem.toUpperCase() }}</div>
          <div style="margin: 1rem 0;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <div style="flex: 1; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">
                <div 
                  :style="`width: ${coverage.percentage}%; height: 100%; background: ${getColorForPercentage(coverage.percentage)}; transition: width 0.3s;`"
                ></div>
              </div>
              <div style="font-size: 1.25rem; font-weight: 600; min-width: 60px; text-align: right;">
                {{ coverage.percentage }}%
              </div>
            </div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.875rem; color: #6b7280;">
            <span>{{ coverage.available }}/{{ coverage.total }} available</span>
            <span style="color: #10b981;">{{ coverage.adopted }} adopted</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Adoption Indicators -->
    <div v-if="data.coverage_analysis?.adoption_indicators && Object.keys(data.coverage_analysis.adoption_indicators).length > 0" style="margin-top: 2rem;">
      <h2 style="margin-bottom: 1rem; font-size: 1.5rem; font-weight: 600;">Projects with Chainguard Adoption</h2>
      <div class="card">
        <div v-for="(indicators, project) in data.coverage_analysis.adoption_indicators" :key="project" style="padding: 1rem; border-bottom: 1px solid #e5e7eb;">
          <div style="font-weight: 600; color: #111827; margin-bottom: 0.5rem;">{{ project }}</div>
          <ul style="margin: 0; padding-left: 1.5rem; color: #6b7280; font-size: 0.875rem;">
            <li v-for="(indicator, idx) in indicators" :key="idx">{{ indicator }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'Overview',
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const formatDate = (timestamp) => {
      return new Date(timestamp).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    }

    const coverageData = computed(() => {
      if (!props.data.coverage_analysis) return {}
      
      const result = {}
      for (const [ecosystem, data] of Object.entries(props.data.coverage_analysis)) {
        if (ecosystem !== 'adoption_indicators') {
          result[ecosystem] = data
        }
      }
      return result
    })

    const overallCoverage = computed(() => {
      if (!props.data.coverage_analysis) return 0
      
      let totalDeps = 0
      let totalAvailable = 0
      
      for (const [ecosystem, data] of Object.entries(props.data.coverage_analysis)) {
        if (ecosystem !== 'adoption_indicators' && data.total) {
          totalDeps += data.total
          totalAvailable += data.available
        }
      }
      
      return totalDeps > 0 ? Math.round((totalAvailable / totalDeps) * 100) : 0
    })

    const totalDependencies = computed(() => {
      if (!props.data.coverage_analysis) return 0
      
      let total = 0
      for (const [ecosystem, data] of Object.entries(props.data.coverage_analysis)) {
        if (ecosystem !== 'adoption_indicators' && data.total) {
          total += data.total
        }
      }
      return total
    })

    const totalAvailable = computed(() => {
      if (!props.data.coverage_analysis) return 0
      
      let total = 0
      for (const [ecosystem, data] of Object.entries(props.data.coverage_analysis)) {
        if (ecosystem !== 'adoption_indicators' && data.available) {
          total += data.available
        }
      }
      return total
    })

    const totalAdopted = computed(() => {
      if (!props.data.coverage_analysis) return 0
      
      let total = 0
      for (const [ecosystem, data] of Object.entries(props.data.coverage_analysis)) {
        if (ecosystem !== 'adoption_indicators' && data.adopted !== undefined) {
          total += data.adopted
        }
      }
      return total
    })

    const adoptionIndicatorCount = computed(() => {
      if (!props.data.coverage_analysis?.adoption_indicators) return 0
      return Object.keys(props.data.coverage_analysis.adoption_indicators).length
    })

    const getColorForPercentage = (percentage) => {
      if (percentage >= 80) return '#10b981' // green
      if (percentage >= 50) return '#f59e0b' // orange
      return '#ef4444' // red
    }

    return {
      formatDate,
      coverageData,
      overallCoverage,
      totalDependencies,
      totalAvailable,
      totalAdopted,
      adoptionIndicatorCount,
      getColorForPercentage
    }
  }
}
</script>
