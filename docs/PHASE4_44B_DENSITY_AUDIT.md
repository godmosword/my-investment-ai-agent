# Phase 4 44b High-Density Audit

**Date:** 2026-05-21  
**Scope:** `/news`, `/columns`, `/insights`, `/dashboard`, `/portfolio`  
**Rule:** Gate 0 keeps workbench critical paths at **N<=3** clicks and keeps reader first screens free of dense quote/matrix tables. This is a decision handoff only; no React or API behavior changes are implied by this document.

## Decision Key

Maintainer pick options:

- **A / Tab**: move or keep the block behind a route tab.
- **B / Dock**: move or keep the block in `GlobalWatchlistDock`, `WorkspacePanel`, or another persistent tool surface.
- **C / Keep**: keep current placement for now; optional wording or E2E tightening only.

Density labels:

- `reader-low`: narrative/list content suitable for reader first screens.
- `workbench-mid`: operational content that can remain in a workbench first screen if it answers the page's main question.
- `workbench-high`: tables, calculators, multi-metric panels, or alert/workspace controls that should usually sit behind a tab, dock, or deeper state.

## Current 44b Baseline

- `/dashboard` already splits **macro overview** from **market depth**: `compute-memory-panel` and `onchain-panel` live under `?tab=depth`.
- `/portfolio` already removed inline `portfolio-watchlist`; shared watchlist lives in `GlobalWatchlistDock`.
- `/portfolio` already hides `portfolio-risk-panel` under `?tab=risk`.
- `/insights` already uses tabs for daily, earnings, paper lifecycle, track record, scenario, and signals.

## Audit Table

