import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The dev API (services/api, ikip_api.app:app) has no CORS middleware and none is added
// here — instead the Vite dev server proxies same-origin requests through to it, so the
// browser never makes a cross-origin call and the backend needs no changes at all.
//
// Override the proxy target with VITE_API_PROXY_TARGET if the API runs somewhere other
// than http://localhost:8000 (see web/.env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
