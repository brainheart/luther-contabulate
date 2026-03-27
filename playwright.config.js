const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:8766',
    headless: true,
  },
  webServer: {
    command: 'python3 -m http.server 8766 -d docs',
    port: 8766,
    reuseExistingServer: true,
  },
});
