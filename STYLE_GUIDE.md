# Wine Tracker — Style Guide

Reference for consistent UI development. All values are derived from `wine-tracker/app/static/style.css`.

---

## Theme Tokens (CSS Custom Properties)

Every theme defines these variables. Always use the variable, never a hardcoded value.

| Token | Purpose | Example (Classic dark) |
|-------|---------|----------------------|
| `--bg` | Page background | `#1a0a0f` |
| `--surface` | Card / modal / header background | `#2a1520` |
| `--border` | Borders, dividers | `#5a2a3a` |
| `--accent` | Primary interactive color (buttons, links, focus rings) | `#c0392b` |
| `--accent2` | Darker accent for hover states on solid buttons | `#8b1a2a` |
| `--gold` | Stars, highlight numbers, secondary accent | `#d4a843` |
| `--text` | Primary text | `#f0e0e5` |
| `--muted` | Secondary text, labels, placeholders | `#9a7a82` |
| `--empty` | Empty-state backgrounds, subtle fills | `#3a2a30` |
| `--radius` | Container border-radius (cards, modals, stat boxes) | `12px` |
| `--shadow` | Elevation shadow | `0 4px 24px rgba(0,0,0,.5)` |

### Wine Type Colors (theme-independent)
```
--wine-rotwein:    #803039
--wine-weisswein:  #f4ca4f
--wine-rose:       #ffd1d8
--wine-schaumwein: #f3efaf
--wine-dessertwein:#eb7a17
--wine-likoerwein: #800f1c
--wine-anderes:    #6c3461
--wine-empty:      #aaa
```

---

## Color Usage Rules

### Theme-aware colors (use variables)
| Situation | Use |
|-----------|-----|
| Primary button background | `var(--accent)` |
| Primary button hover | `var(--accent2)` |
| Focus ring / active border | `var(--accent)` |
| Transparent hover tint | `color-mix(in srgb, var(--accent) 10%, transparent)` |
| Transparent subtle tint | `color-mix(in srgb, var(--accent) 4-6%, transparent)` |
| Star ratings, highlight numbers | `var(--gold)` |

### Semantic colors (hardcoded, theme-independent)
| Situation | Color | Hex |
|-----------|-------|-----|
| Delete button background | Red | `#c0392b` |
| Delete button hover | Bright red | `#e74c3c` |
| Card delete hover bg | Dark red | `#5a1010` |
| Error messages | Red | `#e74c3c` |
| Expired drink window | Red | `#e74c3c` |
| Drink window OK | Green | `#27ae60` |
| Drink window warning | Orange | `#e67e22` |

### Rule of thumb
> **Interactive hover** → `var(--accent2)` or `color-mix()`
> **Danger / error / destructive** → hardcoded red (`#e74c3c` / `#c0392b`)
> Never use hardcoded accent colors for non-danger interactive states.

---

## Typography

### Font Stack
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

### Font Size Scale

| Size | rem | Use |
|------|-----|-----|
| 4xl | `4rem` | Empty state icon |
| 3xl | `3.5rem` / `3rem` | Card placeholder icon |
| 2xl | `2.5rem` | Upload area icon |
| xl | `2rem` | Highlight number, stat big number |
| lg | `1.8rem` | Highlight card emoji |
| h1 | `1.6rem` | FAB icon |
| h2 | `1.15rem` | Brand name |
| h3 | `1.1rem` | Modal title, section headings, header icons |
| body-lg | `1rem` | Card name, qty buttons |
| body | `.95rem` | Submit button, inputs, source label |
| body-sm | `.9rem` | Stat card header, input fields, descriptions |
| caption | `.85rem` | Nav links, star ratings, tooltips, small buttons |
| caption-sm | `.82rem` | Filter options, duplicate hint, Vivino meta |
| small | `.8rem` | Labels, card meta, card actions, settings labels |
| xs | `.78rem` | Card notes, tooltip quantities, nav link mobile |
| xxs | `.75rem` | Card extra tags, wine list rank, price |
| micro | `.72rem` | Drink window bar labels |
| nano | `.7rem` | Section titles (uppercase), settings labels |
| pico | `.65rem` | Ribbon text, donut center label |
| dot | `.6rem` | Donut center subtitle |

