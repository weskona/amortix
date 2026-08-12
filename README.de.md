# Amortix

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/weskona/amortix)](https://github.com/weskona/amortix/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA min version](https://img.shields.io/badge/Home%20Assistant-2024.4%2B-blue)](https://www.home-assistant.io)
[![Validate](https://github.com/weskona/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/weskona/amortix/actions/workflows/validate.yml)

[English](README.md)

Eine **geräteunabhängige Amortisations-Integration für Home Assistant**. Amortix berechnet aus kumulierenden kWh-Sensoren und ein paar Preisen, wann sich eine Energie-Investition bezahlt macht – für Balkonkraftwerke, PV-Anlagen und Batteriespeicher. Keine Hersteller-API, kein Cloud-Konto: jede Integration, die kumulierende kWh liefert, funktioniert.

> Zwei kWh-Sensoren + Preise (als `input_number` oder Sensor) genügen. Die Berechnung ist gemessen, sprungfrei (60-s-Takt, inkrementelle Bewertung) und dynamiktauglich (z. B. Tibber).

---

## Funktionen

- **Geräteunabhängig** — funktioniert mit jeder HA-Entität, die kumulierende kWh liefert (Wechselrichter, Wallbox, BMS, ...), keine Hersteller-Integration nötig.
- **Zwei Modi** — Direktverbrauch (Balkonkraftwerk/PV ohne Speicher) oder Speicher (Batterie-Lade-/Entladebilanz), jeweils mit eigenem Sensor-Set.
- **Gemessen statt geschätzt** — wertet alle 60 Sekunden gegen deine echten, live gelesenen Preis-/Tarif-Entitäten aus, bleibt dadurch auch bei dynamischen Tarifen genau, statt mit einem pauschalen Durchschnitt zu rechnen.
- **Mehrere Erzeugungsquellen** — mehrere Erzeugungssensoren gleichzeitig auswählbar (z. B. Balkonkraftwerk + Dach-PV); werden automatisch summiert.
- **Startgutschrift** — eine bereits laufende Anlage kann mit ihrer bisher aufgelaufenen Ersparnis starten, entweder manuell eingegeben oder automatisch aus den aktuellen Zählerständen berechnet.
- **Reset-sicher** — ein Zähler, der wirklich zurückgesetzt wird (Firmware-Update, Gerätewechsel), wird erkannt und zählt ab dort ohne Historienverlust weiter; ein einmaliger Ausreißer (z. B. kurz `0` statt `unavailable`) wird von einem echten Reset unterschieden und nicht doppelt gezählt.
- **Roundtrip-Wirkungsgrad** (Speicher-Modus) — aus den Lade-/Entlade-Summen berechnet, oder ein vorhandener Wirkungsgrad-Sensor wird stattdessen genutzt.
- **Nachträglich anpassbar** — Anschaffungskosten, Strompreis und Einspeisevergütung lassen sich jederzeit über **Konfigurieren** ändern, ohne die aufgelaufene Historie zu verlieren.

---

## Installation

### HACS

[![Diese Home-Assistant-Instanz öffnen und das Repository in HACS anzeigen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weskona&repository=amortix&category=integration)

Auf den Button oben klicken, um Amortix zu HACS hinzuzufügen, dann **Herunterladen** und Home Assistant neu starten.

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

---

## Einrichtung

**Einstellungen → Geräte & Dienste → Integration hinzufügen → „Amortix"**, dann einen Modus wählen. Jedes Feld im Dialog hat eine Inline-Beschreibung, die genau erklärt, was auszuwählen ist und warum.

| Modus | Pflicht-Sensoren | Optional | Rechnung |
|-------|------------------|----------|----------|
| **Direktverbrauch** (BKW/PV ohne Speicher) | Erzeugung (ein oder mehrere), Einspeisung/`to_grid` | Einspeisevergütung, Startgutschrift | `Eigenverbrauch × Strompreis + Einspeisung × Vergütung` |
| **Speicher** | Ladung, Entladung | Roundtrip-Wirkungsgrad-Sensor, Einspeisevergütung, Startgutschrift | `Entladung × Strompreis − Ladung × Vergütung` |

Beide Modi benötigen außerdem eine Entität für **Anschaffungskosten** und eine für den **Strompreis** (`input_number` oder Sensor — auch ein Live-Tarifsensor wie Tibber funktioniert).

Anforderungen an alle Sensoren:
- **Kumulierende kWh-Zähler** (`state_class: total`/`total_increasing`), keine Watt-Sensoren.
- Müssen **`device_class: energy`** gesetzt haben — der Entitäts-Picker listet nur Sensoren mit dieser Device-Class, ein Template-/Utility-Meter-Sensor ohne diese taucht erst nach Ergänzen auf.
- Einspeisung/Ladung/Entladung als tatsächliches Zähler-Register — kein vorzeichenbehafteter/Saldo-Wert, keine Phasenwerte.

**Anschaffungskosten, Strompreis und Einspeisevergütung lassen sich später ändern**, ohne die Historie zu verlieren: **Einstellungen → Geräte & Dienste → Amortix → Konfigurieren**. Die Erzeugungs-/Einspeisungs-/Lade-/Entlade-Sensoren und die Startgutschrift sind bei der Einrichtung fix und danach nicht mehr editierbar (sie legen die Rechnungsgrundlage fest).

---

## Sensoren

### Gemeinsam (beide Modi)

| Key | Name | Beschreibung |
|-----|------|--------------|
| `fortschritt` | Amortisation Fortschritt | Anteil der zurückgewonnenen Investition, 0–100 % (nach unten auf 0 %, nach oben auf 100 % gedeckelt). `unknown` ohne Investitionswert. |
| `verbleibend` | Amortisation verbleibend | Verbleibender Betrag (€) bis zur vollständigen Amortisation. |
| `tagesschnitt` | Ersparnis pro Tag | Durchschnittliche Tagesersparnis (€) seit Anwendung der Startgutschrift. `unknown` bei weniger als 12 Stunden Historie oder ohne Netto-Ersparnis. |
| `resttage` | Amortisation Restzeit | Geschätzte Resttage bis zur Amortisation, aus dem Tagesdurchschnitt. |
| `datum` | Amortisation Datum | Geschätztes Amortisations-Datum/-Uhrzeit, aus dem Tagesdurchschnitt. |

### Nur Direktverbrauch

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Gesamtersparnis (€): Netzbezugs-Ersparnis + Einspeise-Erlös, inklusive Startgutschrift. Attribute: `startgutschrift_eur`, `einsparung_seit_start_eur`, `erzeugung_kwh`, `eigenverbrauch_kwh`, `einspeisung_kwh`, `inbetriebnahme`. |
| `einsparung_netzbezug` | Einsparung Netzbezug | Ersparnis (€) durch Eigenverbrauch statt Netzbezug. |
| `einsparung_einspeisung` | Einsparung Einspeisung | Erlös (€) durch Einspeisung. |
| `eigenverbrauch` | Eigenverbrauch gesamt | Gesamter Eigenverbrauch (kWh). |

### Nur Speicher

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Speicher-Ersparnis gesamt | Gesamte Speicher-Ersparnis (€): Entladungswert minus entgangene Einspeisung durch Laden, inklusive Startgutschrift. Gleiche Attribute wie bei Direktverbrauch, angepasst auf `entladung_kwh`/`ladung_kwh`. |
| `entladung` | Entladung gesamt | Gesamt entladene Energie (kWh). |
| `ladung` | Ladung gesamt | Gesamt geladene Energie (kWh). |
| `roundtrip` | Roundtrip-Wirkungsgrad | Roundtrip-Wirkungsgrad (%) — aus konfiguriertem Sensor, falls gesetzt, sonst `Entladung ÷ Ladung`. Nicht auf 100 % gedeckelt (braucht mehrere volle Zyklen, bis er sich einschwingt); rein informativ, fließt nicht in die €-Berechnung ein. |

---

## Funktionsweise

Amortix schätzt nicht — es wertet alle 60 Sekunden die konfigurierten Sensoren aus und schreibt Fortschritt nur gut, wenn sich die zugrunde liegenden Zähler tatsächlich bewegt haben.

- **Monotone Buchführung.** Jeder kumulierende Sensor wird als stetig steigender Gesamtwert verfolgt, unabhängig davon, was der rohe Sensor selbst tut. Ein echter Zähler-Reset (Firmware-Update, Gerätewechsel — Wert fällt auf nahe null) wird erkannt und zählt ab dort weiter, ohne die Historie zu verlieren. Ein einmaliger Ausreißer in einer einzelnen Messung (z. B. kurz `0` statt `unavailable`) wird von einem echten Reset unterschieden, indem zwei aufeinanderfolgende niedrige Werte verlangt werden — ein sich erholender Sensor wird dadurch nicht doppelt gezählt.
- **Ersparnis bewegt sich nur vorwärts.** Jede 60-Sekunden-Auswertung addiert neu erzeugte/selbst verbrauchte/entladene Energie zum jeweils aktuell gültigen Preis — nichts wird je von Grund auf neu berechnet, ein späterer Wechsel der Preis-Entität schreibt vergangene Ersparnisse also nicht rückwirkend um.
- **Startgutschrift.** Für eine Anlage, die schon vor der Amortix-Einrichtung lief, wird einmalig bei der Einrichtung eine Startgutschrift berechnet — entweder aus manuell eingegebenen historischen kWh-Werten oder automatisch aus den aktuellen Zählerständen — und dem laufenden Gesamtwert hinzugefügt. Sie wird danach nie neu berechnet; die Sensor-/Preis-Entitäten lassen sich trotzdem später über **Konfigurieren** ändern, ohne sie zu beeinflussen.
- **Fortschritt kann nicht negativ werden.** Im Speicher-Modus kann eine Phase mit Laden ohne Entladen bei gesetzter Einspeisevergütung die Gesamtersparnis vorübergehend unter die Startgutschrift drücken. Der Amortisations-Fortschritt-Sensor ist trotzdem nach unten auf 0 % gedeckelt.

---

## Voraussetzungen

- **Home Assistant 2024.4** oder neuer
- Kumulierende kWh-Sensoren für Erzeugung/Einspeisung (Direktverbrauch) bzw. Ladung/Entladung (Speicher)
- `input_number`- oder Sensor-Entitäten für Anschaffungskosten und Strompreis

---

## Lizenz

MIT – siehe [LICENSE](LICENSE).
