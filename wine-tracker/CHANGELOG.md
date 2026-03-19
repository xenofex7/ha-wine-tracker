# Changelog

## 1.7.1

- **Fix: Globe not rendering** — pin COBE library to v0.6.3 after upstream v2.0 breaking change (released 2026-03-18)

## 1.7.0

- **Cellar view modes** — four ways to browse your wine collection: Cards (default), List, Grid, and Table — switchable in settings
- **List view** — compact one-line rows with corner ribbons matching the stats page style, wine details (year, region, grape, drink window) as a subtitle
- **Grid view** — image-first square tiles with an overlay name, perfect for visual browsing
- **Table view** — sortable columns with persistent sort direction (saved in localStorage), right-aligned price/quantity, and a centered color dot per wine type
- **Responsive table** — columns hide progressively on smaller screens (<900px: grape + price, <700px: region, <500px: only dot + name + qty); fixed-width columns in px for consistent layout at any viewport
- **Settings modal redesign** — theme mode and view mode now use radio buttons instead of segmented controls; scrollable modal body for smaller screens
- **Hamburger menu** — navigation collapses into a menu on narrow viewports
- **DEV_AUTH mode** — `DEV_AUTH` environment variable for quick dev login (`user:pass:role`) without needing Home Assistant
- **217 tests** — 16 new tests covering view modes, hamburger menu, DEV_AUTH parsing, and password hashing

## 1.6.0

- **Activity Timeline** — new page showing a chronological log of every wine added, consumed, restocked, or removed, grouped by month with localized day headers
- **Maturity graph** — smooth bell curve visualizing a wine's drinking phases (Youth, Maturity, Peak, Decline) with a "Today" marker, powered by AI analysis
- **Taste profile** — AI-generated horizontal bars for body, tannin, acidity, and sweetness (1–5 scale), displayed in the wine detail view
- **Food pairings** — AI suggests matching dishes as clickable tags in the detail view
- **Persistent chat history** — sommelier conversations are saved to the database with full session management (load, continue, delete); chat recording can be toggled in settings
- **Wine detail view everywhere** — the detail modal now opens in-place on all pages (cellar, stats, timeline, chat) — no more redirecting to the index page
- **Edit modal everywhere** — extracted the edit form into a shared include so you can edit wines on any page without navigating away
- **Timeline stats cards** — monthly overview showing wines consumed, added, restocked, and total activities
- **Chat sessions in timeline** — sommelier conversations appear as timeline entries and open the correct session on click
- **Landing page update** — new "Why Wine Tracker" section with Local First, AI cost transparency, and Community cards; shields.io badges for data ownership
- **AI cost estimation** — README now includes a per-wine cost table for all supported providers
- **201 tests** — 48 new tests covering timeline, chat sessions, maturity/taste/food data, and edit modal on all pages

## 1.5.1

- **Fix OpenAI compatibility** — replace deprecated `max_tokens` with `max_completion_tokens` for newer OpenAI models (o1, o3, gpt-4o-2024-11-20+) that reject the old parameter
- **About section in settings** — settings modal now shows app version, links to GitHub, Changelog, Community Forum, and MIT license
- **Fix bottom tab bar padding** — safe-area-inset default changed from 20px to 0px so the tab bar doesn't float on non-notched devices
- **MIT license** — project is now officially MIT licensed
- **GitHub Pages landing page** — public landing page with dark/light mode, responsive layout, and lightbox image gallery

## 1.5.0

- **Docker standalone mode** — run Wine Tracker without Home Assistant via `docker-compose up`; pre-built multi-arch images (amd64 + arm64) on GitHub Container Registry
- **User authentication** — ENV-based login system with session cookies and password hashing (no new dependencies — uses werkzeug built into Flask)
- **Readonly role** — `user:password:readonly` format blocks all write operations while allowing full browsing, searching, and AI chat
- **Logout button** — settings modal shows the logged-in username with a sign-out button when auth is enabled
- **ENV configuration** — all add-on options (language, currency, AI provider & keys) can now be set via environment variables for Docker deployments
- **CI/CD pipeline** — GitHub Actions workflow builds and pushes Docker images to GHCR automatically on version tags; tests run as a build gate
- **Login page** — theme-aware login screen with the Wine Tracker logo, matching the active color scheme
- **README overhaul** — full Docker installation guide with Quick Start, all ENV variables documented, and update instructions
- **Rename /release to /deploy** — release skill renamed to avoid Claude Code conflict
- **153 tests** — 28 new tests covering ENV config (5), authentication (11), and readonly roles (12)

## 1.4.3