### Font Weight
| Weight | Use |
|--------|-----|
| `800` | Highlight numbers, stat big numbers |
| `700` | Brand name, card name, modal title, stat headers, buttons |
| `600` | Source labels, active filter, submit buttons |
| `500` | Nav links, theme segment buttons |
| normal | Everything else |

---

## Border-Radius Hierarchy

| Radius | Use | CSS |
|--------|-----|-----|
| `50%` | Circles: spinners, FAB, donut legend dots, status dots | `border-radius: 50%` |
| `20px` | Pills: wine type ribbon | `border-radius: 20px` |
| `var(--radius)` = `12px` | **Containers**: cards, modals, stat boxes, highlight cards, source options, upload area | `border-radius: var(--radius)` |
| `10px` | **Popovers & dropdowns**: filter dropdown, reload popover, Vivino ID popover, chart tooltip, theme dropdown list | `border-radius: 10px` |
| `8px` | **Buttons & inputs**: nav links, submit/cancel, inputs, search box, theme toggle, filter btn, AI buttons, Vivino search, image preview, theme segment control, theme dropdown button, wine list items | `border-radius: 8px` |
| `6px` | **Small interactive items**: filter options, reload menu items, qty buttons, img action buttons, Vivino results, bar chart bars, donut legend hover | `border-radius: 6px` |
| `4px` | **Tags & chips**: card meta tags, card extra tags, chart tooltip items, drink window bar tops | `border-radius: 4px` |
| `3px` | Scrollbar thumb | `border-radius: 3px` |

### Rule of thumb
> **Container** → `var(--radius)` (12px)
> **Popover/floating panel** → `10px`
> **Button or input** → `8px`
> **Small item inside a list** → `6px`
> **Tiny chip/tag** → `4px`

---

## Spacing

### Base Unit
The design uses rem-based spacing. Common increments:

| Size | Value | Use |
|------|-------|-----|
| xs | `.15rem` – `.25rem` | Tight gaps (star icons, filter list, tag padding) |
| sm | `.35rem` – `.5rem` | Label margins, small paddings, card body gaps |
| md | `.6rem` – `.75rem` | Input padding, section gaps, card body padding |
| lg | `1rem` – `1.25rem` | Modal body padding, grid gap, section spacing |
| xl | `1.5rem` | Page padding, panel padding, section margins |
| xxl | `2rem` – `3rem` | Upload area padding, empty state padding |

### Consistent Patterns
- **Grid gap**: `1rem`
- **Card body padding**: `.75rem 1rem`
- **Modal body padding**: `1.25rem`
- **Modal body gap**: `.9rem`
- **Form row gap** (`.row2`): `.75rem`
- **Button padding**: `.6rem 1rem` (standard), `.5rem 1.2rem` (small)
- **Input padding**: `.55rem .75rem`

### Element Heights
Fixed pixel heights for consistent vertical alignment:

| Height | Use |
|--------|-----|
| `56px` | Header (fixed, matches HA toolbar) |
| `42px` | Submit / action buttons |
| `38px` | Standard inputs, selects, inline icon buttons adjacent to inputs |
| `34px` | Header icon buttons, header search/filter inputs |

### Rule of thumb
> **Inline icon button next to an input** → same height as the input (`38px`)
> **Header-level controls** → `34px`
> Never let a button/icon visually "shrink" next to its paired input.

---

## Transitions

| Duration | Easing | Use |
|----------|--------|-----|
| `.15s` | default | Hover backgrounds, color changes, text color |
| `.2s` | default | Button hovers, border-color, card hover lift, general interactions |
| `.25s` | `ease` | Modal width expansion |
| `.3s` | `ease` | Image fade-in (opacity) |
| `.4s` | `ease` | Bar chart segment height, toast opacity |
| `.6s` | `ease` | Progress bar width |
| `.8s` | `linear infinite` | Spinner rotation |

