"""Konstanten für die Amortisations-Integration."""

DOMAIN = "amortix"
PLATFORMS = ["sensor"]

# Anwendungsfall
CONF_MODE = "mode"
MODE_DIRECT = "direct"     # Direktverbrauch (BKW/PV ohne Speicher)
MODE_STORAGE = "storage"   # Speicher (Lade-/Entladebilanz)
MODE_COMBINED = "combined"   # PV + Speicher in einem Eintrag (alt, nur noch für bestehende Einträge)
MODE_PLANT = "plant"        # Anlage: beliebig viele Erzeuger und Speicher, Kosten je Gerät
MODE_OVERVIEW = "overview"   # Gesamtübersicht über alle Amortix-Einträge
MODE_WALLBOX = "wallbox"     # Wallbox / E-Auto
MODE_HEATPUMP = "heatpump"   # Wärmepumpe
MODE_GENERIC = "generic"     # Allgemein: kWh-Zähler gegen Vergleichspreis

# Sensoren – Direktverbrauch
CONF_PRODUCTION_SENSOR = "production_sensor"   # PV-Erzeugung (kWh)
CONF_TO_GRID_SENSOR = "to_grid_sensor"         # Einspeisung / to_grid (kWh)

# Sensoren – Speicher
CONF_CHARGE_SENSOR = "charge_sensor"           # Ladung (kWh)
CONF_DISCHARGE_SENSOR = "discharge_sensor"     # Entladung (kWh)
CONF_ROUNDTRIP_ENTITY = "roundtrip_entity"     # optional: vorhandener η-Sensor (%)

# Sensoren – Wallbox / Allgemein / Wärmepumpe
CONF_ENERGY_SENSOR = "energy_sensor"           # geladene/verbrauchte kWh
CONF_HEAT_SENSOR = "heat_sensor"               # erzeugte Wärme (kWh)
CONF_ELECTRIC_SENSOR = "electric_sensor"       # Stromverbrauch der Wärmepumpe (kWh)

# Anlage (Modus system): Geräteliste
CONF_DEVICES = "devices"        # [{sensor, name, investment_entity}] je Erzeuger
CONF_STORAGES = "storages"      # [{name, charge_sensor, discharge_sensor, investment_entity}]

# Live-Werte (Entität: input_number oder Sensor)
CONF_INVESTMENT_ENTITY = "investment_entity"   # Anschaffungskosten (€)        Pflicht
CONF_PRICE_ENTITY = "price_entity"             # Strompreis Netzbezug (€/kWh)  Pflicht
CONF_FEED_IN_ENTITY = "feed_in_entity"         # Einspeisevergütung (€/kWh)    optional -> 0
CONF_REFERENCE_PRICE_ENTITY = "reference_price_entity"  # Vergleichspreis (€/kWh)  Wallbox/Allgemein/Wärmepumpe
CONF_OWN_PRICE_ENTITY = "own_price_entity"     # eigener Preis (€/kWh)         Wallbox/Allgemein, optional -> 0

# Startgutschrift (nur einmalig bei der Einrichtung wirksam)
CONF_INITIAL_AUTO = "initial_auto"
CONF_INITIAL_SELF_KWH = "initial_self_kwh"         # Direktverbrauch: bisher selbst verbraucht
CONF_INITIAL_EXPORT_KWH = "initial_export_kwh"     # Direktverbrauch: bisher eingespeist
CONF_INITIAL_DISCHARGE_KWH = "initial_discharge_kwh"  # Speicher: bisher entladen
CONF_INITIAL_CHARGE_KWH = "initial_charge_kwh"        # Speicher: bisher geladen
CONF_INITIAL_PRICE = "initial_price"               # bisheriger Ø-Strompreis (optional)
CONF_INITIAL_FEED_IN = "initial_feed_in"           # bisherige Ø-Vergütung (optional)
CONF_INITIAL_SAVINGS = "initial_savings"           # pauschaler Euro-Betrag zusätzlich

EVALUATION_INTERVAL = 60  # Sekunden

SIGNAL_MANAGERS_CHANGED = "amortix_managers_changed"

STORAGE_VERSION = 1
SAVE_DELAY = 15

INVALID_STATES = (None, "unknown", "unavailable", "")
