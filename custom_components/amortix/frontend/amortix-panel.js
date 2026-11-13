/* Amortix – Seitenleisten-Panel (ohne Build-Schritt, reines Web Component) */
const I18N = {
  de: {
    title: "Amortix",
    invest: "Investition",
    savings: "Ersparnis",
    remaining: "Verbleibend",
    progress: "Fortschritt",
    perDay: "Ø pro Tag",
    payback: "Amortisation",
    days: "Tage",
    empty: "Noch keine Amortix-Einträge. Lege unter Einstellungen → Geräte & Dienste einen Eintrag an.",
    loading: "Lade …",
    error: "Daten konnten nicht geladen werden.",
    devices: "Geräte",
    since: "seit",
    unknown: "–",
    paid: "Amortisiert",
    modes: {
      plant: "Anlage", direct: "Direktverbrauch", storage: "Speicher", combined: "PV + Speicher",
      wallbox: "Wallbox", generic: "Allgemein", heatpump: "Wärmepumpe",
    },
    kinds: { pv: "Erzeuger", storage: "Speicher" },
  },
  en: {
    title: "Amortix",
    invest: "Investment",
    savings: "Savings",
    remaining: "Remaining",
    progress: "Progress",
    perDay: "Avg per day",
    payback: "Payback",
    days: "days",
    empty: "No Amortix entries yet. Add one under Settings → Devices & services.",
    loading: "Loading …",
    error: "Could not load data.",
    devices: "Devices",
    since: "since",
    unknown: "–",
    paid: "Paid back",
    modes: {
      plant: "System", direct: "Direct use", storage: "Storage", combined: "PV + storage",
      wallbox: "Wallbox", generic: "General", heatpump: "Heat pump",
    },
    kinds: { pv: "Producer", storage: "Storage" },
  },
};

const STYLE = `
  :host { display: block; background: var(--primary-background-color); color: var(--primary-text-color);
          min-height: 100%; font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  header { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--app-header-background-color, var(--primary-color));
           color: var(--app-header-text-color, #fff); position: sticky; top: 0; z-index: 2; }
  header h1 { font-size: 20px; font-weight: 400; margin: 0; flex: 1; }
  header button { background: none; border: 0; color: inherit; cursor: pointer; font-size: 24px; line-height: 1; display: none; }
  :host([narrow]) header button { display: block; }
  main { max-width: 1100px; margin: 0 auto; padding: 16px; box-sizing: border-box; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .tile, .card { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px);
                 box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
  .tile { padding: 14px 16px; }
  .tile .label { font-size: 12px; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em; }
  .tile .value { font-size: 22px; font-weight: 500; margin-top: 4px; font-variant-numeric: tabular-nums; }
  .card { padding: 16px; margin-bottom: 16px; }
  .card h2 { font-size: 17px; font-weight: 500; margin: 0; }
  .sub { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; }
  .row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  .bar { height: 10px; border-radius: 5px; background: var(--divider-color, #ddd); overflow: hidden; margin: 12px 0 6px; }
  .bar > div { height: 100%; background: var(--primary-color); border-radius: 5px; transition: width .6s ease; }
  .bar.done > div { background: var(--success-color, #43a047); }
  .meta { display: flex; flex-wrap: wrap; gap: 4px 20px; font-size: 14px; font-variant-numeric: tabular-nums; }
  .meta span b { font-weight: 500; }
  .devices { margin-top: 14px; border-top: 1px solid var(--divider-color, #ddd); padding-top: 10px; }
  .devices h3 { font-size: 12px; font-weight: 500; text-transform: uppercase; color: var(--secondary-text-color); margin: 0 0 6px; letter-spacing: .04em; }
  .device { padding: 8px 0; }
  .device + .device { border-top: 1px dashed var(--divider-color, #ddd); }
  .device .bar { height: 6px; margin: 6px 0 4px; }
  .msg { text-align: center; color: var(--secondary-text-color); padding: 48px 16px; }
`;

class AmortixPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = false;
    this._unsub = null;
    this._connected = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this._lang = (hass.language || "en").startsWith("de") ? "de" : "en";
    if (first) {
      this._render();
      if (this._connected) this._subscribe();
    }
  }

  set narrow(value) {
    this.toggleAttribute("narrow", !!value);
  }

  set panel(_panel) {}

  connectedCallback() {
    this._connected = true;
    if (this._hass) this._subscribe();
  }

  disconnectedCallback() {
    this._connected = false;
    if (this._unsub) {
      this._unsub.then((u) => u()).catch(() => {});
      this._unsub = null;
    }
  }

  _subscribe() {
    if (this._unsub || !this._hass) return;
    this._unsub = this._hass.connection.subscribeMessage(
      (data) => {
        this._data = data;
        this._error = false;
        this._render();
      },
      { type: "amortix/subscribe" }
    );
    this._unsub.catch(() => {
      this._unsub = null;
      this._error = true;
      this._render();
    });
  }

  get _t() {
    return I18N[this._lang || "en"];
  }

  _money(value) {
    if (value === null || value === undefined) return this._t.unknown;
    return new Intl.NumberFormat(this._hass?.locale?.language || this._lang, {
      style: "currency", currency: "EUR",
    }).format(value);
  }

  _pct(value) {
    if (value === null || value === undefined) return this._t.unknown;
    return `${new Intl.NumberFormat(this._lang, { maximumFractionDigits: 1 }).format(value)} %`;
  }

  _date(iso) {
    if (!iso) return this._t.unknown;
    return new Date(iso).toLocaleDateString(this._hass?.locale?.language || this._lang, {
      year: "numeric", month: "short", day: "numeric",
    });
  }

  _esc(text) {
    const el = document.createElement("div");
    el.textContent = text ?? "";
    return el.innerHTML;
  }

  _paybackText(m) {
    if (m.remaining === 0 && m.investment) return this._t.paid;
    if (!m.payback_date) return this._t.unknown;
    const days = m.remaining_days !== null && m.remaining_days !== undefined
      ? ` (${new Intl.NumberFormat(this._lang).format(m.remaining_days)} ${this._t.days})` : "";
    return `${this._date(m.payback_date)}${days}`;
  }

  _bar(m) {
    const pct = Math.max(0, Math.min(m.progress ?? 0, 100));
    const done = m.progress !== null && m.progress >= 100;
    return `<div class="bar ${done ? "done" : ""}"><div style="width:${pct}%"></div></div>`;
  }

  _meta(m) {
    const t = this._t;
    return `<div class="meta">
      <span>${t.savings}: <b>${this._money(m.savings)}</b></span>
      <span>${t.invest}: <b>${this._money(m.investment)}</b></span>
      <span>${t.remaining}: <b>${this._money(m.remaining)}</b></span>
      <span>${t.perDay}: <b>${this._money(m.daily_average)}</b></span>
      <span>${t.payback}: <b>${this._paybackText(m)}</b></span>
    </div>`;
  }

  _entryCard(e) {
    const t = this._t;
    const mode = t.modes[e.mode] || e.mode;
    const devices = (e.devices || []).map((d) => `
      <div class="device">
        <div class="row"><span>${this._esc(d.name)} <span class="sub">· ${t.kinds[d.kind] || d.kind}</span></span>
          <b>${this._pct(d.progress)}</b></div>
        ${this._bar(d)}
        ${this._meta(d)}
      </div>`).join("");
    return `<div class="card">
      <div class="row"><div><h2>${this._esc(e.title)}</h2>
        <div class="sub">${this._esc(mode)}${e.start_time ? ` · ${t.since} ${this._date(e.start_time)}` : ""}</div></div>
        <b>${this._pct(e.progress)}</b></div>
      ${this._bar(e)}
      ${this._meta(e)}
      ${devices ? `<div class="devices"><h3>${t.devices}</h3>${devices}</div>` : ""}
    </div>`;
  }

  _render() {
    if (!this._hass) return;
    const t = this._t;
    let body;
    if (this._error) {
      body = `<div class="msg">${t.error}</div>`;
    } else if (!this._data) {
      body = `<div class="msg">${t.loading}</div>`;
    } else if (!this._data.entries.length) {
      body = `<div class="msg">${t.empty}</div>`;
    } else {
      const tot = this._data.total;
      body = `
        <div class="tiles">
          <div class="tile"><div class="label">${t.savings}</div><div class="value">${this._money(tot.savings)}</div></div>
          <div class="tile"><div class="label">${t.invest}</div><div class="value">${this._money(tot.investment)}</div></div>
          <div class="tile"><div class="label">${t.remaining}</div><div class="value">${this._money(tot.remaining)}</div></div>
          <div class="tile"><div class="label">${t.progress}</div><div class="value">${this._pct(tot.progress)}</div></div>
          <div class="tile"><div class="label">${t.perDay}</div><div class="value">${this._money(tot.daily_average)}</div></div>
          <div class="tile"><div class="label">${t.payback}</div><div class="value">${tot.remaining === 0 && tot.investment ? t.paid : this._date(tot.payback_date)}</div></div>
        </div>
        ${this._bar(tot)}
        ${this._data.entries.map((e) => this._entryCard(e)).join("")}`;
    }
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <header><button id="menu" aria-label="Menu">☰</button><h1>${t.title}</h1></header>
      <main>${body}</main>`;
    this.shadowRoot.getElementById("menu").addEventListener("click", () =>
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }))
    );
  }
}

customElements.define("amortix-panel", AmortixPanel);