- **Clickable wine recommendations** — when the sommelier mentions a wine from your cellar, the name is a clickable link that opens the edit modal directly
- **Dedicated mobile chat page** — `/chat` route with full-screen layout, pinned between header and tab bar using `position: fixed` for reliable iOS behavior
- **Sommelier in navigation** — chat is now a proper nav item (desktop header + mobile tab bar) instead of a floating icon button
- **Home Assistant default theme** — HA theme is now the default for new installs and appears first in the theme picker
- **Taller desktop chat panel** — fixed height of 70vh so the panel always feels spacious, even with few messages
- **Fix FAB hidden behind tab bar** — CSS cascade bug: mobile override appeared before base `.fab` definition (same specificity → base always won); moved override after base rule
- **Fix modal header z-index** — image rotate/delete buttons no longer scroll over the sticky modal header (z-index 1 → 5)
- **Unify modal paddings** — all modal content areas now use `1.25rem` (20px) with no exceptions; enforced in Style Guide checklist
- **Larger image preview** — wine photo area increased from 140px to 240px for better visibility
- **125 tests** — 4 new tests covering `/chat` route and wine link instructions in chat prompts

## 1.4.2

- **Fix chat behind keyboard** — chat panel uses dynamic viewport height (`dvh`) so it shrinks when the mobile keyboard opens

## 1.4.1

- **Mobile tab bar** — bottom navigation bar on mobile replaces the header links for easier thumb-reach navigation between Cellar and Statistics
- **Fullscreen chat on mobile** — the sommelier chat panel now opens fullscreen on small screens so the keyboard doesn't cover the conversation
- **Security audit** — comprehensive security review documented in `SECURITY_AUDIT.md` covering XSS, path traversal, CSRF, and more (fixes coming in future releases)

## 1.4.0

- **AI Sommelier chat** — ask your personal sommelier for food pairings, serving temperatures, or bottle recommendations — it knows every wine in your cellar and responds in your language
- **Multi-provider chat** — works with Anthropic, OpenAI, OpenRouter, and Ollama (same providers as label recognition)
- **Markdown responses** — the sommelier formats answers with bold text, lists, and headings for easy reading
- **Session persistence** — chat history survives page navigation via sessionStorage, so you can switch between cellar and stats without losing the conversation
- **Chat in header navigation** — clean ghost icon next to settings instead of a floating bubble
- **Scroll lock** — background stays put while the chat panel is open
- **Style guide** — new `STYLE_GUIDE.md` documents all UI decisions (colors, radii, spacing, typography)
- **CSS consistency pass** — theme-aware hovers, standardized border-radii, and element sizing across all components
- **121 tests** — 10 new tests covering chat endpoint, history validation, provider errors, and wine context building

## 1.3.1

- **Inline stats editing** — click any wine in the statistics page (tooltip links, best rated, price overview, recently added) to open the edit modal right there — no more navigating away to the cellar
- **Wine API endpoint** — new `/api/wine/<id>` endpoint returns full wine data as JSON, powering the inline edit on stats
- **Clickable chart tooltips** — tooltip wine names are now links that open the edit modal directly
- **Shared modal code** — extracted duplicated HTML into Jinja partials (`_settings_modal`, `_wine_form_fields`) and shared JS into `wine-modal.js`, eliminating ~380 lines of duplicated code
- **Shimmer loading for images** — wine card images now show a diagonal shimmer animation while loading, with a smooth fade-in once ready; shimmer color adapts to your active theme
- **Fix highlight stacking** — editing multiple wines in a row no longer leaves all of them glowing; only the most recently saved card gets highlighted
- **Fix tooltip over modal on mobile** — chart tooltips now hide when opening the edit modal, so they don't float over the form
- **111 tests** — 8 new tests covering the wine API endpoint, stats modal presence, tooltip links, and edit parameter handling

## 1.3.0

- **Settings modal** — new gear icon in the header opens a dedicated settings panel (replaces the old theme-cycle button)
- **6 color themes** — choose from Classic, Vineyard, Champagne, Slate, Burgundy, and the new Home Assistant theme with cyan-blue and orange accents
- **Light / Dark / System mode** — pick your preferred mode with a segmented control inside settings
- **Home Assistant theme** — color scheme based on official HA design tokens for a native look
- **Favicon** — the wine tracker logo now appears in your browser tab
- **Logo on empty cellar** — the empty-state screen shows the Wine Tracker logo instead of a generic wine glass icon
- **Add-on README** — the Info tab in Home Assistant now shows project badges, features, and a link to the GitHub repo
- **Scrollbar styling** — thin, themed scrollbars across all views
- **Globe centering** — the 3D globe now centers on the longitude of your biggest wine region instead of a fixed Europe offset
- **Security hardening** — XSS escaping in wine cards, SSRF protection on the Vivino image proxy, upload path validation with extension allowlist
- **Dockerfile cleanup** — dependencies now installed from `requirements.txt` instead of inline `pip install`
- **103 tests** — new tests for path traversal, SSRF protection, and disallowed file extensions

