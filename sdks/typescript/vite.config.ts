/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";

export default defineConfig({
  build: {
    lib: {
      entry: "src/index.ts",
      name: "XAgentSDK",
      formats: ["es", "umd"],
      fileName: (format) => (format === "es" ? "xagent-sdk.js" : "xagent-sdk.umd.cjs"),
    },
    outDir: "dist",
    sourcemap: true,
    // SDK dist: keep identifiers readable (stack traces, constructor.name checks).
    minify: false,
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    globals: false,
  },
});
