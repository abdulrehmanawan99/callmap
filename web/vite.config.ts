import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  // CALLMAP_* values come from the shell (scripts/dev.sh exports them); they are not exposed to the bundle.
  const env = loadEnv(mode, ".", "CALLMAP_");
  return {
    plugins: [react()],
    server: { proxy: { "/api": `http://127.0.0.1:${env.CALLMAP_API_PORT || "8012"}` } },
  };
});
