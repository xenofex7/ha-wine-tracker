# Home Assistant App: Wine Tracker

<p align="center">
  <img src="https://raw.githubusercontent.com/xenofex7/ha-wine-tracker/main/logo.png" alt="Wine Tracker Logo" width="128">
</p>

![version][version-badge]
![ai powered][ai-badge]

A sleek, modern wine cellar tracker running directly in your Home Assistant sidebar. Manage your entire collection — from label photo to tasting notes — with an AI sommelier that can add, edit and delete wines straight from the chat.

## Screenshots

<p align="center">
  <img src="https://raw.githubusercontent.com/xenofex7/ha-wine-tracker/main/assets/260220_main_screen.png" alt="Wine Cellar Overview" width="800">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/xenofex7/ha-wine-tracker/main/assets/260220_statistics_screen.png" alt="Statistics with Globe & Charts" width="800">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/xenofex7/ha-wine-tracker/main/assets/260220_add_wine_screen.png" alt="Add Wine — AI, Vivino or Manual" width="800">
  <img src="https://raw.githubusercontent.com/xenofex7/ha-wine-tracker/main/assets/260220_wine_edit_screen.png" alt="Edit Wine Details" width="800">
</p>

## Features

- **Wine cards** with photo, vintage, type, region, grape variety, rating & notes
- **AI wine label recognition** — snap a label photo and let AI fill in all fields, including maturity phases, taste profile and food pairings (Anthropic, OpenAI, OpenRouter, Ollama, MiniMax)
- **AI sommelier chat with full cellar CRUD** — ask questions about your cellar, upload wine label photos, and add / edit / delete wines directly from the conversation; persistent sessions
- **Vivino wine search** — search by name, see ratings, region & price, and import directly; regional fallback chain surfaces country-specific wines (e.g. Australian labels)
- **Vivino ID management** — view, edit & test Vivino wine links directly in the edit modal
- **Reload missing data** — re-analyze wines with incomplete fields via AI or Vivino
- **Star rating** (1–5 stars), quick `+`/`−` quantity buttons & duplicate wines
- **Bottle format** — track bottle sizes from Piccolo (0.1875l) to Nebuchadnezzar (15l), auto-detected by AI
- **Cellar view modes** — Cards, List, Grid, and a sortable Table view with responsive columns
- **Activity timeline** — chronological log of wines added, consumed, restocked & removed
- **Maturity graph** — AI-generated bell curve showing Youth → Maturity → Peak → Decline with a "Today" marker
- **Taste profile & food pairings** — AI-generated body/tannin/acidity/sweetness bars and matching dishes in your language
- **Unified navigation** — consistent header with filter dropdown across all pages; hamburger menu on narrow viewports
- **Search & filter** by wine type, vintage year, grape variety, name, region or notes
- **Drink window** (from/until year) with AI estimation
- **Purchase price** with configurable currency
- **Autocomplete** for region, grape variety, purchase source & storage location
- **Interactive 3D globe** showing your wine regions on a WebGL globe
- **Statistics** — donut charts, stock history area chart, total bottles, total liters, value overview & average age
- **6 themes** with dark & light mode
- **7 languages**: DE, EN, FR, IT, ES, PT, NL
- **REST API** at `/api/summary` for HA sensor integration
- **Fully responsive** — desktop, tablet & mobile

## Configuration

All options are set in the Home Assistant add-on configuration page.

### General

| Option | Default | Description |
|--------|---------|-------------|
| `currency` | `CHF` | Currency symbol for prices (`CHF`, `EUR`, `USD`, `GBP`, `CAD`, `AUD`, `SEK`, `NOK`, `DKK`, `PLN`, `CZK`, `BRL`) |
| `language` | `de` | UI language: `de`, `en`, `fr`, `it`, `es`, `pt`, `nl` |

### AI Provider (optional)

Pick one AI provider and configure its API key and model. The AI is used for label recognition, maturity/taste/food enrichment, and the sommelier chat.

| Option | Default | Description |
|--------|---------|-------------|
| `ai_provider` | `none` | `none`, `anthropic`, `openai`, `openrouter`, `ollama`, `minimax` |
| `anthropic_api_key` | _(empty)_ | Claude API key from [console.anthropic.com](https://console.anthropic.com) |
| `anthropic_model` | `claude-opus-4-6` | Anthropic model identifier |
| `openai_api_key` | _(empty)_ | OpenAI API key from [platform.openai.com](https://platform.openai.com) |
| `openai_model` | `gpt-5.2` | OpenAI vision model |
| `openrouter_api_key` | _(empty)_ | OpenRouter API key from [openrouter.ai](https://openrouter.ai) |
| `openrouter_model` | `anthropic/claude-opus-4.6` | Any vision-capable OpenRouter model |
| `ollama_host` | `http://localhost:11434` | Local Ollama server URL |
| `ollama_model` | `llava` | Local Ollama vision model |
| `minimax_api_key` | _(empty)_ | MiniMax API key from [api.minimaxi.chat](https://api.minimaxi.chat) |
| `minimax_model` | `MiniMax-Text-01` | MiniMax model (vision-capable despite the "Text" name) |

> **Tip:** Ollama runs fully local and requires no API key. Pull a vision model (`ollama pull llava`) and point `ollama_host` at your Ollama server.

## Data Persistence

All data (SQLite database + photos) is stored under `/share/wine-tracker/` — preserved across add-on updates, restarts, and Home Assistant updates.

## Home Assistant Sensor (Optional)

```yaml
sensor:
  - platform: rest
    name: "Wine Stock"
    resource: "http://<ha-host>:5050/api/summary"
    value_template: "{{ value_json.total_bottles }}"
    unit_of_measurement: "bottles"
    json_attributes:
      - by_type
    scan_interval: 3600
```

## Roadmap

- **Export / Import** (CSV, JSON) — full collection backup and migration
- **Spending trends** — visualize spending by month, region, or wine type
- **Maturity calendar** — overview of which wines become drinkable each year
- **Drink window notifications** via Home Assistant automations
- **Native Lovelace dashboard card** to embed wine stats anywhere in HA
- **PWA support** with offline access
- **Barcode / QR scan** → Vivino lookup

## Documentation

See the full documentation and changelog on [GitHub](https://github.com/xenofex7/ha-wine-tracker).

[version-badge]: https://img.shields.io/badge/version-v1.9.1-blue.svg
[ai-badge]: https://img.shields.io/badge/AI%20powered-label%20recognition-blueviolet.svg
