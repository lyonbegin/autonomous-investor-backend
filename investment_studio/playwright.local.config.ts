import {defineConfig} from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  use: {
    ...base.use,
    launchOptions: {executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium'},
  },
});
