# steam-rec web frontend

Next.js 16 (App Router, Cache Components) + Tailwind 4. A thin UI over the offline demo `steam_rec.serving.demo.Demo`
(see `docs/web-demo.md`). It never touches the pipeline or the data directly; everything goes through the backend API.

```bash
npm install
npm run dev            # http://localhost:3000
npm run lint && npm run build
```

Without `NEXT_PUBLIC_API_URL` the site runs on **mock data** (`src/lib/mock.ts`, same shape as `Demo` output) and shows
a yellow "Mock data" badge. To use the real backend, create `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`NEXT_PUBLIC_*` is inlined at build time, so rebuild after changing it.

## Pages

| Route | What | Data |
|---|---|---|
| `/login` | Sign in with a numeric `user_id` (cookie `uid`, no password); sample users of the current run | `GET /api/health` (`known_sample`) |
| `/discover?model=als\|cb\|popularity` | Feature [1]: the user's precomputed top-K, model switch, `mode` badge, popularity fallback notice | `GET /api/recommend/{user_id}` |
| `/game/[app_id]` | Game detail + **Similar Titles** (feature [2]: game tags → cold-start, game itself excluded) | `GET /api/games/{app_id}`, `GET /api/games/{app_id}/similar` |
| `/browse?tags=a,b` / `/browse?q=` | Top categories, Genres + tag filter sidebar (cold-start by tags), title search | `GET /api/tags`, `GET /api/genres`, `GET /api/recommend/tags`, `GET /api/games?q=` |
| `/about` | Dataset, pipeline, models, benchmark table (static, `src/lib/report.ts`) | — |

`/discover` needs a session; the other pages are public.

## API contract expected from the backend

All responses are JSON. Item lists follow `RecResult` / `RecItem` in `src/lib/types.ts`.

| Endpoint | Returns | Backend implementation |
|---|---|---|
| `GET /api/users/{user_id}` | `{user_id, known}` | `user_id in demo.known` |
| `GET /api/recommend/{user_id}?model=` | `RecResult` | `demo.for_user(user_id, model)` |
| `GET /api/recommend/tags?tags=a&tags=b` | `RecResult` | `demo.for_new_user(tags)`; empty list → popularity fallback |
| `GET /api/games/{app_id}` | `GameDetail` or 404 | row of `demo.catalog` by `app_id`, **all** tags |
| `GET /api/games/{app_id}/similar` | `RecResult` | `for_new_user(game tags)` with k+1, drop the game itself, keep k |
| `GET /api/games?q=` | `GameDetail[]` | case-insensitive title match on `demo.catalog`, limit ~20 |
| `GET /api/tags` | `string[]` | `demo.tag_vocab` without `g_`/`c_` tokens (normalized: lowercase, `_`) |
| `GET /api/genres` | `string[]` | `g_*` tokens of `demo.tag_vocab` (game genres only); sent back as tags |
| `GET /api/health` | `{run_id, games, users, k, known_sample}` | `known_sample` = 4 users with a precomputed top-K |

Every `RecItem` should also carry `price_final` and `positive_ratio` from `demo.catalog` (Demo itself does not return
them); the UI hides them when missing. Enable CORS for the frontend origin. In FastAPI, declare
`/api/recommend/tags` before `/api/recommend/{user_id}` so `tags` is not parsed as a user id.

## Layout

```
src/app/         routes (page.tsx, loading.tsx, error.tsx, not-found.tsx), actions.ts = login/logout
src/components/  SiteHeader/Footer, NavTabs, DiscoverCard, BrowseRow, GameTile, GameImage, TagFilter, Rating, Skeleton
src/lib/         api.ts (fetch + mock switch), mock.ts, types.ts, session.ts, report.ts, format.ts
```

Game images come from Steam's public CDN (`header.jpg`, `capsule_616x353.jpg`) and fall back to the title when missing.
