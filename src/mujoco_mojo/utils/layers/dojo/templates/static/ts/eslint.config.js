// the dojo frontend's lint rules: eslint's and typescript-eslint's recommended
// sets, including the ones that read the type checker's types (floating
// promises, unsafe `any` use, ...). only `src/` is linted, which is what
// tsconfig.json covers, since the type-aware rules need each file to be in it.

import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig(
  { ignores: ["**/*.generated.ts"] },
  {
    files: ["src/**/*.ts"],
    extends: [js.configs.recommended, tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // a name starting with an underscore is unused on purpose, which is also
      // what tsc's noUnusedParameters accepts; so is the name of a property
      // taken out of an object to leave the rest
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", ignoreRestSiblings: true },
      ],
      // alpine's $watch and $nextTick ignore what their callbacks return, so
      // passing them an async function is how they are used. a promise that is
      // dropped on its own line is still reported (no-floating-promises)
      "@typescript-eslint/no-misused-promises": ["error", { checksVoidReturn: { arguments: false } }],
      // a catch that does nothing is how the best-effort storage and UI calls
      // here ignore a failure on purpose
      "no-empty": ["error", { allowEmptyCatch: true }],
    },
  },
  {
    // tests read into mocks and the loosely typed plotly objects the code
    // builds, which are `any` or `unknown` as far as the types go
    files: ["src/**/*.test.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/unbound-method": "off",
    },
  },
);
