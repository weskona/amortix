# Amortix

[English](README.md) · **Deutsch**

[![Validate](https://github.com/weskona/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/weskona/amortix/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![release](https://img.shields.io/github/v/release/weskona/amortix)](https://github.com/weskona/amortix/releases)
[![license](https://img.shields.io/github/license/weskona/amortix)](LICENSE)

Eine **geräteunabhängige Amortisations-Integration** für Home Assistant. Sie berechnet aus
kumulierenden kWh-Sensoren und ein paar Preisen, wann sich eine Energie-Investition bezahlt
macht – für Balkonkraftwerke, PV-Anlagen und Batteriespeicher.

> Zwei kWh-Sensoren + Preise (als `input_number` oder Sensor) genügen. Die Berechnung ist
> gemessen, sprungfrei (60-s-Takt, inkrementelle Bewertung) und dynamiktauglich (z. B. Tibber).

## Installation

### HACS

[![Diese Home-Assistant-Instanz öffnen und das Repository in HACS anzeigen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weskona&repository=amortix&category=integration)

Auf den Button oben klicken, um Amortix zu HACS hinzuzufügen, dann **Herunterladen** und
Home Assistant neu starten.

<details>
<summary>Manuelle HACS-Schritte</summary>

1. HACS → drei Punkte (oben rechts) → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/weskona/amortix`, Kategorie **Integration**.
3. Hinzufügen, dann **Amortix** öffnen und **Herunterladen**.
4. Home Assistant neu starten.
</details>

### Manuell (ohne HACS)
1. Ordner `custom_components/amortix/` ins `config`-Verzeichnis von Home Assistant kopieren.
2. Home Assistant neu starten.

## Einrichtung
**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Amortix"**, dann den
Anwendungsfall wählen. Jeder Dialog enthält Hinweise zu den benötigten Sensoren und zur
korrekten Einrichtung.

Voraussetzungen:
- **Kumulierende kWh-Zähler** (`state_class: total`/`total_increasing`), keine Watt-Sensoren.
- Einspeisung als **saldierter** Wert am Netzübergabepunkt.
- `input_number`-Helfer für Anschaffungskosten, Strompreis und (optional) Einspeisevergütung.

## Anwendungsfälle

| Modus | Pflicht-Sensoren | Rechnung |
|-------|------------------|----------|
| **Direktverbrauch** (BKW/PV ohne Speicher) | Erzeugung, Einspeisung (to_grid) | `Eigenverbrauch × Strompreis + Einspeisung × Vergütung` |
| **Speicher** | Ladung, Entladung | `Entladung × Strompreis − Ladung × Vergütung` |

- **Mehrere Erzeuger** (z. B. BKW + große PV am selben Zähler) lassen sich im
  Direktverbrauch gemeinsam auswählen und werden summiert.
- Speicher funktioniert für **AC- und DC-Kopplung** (nur Lade-/Entlademenge zählt).
- **Roundtrip-Wirkungsgrad** wird berechnet oder aus einem vorhandenen Sensor genutzt
  (rein informativ).
- **Startgutschrift** lässt bereits laufende Anlagen mit ihrer bisherigen Ersparnis starten
  (manuell oder automatisch aus den aktuellen Zählerständen).

## Erzeugte Sensoren
**Direktverbrauch:** Einsparung gesamt (€), Einsparung Netzbezug (€), Einsparung Einspeisung
(€), Eigenverbrauch (kWh), Amortisations-Fortschritt (%), verbleibend (€), Ersparnis/Tag (€),
Restzeit (d), Amortisations-Datum.

**Speicher:** Speicher-Ersparnis (€), Entladung (kWh), Ladung (kWh), Roundtrip-η (%) plus die
gemeinsamen Amortisations-Kennzahlen.

## Lizenz
MIT – siehe [LICENSE](LICENSE).
