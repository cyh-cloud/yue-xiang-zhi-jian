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
        // 媒体目录由 Flask 提供（backend/domains/static_files/routes.py 只放行
        // uploads 与 images 两个目录）。开发时若不代理，请求会落到 Vite 的
        // SPA fallback，返回 index.html，<img> 无法解码，表现为图片全部丢失。
        "/images": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/uploads": {
          target: proxyTarget,
          changeOrigin: true,
        },
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
