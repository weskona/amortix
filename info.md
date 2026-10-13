# Amortix

Geräteunabhängige Amortisations-Berechnung für Home Assistant: Balkonkraftwerk, PV,
Batteriespeicher, Wallbox/E-Auto und Wärmepumpe. Benötigt nur kumulierende kWh-Sensoren und Preise (als `input_number` oder
Sensor). Gemessen, sprungfrei und tauglich für dynamische Tarife (Tibber).

**Modi:** Anlage (mehrere Erzeuger und Speicher, Kosten je Gerät, inkl. Netzladung), Direktverbrauch,
Speicher, Wallbox/E-Auto, Wärmepumpe, allgemeiner Vergleich und Gesamtübersicht mit Breakdown. Mehrere Erzeuger summierbar, Roundtrip-Wirkungsgrad inklusive.