| Route | Block | File / DOM Anchor | Density | First Viewport? | Current Treatment | Recommendation | N=3 Path Impact | Maintainer Pick |
|---|---|---|---|---|---|---|---|---|
| `/news` | Reader intro + CTAs | [`NewsHome.jsx`](../data-verification-ui/src/modules/news/pages/NewsHome.jsx) · `news-reader-layer-intro`, `portal-cta-news-to-insights` | `reader-low` | Yes | Introduces reader layer and sends work to `/insights` or `/columns`. | **C / Keep** as the low-density first task. | News -> Insights is 1 click; within N. | [ ] A [ ] B [ ] C |
| `/news` | Topic filter chips | [`NewsHome.jsx`](../data-verification-ui/src/modules/news/pages/NewsHome.jsx) · `news-filter-*` | `reader-low` | Yes | Simple filters before digest list. | **C / Keep**; this is reader navigation, not a dense table. | Filter is 0 route clicks; within N. | [ ] A [ ] B [ ] C |
| `/news` | Digest item list | [`NewsHome.jsx`](../data-verification-ui/src/modules/news/pages/NewsHome.jsx) · `news-digest-item` | `reader-low` | Yes | Card/list stream with source and summary. | **C / Keep**; do not convert to quote table. | Item open stays on page; symbol links can reach Insights in 1 click. | [ ] A [ ] B [ ] C |
| `/news` | Theme rail + deep panel | [`NewsHome.jsx`](../data-verification-ui/src/modules/news/pages/NewsHome.jsx) · `news-deep-panel` | `workbench-mid` | Desktop side rail can be visible | Detail panel appears after selection; theme rail sits beside list. | **C / Keep** unless maintainer wants side rail deferred on desktop. | Digest -> panel -> Insights remains <=2 route clicks. | [ ] A [ ] B [ ] C |
| `/columns` | Reader intro + CTA | [`ColumnsHome.jsx`](../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) · `columns-reader-layer-intro`, `portal-cta-columns-to-insights` | `reader-low` | Yes | Sets long-form reading mode and points to workbench. | **C / Keep**. | Columns -> Insights is 1 click. | [ ] A [ ] B [ ] C |
| `/columns` | Pillar tabs | [`ColumnsHome.jsx`](../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) · `columns-pillar-*` | `reader-low` | Yes | Three-pillar reader filter. | **C / Keep**; low interaction cost. | Tab switch is 0 route clicks. | [ ] A [ ] B [ ] C |
| `/columns` | Deep Brief cards | [`ColumnsHome.jsx`](../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) · `columns-deep-card`, `columns-card-ticker-to-insights` | `reader-low` | Yes | Card stream with ticker chips. | **C / Keep**; ticker chips already deep-link to workbench. | Card -> ticker -> Insights is <=1 route click. | [ ] A [ ] B [ ] C |
| `/columns` | Sector rotation rail | [`ColumnsHome.jsx`](../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) · `columns-sector-rotation`, `columns-rotation-row` | `workbench-mid` | Desktop side rail can be visible | More tabular than reader cards but scoped to columns context. | **A / Tab** if first-screen feels overloaded; otherwise **C / Keep**. | Moving behind a tab adds 1 in-page click, still within N. | [ ] A [ ] B [ ] C |
| `/columns` | Related themes + side panel | [`ColumnsHome.jsx`](../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) · `columns-theme-card`, `columns-deep-panel` | `workbench-mid` | Desktop side rail can be visible | Related themes plus selected article panel. | **C / Keep** for now; selection-driven panel is not default dense data. | Theme -> panel -> Insights remains <=2 route clicks. | [ ] A [ ] B [ ] C |
| `/insights` | Workbench intro + reverse CTAs | [`InsightsHome.jsx`](../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) · `insights-workbench-intro`, `portal-cta-insights-to-news`, `portal-cta-insights-to-columns` | `workbench-mid` | Yes | Explains workbench and reader return paths. | **C / Keep**; supports N<=3 path. | Insights -> News/Columns is 1 click. | [ ] A [ ] B [ ] C |
| `/insights` | Six-tab board switcher | [`InsightsHome.jsx`](../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) · `insights-tab-*` | `workbench-mid` | Yes | Daily, earnings, paper, track record, scenario, signals in one strip. | **A / Tab** already applied; next step is optional grouping if maintainers choose. | Any tab is 1 in-page click; within N. | [ ] A [ ] B [ ] C |
| `/insights` | Daily brief workspace | [`DailyBriefPage.jsx`](../data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx) via `insights-tab-daily` | `workbench-mid` | Yes by default | Main recommendations and symbol cards are the default workbench answer. | **C / Keep** as default landing. | Starting point is 0 clicks. | [ ] A [ ] B [ ] C |
| `/insights` | Paper lifecycle table/form | [`PaperLifecycleHome.jsx`](../data-verification-ui/src/modules/insights/pages/PaperLifecycleHome.jsx) via `insights-tab-paper` | `workbench-high` | No | Hidden behind `?tab=paper`. | **A / Tab** already correct. | Insights -> Paper is 1 in-page click. | [ ] A [ ] B [ ] C |
| `/insights` | Track Record | [`TrackRecordHome.jsx`](../data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) via `insights-tab-track-record` | `workbench-high` | No | Hidden behind `?tab=track-record`. | **A / Tab** already correct; queue 66 can add monitor/deep-dive links. | Insights -> Track Record -> symbol can remain <=2 clicks. | [ ] A [ ] B [ ] C |
| `/insights` | Quant signals + Intraday Monitor | [`QuantHome.jsx`](../data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) · `quant-intraday-monitor`, `quant-m7-signals` | `workbench-high` | No | Hidden behind `?tab=signals`; uses paper rows and existing quotes. | **A / Tab** already correct. | Insights -> Signals -> symbol deep dive is <=2 clicks. | [ ] A [ ] B [ ] C |
| `/dashboard` | Workbench intro + BTC strip | [`DashboardHome.jsx`](../data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) · `dashboard-workbench-intro`, [`TodayBtcSnapshotStrip.jsx`](../data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx) · `today-btc-snapshot-strip` | `workbench-mid` | Yes | Macro context and BTC alignment warning live above tabs. | **C / Keep**; warning visibility is useful and not a data wall. | Dashboard -> Insights/Portfolio is 1 click. | [ ] A [ ] B [ ] C |
| `/dashboard` | Macro indicator grid | [`DashboardHome.jsx`](../data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) · `macro-indicator-grid`, `macro-indicator-*` | `workbench-mid` | Yes | Overview tab default. | **C / Keep**; it answers the macro overview question. | 0 clicks from dashboard landing. | [ ] A [ ] B [ ] C |
| `/dashboard` | Catalyst calendar + regime panel | [`CatalystCalendar.jsx`](../data-verification-ui/src/components/CatalystCalendar.jsx) · `catalyst-calendar`; [`DashboardHome.jsx`](../data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) · `macro-regime-panel` | `workbench-mid` | Yes on desktop | Overview tab second row. | **C / Keep** unless first viewport tests show crowding. | 0 clicks; supports macro -> position reasoning. | [ ] A [ ] B [ ] C |
| `/dashboard` | Compute/memory panel | [`ComputeMemoryPanel.jsx`](../data-verification-ui/src/components/ComputeMemoryPanel.jsx) · `compute-memory-panel` | `workbench-high` | No | Hidden under `?tab=depth`. | **A / Tab** already correct. | Dashboard -> Depth is 1 in-page click. | [ ] A [ ] B [ ] C |
| `/dashboard` | On-chain panel | [`OnchainMetricsPanel.jsx`](../data-verification-ui/src/components/OnchainMetricsPanel.jsx) · `onchain-panel` | `workbench-high` | No | Hidden under `?tab=depth`. | **A / Tab** already correct. | Dashboard -> Depth is 1 in-page click. | [ ] A [ ] B [ ] C |
| `/portfolio` | Workbench intro + tabs | [`PortfolioHome.jsx`](../data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) · `portfolio-workbench-intro`, `portfolio-tab-*` | `workbench-mid` | Yes | Sets portfolio main question and moves monitor/risk to tabs. | **C / Keep**. | Portfolio -> Insights is 1 click. | [ ] A [ ] B [ ] C |
| `/portfolio` | KPI cards | [`PortfolioHome.jsx`](../data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) · `portfolio-total-value` | `workbench-mid` | Yes | Overview tab first row. | **C / Keep** as portfolio landing summary. | 0 clicks. | [ ] A [ ] B [ ] C |
| `/portfolio` | Action row + holdings table/cards | [`PortfolioHome.jsx`](../data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) · `portfolio-add-button`, `portfolio-import-button`, `portfolio-holdings-table`, `portfolio-holding-card-*` | `workbench-high` | Yes when holdings exist | Overview includes manual operations and holdings. | **C / Keep** if Portfolio is the operating surface; **A / Tab** if maintainer wants a calmer first viewport. | Keeping table at overview is 0 clicks; moving adds 1. | [ ] A [ ] B [ ] C |
| `/portfolio` | Watchlist Monitor | [`WatchlistMonitor.jsx`](../data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx) via `portfolio-tab-monitor` | `workbench-high` | No | Hidden under Monitor tab. | **A / Tab** already correct; shared watchlist remains docked globally. | Portfolio -> Monitor -> symbol is <=2 clicks. | [ ] A [ ] B [ ] C |
| `/portfolio` | Risk / TP-SL calculator | [`PortfolioRiskPanel.jsx`](../data-verification-ui/src/components/PortfolioRiskPanel.jsx) · `portfolio-risk-panel` | `workbench-high` | No | Hidden under `?tab=risk`. | **A / Tab** already correct. | Portfolio -> Risk -> submit intent is <=2 clicks. | [ ] A [ ] B [ ] C |
| Global | Shared watchlist + alerts dock | [`GlobalWatchlistDock.jsx`](../data-verification-ui/src/components/GlobalWatchlistDock.jsx) · `global-watchlist-toggle`, `global-watchlist-panel`; [`PriceAlertsPanel.jsx`](../data-verification-ui/src/components/PriceAlertsPanel.jsx) · `price-alerts-panel`; [`WorkspacePanel.jsx`](../data-verification-ui/src/components/WorkspacePanel.jsx) · `workspace-panel` | `workbench-high` | Toggle visible globally | Removed from Portfolio first screen; available as persistent tool surface. | **B / Dock** already correct. | Any route -> dock is 1 click; alert -> symbol path should stay <=3 in queue 67. | [ ] A [ ] B [ ] C |

