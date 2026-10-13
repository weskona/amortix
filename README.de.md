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
- **Sieben Modi** — Anlage (große PV, Balkonkraftwerke und ein oder mehrere Speicher an einem Netzanschluss, **Kosten und Amortisation je Gerät**), Direktverbrauch, Speicher, Wallbox/E-Auto, Wärmepumpe, ein allgemeiner Vergleich und eine **Gesamtübersicht**, die alle Einträge mit vollständigem Breakdown zusammenfasst.
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
| **Anlage** | Ein Zähler je Erzeuger, eine Einspeisung, je Speicher Ladung + Entladung | Einspeisevergütung, Kosten-Entität je Gerät, Startwerte | `(Σ Erzeugung − Einspeisung − Σ Ladung + Σ Entladung) × Strompreis + Einspeisung × Vergütung`, aufgeteilt je Gerät (siehe unten) |
| **Wallbox / E-Auto** | Geladene Energie | Eigener Preis, Startgutschrift | `kWh × (Vergleichspreis − eigener Preis)` |
| **Wärmepumpe** | Wärme (kWh), Stromverbrauch (kWh) | Startgutschrift | `Wärme × Referenzpreis − Strom × Strompreis` |
| **Allgemein** | Ein kWh-Zähler | Eigener Preis, Startgutschrift | `kWh × (Vergleichspreis − eigener Preis)` |
| **Gesamtübersicht** | — (nutzt alle anderen Einträge) | — | Summe aller Einträge plus Breakdown je Gerät |

Alle Modi außer Anlage (Kosten je Gerät) und Gesamtübersicht benötigen außerdem eine Entität für **Anschaffungskosten**. Direktverbrauch, Speicher und Anlage brauchen einen **Strompreis**, Wallbox/Allgemein einen **Vergleichspreis** (was dieselbe kWh sonst kosten würde, z. B. öffentliche Ladesäule oder Kraftstoff pro kWh) und optional einen **eigenen Preis**, die Wärmepumpe einen Strompreis und einen **Referenzpreis pro kWh Wärme** (z. B. Gaspreis ÷ Kesselwirkungsgrad).

Alle Preis-Entitäten können ein `input_number`, ein `number` oder ein Sensor sein — **auch dynamische Tarife** wie Tibber, die jede Minute live gelesen werden. Preise in **ct/kWh werden automatisch in €/kWh umgerechnet**; fällt ein Sensor kurz aus, gilt der letzte bekannte Preis.

### Anlage: mehrere Erzeuger und Speicher an einem Netzanschluss

Dieser Modus ist für alles gedacht, was an **einem Netzanschluss** hängt — z. B. eine große PV mit DC-Speicher, zwei Balkonkraftwerke und später ein zusätzlicher AC-Speicher. Er vermeidet einen typischen Fehler: Der Einspeisezähler gehört zum ganzen Anschluss, getrennte Einträge je Erzeuger würden jeweils die komplette Einspeisung abziehen.

Die Einrichtung fragt den Erzeugungszähler **jedes Erzeugers einzeln** ab (jedes Balkonkraftwerk für sich), **einen** Einspeisezähler und den Strompreis, danach je Erzeuger und je Speicher einen Namen, die **Kosten-Entität** und einen optionalen **Startwert**. Speicher kannst du beliebig viele hinzufügen (DC oder AC; jeder braucht eigene Lade- und Entlade-Zähler und darf nicht in den Erzeugungssensoren stecken).

**Gesamt:** `(Σ Erzeugung − Einspeisung − Σ Ladung + Σ Entladung) × Strompreis + Einspeisung × Vergütung`. Jede Komponente wird zum jeweils aktuellen Preis bewertet. Ladeverluste kosten so automatisch den Strompreis, und **Laden aus dem Netz** (günstiger Nachttarif) ist korrekt abgebildet: Die Ladung kostet beim Laden, die Entladung bringt beim Entladen den dann gültigen Preis.

**Aufteilung je Gerät** (die Teile ergeben immer die Gesamtersparnis):
- Die Erzeuger teilen sich `(Σ Erzeugung − Einspeisung − Σ Ladung) × Strompreis + (Einspeisung + Σ Ladung) × Vergütung` **nach ihrem Anteil an der Erzeugung**.
- Jeder Speicher bekommt `Entladung × Strompreis − Ladung × Vergütung`.

Jedes Gerät bekommt eigene Sensoren *Einsparung*, *Amortisation Fortschritt*, *verbleibend*, *Ersparnis pro Tag*, *Restzeit* und *Datum*; der Fortschritt des Eintrags nutzt die Summe aller Gerätekosten. Die Kosten lassen sich später über **Konfigurieren** ändern.

**Startwerte bei bereits laufenden Anlagen:** Gib je Gerät die bisher aufgelaufene Ersparnis als Euro-Betrag an (je Erzeuger/Speicher). Zusätzlich kann der Eintrag eine Startgutschrift automatisch aus den aktuellen Zählerständen berechnen (aufgeteilt auf die Geräte wie oben) und/oder einen Pauschalbetrag aufnehmen. Die automatische Gutschrift und einen Betrag je Gerät nicht für dieselbe Energie verwenden.

