# Amortix

[![Validate](https://github.com/USERNAME/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/USERNAME/amortix/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Eine **geräteunabhängige Amortisations-Integration** für Home Assistant. Sie berechnet aus
kumulierenden kWh-Sensoren und ein paar Preisen, wann sich eine Energie-Investition bezahlt
macht – für Balkonkraftwerke, PV-Anlagen und Batteriespeicher.

> Kern: zwei kWh-Sensoren + Preise (als `input_number` oder Sensor) genügen. Die Berechnung
> ist gemessen, sprungfrei (60-s-Takt, inkrementelle Bewertung) und dynamiktauglich (Tibber).

## Anwendungsfälle

| Modus | Pflicht-Sensoren | Rechnung |
|-------|------------------|----------|
| **Direktverbrauch** (BKW/PV ohne Speicher) | Erzeugung, Einspeisung (to_grid) | `Eigenverbrauch × Strompreis + Einspeisung × Vergütung` |
| **Speicher** | Ladung, Entladung | `Entladung × Strompreis − Ladung × Vergütung` |

- **Mehrere Erzeuger** (z. B. BKW + große PV am selben Zähler) lassen sich im Direktverbrauch
  gemeinsam auswählen und werden summiert.
- Speicher funktioniert für **AC- und DC-Kopplung** (nur Lade-/Entlademenge zählt).
- **Roundtrip-Wirkungsgrad** wird berechnet oder ein vorhandener Sensor genutzt (rein informativ).

## Installation

### HACS (empfohlen)
1. HACS → drei Punkte → **Benutzerdefinierte Repositories**.
2. URL dieses Repos eintragen, Kategorie **Integration**.
3. „Amortix" installieren, Home Assistant neu starten.

### Manuell
1. Ordner `custom_components/amortix/` ins Home-Assistant-Konfigverzeichnis kopieren.
2. Home Assistant neu starten.

## Einrichtung
**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Amortix"**, dann den
Anwendungsfall wählen. Jeder Dialog enthält Hinweise zu den benötigten Sensoren und zur
korrekten Einrichtung.

Voraussetzungen:
- **Kumulierende kWh-Zähler** (`state_class: total`/`total_increasing`), keine Watt-Sensoren.
- Einspeisung als **saldierter** Wert am Netzübergabepunkt.
- `input_number`-Helfer für Anschaffungskosten, Strompreis und (optional) Einspeisevergütung.

## Erzeugte Sensoren
**Direktverbrauch:** Einsparung gesamt (€), Einsparung Netzbezug (€), Einsparung Einspeisung
(€), Eigenverbrauch (kWh), Amortisations-Fortschritt (%), verbleibend (€), Ersparnis/Tag (€),
Restzeit (d), Amortisations-Datum.

**Speicher:** Speicher-Ersparnis (€), Entladung (kWh), Ladung (kWh), Roundtrip-η (%) plus die
gemeinsamen Amortisations-Kennzahlen.

## Icon
Die Icons liegen unter `icons/`. Für die Anzeige in Home Assistant müssen sie ins
[home-assistant/brands](https://github.com/home-assistant/brands)-Repo unter
`custom_integrations/amortix/icon.png` (256×256) und `icon@2x.png` (512×512).

## Lizenz
MIT – siehe [LICENSE](LICENSE).
