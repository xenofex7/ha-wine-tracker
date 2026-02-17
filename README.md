# 🍷 Wine Tracker – Home Assistant Add-on

Ein schlanker, eleganter Weinkeller-Tracker als lokales Home Assistant Add-on.

![Dark wine-themed UI with card grid]

## Features

- 🍾 **Weinliste als Karten** mit Foto, Jahrgang, Typ, Region, Bewertung & Notizen
- 📷 **Foto-Upload** direkt vom Handy (Etikett fotografieren)
- ⭐ **Sternebewertung** (1–5)
- ➕/➖ **Schnelle Mengen-Buttons** direkt auf der Karte
- ⎘ **Duplizieren** – perfekt wenn sich nur der Jahrgang ändert
- ⊘ **Quantity = 0** bleibt sichtbar als Platzhalter (ausblendbar per Toggle)
- 🔍 **Suche & Filter** nach Weintyp
- 🏠 **HA Ingress** – direkt in der HA-Sidebar eingebettet, kein extra Port nötig
- 📡 **REST API** unter `/api/summary` für HA-Sensoren

## Installation

### 1. Repository als lokales Add-on einbinden

```
/addons/
└── wine_tracker/
    ├── config.yaml
    ├── Dockerfile
    └── app/
        ├── app.py
        ├── templates/
        │   └── index.html
        └── uploads/      ← wird automatisch angelegt
```

Dateien ins Verzeichnis `/addons/wine_tracker/` auf deinem HA-System kopieren  
(z.B. via **Studio Code Server** oder **Samba Share**).

### 2. Add-on installieren

1. **Einstellungen → Add-ons → Add-on Store**
2. Oben rechts: **⋮ → Lokale Add-ons neu laden**
3. „Wine Tracker" erscheint unter **Lokale Add-ons**
4. **Installieren → Starten**

Das war's. Die App öffnet sich in der HA-Sidebar unter 🍷 **Wine Tracker**.

## Datenpersistenz

Alle Daten (SQLite-DB + Fotos) werden unter `/share/wine-tracker/` gespeichert –  
bleiben also bei Add-on-Updates, Neustarts und HA-Updates erhalten.

## Home Assistant Sensor (optional)

```yaml
# configuration.yaml
sensor:
  - platform: rest
    name: "Weinbestand"
    resource: "http://localhost:5050/api/summary"
    value_template: "{{ value_json.total_bottles }}"
    unit_of_measurement: "Flaschen"
    json_attributes:
      - by_type
    scan_interval: 3600
```

Damit hast du einen HA-Sensor `sensor.weinbestand` den du auf dem Dashboard  
oder in Automationen nutzen kannst.

## Datenbank-Felder

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `name` | Text | Weinname (Pflichtfeld) |
| `year` | Integer | Jahrgang |
| `type` | Text | Rotwein / Weisswein / Rosé / Schaumwein / Dessertwein |
| `region` | Text | Herkunft (z.B. „Piemont, IT") |
| `quantity` | Integer | Anzahl Flaschen (0 = Platzhalter) |
| `rating` | Integer | 1–5 Sterne |
| `notes` | Text | Freitext (Trinkfenster, Aromen, …) |
| `image` | Text | Dateiname des Etikettfotos |
| `added` | Date | Erfassungsdatum |

## Technologie

- **Backend**: Python 3 + Flask
- **Datenbank**: SQLite (eine einzige Datei)
- **Frontend**: Vanilla HTML/CSS (kein Framework, kein Node.js)
- **Base Image**: Home Assistant Alpine-basiert

## Lizenz

MIT
