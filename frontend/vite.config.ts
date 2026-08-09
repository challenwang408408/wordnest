import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

/** 生产默认挂在个人网站子路径；本地 dev 用根路径。可用 VITE_BASE_PATH 覆盖。 */
const DEFAULT_PROD_BASE = "/projects/wordnest/";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const base =
    env.VITE_BASE_PATH || (command === "build" ? DEFAULT_PROD_BASE : "/");

  return {
    base,
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      globals: true,
    },
  };
});
