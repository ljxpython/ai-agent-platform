import { createRouter, createWebHistory } from "vue-router";
import { registerRouterGuards } from "./guards";
import { routes } from "./routes";
import { errorRingBuffer } from "@/services/observability/error-buffer";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }

    if (to.hash) {
      return {
        el: to.hash,
        top: 96,
        behavior: "smooth",
      };
    }

    return { top: 0 };
  },
});

router.onError((error, to) => {
  const isChunkLoadFailed =
    /Failed to fetch dynamically imported module/i.test(error.message) ||
    /Loading chunk .* failed/i.test(error.message) ||
    /Importing a module script failed/i.test(error.message);

  errorRingBuffer.push({
    type: "route",
    url: to?.fullPath,
    message: error.message,
    stack: error.stack,
    detail: { isChunkLoadFailed },
  });

  if (isChunkLoadFailed && typeof window !== "undefined") {
    const reloadKey = "chunk_reload_" + (to?.path || "default");
    const hasReloaded = sessionStorage.getItem(reloadKey);
    if (!hasReloaded) {
      sessionStorage.setItem(reloadKey, "1");
      window.location.reload();
    }
  }
});

registerRouterGuards(router);

export default router;
