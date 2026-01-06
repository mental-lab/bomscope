<template>
  <div>
    <!-- Executive Summary -->
    <div style="margin-bottom: 3rem;">
      <h1 style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{{ data.organization_name }}</h1>
      <p style="color: #6b7280; font-size: 1rem;">Dependency & Container Analysis · {{ formatDate(data.timestamp) }}</p>
    </div>

    <!-- Key Metrics -->
    <div class="stats-grid" style="margin-bottom: 3rem;">
      <div class="stat-card" style="background: white; border: 2px solid #e5e7eb;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
          <div style="width: 48px; height: 48px; background: #eff6ff; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <svg style="width: 24px; height: 24px; color: #3b82f6;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
          </div>
          <div>
            <div style="font-size: 0.875rem; color: #6b7280; font-weight: 500;">Total Projects</div>
            <div style="font-size: 2rem; font-weight: 700; color: #111827;">{{ data.analyzed_projects }}</div>
          </div>
        </div>
        <div style="font-size: 0.875rem; color: #6b7280;">{{ data.analyzed_projects }}/{{ data.total_projects }} analyzed</div>
      </div>

      <div class="stat-card" style="background: white; border: 2px solid #e5e7eb;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
          <div style="width: 48px; height: 48px; background: #f0fdf4; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <svg style="width: 24px; height: 24px; color: #22c55e;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
            </svg>
          </div>
          <div>
            <div style="font-size: 0.875rem; color: #6b7280; font-weight: 500;">Chainguard Images</div>
            <div style="font-size: 2rem; font-weight: 700; color: #111827;">{{ dockerfileAdoptionCount }}</div>
          </div>
        </div>
        <div style="font-size: 0.875rem; color: #6b7280;">{{ dockerfileAdoptionCount }}/{{ totalDockerfiles }} repos using Chainguard</div>
      </div>

      <div class="stat-card" style="background: white; border: 2px solid #e5e7eb;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
          <div style="width: 48px; height: 48px; background: #fef3c7; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <svg style="width: 24px; height: 24px; color: #f59e0b;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path>
            </svg>
          </div>
          <div>
            <div style="font-size: 0.875rem; color: #6b7280; font-weight: 500;">Dependencies</div>
            <div style="font-size: 2rem; font-weight: 700; color: #111827;">{{ formatNumber(data.total_dependencies) }}</div>
          </div>
        </div>
        <div style="font-size: 0.875rem; color: #6b7280;">{{ Object.keys(data.ecosystems_breakdown).length }} ecosystems detected</div>
      </div>

      <div v-if="data.coverage_analysis" class="stat-card" style="background: white; border: 2px solid #e5e7eb;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
          <div style="width: 48px; height: 48px; background: #ede9fe; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <svg style="width: 24px; height: 24px; color: #8b5cf6;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
          </div>
          <div>
            <div style="font-size: 0.875rem; color: #6b7280; font-weight: 500;">Python Coverage</div>
            <div style="font-size: 2rem; font-weight: 700; color: #111827;">{{ pythonCoverage }}%</div>
          </div>
        </div>
        <div style="font-size: 0.875rem; color: #6b7280;">{{ pythonAvailable }}/{{ pythonTotal }} packages available</div>
      </div>
    </div>

    <!-- Collapsible Sections -->
    <!-- Dockerfile Adoption -->
    <div v-if="dockerfileProjects.length > 0" class="card" style="margin-bottom: 2rem;">
      <div @click="toggleSection('dockerfile')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e5e7eb;">
        <div>
          <h2 style="font-size: 1.25rem; font-weight: 600; color: #111827; margin: 0;">Container Image Adoption</h2>
          <p style="margin: 0.25rem 0 0 0; font-size: 0.875rem; color: #6b7280;">{{ dockerfileAdoptionCount }} of {{ dockerfileProjects.length }} repositories using Chainguard images</p>
        </div>
        <svg :style="`transform: rotate(${expandedSections.dockerfile ? '180deg' : '0deg'}); transition: transform 0.2s;`" style="width: 20px; height: 20px; color: #6b7280;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
        </svg>
      </div>
      <div v-show="expandedSections.dockerfile" style="padding: 1.5rem;">
        <div v-for="project in dockerfileProjects" :key="project.name" style="padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
              <div style="font-weight: 600; color: #111827; margin-bottom: 0.5rem;">{{ project.name }}</div>
              <div v-if="project.chainguard_images.length > 0" style="margin-top: 0.75rem;">
                <div style="font-size: 0.875rem; font-weight: 500; color: #059669; margin-bottom: 0.5rem;">✓ Chainguard Images</div>
                <div v-for="(image, idx) in project.chainguard_images" :key="idx" style="font-family: 'Monaco', 'Menlo', monospace; font-size: 0.875rem; color: #374151; background: #f3f4f6; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.25rem;">
                  {{ image }}
                </div>
              </div>
              <div v-if="project.other_images.length > 0" style="margin-top: 0.75rem;">
                <div style="font-size: 0.875rem; font-weight: 500; color: #6b7280; margin-bottom: 0.5rem;">Other Images</div>
                <div v-for="(image, idx) in project.other_images" :key="idx" style="font-family: 'Monaco', 'Menlo', monospace; font-size: 0.875rem; color: #6b7280; background: #f9fafb; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.25rem;">
                  {{ image }}
                </div>
              </div>
            </div>
            <div style="margin-left: 1rem;">
              <div v-if="project.chainguard_images.length > 0" style="display: inline-block; padding: 0.375rem 0.75rem; background: #d1fae5; color: #065f46; border-radius: 6px; font-size: 0.875rem; font-weight: 500;">
                ✓ Adopted
              </div>
              <div v-else style="display: inline-block; padding: 0.375rem 0.75rem; background: #fef3c7; color: #92400e; border-radius: 6px; font-size: 0.875rem; font-weight: 500;">
                Opportunity
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Ecosystems Breakdown -->
    <div class="card" style="margin-bottom: 2rem;">
      <div @click="toggleSection('ecosystems')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e5e7eb;">
        <div>
          <h2 style="font-size: 1.25rem; font-weight: 600; color: #111827; margin: 0;">Ecosystems Detected</h2>
          <p style="margin: 0.25rem 0 0 0; font-size: 0.875rem; color: #6b7280;">{{ Object.keys(data.ecosystems_breakdown).length }} ecosystems across {{ data.analyzed_projects }} projects</p>
        </div>
        <svg :style="`transform: rotate(${expandedSections.ecosystems ? '180deg' : '0deg'}); transition: transform 0.2s;`" style="width: 20px; height: 20px; color: #6b7280;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
        </svg>
      </div>
      <div v-show="expandedSections.ecosystems" style="padding: 1.5rem;">
        <div class="stats-grid">
          <div v-for="(ecosystem, name) in sortedEcosystems" :key="name" class="stat-card" style="background: #f9fafb; border: 1px solid #e5e7eb;">
            <div style="font-size: 0.875rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{{ name }}</div>
            <div style="font-size: 1.75rem; font-weight: 700; color: #111827; margin: 0.5rem 0;">{{ formatNumber(ecosystem.total_dependencies) }}</div>
            <div style="font-size: 0.875rem; color: #6b7280;">{{ ecosystem.total_projects }} project{{ ecosystem.total_projects > 1 ? 's' : '' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Coverage Analysis -->
    <div v-if="data.coverage_analysis" class="card">
      <div @click="toggleSection('coverage')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid #e5e7eb;">
        <div>
          <h2 style="font-size: 1.25rem; font-weight: 600; color: #111827; margin: 0;">Chainguard Coverage Analysis</h2>
          <p style="margin: 0.25rem 0 0 0; font-size: 0.875rem; color: #6b7280;">Package availability across supported ecosystems</p>
        </div>
        <svg :style="`transform: rotate(${expandedSections.coverage ? '180deg' : '0deg'}); transition: transform 0.2s;`" style="width: 20px; height: 20px; color: #6b7280;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
        </svg>
      </div>
      <div v-show="expandedSections.coverage" style="padding: 1.5rem;">
        <div class="stats-grid">
          <div v-for="(coverage, ecosystem) in coverageData" :key="ecosystem" class="stat-card" style="background: #f9fafb; border: 1px solid #e5e7eb;">
            <div style="font-size: 0.875rem; font-weight: 500; color: #6b7280; text-transform: uppercase; margin-bottom: 0.75rem;">{{ ecosystem }}</div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
              <div style="flex: 1; height: 10px; background: #e5e7eb; border-radius: 5px; overflow: hidden;">
                <div :style="`width: ${coverage.percentage}%; height: 100%; background: ${getColorForPercentage(coverage.percentage)}; transition: width 0.3s;`"></div>
              </div>
              <div style="font-size: 1.5rem; font-weight: 700; color: #111827; min-width: 65px; text-align: right;">
                {{ coverage.percentage }}%
              </div>
            </div>
            <div style="font-size: 0.875rem; color: #6b7280;">
              {{ coverage.available }}/{{ coverage.total }} packages available
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'

export default {
  name: 'Overview',
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const expandedSections = ref({
      dockerfile: false,
      ecosystems: false,
      coverage: false
    })

    const toggleSection = (section) => {
      expandedSections.value[section] = !expandedSections.value[section]
    }

    const formatDate = (timestamp) => {
      return new Date(timestamp).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    }

    const formatNumber = (num) => {
      return num.toLocaleString()
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

    const pythonCoverage = computed(() => {
      if (!props.data.coverage_analysis?.python) return 0
      return Math.round(props.data.coverage_analysis.python.percentage)
    })

    const pythonAvailable = computed(() => {
      if (!props.data.coverage_analysis?.python) return 0
      return props.data.coverage_analysis.python.available
    })

    const pythonTotal = computed(() => {
      if (!props.data.coverage_analysis?.python) return 0
      return props.data.coverage_analysis.python.total
    })

    const sortedEcosystems = computed(() => {
      if (!props.data.ecosystems_breakdown) return {}
      
      const entries = Object.entries(props.data.ecosystems_breakdown)
      entries.sort((a, b) => b[1].total_dependencies - a[1].total_dependencies)
      
      return Object.fromEntries(entries)
    })

    const dockerfileAdoptionCount = computed(() => {
      if (!props.data.projects) return 0
      
      let count = 0
      for (const project of props.data.projects) {
        if (project.dockerfile_adoption?.adoption_detected) {
          count++
        }
      }
      return count
    })

    const totalDockerfiles = computed(() => {
      if (!props.data.projects) return 0
      
      let count = 0
      for (const project of props.data.projects) {
        if (project.dockerfile_adoption?.dockerfiles_found) {
          count += project.dockerfile_adoption.dockerfiles_found
        }
      }
      return count
    })

    const dockerfileProjects = computed(() => {
      if (!props.data.projects) return []
      
      return props.data.projects
        .filter(p => p.dockerfile_adoption?.dockerfiles_found > 0)
        .map(p => ({
          name: p.repository.name,
          dockerfiles: p.dockerfile_adoption.dockerfiles_found,
          chainguard_images: p.dockerfile_adoption.chainguard_images || [],
          other_images: p.dockerfile_adoption.other_images || []
        }))
    })

    const getColorForPercentage = (percentage) => {
      if (percentage >= 80) return '#10b981' // green
      if (percentage >= 50) return '#f59e0b' // orange
      return '#ef4444' // red
    }

    return {
      expandedSections,
      toggleSection,
      formatDate,
      formatNumber,
      coverageData,
      pythonCoverage,
      pythonAvailable,
      pythonTotal,
      sortedEcosystems,
      dockerfileAdoptionCount,
      totalDockerfiles,
      dockerfileProjects,
      getColorForPercentage
    }
  }
}
</script>
