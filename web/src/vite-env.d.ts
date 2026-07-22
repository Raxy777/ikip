/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Direct API base URL, bypassing the dev proxy (used in production builds). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
