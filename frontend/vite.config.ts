import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const repoRoot = fileURLToPath(new URL("..", import.meta.url));
  const env = loadEnv(mode, repoRoot, "");
  const backendPort =
    (process.env.PORT || env.PORT || "5000").trim() || "5000";
  const proxyTarget =
    (process.env.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || "").trim() ||
    `http://127.0.0.1:${backendPort}`;

  return {
    plugins: [
      vue({
        template: {
          compilerOptions: {
            isCustomElement: (tag) => tag === "model-viewer",
          },
        },
      }),
    ],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 4173,
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});