### Gesamtübersicht

Die **Gesamtübersicht** einmal anlegen, um **alle anderen Amortix-Einträge** zusammenzufassen: *Einsparung gesamt*, *Investition gesamt*, Fortschritt, Restbetrag, Ersparnis pro Tag, Restzeit und Datum. Der Sensor *Einsparung gesamt* trägt den vollständigen Breakdown im Attribut `geraete`: eine Liste mit Name, Typ, Investition, Ersparnis, Fortschritt und Restbetrag für jedes Gerät (und eine Zeile für pauschale Startgutschriften). Neue Einträge werden automatisch einbezogen.

Anforderungen an alle Sensoren:
- **Kumulierende kWh-Zähler** (`state_class: total`/`total_increasing`), keine Watt-Sensoren.
- Müssen **`device_class: energy`** gesetzt haben — der Entitäts-Picker listet nur Sensoren mit dieser Device-Class, ein Template-/Utility-Meter-Sensor ohne diese taucht erst nach Ergänzen auf.
- Müssen **kWh** liefern. Die Einrichtung lehnt Sensoren mit anderer Einheit (Wh, MWh, …) ab, weil sie um den Faktor 1000 falsch rechnen würden; vorher umrechnen (Template oder Utility-Meter).
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

### Nur Anlage

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Gesamtersparnis (€) inklusive Startgutschrift. Attribute: `startgutschrift_eur`, `einsparung_seit_start_eur`, `erzeugung_kwh`, `einspeisung_kwh`, `ladung_kwh`, `entladung_kwh`, `geraete` (Breakdown je Gerät), `inbetriebnahme`. |
| `einsparung_netzbezug` | Einsparung Netzbezug | Ersparnis (€) durch vermiedenen Netzbezug (Eigenversorgung inkl. Speicher, abzüglich Ladung). |
| `einsparung_einspeisung` | Einsparung Einspeisung | Erlös (€) durch Einspeisung. |
| `eigenverbrauch` | Eigenverbrauch gesamt | Σ Erzeugung − Einspeisung (kWh), enthält die in Speicher geladene Energie. |
| `erzeugung`, `ladung`, `entladung` | Erzeugung / Ladung / Entladung gesamt | Gesamtenergie (kWh); Ladung/Entladung nur mit konfiguriertem Speicher. |
| `roundtrip` | Roundtrip-Wirkungsgrad | `Σ Entladung ÷ Σ Ladung` (%). |
| `einsparung_<Gerät>` | Einsparung *Gerät* | Diesem Erzeuger/Speicher zugerechnete Ersparnis (€). Attribute: `investition_eur`, `startgutschrift_eur`, `einsparung_seit_start_eur`. |
| `fortschritt_<Gerät>`, `verbleibend_<Gerät>`, `tagesschnitt_<Gerät>`, `resttage_<Gerät>`, `datum_<Gerät>` | Amortisation … *Gerät* | Fortschritt, Restbetrag, Ersparnis pro Tag, Restzeit und Datum je Gerät (benötigen die Kosten-Entität des Geräts). |

### Nur Gesamtübersicht

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Summe der Ersparnis aller anderen Einträge. Attribute: `eintraege`, `startgutschrift_eur`, `einsparung_seit_start_eur`, `geraete` (Liste: Name, Modus, Investition, Ersparnis, Fortschritt, Restbetrag je Gerät; pauschale Startgutschriften als eine Extra-Zeile), `inbetriebnahme` (frühester Start). |
| `investition` | Investition gesamt | Summe aller Investitionen (€). |
| *gemeinsame Sensoren* | | Fortschritt, Restbetrag, Ersparnis pro Tag, Restzeit und Datum für das Ganze. |

### Nur Wallbox / E-Auto und Allgemein

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Gesamtersparnis (€) inklusive Startgutschrift. |
| `energie` | Energie gesamt | Gesamtenergie (kWh). |

### Nur Wärmepumpe

| Key | Name | Beschreibung |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Gesamtersparnis (€) inklusive Startgutschrift. |
| `einsparung_waerme` | Einsparung Wärme | Wert (€) der Wärme gegenüber der Referenzheizung. |
| `stromkosten` | Stromkosten Wärmepumpe | Stromkosten (€, negativ). |
| `waerme`, `strom` | Wärme / Strom gesamt | Gesamte Wärme und Strom (kWh). |
| `jaz` | Arbeitszahl | `Wärme ÷ Strom`. |

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

