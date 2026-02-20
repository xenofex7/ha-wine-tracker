# Changelog

## 1.0.0

### 🎉 Major UI Overhaul

- **Unified navigation header** — single consistent nav bar across all pages replaces the old header + toolbar layout
- **Filter dropdown** — wine-type filter moved into a dropdown popup with radio-button list (replaces inline tab chips)
- **"Leere ausblenden" toggle** integrated into the filter dropdown
- Removed stats-pill, back button, and separate toolbar row

### 🎨 Visual Refinements

- **Flat header** with clean `var(--surface)` background (no more gradient)
- **Fixed 55 px header height** for consistent appearance across pages
- Header buttons (filter + theme toggle) now share identical styling
- Wine-glass logo icon enlarged for better visibility
- Globe legend repositioned to **upper-left corner** with solid background, hidden on mobile
- Removed info-chips section from statistics page

### 🐛 Bug Fixes

- **Vivino links now point to the correct wine** — stores vintage ID instead of generic wine ID, URL changed from `/wines/` to `/w/`
- Type-corner ribbon no longer clipped at the bottom edge

### 🌍 Translations

- Added `nav_cellar` translation key to all 7 languages (DE, EN, FR, IT, ES, PT, NL)

## 0.4.5

- **AI reload works without image** — text-only mode uses wine name, region, grape etc. to fill missing fields; image + text combined for best results
- Fixed **Vivino image not saved** on edit — `/edit/` endpoint now checks `ai_image` field
- **Placeholders hidden** in edit mode (shown only when adding new wines)
- Renamed AI reload label to "Fehlende Daten von der KI laden"

## 0.4.4

- **"Daten ergänzen" moved into edit modal** — popover next to save button with AI / Vivino options (removed from card actions)
- Fixed **Vivino image download** — protocol-relative URLs now handled correctly
- Updated **wine-type colors** to match Vivino palette

## 0.4.3

- Fixed **Vivino search** — rewrote to scrape HTML search page (explore API no longer supports text queries)
- **Image downscaling** on upload (longest edge ≤ 1800 px)
- Wine-type **ribbon moved to top-left** corner (qty badge occupies top-right)
- **Empty bottles hidden** on initial page load when toggle is off
- **Changelog** now ships inside the add-on directory (fixes "No changelog found" in HA)

## 0.4.2

- Centralized **wine-type colors** as CSS Custom Properties
- **Donut chart** uses type-based color mapping (fixes wrong colors)
- Globe starts centered on the **region with most wines**
- Removed redundant wine-type tag from card meta (ribbon is sufficient)
- Adjusted **modal widths** (source step 360 px, wine form 480 / 900 px)

## 0.4.1

- Search wines on **Vivino** directly from the add dialog (name, region, rating, price)
- **Reload missing data** button to re-analyze wines with incomplete AI results
- Improved **AI drink-window estimation** (better prompts, more reliable responses)
- Redesigned source-selection step with three full-width options (AI / Vivino / Manual)
- Extracted all CSS into a dedicated stylesheet for faster page loads
- Globe now starts centered on **equator height** for a more balanced view
- Version bumping script for maintainers (`set_version_nr.sh`)

## 0.4.0

- **Vivino wine search** integrated into the add-wine flow
- **Reload missing data** for wines with incomplete AI analysis
- Improved **drink-window estimation** from AI providers

## 0.3.5

- **Autocomplete** for region and purchase source fields
- Added DOCS page with logo and commit-activity badge

## 0.3.4

- Polished **photo panel** layout and styling
- Added version and license **badges** to README

## 0.3.3

- **Grape autocomplete** when entering grape varieties
- Responsive **side-panel photo layout** (photo next to wine details on wide screens)

## 0.3.2

- AI now estimates a **drinking window** (best-before range) for each wine

## 0.3.1

- New **grape varieties** field on every wine entry
- Cleaned up Home Assistant add-on configuration
- Reorganized translation files into per-language YAML

## 0.3.0

- **AI-powered onboarding**: snap a photo of a wine label and let AI fill in all fields
- Supports **Anthropic Claude**, **OpenAI**, **OpenRouter**, and local **Ollama** models
- Configurable AI provider and model in the add-on settings

## 0.2.3

- **Vertical drag** on the interactive globe (move up and down, not just left/right)
- Fixed donut-chart card width on smaller screens

## 0.2.2

- **Configurable currency** (CHF, EUR, USD, ...) in add-on settings
- Globe now supports **click-and-drag interaction** with smooth momentum
- Added **country legend** next to the globe
- Refined donut-chart colors and layout

## 0.2.1

- **3D globe** showing wine origins by country
- **Donut chart** for wine-type distribution
- New **app logo**

## 0.2.0

- **Statistics page** with country breakdown, wine-type summary, and price overview

## 0.1.8

- Client-side **filter tabs** (Red, White, Rosé, Sparkling, All)
- **Live search** across all wine fields
- **Status toggle** (consumed / in stock) without page reload

## 0.1.7

- **AJAX saves** — adding and editing wines no longer reloads the page
- **Lightbox** for full-screen wine photos
- **Dirty-tracking** warns before leaving unsaved changes
- Fixed duplicate image uploads

## 0.1.6

- Merged add and edit forms into a **single modal dialog**
- Newly saved wines are **highlighted** in the list

## 0.1.5

- Newly added wines are **highlighted and auto-scrolled** into view

## 0.1.4

- Consistent **card layout** — action buttons always pinned to the bottom

## 0.1.3

- Custom **delete confirmation dialog** (replaces the native browser popup)

## 0.1.2

- **Dark / Light theme** with one-click toggle
- Unified **toolbar** with search, filters, and theme switch
- General UI polish

## 0.1.1

- **Multi-language support** — German, English, French, Italian, Spanish, Portuguese, Dutch
- All emojis replaced with **Material Design Icons**
- **Floating action button** (FAB) to add wines
- Storage location selectable from a **dropdown**

## 0.1.0

- Initial release as a **Home Assistant add-on**
- Add, edit, and delete wines with photo upload
- Wine cards with image, name, vintage, region, type, and price
- SQLite database stored on the HA shared volume
- Full **ingress** support (runs behind the HA reverse proxy)
