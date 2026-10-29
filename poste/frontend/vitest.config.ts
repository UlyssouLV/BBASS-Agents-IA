import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

// Tests du front (spec 1.6.3) : même résolution d'alias que le build, dans
// un DOM simulé ; le poste FastAPI n'est jamais lancé, chaque test simule
// fetch à la frontière HTTP.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  })
);