### Rule of thumb
> **Micro-interactions** (hover, focus) → `.15s` – `.2s`
> **Visible UI changes** (expand, reveal) → `.25s` – `.4s`
> **Animations** (progress, spin) → `.6s`+

---

## Shadows

| Level | Value | Use |
|-------|-------|-----|
| Card elevation | `var(--shadow)` | Header, card hover, dropdown panels |
| Floating panel | `0 8px 24px rgba(0,0,0,.4)` | Reload popover, Vivino ID popover, chart tooltip |
| Lightbox | `0 0 40px rgba(0,0,0,.6)` | Photo lightbox |
| FAB | `0 4px 16px rgba(0,0,0,.4)` | Floating action button |
| FAB hover | `0 6px 20px rgba(0,0,0,.5)` | FAB hover state |
| Highlight glow | `0 0 20px 6px rgba(212,168,67,.7)` | New/edited wine pulse |
| Badge | `0 2px 4px rgba(0,0,0,.18)` | Drink window badge |

---

## Component Quick-Reference

### Buttons
| Type | Background | Hover | Radius |
|------|-----------|-------|--------|
| Primary (submit, FAB) | `var(--accent)` | `var(--accent2)` | `8px` |
| Secondary (cancel) | `var(--empty)` | lighter `--empty` | `8px` |
| Danger (delete) | `#c0392b` | `#e74c3c` | `8px` |
| Ghost (icon buttons) | `none` / `transparent` | `rgba(0,0,0,.06)` | `8px` |
| Small (AI buttons) | `var(--accent)` | `var(--accent2)` | `8px` |

### Inputs
- Height: `38px` (standard), `34px` (header search/filter)
- Border: `1px solid var(--border)`
- Focus: `border-color: var(--accent)`
- Background: `var(--bg)`
- Radius: `8px`

### Cards
- Background: `var(--surface)`
- Border: `1px solid var(--border)`
- Radius: `var(--radius)` (12px)
- Hover: `translateY(-2px)` + `var(--shadow)`

### Modals
- Max-width: `360px` (default), `640px` (expanded with photo)
- Background: `var(--surface)`
- Radius: `var(--radius)` (12px)
- Header: `1rem 1.25rem` padding, bottom border
- Body: `1.25rem` padding, `.9rem` gap
- Footer: `0 1.25rem 1.25rem` padding, `.75rem` gap

### Stat Cards
- Background: `var(--surface)`
- Radius: `var(--radius)` (12px)
- Header: `.85rem 1rem` padding, bottom border
- Body: `1rem` padding

---

## Themes Overview

Six themes, each with dark and light mode:

| Theme | Accent (dark) | Accent (light) | Character |
|-------|--------------|----------------|-----------|
| Classic | `#c0392b` (red) | `#a03025` | Default wine red |
| Vineyard | `#4caf50` (green) | `#388e3c` | Natural, earthy |
| Champagne | `#c9a84c` (gold) | `#a08030` | Elegant, warm |
| Slate | `#5c7cfa` (blue) | `#4263d8` | Cool, modern |
| Burgundy | `#ab47bc` (purple) | `#9c27b0` | Rich, luxurious |
| Home Assistant | `#009ac7` (cyan) | `#006787` | HA native look |

Each theme defines: `--bg`, `--surface`, `--border`, `--accent`, `--accent2`, `--gold`, `--text`, `--muted`, `--empty`, `--shadow`.

---

## Checklist for New Components

- [ ] Use `var(--accent)` / `var(--accent2)` for interactive colors, never hardcoded hex
- [ ] Only use hardcoded red (`#e74c3c`) for danger/error states
- [ ] Use `color-mix(in srgb, var(--accent) N%, transparent)` for transparent tints
- [ ] Use the correct border-radius tier (container=12, popover=10, button=8, small=6, tag=4)
- [ ] Use `var(--surface)` for elevated backgrounds, `var(--bg)` for recessed backgrounds
- [ ] Use `var(--border)` for all borders and dividers
- [ ] Use `var(--text)` for primary text, `var(--muted)` for secondary text
- [ ] Keep transitions under `.2s` for hover, `.3s`–`.4s` for visible changes
- [ ] Test in all 6 themes × dark + light mode
