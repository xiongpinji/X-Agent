<template>
  <main class="shell">
    <header>
      <p class="eyebrow">X-Agent Desktop</p>
      <h1>Authenticated Agent Runner</h1>
      <p class="subtitle">Connect to your X-Agent service and run one auditable task at a time.</p>
    </header>

    <section v-if="!authenticated" class="card" aria-labelledby="sign-in-title">
      <h2 id="sign-in-title">Sign in</h2>
      <label>
        API URL
        <input v-model.trim="baseUrl" autocomplete="url" placeholder="https://api.example.com" />
      </label>
      <label>
        Email
        <input v-model.trim="email" type="email" autocomplete="username" />
      </label>
      <label>
        Password
        <input v-model="password" type="password" autocomplete="current-password" />
      </label>
      <button :disabled="busy" @click="signIn">{{ busy ? 'Connecting…' : 'Connect and sign in' }}</button>
    </section>

    <section v-else class="card" aria-labelledby="runner-title">
      <div class="row between">
        <h2 id="runner-title">Run Agent</h2>
        <button class="secondary" :disabled="busy" @click="signOut">Sign out</button>
      </div>
      <label>
        Agent ID
        <input v-model.trim="agentId" maxlength="128" />
      </label>
      <label>
        Task
        <textarea v-model.trim="task" maxlength="4096" rows="7" />
      </label>
      <button :disabled="busy || !task" @click="startRun">{{ busy ? 'Submitting…' : 'Start Agent' }}</button>

      <div v-if="runId" class="run" aria-live="polite">
        <dl>
          <div><dt>Run</dt><dd>{{ runId }}</dd></div>
          <div><dt>Status</dt><dd>{{ runStatus?.status ?? 'pending' }}</dd></div>
          <div><dt>Progress</dt><dd>{{ runStatus?.progress_percent ?? 0 }}%</dd></div>
        </dl>
        <p v-if="runStatus?.result_summary" class="result">{{ runStatus.result_summary }}</p>
        <div class="row">
          <button class="secondary" :disabled="busy" @click="refreshRun">Refresh status</button>
          <button v-if="!terminal" class="danger" :disabled="busy" @click="stopRun">Cancel run</button>
        </div>
      </div>
    </section>

    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  cancelRun,
  configureBackend,
  getRunStatus,
  login,
  logout,
  safeErrorMessage,
  triggerAgent,
  type RunStatusResponse,
} from './services/desktopApi'

const baseUrl = ref('http://localhost:8000')
const email = ref('')
const password = ref('')
const agentId = ref('default-agent')
const task = ref('')
const authenticated = ref(false)
const busy = ref(false)
const notice = ref('')
const errorMessage = ref('')
const runId = ref('')
const runStatus = ref<RunStatusResponse | null>(null)
const terminal = computed(() => ['completed', 'failed', 'cancelled'].includes(runStatus.value?.status ?? ''))

async function perform(action: () => Promise<void>) {
  busy.value = true
  notice.value = ''
  errorMessage.value = ''
  try {
    await action()
  } catch (error) {
    errorMessage.value = safeErrorMessage(error)
  } finally {
    busy.value = false
  }
}

function operationId() {
  return `desktop-${globalThis.crypto.randomUUID()}`
}

async function signIn() {
  await perform(async () => {
    await configureBackend(baseUrl.value)
    await login(email.value, password.value)
    password.value = ''
    authenticated.value = true
    notice.value = 'Authenticated.'
  })
}

async function signOut() {
  await perform(async () => {
    await logout()
    authenticated.value = false
    runId.value = ''
    runStatus.value = null
    notice.value = 'Signed out.'
  })
}

async function startRun() {
  await perform(async () => {
    const response = await triggerAgent({
      agentId: agentId.value,
      task: task.value,
      operationId: operationId(),
    })
    runId.value = response.run_id
    runStatus.value = {
      run_id: response.run_id,
      trace_id: response.trace_id,
      status: response.status,
      progress_percent: 0,
      current_step: 'Waiting to start',
      result_summary: '',
      error: null,
      error_code: null,
    }
    notice.value = 'Agent run submitted.'
  })
}

async function refreshRun() {
  if (!runId.value) return
  await perform(async () => {
    runStatus.value = await getRunStatus(runId.value)
  })
}

async function stopRun() {
  if (!runId.value) return
  await perform(async () => {
    await cancelRun(runId.value)
    runStatus.value = await getRunStatus(runId.value)
    notice.value = 'Run cancelled.'
  })
}
</script>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(body) { margin: 0; min-width: 320px; min-height: 100vh; background: #0b1220; color: #e7edf8; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
.shell { width: min(720px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }
header { margin-bottom: 28px; }
.eyebrow { color: #75a7ff; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: 6px 0; font-size: clamp(30px, 5vw, 48px); }
.subtitle { color: #a8b4c8; line-height: 1.6; }
.card { display: grid; gap: 18px; padding: 28px; border: 1px solid #26344d; border-radius: 18px; background: #121c2e; box-shadow: 0 24px 60px rgba(0,0,0,.25); }
h2 { margin: 0; }
label { display: grid; gap: 8px; color: #cbd6e8; font-weight: 600; }
input, textarea { width: 100%; border: 1px solid #344563; border-radius: 10px; background: #0b1424; color: #fff; padding: 12px 14px; font: inherit; }
textarea { resize: vertical; }
button { border: 0; border-radius: 10px; background: #3977ef; color: #fff; padding: 12px 18px; font-weight: 700; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .55; }
.secondary { background: #26344d; }
.danger { background: #b63b4a; }
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.between { justify-content: space-between; }
.run { display: grid; gap: 16px; border-top: 1px solid #26344d; padding-top: 18px; }
dl { display: grid; gap: 10px; margin: 0; }
dl div { display: grid; grid-template-columns: 90px 1fr; gap: 12px; }
dt { color: #8fa1ba; }
dd { margin: 0; overflow-wrap: anywhere; }
.result { white-space: pre-wrap; line-height: 1.6; }
.notice, .error { padding: 12px 16px; border-radius: 10px; }
.notice { background: #173e32; color: #a9ebd2; }
.error { background: #481f28; color: #ffc4cc; }
</style>
