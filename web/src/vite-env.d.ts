/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TILE_URL?: string
  readonly VITE_TILE_ATTRIBUTION?: string
  /** "lat,lng" */
  readonly VITE_MAP_CENTER?: string
  readonly VITE_MAP_ZOOM?: string
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
