# Traffic App Frontend

The public interface is a Svelte 5 single-page app built with Vite. It renders the incident feed, statistics, comments, and MapLibre/PMTiles maps while the Flask backend provides `/api` and legacy `/maps` routes.

## Commands

```bash
npm install
npm run dev
npm run build
npm run preview
```

The dev server proxies `/api` and `/maps` to `http://127.0.0.1:5002` by default. Set `VITE_PROD_URL` to use another backend.

## Source layout

- `src/App.svelte`: application orchestration and page-level state
- `src/components/feed/`: incident feed cards, tables, comments, and loading states
- `src/components/map/`: full and compact map views
- `src/components/shared/`: components reused across multiple features
- `src/components/stats/`: incident statistics and activity charts
- `src/components/ui/`: page-level controls and feedback
- `src/stores/`: shared toast and map-selection state
- `src/utils/apiUrls.js`: API query construction
- `src/utils/cache.js`: bounded client-side cache helpers
- `src/utils/incidents.js`: API incident-to-view-model normalization
- `src/utils/i18n.js`: localized strings and date formatting
- `src/utils/mapRuntime.js`: lazy MapLibre and PMTiles loading

Production output is written to `dist/` and served by Flask.
