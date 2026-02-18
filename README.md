# Wine Tracker – Home Assistant App

<p align="center">
  <img src="logo.png" alt="Wine Tracker Logo" width="128">
</p>

Ein schlanker, eleganter Weinkeller-Tracker als Home Assistant App.

## Features

- Weinliste als Karten mit Foto, Jahrgang, Typ, Region, Bewertung & Notizen
- Foto-Upload direkt vom Handy (Etikett fotografieren)
- Sternebewertung (1-5)
- Schnelle Mengen-Buttons direkt auf der Karte
- Duplizieren - perfekt wenn sich nur der Jahrgang aendert
- Quantity = 0 bleibt sichtbar als Platzhalter (ausblendbar per Toggle)
- Suche & Filter nach Weintyp
- HA Ingress - direkt in der HA-Sidebar eingebettet
- REST API unter `/api/summary` fuer HA-Sensoren

## Installation als GitHub-Repository

1. **Einstellungen > Apps > App Store**
2. Oben rechts: **drei Punkte > Repositories**
3. Repository-URL eingeben: `https://github.com/xenofex7/ha-wine-tracker`
4. **Wine Tracker** erscheint im Store
5. **Installieren > Starten**

Die App oeffnet sich in der HA-Sidebar unter **Wine Tracker**.

## Datenpersistenz

Alle Daten (SQLite-DB + Fotos) werden unter `/share/wine-tracker/` gespeichert -
bleiben also bei App-Updates, Neustarts und HA-Updates erhalten.

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
| `type` | Text | Rotwein / Weisswein / Rose / Schaumwein / Dessertwein |
| `region` | Text | Herkunft (z.B. Piemont, IT) |
| `quantity` | Integer | Anzahl Flaschen (0 = Platzhalter) |
| `rating` | Integer | 1-5 Sterne |
| `notes` | Text | Freitext |
| `image` | Text | Dateiname des Etikettfotos |
| `added` | Date | Erfassungsdatum |
| `purchased_at` | Text | Bezugsquelle |
| `price` | Real | Kaufpreis (CHF) |
| `drink_from` | Integer | Trinkfenster von (Jahr) |
| `drink_until` | Integer | Trinkfenster bis (Jahr) |
| `location` | Text | Lagerort |

## Technologie

- **Backend**: Python 3 + Flask
- **Datenbank**: SQLite (eine einzige Datei)
- **Frontend**: Vanilla HTML/CSS (kein Framework, kein Node.js)
- **Base Image**: Home Assistant Alpine-basiert

## Offene Features

- Export / Import Funktion
- Integration von AI zum Adden von Weininfos oder Weininfos laden per API
- Bugfixes Themes
- Custom Sortierungen
- Multi-Language
- Darstellung - Listen-Ansicht oder Portal

## Lizenz

MIT