- **Monotone Buchführung.** Jeder kumulierende Sensor wird als stetig steigender Gesamtwert verfolgt, unabhängig davon, was der rohe Sensor selbst tut. Ein echter Zähler-Reset (Firmware-Update, Gerätewechsel — Wert fällt unter die Hälfte des letzten Stands) wird erkannt und zählt ab dort weiter, ohne die Historie zu verlieren. Ein Reset wird erst nach zwei aufeinanderfolgenden niedrigen Werten bestätigt, damit ein kurzer Ausreißer (z. B. kurz `0` statt `unavailable`) nicht als Reset gilt. Hält ein Glitch so lange an, dass er als Reset bestätigt wird, und springt der Zähler innerhalb weniger Updates auf den alten Stand zurück, wird die Fehlbuchung zurückgenommen — die Historie wird nie doppelt gezählt. Kleinere Rücksprünge (Rundung, geringe Korrekturen) werden ignoriert.
- **Ersparnis bewegt sich nur vorwärts.** Jede 60-Sekunden-Auswertung addiert neu erzeugte/selbst verbrauchte/entladene Energie zum jeweils aktuell gültigen Preis — nichts wird je von Grund auf neu berechnet, ein späterer Wechsel der Preis-Entität schreibt vergangene Ersparnisse also nicht rückwirkend um.
- **Startgutschrift.** Für eine Anlage, die schon vor der Amortix-Einrichtung lief, wird einmalig bei der Einrichtung eine Startgutschrift berechnet — entweder aus manuell eingegebenen historischen kWh-Werten oder automatisch aus den aktuellen Zählerständen — und dem laufenden Gesamtwert hinzugefügt. Ist beim ersten Start ein Sensor, der Strompreis oder die Einspeisevergütung nicht verfügbar, wird die Gutschrift nicht still mit 0 angesetzt: Sie wird zurückgestellt (`initial_pending`, Warnung im Log) und berechnet, sobald alles lesbar ist — auf Basis der Zählerstände beim ersten Lesen. Sie wird danach nie neu berechnet; die Sensor-/Preis-Entitäten lassen sich trotzdem später über **Konfigurieren** ändern, ohne sie zu beeinflussen.
- **Fortschritt kann nicht negativ werden.** Im Speicher-Modus kann eine Phase mit Laden ohne Entladen bei gesetzter Einspeisevergütung die Gesamtersparnis vorübergehend unter die Startgutschrift drücken. Der Amortisations-Fortschritt-Sensor ist trotzdem nach unten auf 0 % gedeckelt. Aus demselben Grund kann auch die Speicher-Startgutschrift negativ sein (z. B. viel geladen, bisher wenig entladen); sie entspricht immer der Summe ihrer Aufschlüsselungs-Attribute.


### Grenzen

- **Speicher: Netzladung wird nicht bepreist.** Die Speicher-Rechnung geht davon aus, dass der Akku aus eigenem PV-Überschuss geladen wird: Geladene Energie „kostet" nur die entgangene Einspeisevergütung. Wird zusätzlich aus dem Netz geladen (dynamischer Tarif, Nachtstrom), werden die Kosten dieses Stroms **nicht** abgezogen und die Ersparnis fällt zu hoch aus. Dafür den Modus **Anlage** verwenden, der Netzladung berücksichtigt.
- **Prognose ist linear.** *Ersparnis pro Tag*, *Restzeit* und *Datum* extrapolieren den Durchschnitt seit der Einrichtung. Bei PV ist der Ertrag stark saisonal, ein Start im Winter oder Sommer verzerrt die Schätzung; nach einem vollen Jahr wird sie belastbarer.
- **Negative Preise.** Wird die Preis-Entität negativ (dynamische Tarife), wird Eigenverbrauch ebenfalls negativ bewertet.
- **Anlage: Batterie speist ins Netz.** Exportiert eine Batterie ins Netz, zählt das zur Einspeisung und wird mit der Vergütung statt dem Strompreis bewertet.
- **Anlage: Aufteilung je Gerät ist eine Zurechnung.** Die Erzeuger teilen den Pool nach Erzeugungsanteil (ein Balkonkraftwerk mit 10 % der Erzeugung bekommt 10 % der gepoolten Ersparnis); das ist keine Messung je Gerät. Netzladung ist in der Summe korrekt, wird in der Aufteilung aber dem Speicher gutgeschrieben, ein auch netzgeladener Speicher sieht also besser aus als ein nur PV-geladener. Bei der Wallbox nicht *eigener Preis* = 0 für PV-Laden ansetzen — dieselbe kWh würde doppelt zählen; den Strompreis verwenden.
- **Zähler-Resets.** Ein Reset, der den Wert um weniger als die Hälfte senkt (z. B. 12 → 8 kWh), gilt als normale Korrektur und wird nicht erkannt — jeden mäßigen Rücksprung als Reset zu behandeln würde Energie doppelt zählen.
- **Einheiten.** Preis-Entitäten müssen €/kWh liefern (nicht ct/kWh), Energie-Sensoren kWh.
---

## Voraussetzungen

- **Home Assistant 2024.4** oder neuer
- Kumulierende kWh-Sensoren für Erzeugung/Einspeisung (Direktverbrauch) bzw. Ladung/Entladung (Speicher)
- `input_number`- oder Sensor-Entitäten für Anschaffungskosten und Strompreis

---

## Lizenz

MIT – siehe [LICENSE](LICENSE).
