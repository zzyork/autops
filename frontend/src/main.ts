import { createApp } from 'vue'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import './styles/ui.css'

createApp(App).use(router).mount('#app')
