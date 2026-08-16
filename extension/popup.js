(function exposePopup(root, factory) {
  const popup = factory()
  if (typeof module === 'object' && module.exports) module.exports = popup
  if (root.document && root.XAgentExtension) {
    root.document.addEventListener('DOMContentLoaded', () => {
      popup.bindPopup(root.document, new root.XAgentExtension.XAgentExtensionApi())
    })
  }
})(globalThis, function createPopup() {
  async function bindPopup(document, api) {
    const loginForm = document.getElementById('login-form')
    const runner = document.getElementById('runner')
    const runCard = document.getElementById('run-card')
    const notice = document.getElementById('notice')
    const error = document.getElementById('error')
    let runId = ''

    function showMessage(element, message) {
      element.textContent = message
      element.classList.toggle('hidden', !message)
    }

    function clearMessages() {
      showMessage(notice, '')
      showMessage(error, '')
    }

    function setAuthenticated(authenticated) {
      loginForm.classList.toggle('hidden', authenticated)
      runner.classList.toggle('hidden', !authenticated)
    }

    async function safely(action) {
      clearMessages()
      try {
        await action()
      } catch (caught) {
        showMessage(error, globalThis.XAgentExtension.safeErrorMessage(caught))
      }
    }

    async function refreshStatus() {
      if (!runId) return
      const status = await api.getRunStatus(runId)
      document.getElementById('run-status').textContent = status.status || 'unknown'
      document.getElementById('result').textContent = status.result_summary || ''
      document.getElementById('cancel').disabled = ['completed', 'failed', 'cancelled'].includes(status.status)
    }

    const [config, session] = await Promise.all([api.getConfig(), api.getSession()])
    document.getElementById('base-url').value = config.baseUrl || 'http://localhost:8000'
    setAuthenticated(session.authenticated)

    loginForm.addEventListener('submit', (event) => {
      event.preventDefault()
      safely(async () => {
        await api.configureBackend(document.getElementById('base-url').value)
        await api.login(
          document.getElementById('email').value,
          document.getElementById('password').value,
        )
        document.getElementById('password').value = ''
        setAuthenticated(true)
        showMessage(notice, '登录成功。')
      })
    })

    document.getElementById('run-form').addEventListener('submit', (event) => {
      event.preventDefault()
      safely(async () => {
        const response = await api.triggerAgent({
          agentId: document.getElementById('agent-id').value,
          task: document.getElementById('task').value,
          operationId: `extension-${globalThis.crypto.randomUUID()}`,
        })
        runId = response.run_id
        document.getElementById('run-id').textContent = runId
        document.getElementById('run-status').textContent = response.status
        document.getElementById('result').textContent = ''
        document.getElementById('cancel').disabled = false
        runCard.classList.remove('hidden')
        showMessage(notice, 'Agent 运行已提交。')
      })
    })

    document.getElementById('refresh').addEventListener('click', () => safely(refreshStatus))
    document.getElementById('cancel').addEventListener('click', () => {
      safely(async () => {
        await api.cancelRun(runId)
        await refreshStatus()
        showMessage(notice, '运行已取消。')
      })
    })
    document.getElementById('logout').addEventListener('click', () => {
      safely(async () => {
        await api.logout()
        runId = ''
        runCard.classList.add('hidden')
        setAuthenticated(false)
        showMessage(notice, '已退出。')
      })
    })
  }

  return { bindPopup }
})
