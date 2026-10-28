# Shared n8n Studio: stock project Pan integration (issue #9)

This branch introduces only an **isolated sandbox** image and smoke tests. It does not alter production deployment Dockerfiles, credentials, DBs, active workflows, TradingView, any Python investment engine, or order paths.

- Stock upstream: official `n8n@2.44.5`, SHA `e993c789c83dba66030f3b0259b42e452b64c3b9`.
- Shared patch: `lyonbegin/shared-n8n-studio`, **pinned** `999062f1676bdffafa852a36e6c986ef5ce7589f`.
- Source integration: `n8n/Dockerfile.shared-pan-sandbox` clones upstream, verifies upstream SHA, clones shared patch, verifies shared SHA, patches upstream `Canvas.vue` *before* `pnpm install`, then builds.
- Isolated preview: `n8n/docker-compose.shared-pan-sandbox.yml` starts a fresh ephemeral n8n instance and GET-only Caddy gateway on `127.0.0.1:39087`; no host production services.
- Chrome regression: `n8n/tests/official-pan-chrome.mjs`; expects **actual upstream n8n Vue DOM**, not the standalone playground.
- CI: `.github/workflows/shared-n8n-official-pan.yml`. Retain screenshots, JSON before/after, Docker logs; CI must fail when actual official Pan does not work.

## Reproduce

```bash
docker compose -f n8n/docker-compose.shared-pan-sandbox.yml build
docker compose -f n8n/docker-compose.shared-pan-sandbox.yml up -d
# install Playwright dependencies from investment_studio/
(cd investment_studio && npm install --no-audit --no-fund)
node investment_studio/../n8n/tests/official-pan-chrome.mjs
docker compose -f n8n/docker-compose.shared-pan-sandbox.yml down --remove-orphans
```

## Hard gates

1. Source-patch validation and actual official compiled n8n build.
2. Real Chrome on **sandbox**: F01 demo nodes loaded, blank left/middle Pan, Shift selection, wheel zoom and Fit. Nodes/edge rendering must persist; before/after viewport CSS transform and screenshots saved.
3. Editing and server persistence: on an independently initialized non-preview sandbox with owner account (never production DB), validate add/delete/move/connect/edit/Undo and reload persistence; track separate test evidence. A preview-only green result does **not** pass this gate.
4. Safe execution: only synthetic nodes, log/result trace, no broker or LIVE trading. The real engine end-to-end gate is separate.

**Do not call issue #9 complete until ALL hard gates have actual proof.**
