import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Non-negotiable 1: no model SDK in the web app. Every model call goes through the worker's gateway.
const bannedModelSdks = {
  paths: [
    { name: "@anthropic-ai/sdk", message: "Model calls go through the worker gateway (run_agent) only." },
    {
      name: "@anthropic-ai/bedrock-sdk",
      message: "Model calls go through the worker gateway (run_agent) only.",
    },
    {
      name: "@aws-sdk/client-bedrock-runtime",
      message: "Model calls go through the worker gateway (run_agent) only.",
    },
    { name: "openai", message: "Model calls go through the worker gateway (run_agent) only." },
    { name: "ai", message: "Model calls go through the worker gateway (run_agent) only." },
  ],
  patterns: [
    {
      group: ["@ai-sdk/*", "@anthropic-ai/*", "@google/generative-ai*"],
      message: "No model SDKs outside the gateway.",
    },
  ],
};

const config = [
  ...nextVitals,
  ...nextTs,
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
      "src/server/db-types.ts",
    ],
  },
  {
    rules: {
      "no-restricted-imports": ["error", bannedModelSdks],
      "no-console": "error",
    },
  },
];

export default config;
