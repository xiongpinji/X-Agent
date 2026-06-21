import AuthGuard from '@/components/AuthGuard'
import Login from '@/pages/Login'
import PandaAgentApp from '@/panda/PandaAgentApp'
import { installAuthenticatedFetch } from '@/services/authHeaders'

installAuthenticatedFetch()

export const App = () => {
  if (window.location.pathname === '/login') {
    return <Login />
  }

  return (
    <AuthGuard>
      <PandaAgentApp />
    </AuthGuard>
  )
}

export default App
