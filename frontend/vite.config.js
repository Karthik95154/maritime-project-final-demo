var _a, _b;
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
var frontendPort = Number((_a = process.env.FRONTEND_PORT) !== null && _a !== void 0 ? _a : 5173);
var backendTarget = (_b = process.env.BACKEND_TARGET) !== null && _b !== void 0 ? _b : "http://127.0.0.1:8000";
var tunnelHost = process.env.TUNNEL_HOST;
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
