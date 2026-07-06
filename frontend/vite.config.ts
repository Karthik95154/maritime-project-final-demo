import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

declare const process: {
  env: Record<string, string | undefined>;
};

const frontendPort = Number(process.env.FRONTEND_PORT ?? 5173);
const backendTarget = process.env.BACKEND_TARGET ?? "http://127.0.0.1:8000";
const tunnelHost = process.env.TUNNEL_HOST;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: frontendPort,
    strictPort: true,
    allowedHosts: true,
    hmr: tunnelHost
      ? {
          protocol: "wss",
          host: tunnelHost,
          clientPort: 443,
        }
      : {
          protocol: "ws",
          host: "localhost",
          clientPort: frontendPort,
        },
    proxy: {
      "/api": backendTarget,
      "/outputs": backendTarget,
    },
  },
  preview: {
    host: "0.0.0.0",
    port: frontendPort,
    strictPort: true,
    allowedHosts: true,
  },
});
