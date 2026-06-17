import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
// During `vite dev`, proxy API calls to the FastAPI backend on :8000.
// In production the same FastAPI process serves this built bundle, so the
// relative `/api` paths used by the frontend resolve to the same origin.
export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
        proxy: {
            "/api": "http://localhost:8000",
            "/payloads.json": "http://localhost:8000",
        },
    },
    build: {
        outDir: "dist",
    },
});
