<template>
  <div>
    <h1 class="page-title">Settings</h1>
    <p class="page-sub">Dashboard configuration — saved server-side, applies to all viewers</p>

    <div class="panel">
      <div class="panel-title">Platform Connection</div>

      <div class="form-field">
        <label for="platform">Platform</label>
        <select id="platform" v-model="platformForm.platform" class="input">
          <option value="github">GitHub</option>
          <option value="gitlab">GitLab</option>
          <option value="ado">Azure DevOps</option>
        </select>
      </div>

      <div class="form-field">
        <label for="source">Instance URL</label>
        <input id="source" v-model="platformForm.source" class="input" placeholder="https://github.com" />
      </div>

      <div class="form-field">
        <label for="organization">Organization</label>
        <input id="organization" v-model="platformForm.organization" class="input" placeholder="your-org" />
      </div>

      <div class="form-field">
        <label for="repo-scope">Repository scope</label>
        <input id="repo-scope" v-model="platformForm.repo_scope" class="input" placeholder="leave empty for the whole org, or e.g. myorg/api, myorg/web" />
        <p class="field-help">Comma-separated <code>owner/repo</code> entries. Empty scans the entire organization — useful for piloting on a few repos first.</p>
      </div>

      <div class="form-field">
        <label for="token">Access token</label>
        <input id="token" v-model="platformForm.token" type="password" class="input" :placeholder="platform.token_set ? '(token saved — enter to replace)' : 'paste a personal access token'" />
        <p class="field-help">Stored server-side only; never sent back to the browser. Needs read access to repos and packages.</p>
      </div>

      <div class="form-actions">
        <button class="btn" @click="savePlatform" :disabled="saving || scanStatus === 'running'">Save connection</button>
        <span v-if="platformSaved" class="save-confirm">saved</span>
        <span v-if="platformError" class="save-error">{{ platformError }}</span>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">Adoption Source</div>

      <div class="form-field">
        <label for="adoption-label">Display label</label>
        <input id="adoption-label" v-model="form.label" class="input" placeholder="e.g. Trusted" />
        <p class="field-help">Shown in the dashboard stat cards and trend chart (e.g. "Trusted adoption").</p>
      </div>

      <div class="form-field">
        <label for="adoption-patterns">Match patterns</label>
        <input id="adoption-patterns" v-model="form.patterns" class="input" placeholder="e.g. registry.example.com/secure, myregistry.io" />
        <p class="field-help">
          Comma-separated regex strings describing your trusted image sources.
          Saving triggers a background rescan that re-classifies all repos
          against the new patterns — the dashboard updates when it completes.
        </p>
      </div>

      <div class="form-actions">
        <button class="btn" @click="save" :disabled="saving || scanStatus === 'running'">Save settings</button>
        <span v-if="saved && scanStatus !== 'running'" class="save-confirm">saved</span>
        <span v-if="saveError" class="save-error">{{ saveError }}</span>
        <button class="btn secondary" @click="runScan" :disabled="scanStatus === 'running'">Run scan now</button>
      </div>

      <div v-if="scanStatus === 'running'" class="scan-banner running">
        Scanning… the dashboard will update when it completes.
      </div>
      <div v-else-if="scanStatus === 'completed'" class="scan-banner done">
        Scan complete — dashboard is up to date.
      </div>
      <div v-else-if="scanStatus === 'failed'" class="scan-banner failed">
        Scan failed: {{ scanError }}
      </div>

      <div v-if="scanLog.length" class="console">
        <div class="console-line" v-for="(line, i) in scanLog" :key="i">{{ line }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">Access Tokens</div>
          <p class="field-help" style="margin: 4px 0 0;">Named API tokens for people or automations. Shown
          <b>once at creation</b>, stored hashed.</p>
        </div>
        <button class="btn" @click="showCreate = !showCreate">
          {{ showCreate ? 'Cancel' : '+ Create access token' }}
        </button>
      </div>

      <div v-if="createdToken" class="created-token">
        <p><b>Token created</b> — copy it now, it's never shown again:</p>
        <div class="created-token-value mono">{{ createdToken.token }}</div>
        <button class="btn secondary" @click="copyToken">Copy</button>
        <span v-if="copied" class="save-confirm">copied</span>
      </div>

      <div v-if="showCreate" class="token-create-form">
        <div class="form-field">
          <label for="tok-name">Token name</label>
          <input id="tok-name" v-model="newToken.name" class="input" placeholder="e.g. Alice's laptop" />
        </div>
        <div class="form-field">
          <label>Scope</label>
          <label class="scope-option"><input type="radio" v-model="newToken.scope" value="viewer" /> <b>viewer</b> — read-only dashboard & API</label>
          <label class="scope-option"><input type="radio" v-model="newToken.scope" value="admin" /> <b>admin</b> — settings, token management, trigger scans</label>
        </div>
        <div class="form-field">
          <label for="tok-exp">Expires in (days)</label>
          <input id="tok-exp" v-model.number="newToken.expires_in_days" type="number" min="0" class="input" style="max-width: 140px;" />
          <p class="field-help">0 = never expires. Default is 30.</p>
        </div>
        <div class="form-actions">
          <button class="btn" @click="createToken" :disabled="!newToken.name">Create token</button>
          <span v-if="tokenError" class="save-error">{{ tokenError }}</span>
        </div>
      </div>

      <template v-if="activeTokens.length">
        <div class="token-section-label">Active tokens</div>
        <table class="table">
          <thead><tr><th>Name</th><th>Token</th><th>Scope</th><th>Last used</th><th>Expires</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in activeTokens" :key="t.id">
              <td><b>{{ t.name }}</b></td>
              <td class="mono">{{ t.token_prefix }}…</td>
              <td><span class="badge accent">{{ t.scope }}</span></td>
              <td class="mono">{{ t.last_used_at ? timeAgo(t.last_used_at) : 'Never' }}</td>
              <td><span :class="['badge', expiryBadge(t).cls]">{{ expiryBadge(t).text }}</span></td>
              <td><button class="btn secondary" @click="revokeToken(t.id)">Revoke</button></td>
            </tr>
          </tbody>
        </table>
      </template>

      <template v-if="inactiveTokens.length">
        <div class="token-section-label">Revoked / expired</div>
        <table class="table">
          <thead><tr><th>Name</th><th>Token</th><th>Scope</th><th>Status</th><th></th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in inactiveTokens" :key="t.id" class="token-revoked">
              <td>{{ t.name }}</td>
              <td class="mono">{{ t.token_prefix }}…</td>
              <td><span class="badge">{{ t.scope }}</span></td>
              <td><span class="badge red">{{ t.revoked ? 'Revoked' : 'Expired' }}</span></td>
              <td></td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>
  </div>
</template>

<style scoped>
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.token-create-form { border: 1px solid var(--border); border-radius: 6px; padding: 16px; margin-bottom: 16px; background: var(--surface-elev, rgba(255,255,255,.03)); }
.scope-option { display: block; font-weight: 400; font-size: 13px; margin: 6px 0; color: var(--fg); }
.scope-option b { font-family: inherit; }
.token-section-label { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 14px 0 8px; }
.token-revoked { opacity: .5; }
.created-token { margin-bottom: 14px; padding: 14px; border: 1px solid var(--accent); border-radius: 6px; }
.created-token-value { font-size: 13px; background: rgba(255,255,255,.06); padding: 10px; border-radius: 4px; margin: 10px 0; word-break: break-all; }
.form-field { margin-bottom: 20px; }
.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.field-help {
  color: var(--text-faint);
  font-size: 12px;
  margin-top: 8px;
  line-height: 1.5;
}
</style>

<script>
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../api'

export default {
  name: 'SettingsPage',
  setup() {
    const adoption = inject('adoption')
    const form = ref({ ...adoption.value })
    const platform = ref({ platform: 'github', source: 'https://github.com', organization: '', repo_scope: '', token_set: false })
    const platformForm = ref({ platform: 'github', source: 'https://github.com', organization: '', token: '' })
    const saved = ref(false)
    const platformSaved = ref(false)
    const saving = ref(false)
    const saveError = ref(null)
    const platformError = ref(null)
    const scanStatus = ref(null)
    const scanError = ref(null)
    const scanLog = ref([])
    const tokens = ref([])
    const newToken = ref({ name: '', scope: 'viewer', expires_in_days: 30 })
    const createdToken = ref(null)
    const tokenError = ref(null)
    const copied = ref(false)
    const showCreate = ref(false)
    let poller = null

    const fmtDate = (iso) => iso ? new Date(iso + 'Z').toLocaleDateString() : '—'

    const timeAgo = (iso) => {
      const s = Math.max(0, (Date.now() - new Date(iso + 'Z')) / 1000)
      if (s < 60) return 'just now'
      if (s < 3600) return Math.floor(s / 60) + 'm ago'
      if (s < 86400) return Math.floor(s / 3600) + 'h ago'
      return Math.floor(s / 86400) + 'd ago'
    }

    const tokenAlive = (t) => !t.revoked && (!t.expires_at || new Date(t.expires_at + 'Z') > new Date())
    const activeTokens = computed(() => tokens.value.filter(tokenAlive))
    const inactiveTokens = computed(() => tokens.value.filter(t => !tokenAlive(t)))

    const expiryBadge = (t) => {
      if (!t.expires_at) return { text: 'Never', cls: 'green' }
      const days = (new Date(t.expires_at + 'Z') - Date.now()) / 86400000
      if (days < 1) return { text: 'Today', cls: 'red' }
      if (days < 7) return { text: `in ${Math.ceil(days)}d`, cls: 'yellow' }
      return { text: `in ${Math.ceil(days)}d`, cls: 'green' }
    }

    const loadTokens = async () => {
      try {
        const res = await apiFetch('/api/auth/tokens')
        if (res.ok) tokens.value = await res.json()
      } catch { /* non-fatal */ }
    }

    const createToken = async () => {
      tokenError.value = null
      try {
        const res = await apiFetch('/api/auth/tokens', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newToken.value.name,
            scope: newToken.value.scope,
            expires_in_days: newToken.value.expires_in_days || null,
          }),
        })
        if (!res.ok) throw new Error((await res.json()).detail || 'failed')
        createdToken.value = await res.json()
        copied.value = false
        await loadTokens()
        newToken.value.name = ''
      } catch (e) {
        tokenError.value = e.message
      }
    }

    const revokeToken = async (id) => {
      try {
        await apiFetch('/api/auth/tokens/' + id, { method: 'DELETE' })
        await loadTokens()
      } catch { /* non-fatal */ }
    }

    const copyToken = async () => {
      await navigator.clipboard.writeText(createdToken.value.token)
      copied.value = true
    }

    const applyStatus = (st) => {
      scanStatus.value = st.status
      scanError.value = st.error
      scanLog.value = st.log || []
      if (st.status !== 'running' && poller) {
        clearInterval(poller)
        poller = null
      }
    }

    const startPolling = () => {
      if (poller) return
      poller = setInterval(async () => {
        try {
          const res = await apiFetch('/api/scans/status')
          applyStatus(await res.json())
        } catch { /* keep polling */ }
      }, 3000)
    }

    onMounted(async () => {
      try {
        const res = await apiFetch('/api/config')
        const cfg = await res.json()
        if (cfg.platform) {
          platform.value = cfg.platform
          platformForm.value = { ...cfg.platform, token: '' }
        }
        // If a scan is already running (e.g. scheduled), reflect it
        const st = await (await apiFetch('/api/scans/status')).json()
        if (st.status === 'running') { applyStatus(st); startPolling() }
        else if (st.status !== 'idle') applyStatus(st)
      } catch { /* ignore */ }
      loadTokens()
    })

    onUnmounted(() => { if (poller) clearInterval(poller) })

    const savePlatform = async () => {
      saving.value = true
      platformError.value = null
      try {
        const res = await apiFetch('/api/config/platform', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(platformForm.value)
        })
        if (!res.ok) throw new Error('save failed')
        platform.value = { ...platformForm.value, token_set: platform.value.token_set || !!platformForm.value.token }
        platformForm.value.token = ''
        platformSaved.value = true
        setTimeout(() => { platformSaved.value = false }, 1500)
      } catch (e) {
        platformError.value = e.message
      } finally {
        saving.value = false
      }
    }

    const save = async () => {
      saving.value = true
      saveError.value = null
      try {
        const res = await apiFetch('/api/config/adoption', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label: form.value.label, patterns: form.value.patterns })
        })
        if (!res.ok) throw new Error('save failed')
        const data = await res.json()
        adoption.value = { label: data.label, patterns: data.patterns }
        saved.value = true
        setTimeout(() => { saved.value = false }, 1500)
        if (data.scan_started) {
          scanStatus.value = 'running'
          scanError.value = null
          startPolling()
        }
      } catch (e) {
        saveError.value = e.message
      } finally {
        saving.value = false
      }
    }

    const runScan = async () => {
      try {
        const res = await apiFetch('/api/scans/run', { method: 'POST' })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || 'scan failed to start')
        }
        scanStatus.value = 'running'
        scanError.value = null
        startPolling()
      } catch (e) {
        scanStatus.value = 'failed'
        scanError.value = e.message
      }
    }

    return {
      adoption, form, saved, saving, saveError,
      platform, platformForm, platformSaved, platformError, savePlatform,
      scanStatus, scanError, scanLog, save, runScan,
      tokens, newToken, createdToken, tokenError, copied, fmtDate, showCreate,
      activeTokens, inactiveTokens, timeAgo, expiryBadge,
      loadTokens, createToken, revokeToken, copyToken,
    }
  }
}
</script>

<style scoped>
.form-field { margin-bottom: 20px; }
.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.field-help {
  color: var(--text-faint);
  font-size: 12px;
  margin-top: 8px;
  line-height: 1.5;
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.save-confirm {
  color: var(--green);
  font-family: var(--mono);
  font-size: 13px;
}
.save-error {
  color: var(--red);
  font-family: var(--mono);
  font-size: 13px;
}
.scan-banner {
  margin-top: 16px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-family: var(--mono);
}
.scan-banner.running {
  background: rgba(122, 162, 247, 0.12);
  color: var(--accent);
  border: 1px solid rgba(122, 162, 247, 0.3);
}
.scan-banner.done {
  background: rgba(158, 206, 106, 0.12);
  color: var(--green);
  border: 1px solid rgba(158, 206, 106, 0.3);
}
.scan-banner.failed {
  background: rgba(247, 118, 142, 0.12);
  color: var(--red);
  border: 1px solid rgba(247, 118, 142, 0.3);
}
.console {
  margin-top: 12px;
  background: #0a0e14;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
  max-height: 320px;
  overflow-y: auto;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-all;
}
.settings-readout {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-dim);
}
.settings-readout strong { color: var(--text); }
</style>
