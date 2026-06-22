# Amortix

Geräteunabhängige Amortisations-Berechnung für Home Assistant: Balkonkraftwerk, PV und
Batteriespeicher. Benötigt nur kumulierende kWh-Sensoren und Preise (als `input_number` oder
Sensor). Gemessen, sprungfrei und tauglich für dynamische Tarife (Tibber).

**Modi:** Direktverbrauch (Erzeugung + Einspeisung) und Speicher (Ladung + Entladung).
Mehrere Erzeuger summierbar, Roundtrip-Wirkungsgrad inklusive.
