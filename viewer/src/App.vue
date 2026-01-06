<template>
  <div style="min-height: 100vh; background: #fafafa;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem 0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
      <div class="container">
        <h1 style="margin: 0; font-size: 1.75rem; font-weight: 700;">Ecosystems Analysis</h1>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9; font-size: 0.95rem;">Dependency & Container Security Insights</p>
      </div>
    </div>

    <div class="container">
      <!-- Upload Zone -->
      <div v-if="!analysisData" class="upload-zone" @click="$refs.fileInput.click()">
        <input 
          ref="fileInput" 
          type="file" 
          accept=".json" 
          @change="handleFileUpload"
        >
        <div>
          <h2>📁 Upload Analysis File</h2>
          <p style="margin-top: 0.5rem; color: #6b7280;">
            Click to select or drag and drop your analysis.json file
          </p>
        </div>
      </div>

      <!-- Analysis View -->
      <div v-else>
        <!-- Tabs -->
        <div style="background: white; border-radius: 12px; padding: 0.5rem; margin: 2rem 0; box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1); display: inline-flex; gap: 0.5rem;">
          <button 
            v-for="tab in tabs" 
            :key="tab"
            @click="activeTab = tab"
            :style="`
              padding: 0.75rem 1.5rem;
              border: none;
              border-radius: 8px;
              background: ${activeTab === tab ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'transparent'};
              color: ${activeTab === tab ? 'white' : '#6b7280'};
              font-weight: ${activeTab === tab ? '600' : '500'};
              cursor: pointer;
              transition: all 0.2s;
              font-size: 0.95rem;
            `"
          >
            {{ tab }}
          </button>
        </div>

        <!-- Tab Content -->
        <Overview v-if="activeTab === 'Overview'" :data="analysisData" />
        <ContainerImages v-if="activeTab === 'Container Images'" :data="analysisData" />
        <Dependencies v-if="activeTab === 'Dependencies'" :data="analysisData" />
        <Projects v-if="activeTab === 'Projects'" :data="analysisData" />
        <Stats v-if="activeTab === 'Stats'" :data="analysisData" />
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import Overview from './components/Overview.vue'
import Stats from './components/Stats.vue'
import Projects from './components/Projects.vue'
import Dependencies from './components/Dependencies.vue'
import ContainerImages from './components/ContainerImages.vue'

export default {
  name: 'App',
  components: {
    Overview,
    Stats,
    Projects,
    Dependencies,
    ContainerImages
  },
  setup() {
    const analysisData = ref(null)
    const activeTab = ref('Overview')
    const tabs = ['Overview', 'Container Images', 'Dependencies', 'Projects', 'Stats']

    // Try to auto-load analysis.json from public directory
    const loadDefaultAnalysis = async () => {
      try {
        const response = await fetch('/ecosystems-evaluate/analysis.json')
        if (response.ok) {
          analysisData.value = await response.json()
        }
      } catch (error) {
        // No default analysis file, user will need to upload
        console.log('No default analysis file found, waiting for upload')
      }
    }

    const handleFileUpload = (event) => {
      const file = event.target.files[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          analysisData.value = JSON.parse(e.target.result)
        } catch (error) {
          alert('Error parsing JSON file: ' + error.message)
        }
      }
      reader.readAsText(file)
    }

    // Load default analysis on mount
    loadDefaultAnalysis()

    return {
      analysisData,
      activeTab,
      tabs,
      handleFileUpload
    }
  }
}
</script>
