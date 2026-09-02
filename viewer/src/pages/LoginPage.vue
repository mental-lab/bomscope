<template>
  <div class="login-wrap">
    <div class="panel login-card">
      <h1 class="page-title" style="text-align:center">bomscope</h1>
      <p class="page-sub" style="text-align:center">Sign in with an access token</p>

      <input class="input" type="password" v-model="token" placeholder="access token"
             @keyup.enter="login" autofocus />
      <div v-if="error" class="error" style="margin: 8px 0;">{{ error }}</div>
      <button class="btn" style="width:100%; margin-top: 10px;" @click="login" :disabled="!token || busy">
        {{ busy ? 'checking…' : 'Sign in' }}
      </button>

      <p class="login-hint">
        First boot? bomscope generated an initial admin token — see
        <code>docker logs bomscope-web</code> or <code>/data/initial_admin_token</code>.
        Set <code>BOMSCOPE_ADMIN_TOKEN</code> in the environment to pin your own.
      </p>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setToken } from '../api'

export default {
  name: 'LoginPage',
  setup() {
    const router = useRouter()
    const token = ref('')
    const error = ref('')
    const busy = ref(false)

    const login = async () => {
      busy.value = true
      error.value = ''
      try {
        const res = await fetch('/api/auth/check', {
          headers: { Authorization: 'Bearer ' + token.value },
        })
        if (res.status === 401) {
          error.value = 'Token not recognized'
          return
        }
        const data = await res.json()
        setToken(token.value, data.role || 'viewer')
        router.push('/')
      } catch (e) {
        error.value = 'Could not reach the API'
      } finally {
        busy.value = false
      }
    }

    return { token, error, busy, login }
  }
}
</script>

<style scoped>
.login-wrap { display: flex; justify-content: center; padding-top: 12vh; }
.login-card { width: 380px; padding: 28px; }
.login-hint { font-size: 12px; color: var(--muted); margin-top: 18px; line-height: 1.5; }
.login-hint code { color: var(--fg); }
</style>
