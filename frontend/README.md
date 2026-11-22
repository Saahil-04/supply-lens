# SupplyLens frontend

Web client for SupplyLens: analyze a GitHub repository's npm dependencies, review known vulnerabilities by priority, explore the dependency graph, and export a CycloneDX SBOM.

Built with React 19, TypeScript and Vite.

## Getting started

```bash
npm install
npm run dev        # http://localhost:5173
```

| Script            | Purpose                                  |
| ----------------- | ---------------------------------------- |
| `npm run dev`     | Start the dev server                     |
| `npm run build`   | Typecheck and create a production build  |
| `npm run preview` | Serve the production build locally       |
| `npm run lint`    | Run ESLint                               |

## Configuration

| Variable            | Description                                                              |
| ------------------- | ------------------------------------------------------------------------ |
| `VITE_API_BASE_URL` | Base URL of the SupplyLens API. Defaults to `/api` (proxied by Vite in development). |

Copy `.env.example` to `.env` to override it.

## Project structure

```
src/
  api.ts            API types, HTTP client and ApiError
  App.tsx           Shell: sidebar, topbar, tab routing
  views/            One component per tab (Overview, Projects, Packages, …)
  components/
    layout/         Sidebar, Topbar, PageFooter
    ui/             Shared primitives (Panel, Badge, Alert, Drawer, DataPanel, …)
    overview/ graph/ packages/ projects/ recommendations/ vulnerabilities/
  hooks/            useApi, useResource, useAnalysisSession, useViewport, useTheme, …
  lib/              Formatting, vocabulary (priorities, severities), graph layout model
  styles/           tokens.css (light/dark design tokens) plus one stylesheet per area
```

## Conventions

- **One source of truth for colour.** All colours are CSS variables in `styles/tokens.css`; dark mode only overrides those variables.
- **Data fetching** goes through `useApi` (abortable GET) or `useResource` (paginated, searchable, filterable list). Views do not call `fetch` directly.
- **Routing** is hash-based (`#/vulnerabilities`) so refresh and back/forward work without server configuration.
- **Graph layout** is computed in `lib/graph.ts` (pure, no React); `useViewport` owns pan/zoom; `GraphCanvas` only draws.
