# Amortix

Geräteunabhängige Amortisations-Berechnung für Home Assistant: Balkonkraftwerk, PV,
Batteriespeicher, Wallbox/E-Auto und Wärmepumpe. Benötigt nur kumulierende kWh-Sensoren und Preise (als `input_number` oder
Sensor). Gemessen, sprungfrei und tauglich für dynamische Tarife (Tibber).

**Modi:** Direktverbrauch, Speicher, PV mit Speicher (kombiniert, inkl. Netzladung), Wallbox/E-Auto,
Wärmepumpe und ein allgemeiner Vergleich. Mehrere Erzeuger summierbar, Roundtrip-Wirkungsgrad inklusive.
