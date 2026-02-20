# Home Assistant App: Wine Tracker

<p align="center">
  <img src="logo.png" alt="Wine Tracker Logo" width="128">
</p>

![version][version-badge]
![ai powered][ai-badge]

A sleek, modern wine cellar tracker running directly in your Home Assistant sidebar. Manage your entire collection — from label photo to tasting notes.

## Features

- **Wine cards** with photo, vintage, type, region, grape variety, rating & notes
- **AI wine label recognition** — snap a label photo and let AI fill in all fields (Anthropic, OpenAI, OpenRouter, Ollama)
- **Vivino wine search** — search by name, see ratings, region & price, and import directly
- **Reload missing data** — re-analyze wines with incomplete fields via AI or Vivino
- **Star rating** (1–5 stars), quick quantity buttons & duplicate wines
- **Unified navigation** — consistent header with filter dropdown across all pages
- **Search & filter** by wine type (Red, White, Rosé, Sparkling, ...)
- **Drink window** (from/until year) with AI estimation
- **Purchase price** with configurable currency
- **Autocomplete** for region, grape variety, purchase source & storage location
- **Interactive 3D globe** showing your wine regions on a WebGL globe
- **Statistics** — donut charts, country breakdown, price overview & bottle count
- **7 languages**: DE, EN, FR, IT, ES, PT, NL
- **REST API** at `/api/summary` for HA sensor integration
- **Fully responsive** — desktop, tablet & mobile

## Configuration

All options are set in the Home Assistant add-on configuration page:

| Option | Default | Description |
|--------|---------|-------------|
| `currency` | `CHF` | Currency symbol for prices (EUR, USD, GBP, ...) |
| `language` | `de` | UI language: `de`, `en`, `fr`, `it`, `es`, `pt`, `nl` |
| `ai_provider` | `none` | AI provider: `none`, `anthropic`, `openai`, `openrouter`, `ollama` |

When an AI provider is selected, additional fields for API key and model appear.

## Data Persistence

All data (SQLite database + photos) is stored under `/share/wine-tracker/` — preserved across add-on updates, restarts, and HA updates.

## Roadmap

- Export / Import function
- Custom sorting options
- Display modes — list view or portal

## Documentation

See the full documentation and changelog on [GitHub](https://github.com/xenofex7/ha-wine-tracker).

[version-badge]: https://img.shields.io/badge/version-v1.0.1-blue.svg
[ai-badge]: https://img.shields.io/badge/AI%20powered-label%20recognition-blueviolet.svg
