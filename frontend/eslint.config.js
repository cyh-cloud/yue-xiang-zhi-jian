import pluginVue from "eslint-plugin-vue";
import vueTsEslintConfig from "@vue/eslint-config-typescript";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "test-results/**", "playwright-report/**"],
  },
  ...pluginVue.configs["flat/recommended"],
  ...vueTsEslintConfig(),
  {
    files: ["**/*.{ts,vue}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "vue/multi-word-component-names": "off"
    },
  },
];
