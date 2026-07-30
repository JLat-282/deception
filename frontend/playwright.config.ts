import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(frontendDir, "..");
const python = path.join(projectRoot, ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "tablet-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: "mobile-320-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 320, height: 800 },
        hasTouch: true,
        isMobile: true,
      },
    },
  ],
  webServer: [
    {
      command: `"${python}" -m uvicorn backend.app.main:app --port 8002`,
      cwd: projectRoot,
      url: "http://127.0.0.1:8002/api/health",
      reuseExistingServer: false,
      env: {
        ...process.env,
        DECEPTION_DB_PATH: ".tmp/e2e.sqlite",
        DECEPTION_DAILY_SEED: "e2e-seed",
        DECEPTION_FIXED_ANSWER: "crane",
        DECEPTION_FIXED_NOW: "2026-07-28T12:00:00Z",
        DECEPTION_FIXED_LIE_ROWS: "1,2",
        DECEPTION_FIXED_SESSION_SEED: "seed-0",
      },
    },
    {
      command: "npm run dev --workspace @deception/frontend -- --port 5174",
      cwd: projectRoot,
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      env: {
        ...process.env,
        DECEPTION_API_PROXY_TARGET: "http://127.0.0.1:8002",
      },
    },
  ],
});