## Recommended Maintainer Picks

Minimum picks before queue 62:

1. Keep current reader layer placement on `/news` and `/columns` unless a product review finds first-screen overload.
2. Confirm whether `/columns` `columns-sector-rotation` should stay as a side rail (**C**) or move behind a tab (**A**).
3. Confirm whether `/portfolio` overview should keep holdings/actions in first view (**C**) or split operations into another tab (**A**).
4. Keep `/dashboard` depth panels and `/portfolio` risk/watchlist under tabs; those 44b moves are already covered by `phase4-ia-portal.spec.js`.
5. Treat `GlobalWatchlistDock` + alert/workspace surfaces as the canonical **B / Dock** pattern for cross-route tools.

## Verification Anchors

Existing E2E coverage:

- [`phase4-ia-portal.spec.js`](../data-verification-ui/e2e/phase4-ia-portal.spec.js): reader intros, bidirectional CTAs, dashboard depth tab, portfolio dock/risk tab.
- [`dashboard-compute-memory.spec.js`](../data-verification-ui/e2e/dashboard-compute-memory.spec.js) and [`dashboard-onchain.spec.js`](../data-verification-ui/e2e/dashboard-onchain.spec.js): depth panels.
- [`portfolio-tpsl.spec.js`](../data-verification-ui/e2e/portfolio-tpsl.spec.js): risk panel.
- [`monitor-watchlist.spec.js`](../data-verification-ui/e2e/monitor-watchlist.spec.js): portfolio monitor tab.

Doc-only verification command:

```bash
test -f docs/BLOOMBERG_ALIGNMENT.md \
  && test -f docs/PHASE4_44B_DENSITY_AUDIT.md \
  && test -f data-verification-ui/e2e/phase4-ia-portal.spec.js \
  && rg -n "44b|PHASE4_44B_DENSITY_AUDIT|portfolio-risk-panel|compute-memory-panel|onchain-panel" \
    TODOS.md CHANGELOG.md docs data-verification-ui/e2e/phase4-ia-portal.spec.js
```
