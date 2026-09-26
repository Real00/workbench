import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'vue-sonner/style.css'
import './style.css'
import App from './App.vue'
import { router } from './app/router'

createApp(App).use(createPinia()).use(router).mount('#app')
