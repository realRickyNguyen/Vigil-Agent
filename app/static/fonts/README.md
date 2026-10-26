# Fonts for the investigation page

Served by `app/server.py` at `GET /fonts/<file>`, so the page needs no network (sample mode runs offline).
Latin subsets in WOFF2, from Google Fonts on 26 Oct 2026. Each family is under the SIL Open Font License 1.1;
the licence texts are the `OFL-*.txt` files here.

| File | Family | Use on the page |
|---|---|---|
| `newsreader.woff2`, `newsreader-italic.woff2` | Newsreader (Production Type), variable weight and optical size | Headings, the drug name, the agents' prose |
| `publicsans.woff2` | Public Sans (U.S. Web Design System), variable weight | Interface text, tables and figures |
| `plexmono-400.woff2`, `plexmono-600.woff2` | IBM Plex Mono | Run IDs, query IDs, SQL and the progress log |
