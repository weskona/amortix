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
    timeLeft: "Restzeit",
    total: "Gesamt",
    entries: "Einträge",
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
    timeLeft: "Time left",
    total: "Total",
    entries: "entries",
    modes: {
      plant: "System", direct: "Direct use", storage: "Storage", combined: "PV + storage",
      wallbox: "Wallbox", generic: "General", heatpump: "Heat pump",
    },
    kinds: { pv: "Producer", storage: "Storage" },
  },
};

const STYLE = `
  :host { display: block; min-height: 100%; container-type: inline-size;
    --bg:#0b0d12; --line:rgba(255,255,255,.065); --tile:rgba(255,255,255,.032); --tileb:rgba(255,255,255,.07);
    --text:#f3f5f9; --muted:#8b91a1; --dim:#5d6373;
    --gold:#f7b733; --cyan:#38bdf8; --green:#34d399; --orange:#fb923c; --violet:#a78bfa;
    background: var(--bg); color: var(--text);
    font-family: 'Outfit','Plus Jakarta Sans','Segoe UI',system-ui,sans-serif; -webkit-font-smoothing: antialiased; }
  * { box-sizing: border-box; }
  header { display: flex; align-items: center; gap: 12px; padding: 14px 22px 0; }
  header h1 { font-size: 15px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 0; }
  header button { display: none; width: 40px; height: 40px; border-radius: 14px; background: rgba(255,255,255,.05);
    border: 1px solid var(--line); color: var(--text); font-size: 20px; cursor: pointer; }
  :host([narrow]) header button { display: block; }
  .wrap { padding: 14px 22px 28px; max-width: 1400px; margin: 0 auto; }
  .panel { background: linear-gradient(180deg,#161920,#12151b); border: 1px solid var(--line); border-radius: 30px;
    padding: 20px 22px; position: relative; overflow: hidden; }
  .hd { display: flex; align-items: center; gap: 12px; min-height: 40px; margin-bottom: 14px; }
  .ttl { font-size: 15px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
  .lbl { margin-left: auto; font-size: 15px; color: rgba(243,245,249,.78); white-space: nowrap; }
  .lbl.ok { color: var(--green); font-weight: 600; }
  .sub { color: var(--dim); font-size: 13px; margin: -8px 0 14px; }
  .hero { display: grid; grid-template-columns: 170px 1fr; gap: 22px; align-items: center; margin-bottom: 20px; }
  .ring { position: relative; width: 170px; height: 170px; }
  .ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring .track { stroke: rgba(255,255,255,.07); }
  .ring .arc { stroke: url(#g); transition: stroke-dashoffset .8s ease; }
  .ring .c { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .ring .c b { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .ring .c span { font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
  .stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 8px; }
  .stat { display: flex; flex-direction: column; gap: 2px; padding: 9px 11px; border-radius: 15px;
    background: var(--tile); border: 1px solid var(--tileb); min-width: 0; }
  .stat span { font-size: 11.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .stat b { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .stat.gold b { color: var(--gold); } .stat.green b { color: var(--green); } .stat.cyan b { color: var(--cyan); }
  .bar { height: 10px; border-radius: 6px; overflow: hidden; background: rgba(255,255,255,.07); margin: 0 0 14px; }
  .bar i { display: block; height: 100%; border-radius: 6px; background: linear-gradient(90deg, var(--cyan), var(--green));
    transition: width .8s ease; }
  .bar.done i { background: var(--green); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 20px; }
  .devices { margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
  .dev { border-radius: 16px; background: var(--tile); border: 1px solid var(--tileb); padding: 10px 14px; }
  .dev .top { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .dev .top b { font-weight: 600; font-size: 15px; }
  .dev .top small { color: var(--dim); font-size: 12px; letter-spacing: .06em; text-transform: uppercase; }
  .dev .top em { margin-left: auto; font-style: normal; font-weight: 700; font-variant-numeric: tabular-nums; }
  .dev .bar { height: 6px; margin-bottom: 8px; }
  .dev .stats { grid-template-columns: repeat(3, minmax(0,1fr)); }
  .dev .stat { padding: 6px 9px; border-radius: 12px; } .dev .stat b { font-size: 14px; }
  .dev .stat span { font-size: 10.5px; }
  .msg { text-align: center; color: var(--dim); padding: 64px 16px; font-size: 15px; }
  @container (max-width: 720px) {
    .wrap { padding: 12px 12px 24px; } .grid { grid-template-columns: 1fr; }
    .hero { grid-template-columns: 1fr; justify-items: center; } .hero .stats { width: 100%; }
    .stat b { font-size: 16.5px; } .dev .stats { grid-template-columns: repeat(2, minmax(0,1fr)); }
  }
`;

