<template>
  <div class="card">
    <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="Search dependencies or projects..." 
        style="flex: 1; min-width: 250px; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem;"
      />
      <select 
        v-model="ecosystemFilter" 
        style="padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem; background: white;"
      >
        <option value="">All Ecosystems</option>
        <option v-for="eco in ecosystems" :key="eco" :value="eco">
          {{ eco.toUpperCase() }}
        </option>
      </select>
      <select 
        v-model="coverageFilter" 
        style="padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem; background: white;"
      >
        <option value="">All Coverage Status</option>
        <option value="available">✓ Available Only</option>
        <option value="missing">— Missing Only</option>
      </select>
    </div>
    
    <!-- Summary Stats -->
    <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem; background: #f9fafb; border-radius: 0.5rem;">
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Total Dependencies</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #111827;">{{ filteredDependencies.length }}</div>
      </div>
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Available in Chainguard</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #10b981;">{{ availableCount }}</div>
      </div>
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Not Available</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #ef4444;">{{ missingCount }}</div>
      </div>
    </div>
    
    <div style="overflow-x: auto;">
      <table style="table-layout: fixed; width: 100%;">
        <colgroup>
          <col style="width: 30%;">
          <col style="width: 15%;">
          <col style="width: 15%;">
          <col style="width: 25%;">
          <col v-if="data.coverage_analysis" style="width: 15%;">
        </colgroup>
        <thead>
          <tr>
            <th>Dependency</th>
            <th>Version</th>
            <th>Ecosystem</th>
            <th>Project</th>
            <th v-if="data.coverage_analysis">Available in Chainguard</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="dep in filteredDependencies" :key="dep.id">
            <td style="word-break: break-word;"><strong>{{ dep.name }}</strong></td>
            <td><code style="background: #f3f4f6; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">{{ dep.version }}</code></td>
            <td>
              <span :class="['badge', `badge-${dep.ecosystem}`]">
                {{ dep.ecosystem }}
              </span>
            </td>
            <td style="font-size: 0.875rem; color: #6b7280; word-break: break-word;">{{ dep.project }}</td>
            <td v-if="data.coverage_analysis">
              <span v-if="dep.covered" style="color: #10b981; font-weight: 600;">✓ Yes</span>
              <span v-else style="color: #ef4444; font-weight: 600;">✗ No</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <div v-if="filteredDependencies.length === 0" style="text-align: center; padding: 2rem; color: #6b7280;">
      No dependencies found
    </div>
    
    <div style="margin-top: 1rem; font-size: 0.875rem; color: #6b7280;">
      Showing {{ filteredDependencies.length }} of {{ allDependencies.length }} dependencies
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'Dependencies',
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const searchQuery = ref('')
    const ecosystemFilter = ref('')
    const coverageFilter = ref('')

    const allDependencies = computed(() => {
      const deps = []
      let id = 0
      
      props.data.projects.forEach(project => {
        project.manifests.forEach(manifest => {
          manifest.dependencies.forEach(dep => {
            deps.push({
              id: id++,
              name: dep.name,
              version: dep.version || 'N/A',
              ecosystem: manifest.ecosystem,
              project: project.repository.name,
              covered: isCovered(dep.name, manifest.ecosystem),
              adopted: isAdopted(project.repository.name, dep.name)
            })
          })
        })
      })
      
      return deps
    })

    const ecosystems = computed(() => {
      const ecos = new Set()
      allDependencies.value.forEach(dep => ecos.add(dep.ecosystem))
      return Array.from(ecos).sort()
    })

    const isAdopted = (projectName, depName) => {
      if (!props.data.coverage_analysis?.adoption_indicators) return false
      
      const indicators = props.data.coverage_analysis.adoption_indicators[projectName]
      return indicators && indicators.length > 0
    }

    const isCovered = (depName, ecosystem) => {
      if (!props.data.coverage_analysis) return false
      
      const coverage = props.data.coverage_analysis[ecosystem]
      if (!coverage) return false
      
      // If missing array doesn't exist, we can't determine coverage
      if (!Array.isArray(coverage.missing)) return false
      
      // Check if the dependency is NOT in the missing list
      // If it's not in the missing list, it means it's available/covered
      const isInMissingList = coverage.missing.some(pkg => {
        // Handle different formats:
        // Python/JS: "package==version"
        // Java: "groupId:artifactId==version" or just the package name
        let pkgName = pkg
        
        // Split on == to get just the package identifier
        if (pkg.includes('==')) {
          pkgName = pkg.split('==')[0]
        }
        
        // Compare package names (case-insensitive)
        return pkgName.toLowerCase() === depName.toLowerCase()
      })
      
      // Return true if NOT in missing list (meaning it's available)
      return !isInMissingList
    }

    const filteredDependencies = computed(() => {
      let result = allDependencies.value
      
      if (ecosystemFilter.value) {
        result = result.filter(dep => dep.ecosystem === ecosystemFilter.value)
      }
      
      if (coverageFilter.value) {
        if (coverageFilter.value === 'available') {
          result = result.filter(dep => dep.covered)
        } else if (coverageFilter.value === 'missing') {
          result = result.filter(dep => !dep.covered)
        }
      }
      
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        result = result.filter(dep => 
          dep.name.toLowerCase().includes(query) ||
          dep.project.toLowerCase().includes(query)
        )
      }
      
      return result
    })

    const availableCount = computed(() => {
      return filteredDependencies.value.filter(dep => dep.covered).length
    })

    const missingCount = computed(() => {
      return filteredDependencies.value.filter(dep => !dep.covered).length
    })

    return {
      searchQuery,
      ecosystemFilter,
      coverageFilter,
      ecosystems,
      allDependencies,
      filteredDependencies,
      availableCount,
      missingCount
    }
  }
}
</script>
