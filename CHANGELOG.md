# Changelog

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