## 1.2.1

- **Fix drink window color on duplicate/add/edit** — drink window badges now show the correct color (green/orange/red) immediately after AJAX operations instead of requiring a page reload
- **Fix bottle format on duplicate** — duplicating a wine with a non-standard bottle size no longer silently resets to 0.75L
- **Test suite** — 95 pytest tests covering routes, API endpoints, database operations, and helper functions; tests run automatically as a release gate
- **Expanded roadmap** — structured roadmap with 25 planned features across 7 categories

## 1.2.0

- **Bottle format support** — track different wine bottle sizes from Piccolo (0.1875L) to Nebuchadnezzar (15L) with a new dropdown in the wine form
- **AI bottle size detection** — AI label recognition now detects bottle format from the label photo when clearly visible
- **Total liters statistic** — new highlight card on the statistics page showing total liters in your cellar, calculated from quantity × bottle size
- **Compact stats layout** — all five highlight cards now fit in a single row on desktop
- **2-column form layout** — grape variety and bottle format sit side-by-side for better space usage
- **Database migration** — existing wines automatically set to standard 0.75L bottles
- **Multilingual** — bottle format labels and total liters translated for all 7 languages

## 1.1.4

- **Improved SSL certificate handling** — force-reinstall requests, urllib3, and certifi packages to ensure reliable HTTPS connections to Vivino
- **SSL debug logging** — certificate path detection now logs to console for easier troubleshooting
- **Fix Vivino ID reload bug** — reload via Vivino now always updates the wine ID, fixing wines with wrong vintage IDs from previous searches

## 1.1.3

