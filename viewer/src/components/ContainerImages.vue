<template>
  <div class="card">
    <h2 style="margin-bottom: 1.5rem; font-size: 1.5rem; font-weight: 600;">Container Images</h2>
    
    <!-- Search and Filter -->
    <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem;">
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="Search by repository name..." 
        style="flex: 1; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem;"
      />
      <select 
        v-model="statusFilter" 
        style="padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem; background: white;"
      >
        <option value="">All Status</option>
        <option value="adopted">✓ Adopted Only</option>
        <option value="not-using">Not Using Only</option>
      </select>
    </div>
    
    <!-- Summary Stats -->
    <div style="display: flex; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem; background: #f9fafb; border-radius: 0.5rem;">
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Repositories with Dockerfiles</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #111827;">{{ dockerfileProjects.length }}</div>
      </div>
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Using Chainguard Images</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #10b981;">{{ chainguardCount }}</div>
      </div>
      <div style="flex: 1;">
        <div style="font-size: 0.875rem; color: #6b7280;">Total Images</div>
        <div style="font-size: 1.5rem; font-weight: 600; color: #3b82f6;">{{ totalImages }}</div>
      </div>
    </div>
    
    <div style="overflow-x: auto;">
      <table>
        <thead>
          <tr>
            <th>Repository</th>
            <th>Dockerfile</th>
            <th>Location</th>
            <th>Status</th>
            <th>Images</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="project in filteredProjects" :key="project.name">
            <tr v-for="(dockerfile, idx) in project.dockerfiles" :key="`${project.name}-${idx}`">
              <td v-if="idx === 0" :rowspan="project.dockerfiles.length"><strong>{{ project.name }}</strong></td>
              <td style="font-family: monospace; font-size: 0.875rem; color: #374151;">{{ getDockerfileName(dockerfile.path) }}</td>
              <td style="font-family: monospace; font-size: 0.875rem; color: #6b7280;">{{ getDockerfileDir(dockerfile.path) }}</td>
              <td>
                <span v-if="dockerfile.chainguard_images.length > 0" style="display: inline-block; padding: 0.25rem 0.75rem; background: #d1fae5; color: #065f46; border-radius: 9999px; font-size: 0.875rem; font-weight: 500;">
                  ✓ Adopted
                </span>
                <span v-else style="display: inline-block; padding: 0.25rem 0.75rem; background: #fee2e2; color: #991b1b; border-radius: 9999px; font-size: 0.875rem; font-weight: 500;">
                  Not Using
                </span>
              </td>
              <td>
                <div v-if="dockerfile.chainguard_images.length > 0" style="margin-bottom: 0.5rem;">
                  <div v-for="(image, imgIdx) in dockerfile.chainguard_images" :key="imgIdx" style="font-family: monospace; font-size: 0.875rem; color: #059669; margin-bottom: 0.25rem;">
                    ✓ {{ image }}
                  </div>
                </div>
                <div v-if="dockerfile.other_images.length > 0">
                  <div v-for="(image, imgIdx) in dockerfile.other_images" :key="imgIdx" style="font-family: monospace; font-size: 0.875rem; color: #6b7280; margin-bottom: 0.25rem;">
                    {{ image }}
                  </div>
                </div>
                <span v-if="dockerfile.chainguard_images.length === 0 && dockerfile.other_images.length === 0" style="color: #9ca3af;">—</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    
    <div v-if="dockerfileProjects.length === 0" style="text-align: center; padding: 2rem; color: #6b7280;">
      No Dockerfiles found in analyzed repositories
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'ContainerImages',
  props: {
    data: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const searchQuery = ref('')
    const statusFilter = ref('')

    const dockerfileProjects = computed(() => {
      if (!props.data.projects) return []
      
      return props.data.projects
        .filter(p => p.dockerfile_adoption?.dockerfiles_found > 0)
        .map(p => ({
          name: p.repository.name,
          dockerfiles: p.dockerfile_adoption.dockerfiles || [],
          chainguard_images: p.dockerfile_adoption.chainguard_images || [],
          other_images: p.dockerfile_adoption.other_images || []
        }))
    })

    const filteredProjects = computed(() => {
      let filtered = dockerfileProjects.value
      
      // Apply search filter
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        filtered = filtered.filter(p => p.name.toLowerCase().includes(query))
      }
      
      // Apply status filter
      if (statusFilter.value === 'adopted') {
        filtered = filtered.filter(p => p.chainguard_images.length > 0)
      } else if (statusFilter.value === 'not-using') {
        filtered = filtered.filter(p => p.chainguard_images.length === 0)
      }
      
      return filtered
    })

    const chainguardCount = computed(() => {
      return dockerfileProjects.value.filter(p => p.chainguard_images.length > 0).length
    })

    const totalImages = computed(() => {
      return dockerfileProjects.value.reduce((sum, p) => 
        sum + p.chainguard_images.length + p.other_images.length, 0
      )
    })

    const getDockerfileName = (path) => {
      return path.split('/').pop()
    }

    const getDockerfileDir = (path) => {
      const parts = path.split('/')
      if (parts.length > 1) {
        return parts.slice(0, -1).join('/')
      }
      return '/' // Root directory
    }

    return {
      searchQuery,
      statusFilter,
      dockerfileProjects,
      filteredProjects,
      chainguardCount,
      totalImages,
      getDockerfileName,
      getDockerfileDir
    }
  }
}
</script>