// @font-face wirkt nicht im Shadow DOM, daher einmalig im Seitenkopf (Outfit, SIL OFL 1.1)
if (!document.getElementById("amortix-font")) {
  const font = document.createElement("style");
  font.id = "amortix-font";
  font.textContent = `@font-face{font-family:"Outfit";font-style:normal;font-display:swap;font-weight:100 900;` +
    `src:url(/amortix_panel/outfit.woff2) format("woff2")}`;
  document.head.appendChild(font);
}

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
    return this._date(m.payback_date);
  }

  _daysText(m) {
    if (m.remaining_days === null || m.remaining_days === undefined || !m.payback_date) return "";
    return `${new Intl.NumberFormat(this._lang).format(m.remaining_days)} ${this._t.days}`;
  }

  _bar(m) {
    const pct = Math.max(0, Math.min(m.progress ?? 0, 100));
    const done = m.progress !== null && m.progress >= 100;
    return `<div class="bar ${done ? "done" : ""}"><i style="width:${pct}%"></i></div>`;
  }

  _stat(label, value, cls = "") {
    return `<div class="stat ${cls}"><span>${label}</span><b>${value}</b></div>`;
  }

  _stats(m, devices = false) {
    const t = this._t;
    const items = [
      this._stat(t.savings, this._money(m.savings), "gold"),
      this._stat(t.invest, this._money(m.investment)),
      this._stat(t.remaining, this._money(m.remaining)),
      this._stat(t.perDay, this._money(m.daily_average), "green"),
      this._stat(t.payback, this._paybackText(m), "cyan"),
    ];
    if (!devices) items.push(this._stat(t.timeLeft, this._daysText(m) || t.unknown));
    return `<div class="stats">${items.join("")}</div>`;
  }

  _ring(pct) {
    const r = 74, c = 2 * Math.PI * r;
    const v = Math.max(0, Math.min(pct ?? 0, 100));
    return `<div class="ring"><svg viewBox="0 0 170 170">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#34d399"/></linearGradient></defs>
      <circle class="track" cx="85" cy="85" r="${r}" fill="none" stroke-width="12"/>
      <circle class="arc" cx="85" cy="85" r="${r}" fill="none" stroke-width="12" stroke-linecap="round"
        stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - v / 100)}"/></svg>
      <div class="c"><b>${this._pct(pct)}</b><span>${this._t.progress}</span></div></div>`;
  }

  _entryCard(e) {
    const t = this._t;
    const mode = t.modes[e.mode] || e.mode;
    const done = e.progress !== null && e.progress >= 100;
    const devices = (e.devices || []).map((d) => `
      <div class="dev">
        <div class="top"><b>${this._esc(d.name)}</b><small>${t.kinds[d.kind] || d.kind}</small><em>${this._pct(d.progress)}</em></div>
        ${this._bar(d)}
        ${this._stats(d, true)}
      </div>`).join("");
    return `<section class="panel">
      <div class="hd"><span class="ttl">${this._esc(e.title)}</span>
        <span class="lbl ${done ? "ok" : ""}">${this._pct(e.progress)}</span></div>
      <div class="sub">${this._esc(mode)}${e.start_time ? ` · ${t.since} ${this._date(e.start_time)}` : ""}</div>
      ${this._bar(e)}
      ${this._stats(e)}
      ${devices ? `<div class="devices">${devices}</div>` : ""}
    </section>`;
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
      body = `<section class="panel" style="margin-bottom:20px">
          <div class="hd"><span class="ttl">${t.total}</span>
            <span class="lbl">${this._data.entries.length} ${t.entries}</span></div>
          <div class="hero">${this._ring(tot.progress)}${this._stats(tot)}</div>
        </section>
        <div class="grid">${this._data.entries.map((e) => this._entryCard(e)).join("")}</div>`;
    }
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <header><button id="menu" aria-label="Menu">☰</button><h1>${t.title}</h1></header>
      <div class="wrap">${body}</div>`;
    this.shadowRoot.getElementById("menu").addEventListener("click", () =>
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }))
    );
  }
}

customElements.define("amortix-panel", AmortixPanel);
