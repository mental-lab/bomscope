<template>
  <div class="card">
    <input 
      v-model="searchQuery" 
      type="text" 
      placeholder="Search projects..." 
      class="search-box"
    >
    
    <table>
      <thead>
        <tr>
          <th>Project Name</th>
          <th>Ecosystems</th>
          <th>Dependencies</th>
          <th>Manifests</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="project in filteredProjects" :key="project.repository.name">
          <td>
            <strong>{{ project.repository.name }}</strong>
            <div style="font-size: 0.875rem; color: #6b7280; margin-top: 0.25rem;">
              {{ project.repository.url }}
            </div>
          </td>
          <td>
            <span 
              v-for="ecosystem in getEcosystems(project)" 
              :key="ecosystem"
              :class="['badge', `badge-${ecosystem}`]"
              style="margin-right: 0.5rem;"
            >
              {{ ecosystem }}
            </span>
          </td>
          <td>{{ project.total_dependencies }}</td>
          <td>{{ project.manifests.length }}</td>
        </tr>
      </tbody>
    </table>
    
    <div v-if="filteredProjects.length === 0" style="text-align: center; padding: 2rem; color: #6b7280;">
      No projects found matching "{{ searchQuery }}"
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'Projects',
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const searchQuery = ref('')

    const getEcosystems = (project) => {
      const ecosystems = new Set()
      project.manifests.forEach(manifest => {
        ecosystems.add(manifest.ecosystem)
      })
      return Array.from(ecosystems)
    }

    const filteredProjects = computed(() => {
      if (!searchQuery.value) return props.data.projects
      
      const query = searchQuery.value.toLowerCase()
      return props.data.projects.filter(project => 
        project.repository.name.toLowerCase().includes(query) ||
        project.repository.url.toLowerCase().includes(query)
      )
    })

    return {
      searchQuery,
      getEcosystems,
      filteredProjects
    }
  }
}
</script>
