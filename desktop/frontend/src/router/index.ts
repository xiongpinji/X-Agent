import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Agents from '../views/Agents.vue'
import Files from '../views/Files.vue'
import Runs from '../views/Runs.vue'
import Settings from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/agents',
    name: 'Agents',
    component: Agents
  },
  {
    path: '/files',
    name: 'Files',
    component: Files
  },
  {
    path: '/runs',
    name: 'Runs',
    component: Runs
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
