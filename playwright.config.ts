// Einzige Playwright-Suite des Projekts ist der Doku-Test. Ein schlichtes
// `npx playwright test` nutzt deshalb dieselbe Konfiguration wie
// `-c playwright.docs.config.ts`; ohne diese Datei suchte Playwright mit
// seinem Standardmuster auch die `*.test.mjs`-Harnische, die pytest startet.
export { default } from './playwright.docs.config';
