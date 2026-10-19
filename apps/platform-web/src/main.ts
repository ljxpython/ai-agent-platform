import "@/utils/polyfill";
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import i18n from "./i18n";
import { useThemeStore } from "@/stores/theme";
import { errorRingBuffer } from "@/services/observability/error-buffer";
import "@/styles/index.css";

if (typeof window !== "undefined") {
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    errorRingBuffer.push({
      type: "js_runtime",
      message:
        reason instanceof Error
          ? reason.message
          : `Unhandled Rejection: ${String(reason)}`,
      stack: reason instanceof Error ? reason.stack : undefined,
      detail: reason,
    });
  });
}

async function bootstrap() {
  const app = createApp(App);

  app.config.errorHandler = (err, _instance, info) => {
    console.error("[Vue Global Error]", err, info);
    errorRingBuffer.push({
      type: "js_runtime",
      message: err instanceof Error ? err.message : String(err),
      stack: err instanceof Error ? err.stack : undefined,
      detail: { componentInfo: info },
    });
  };

  const pinia = createPinia();

  app.use(pinia);
  if (typeof window !== "undefined") {
    (window as any).__pinia = pinia;
  }

  const themeStore = useThemeStore(pinia);
  themeStore.init();

  app.use(router);
  app.use(i18n);

  await router.isReady();
  app.mount("#app");
}

void bootstrap();