- **No more theme flicker** — switching between Cellar and Statistics no longer flashes dark mode; an inline script applies your theme before the first paint
- **Custom logo** — the wine glass icon in the header is now a proper logo image
- **Vivino ID management** — new developer icon (</>) in the edit modal header opens a popover to view, edit, and test-link the Vivino wine ID
- **Fix Vivino ID bug** — wine links now use the stable wine ID instead of the vintage ID, so they always point to the correct Vivino page
- **Smarter year labels** — drink window chart shortens year labels (e.g. '25 instead of 2025) when there are many years, with responsive breakpoints for mobile
- **Cleaner codebase** — theme logic extracted into shared theme.js, removed unused updateStats() dead code

## 1.1.2

- **Interactive chart tooltips** — hover over donut segments, region bars, or drink window chart segments to see which wines are behind the numbers (name, vintage, quantity)
- **Drink window filter** — filter the cellar view by drink window status (ready, not ready, past) with counts and section titles; filter auto-hides when no wines have drinking windows
- **Drink window stacked bar chart** — new chart on the statistics page showing drinking windows grouped by year and wine type
- **Mobile tooltip support** — tap to show, tap elsewhere to dismiss
- **Fix Vivino SSL on all Home Assistant OS installations** — bundle Mozilla CA certificates via certifi so HTTPS connections work even when system certificates are incomplete
- **Fix drink window subtitle position** — subtitle no longer overlaps the section border

## 1.1.1

- **Drink window warnings** — red alert icon when a wine is past its drinking window, orange when in its last year
- **Fix Vivino search on all platforms** — add missing CA certificates to Docker image so SSL connections work reliably

## 1.1.0

- **Rotate photos** — rotate wine label images directly in the edit dialog with a single click
- **Delete photos** — remove a wine's photo with confirmation before saving

## 1.0.3

- **Fix image orientation** — Apply EXIF rotation during upload resize so smartphone photos display correctly

## 1.0.2

- **Cleaner add-wine dialogs** — AI and Vivino steps now share a unified, streamlined layout
- **Mobile space saver** — navigation icon hidden on small screens to free up header room

## 1.0.1

- **Your photos stay yours** — reloading data from Vivino no longer replaces your own wine photos
- **Compact reload button** — cleaner edit dialog with a sleek icon-only button
- **Pixel-perfect header** — now matches the Home Assistant toolbar height exactly
- System theme is now the default — automatically adapts to your device's dark or light mode

## 1.0.0

- **Redesigned navigation** — a clean, unified header across every page for a polished app-like experience
- **Smart filter menu** — tap the filter icon to pick your wine type from a neat dropdown list
- **Hide empty bottles** toggle now lives right inside the filter menu — one less thing cluttering the screen
- **Cleaner interface** — removed visual clutter for a more focused wine browsing experience
- **Sleek flat header** — modern, minimal design that looks great in dark and light mode
- **Consistent layout** — every page now feels like it belongs to the same app
- **Bigger wine glass icon** — because your cellar deserves a proper logo
- **Polished globe view** — legend tucked into the corner, cleaner on mobile
- **Streamlined statistics** — focused on what matters: your charts and numbers
- **Vivino links actually work now** — clicking a Vivino link on a wine card opens the correct wine page (not a random one)
- **Wine type ribbon** no longer gets cut off at the bottom
- All 7 languages fully updated (German, English, French, Italian, Spanish, Portuguese, Dutch)

## 0.4.5

- **AI gets smarter** — even without a photo, AI can now fill in missing data using just the wine name, region, and grape
- Photo + text together still gives the best results
- Fixed an issue where Vivino images weren't saved when editing a wine
- Cleaner edit form — no more confusing placeholder text on existing wines

## 0.4.4

- **"Reload data" moved into the edit dialog** — find AI and Vivino options right next to the save button
- Fixed Vivino image downloads that sometimes failed
- Wine type colors now match the Vivino palette

## 0.4.3

- **Vivino search is back** — completely rebuilt to work reliably again
- **Smaller photos** — uploaded images are automatically downsized for faster loading
- Wine type ribbon moved to the top-left corner for better readability
- Empty bottles now properly hidden on page load when the toggle is off
- Changelog visible in Home Assistant (no more "No changelog found")

## 0.4.2

- **Smarter donut chart** — colors now match the wine type (red for red, gold for white, etc.)
- **Globe finds your wines** — automatically centers on the country where most of your wine comes from
- Cleaner wine cards with less redundant info
- Improved modal sizes on different screen sizes

## 0.4.1

- **Vivino search** — search for wines by name, see ratings, prices, and import directly
- **Reload missing data** — re-analyze wines where AI couldn't fill all fields
- **Better drink window estimation** — AI now gives more accurate "best before" ranges
- **Redesigned "add wine" flow** — choose between AI, Vivino, or manual entry with big clear buttons
- Faster page loads thanks to optimized stylesheets
- Globe starts with a nicer balanced view

## 0.4.0

- **Vivino integration** — search and import wines from Vivino
- **Reload incomplete wines** — let AI retry on wines with missing data
- Improved drink window predictions

## 0.3.5

- **Autocomplete everywhere** — region and purchase source now suggest values as you type

## 0.3.4

- Polished photo layout and styling

## 0.3.3

- **Grape variety autocomplete** — quickly find the right grape as you type
- **Side-by-side photo layout** — on wider screens, the photo sits next to the wine details

## 0.3.2

- **Drinking window** — AI now estimates when your wine is at its best

## 0.3.1

- New **grape variety** field on every wine
- Cleaned up add-on settings

## 0.3.0

- **AI label recognition** — snap a photo of any wine label and let AI fill in all the details automatically
- Supports **4 AI providers**: Anthropic Claude, OpenAI, OpenRouter, and local Ollama
- Choose your provider and model in the add-on settings

## 0.2.3

- Globe now supports **vertical dragging** — explore the whole world, not just left and right
- Better chart sizing on smaller screens

## 0.2.2

- **Configurable currency** — set your preferred currency (CHF, EUR, USD, ...) in settings
- Globe supports **click-and-drag** with smooth momentum — feels like spinning a real globe
- **Country legend** next to the globe
- Refined chart colors

## 0.2.1

- **Interactive 3D globe** — see where your wines come from on a beautiful spinning globe
- **Donut chart** — visual breakdown of your wine types
- New **app logo**

## 0.2.0

- **Statistics page** — country breakdown, wine type distribution, and price overview at a glance

## 0.1.8

- **Filter by type** — quickly switch between Red, White, Rosé, Sparkling, or show all
- **Live search** — find any wine instantly as you type
- **Quick status toggle** — mark wines as consumed without reloading

## 0.1.7

- **Instant saves** — adding or editing a wine no longer reloads the page
- **Photo lightbox** — tap any wine photo to see it full screen
- **Unsaved changes warning** — no more accidentally losing your edits

## 0.1.6

- **Single dialog for everything** — add and edit wines in the same clean modal
- Newly saved wines get **highlighted** so you spot them immediately

## 0.1.5

- New wines are **highlighted and scrolled into view** — you'll never wonder where they went

## 0.1.4

- **Consistent card layout** — action buttons always at the bottom, no more jumping around

## 0.1.3

- **Custom delete confirmation** — a proper dialog instead of the ugly browser popup

## 0.1.2

- **Dark & Light theme** — switch with one click
- Unified toolbar with search, filters, and theme toggle
- General visual polish

## 0.1.1

- **7 languages** — German, English, French, Italian, Spanish, Portuguese, Dutch
- Beautiful **Material Design icons** throughout
- **Floating + button** to quickly add new wines
- Storage location as a **dropdown** for easy selection

## 0.1.0

- **First release!** 🍷
- Add, edit, and delete wines with label photo upload
- Wine cards with photo, name, vintage, region, type, and price
- Runs as a **Home Assistant add-on** right in your sidebar
- All data safely stored and preserved across updates
