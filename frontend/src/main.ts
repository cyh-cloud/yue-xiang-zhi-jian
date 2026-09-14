import { createPinia } from 'pinia'
import { createApp } from 'vue'

import { installSessionExpiredHandler } from './api/session-expiry'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/tokens.css'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)
installSessionExpiredHandler(useAuthStore(), router)

app.mount('#app')
