import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { createAppRouter } from "./router";
import { clearLegacyServiceWorker } from "./shared/legacyServiceWorker";
import { initializePreferences } from "./shared/preferences";
import "./styles/legacy-public.css";
import "./styles/global.css";
import "./styles/public-shell.css";

initializePreferences();

const app = createApp(App);
app.use(createPinia());
const router = createAppRouter();
app.use(router);
router.isReady().then(() => {
  app.mount("#app");
  void clearLegacyServiceWorker();
});
