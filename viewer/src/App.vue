<template>
  <div>
    <div class="header">
      <div class="container">
        <h1>🔍 Ecosystems Evaluate - Analysis Viewer</h1>
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
        <div class="tabs">
          <button 
            v-for="tab in tabs" 
            :key="tab"
            :class="['tab', { active: activeTab === tab }]"
            @click="activeTab = tab"
          >
            {{ tab }}
          </button>
        </div>

        <!-- Tab Content -->
        <Overview v-if="activeTab === 'Overview'" :data="analysisData" />
        <Stats v-if="activeTab === 'Stats'" :data="analysisData" />
        <Projects v-if="activeTab === 'Projects'" :data="analysisData" />
        <Dependencies v-if="activeTab === 'Dependencies'" :data="analysisData" />
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

export default {
  name: 'App',
  components: {
    Overview,
    Stats,
    Projects,
    Dependencies
  },
  setup() {
    const analysisData = ref(null)
    const activeTab = ref('Overview')
    const tabs = ['Overview', 'Stats', 'Projects', 'Dependencies']

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

    return {
      analysisData,
      activeTab,
      tabs,
      handleFileUpload
    }
  }
}
</script>
