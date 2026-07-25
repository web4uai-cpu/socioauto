/// <reference types="vite/client" />

// Typed view of the env vars this app reads (see frontend/.env.example).
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
