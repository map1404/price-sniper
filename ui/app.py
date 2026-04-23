"""
ui/app.py
Streamlit demo interface for the Price Drop Sniper Agent.
Run with: streamlit run ui/app.py
"""

import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def verdict_meta(verdict: str) -> tuple[str, str]:
    mapping = {
        "BUY NOW": ("verdict-buy", "The market is giving you a strong enough window to act now."),
        "WAIT": ("verdict-wait", "The setup is promising, but timing still favors patience."),
        "AVOID": ("verdict-avoid", "Current pricing quality is weak and the downside is not justified."),
    }
    return mapping.get(verdict, ("verdict-wait", "The setup is promising, but timing still favors patience."))


def format_money(value: float | int | str | None) -> str:
    if value in (None, "", "N/A"):
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return str(value)


def summary_tile(label: str, value: str, note: str) -> str:
    return f"""
    <div class="summary-tile">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{note}</small>
    </div>
    """


def stat_tile(label: str, value: str) -> str:
    return f"""
    <div class="stat-tile">
        <span>{label}</span>
        <strong>{value}</strong>
    </div>
    """


def signal_tile(label: str, value: str) -> str:
    return f"""
    <div class="signal-tile">
        <span>{label}</span>
        <strong>{value}</strong>
    </div>
    """


def stock_note(signals: dict) -> str:
    if signals.get("has_low_stock_warning"):
        retailers = ", ".join(signals.get("low_stock_retailers", [])[:2])
        return retailers or "Low-stock pressure detected"
    if signals.get("majority_out_of_stock"):
        return "Availability is tightening"
    return "Availability looks stable"


st.set_page_config(page_title="Price Drop Sniper", page_icon="S", layout="wide")

if "page" not in st.session_state:
    st.session_state["page"] = "home"

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Manrope:wght@400;500;600;700&display=swap');

:root {
  --bg: #f4efe6;
  --paper: #fffaf3;
  --panel: rgba(255, 250, 243, 0.86);
  --ink: #171411;
  --muted: #665f57;
  --line: rgba(23, 20, 17, 0.08);
  --shadow: 0 20px 50px rgba(88, 66, 42, 0.10);
  --burnt: #c45a2a;
  --forest: #215e53;
  --amber: #c89220;
}

.stApp {
  background:
    radial-gradient(circle at 0% 0%, rgba(196, 90, 42, 0.08), transparent 28%),
    radial-gradient(circle at 100% 0%, rgba(33, 94, 83, 0.09), transparent 26%),
    linear-gradient(180deg, #f6f1e8 0%, #efe7da 100%);
  color: var(--ink);
}

[data-testid="stAppViewContainer"] > .main {
  background: transparent;
}

[data-testid="stSidebar"] {
  display: none;
}

.block-container {
  max-width: 1180px;
  padding-top: 1.2rem;
  padding-bottom: 3rem;
}

h1, h2, h3, h4 {
  font-family: "Space Grotesk", sans-serif !important;
  letter-spacing: -0.03em;
  color: var(--ink);
}

p, li, div, span, label {
  font-family: "Manrope", sans-serif !important;
}

[data-testid="stTextInputRootElement"] input {
  min-height: 3.5rem;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255, 252, 247, 0.95);
  color: var(--ink);
  padding-left: 1rem;
}

.stButton > button,
[data-testid="stBaseButton-primary"] {
  min-height: 3.5rem;
  border-radius: 18px;
  border: 1px solid rgba(0,0,0,0.04);
  background: linear-gradient(135deg, #c45a2a, #b24d22);
  color: #fff8f2;
  font-weight: 700;
  box-shadow: 0 14px 24px rgba(196, 90, 42, 0.18);
}

.stButton > button:hover,
[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-1px);
}

[data-testid="stProgressBar"] > div > div {
  background: linear-gradient(90deg, #215e53, #c45a2a) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 0.55rem;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
  background: rgba(0, 0, 0, 0.04);
  color: var(--muted);
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
}

[data-testid="stTabs"] [aria-selected="true"] {
  background: rgba(196, 90, 42, 0.12);
  color: var(--ink);
}

[data-testid="stDataFrame"] {
  border: 1px solid var(--line);
  border-radius: 20px;
  overflow: hidden;
}

.hero {
  padding: 2.5rem;
  border-radius: 34px;
  border: 1px solid var(--line);
  background:
    radial-gradient(circle at top right, rgba(33, 94, 83, 0.10), transparent 28%),
    radial-gradient(circle at left top, rgba(196, 90, 42, 0.10), transparent 24%),
    linear-gradient(180deg, rgba(255, 251, 245, 0.94), rgba(250, 243, 232, 0.92));
  box-shadow: var(--shadow);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.9fr);
  gap: 1rem;
}

.hero-kicker {
  display: inline-block;
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  background: rgba(23, 20, 17, 0.05);
  color: var(--burnt);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.8rem;
}

.hero h1 {
  margin: 1rem 0 0.7rem 0;
  font-size: clamp(3rem, 5vw, 5.2rem);
  line-height: 0.92;
  max-width: 8.5em;
}

.hero-copy {
  max-width: 42rem;
  color: var(--muted);
  font-size: 1.05rem;
  line-height: 1.75;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.stat-tile {
  padding: 1rem;
  border-radius: 20px;
  background: rgba(255,255,255,0.56);
  border: 1px solid var(--line);
}

.stat-tile span {
  display: block;
  color: var(--muted);
  font-size: 0.82rem;
}

.stat-tile strong {
  display: block;
  margin-top: 0.35rem;
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.35rem;
}

.hero-side {
  padding: 1.1rem;
  border-radius: 24px;
  background: #1f5d53;
  color: #fff9f1;
}

.hero-side h3 {
  margin: 0 0 0.8rem 0;
  color: #fff9f1;
  font-size: 1rem;
}

.hero-side-item {
  padding: 0.9rem 1rem;
  border-radius: 18px;
  background: rgba(255,255,255,0.08);
  margin-top: 0.7rem;
}

.hero-side-item strong {
  display: block;
  color: #fffaf4;
}

.hero-side-item span {
  display: block;
  color: rgba(255, 249, 241, 0.76);
  margin-top: 0.25rem;
  font-size: 0.88rem;
}

.cta-row {
  display: flex;
  gap: 0.8rem;
  align-items: center;
  margin-top: 1.35rem;
}

.cta-note {
  color: var(--muted);
  font-size: 0.92rem;
}

.panel {
  margin-top: 1rem;
  padding: 1.35rem;
  border-radius: 28px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow);
}

.input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 210px;
  gap: 0.8rem;
  align-items: end;
}

.helper {
  color: var(--muted);
  margin-top: 0.65rem;
}

.sample-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 0.9rem;
}

.sample-tag {
  padding: 0.65rem 0.9rem;
  border-radius: 999px;
  background: rgba(0,0,0,0.04);
  border: 1px solid var(--line);
  color: var(--ink);
  font-size: 0.9rem;
}

.status-card {
  margin-top: 0.85rem;
  padding: 1rem 1.1rem;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.58);
}

.report-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 1rem;
  align-items: start;
}

.eyebrow {
  color: var(--burnt);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.8rem;
}

.product-title {
  margin: 0.45rem 0 0 0;
  font-size: clamp(2rem, 3vw, 3.25rem);
  line-height: 0.98;
}

.product-url {
  margin-top: 0.7rem;
  color: var(--muted);
  word-break: break-all;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}

.summary-tile {
  padding: 1rem;
  border-radius: 20px;
  background: rgba(255,255,255,0.58);
  border: 1px solid var(--line);
}

.summary-tile span {
  display: block;
  font-size: 0.78rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-tile strong {
  display: block;
  margin-top: 0.35rem;
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.32rem;
}

.summary-tile small {
  display: block;
  margin-top: 0.4rem;
  color: var(--muted);
}

.retailer-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
}

.retailer-card {
  padding: 0.9rem 1rem;
  border-radius: 20px;
  background: rgba(255,255,255,0.6);
  border: 1px solid var(--line);
}

.retailer-card span {
  display: block;
  color: var(--muted);
  font-size: 0.82rem;
}

.retailer-card strong {
  display: block;
  margin-top: 0.25rem;
  font-family: "Space Grotesk", sans-serif;
}

.content-grid {
  display: grid;
  grid-template-columns: 0.95fr 1.25fr;
  gap: 1rem;
  margin-top: 1rem;
}

.verdict-box {
  padding: 1.35rem;
  border-radius: 28px;
  color: #fff9f1;
}

.verdict-buy { background: linear-gradient(135deg, #215e53, #2e7c6f); }
.verdict-wait { background: linear-gradient(135deg, #b37d1a, #cd9a28); }
.verdict-avoid { background: linear-gradient(135deg, #b24d22, #c45a2a); }

.verdict-box span {
  display: inline-block;
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.14);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.78rem;
}

.verdict-box h2 {
  margin: 0.8rem 0 0 0;
  color: #fffaf3;
  font-size: clamp(2rem, 3vw, 3.2rem);
}

.verdict-box p {
  margin: 0.6rem 0 0 0;
  color: rgba(255,249,241,0.84);
  line-height: 1.65;
}

.best-deal {
  margin-top: 0.9rem;
  padding: 1rem 1.1rem;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: linear-gradient(135deg, rgba(33, 94, 83, 0.10), rgba(200, 146, 32, 0.12));
}

.best-deal span {
  color: var(--muted);
}

.best-deal strong {
  display: block;
  margin-top: 0.3rem;
  font-family: "Space Grotesk", sans-serif;
  font-size: 1.25rem;
}

.stack {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.reason-card,
.evidence-card {
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.58);
}

.reason-card {
  border-left: 4px solid var(--burnt);
}

.evidence-card h4 {
  margin: 0 0 0.35rem 0;
  font-size: 1rem;
}

.evidence-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

.section-head p {
  margin: 0;
  color: var(--muted);
  font-size: 0.92rem;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.signal-tile {
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.56);
}

.signal-tile span {
  display: block;
  color: var(--muted);
  font-size: 0.82rem;
}

.signal-tile strong {
  display: block;
  margin-top: 0.28rem;
  font-family: "Space Grotesk", sans-serif;
}

.season-card {
  padding: 1rem 1.1rem;
  border-radius: 20px;
  border: 1px solid rgba(33, 94, 83, 0.12);
  background: rgba(33, 94, 83, 0.07);
}

.footer-note {
  margin-top: 1rem;
  text-align: center;
  color: var(--muted);
}

@media (max-width: 980px) {
  .hero-grid,
  .input-row,
  .report-head,
  .summary-grid,
  .content-grid,
  .signal-grid {
    grid-template-columns: 1fr;
  }

  .hero,
  .panel {
    padding: 1.25rem;
  }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<section class="hero">
  <div class="hero-grid">
    <div>
      <span class="hero-kicker">Price intelligence engine</span>
      <h1>Know when to buy. Skip when to wait.</h1>
      <p class="hero-copy">
        Turn a product URL into a clear purchase decision using live retailer pricing, 90-day trend context,
        stock pressure, and retrieved buying guidance.
      </p>
      <div class="hero-stats">
        <div class="stat-tile"><span>Retailers</span><strong>5-store scan</strong></div>
        <div class="stat-tile"><span>History</span><strong>90-day context</strong></div>
        <div class="stat-tile"><span>Decision</span><strong>BUY / WAIT / AVOID</strong></div>
      </div>
      <div class="cta-row">
        <div class="cta-note">Open the scan page when you want to run a URL through the pipeline.</div>
      </div>
    </div>
    <div class="hero-side">
      <h3>What drives the call</h3>
      <div class="hero-side-item"><strong>Price spread</strong><span>See whether the lowest offer is genuinely exceptional.</span></div>
      <div class="hero-side-item"><strong>Stock pressure</strong><span>Low inventory changes the cost of waiting.</span></div>
      <div class="hero-side-item"><strong>Retrieved context</strong><span>Category and seasonal guidance shape the final verdict.</span></div>
    </div>
  </div>
</section>
""",
    unsafe_allow_html=True,
)

home_cta_cols = st.columns([0.28, 0.72])
with home_cta_cols[0]:
    if st.button("Open Scan Page", type="primary", use_container_width=True):
        st.session_state["page"] = "scan"
        st.rerun()

samples = {
    "Sony Headphones": "https://www.amazon.com/dp/B09XS7JWHH",
    "AirPods Pro": "https://www.amazon.com/dp/B0BDHWDR12",
    "iPad Air": "https://www.bestbuy.com/site/apple-ipad-air/1234567.p",
    "PS5 Controller": "https://www.walmart.com/ip/PS5-DualSense/123456789",
}

product_url = ""
run_btn = False

if st.session_state["page"] == "scan":
    st.markdown('<section class="panel">', unsafe_allow_html=True)
    top_cols = st.columns([0.22, 0.78])
    with top_cols[0]:
        if st.button("Back Home", use_container_width=True):
            st.session_state["page"] = "home"
            st.rerun()
    st.markdown(
        """
        <div class="section-head">
          <div>
            <h3 style="margin:0;">Launch a Product Scan</h3>
            <p>Paste a live product URL or load one of the demo SKUs below.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_url = st.session_state.get("sample_url", "")
    st.markdown('<div class="input-row">', unsafe_allow_html=True)
    product_url = st.text_input(
        "Product URL",
        value=default_url,
        label_visibility="collapsed",
        placeholder="https://www.amazon.com/dp/B09XS7JWHH",
    )
    run_btn = st.button("Analyze Price", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="sample-row">' + "".join(f'<span class="sample-tag">{label}</span>' for label in samples) + "</div>",
        unsafe_allow_html=True,
    )
    sample_cols = st.columns(len(samples))
    for col, (label, url) in zip(sample_cols, samples.items()):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state["sample_url"] = url
                st.rerun()
    st.markdown('<div class="helper">The full run includes retailer scan, history analysis, local retrieval, and verdict generation.</div>', unsafe_allow_html=True)
    st.markdown("</section>", unsafe_allow_html=True)

if run_btn and product_url:
    from agent import run_agent

    progress_bar = st.progress(0, text="Starting scan...")
    status = st.empty()
    steps = [
        (12, "Identifying the product..."),
        (34, "Scanning retailers for live pricing..."),
        (58, "Building the 90-day context..."),
        (78, "Computing signals and stock pressure..."),
        (90, "Retrieving category guidance..."),
        (97, "Producing the final verdict..."),
    ]

    for pct, msg in steps:
        progress_bar.progress(pct, text=msg)
        status.markdown(
            f"""
            <div class="status-card">
              <strong style="font-family:'Space Grotesk',sans-serif;">Agent Status</strong>
              <div class="helper">{msg}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        time.sleep(0.4)

    with st.spinner("Running full agent pipeline..."):
        result = run_agent(product_url)

    progress_bar.progress(100, text="Analysis complete")
    status.empty()
    progress_bar.empty()

    if result.get("error") and not result.get("retailer_prices"):
        st.error(f"Agent error: {result['error']}")
        st.stop()

    verdict = result.get("verdict", "WAIT")
    confidence = result.get("confidence", 0)
    best = result.get("best_deal")
    prices = result.get("retailer_prices", [])
    history = result.get("price_history", [])
    signals = result.get("signals", {})
    retrieved_context = result.get("retrieved_context", [])
    verdict_class, verdict_copy = verdict_meta(verdict)
    price_spread = signals.get("price_spread_pct", "N/A")

    st.markdown(
        f"""
        <section class="panel">
          <div class="report-head">
            <div>
              <span class="eyebrow">Product intelligence report</span>
              <h2 class="product-title">{result.get('product_name') or 'Product Analysis'}</h2>
              <div class="product-url">{product_url}</div>
            </div>
            <div class="retailer-strip">
              {''.join(f'<div class="retailer-card"><span>{item["retailer"]}</span><strong>{format_money(item["price"])}</strong></div>' for item in prices[:5])}
            </div>
          </div>
          <div class="summary-grid">
            {summary_tile("Confidence", f"{confidence}%", "Model confidence in the recommendation")}
            {summary_tile("Best live price", format_money(best['price']) if best else "N/A", best['retailer'] if best else "No current winner")}
            {summary_tile("Price spread", f"{price_spread}%" if price_spread != "N/A" else "N/A", "Gap between cheapest and highest offer")}
            {summary_tile("Stock pressure", "High" if signals.get("has_low_stock_warning") else "Stable", stock_note(signals))}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="content-grid">', unsafe_allow_html=True)

    with st.container():
        left, right = st.columns([0.95, 1.25], gap="large")

        with left:
            st.markdown(
                f"""
                <section class="panel" style="margin-top:0;">
                  <div class="verdict-box {verdict_class}">
                    <span>Agent Recommendation</span>
                    <h2>{verdict}</h2>
                    <p>{verdict_copy}</p>
                  </div>
                """,
                unsafe_allow_html=True,
            )
            if best:
                st.markdown(
                    f"""
                    <div class="best-deal">
                      <span>Best current offer</span>
                      <strong>{format_money(best['price'])} at {best['retailer']}</strong>
                      <div style="margin-top:0.55rem;"><a href="{best['url']}" target="_blank" style="color:#171411;text-decoration:none;font-weight:700;">Open retailer ↗</a></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown(
                """
                <div class="section-head" style="margin-top:1.2rem;">
                  <div>
                    <h3 style="margin:0;">Reasoning Trail</h3>
                    <p>How the system justified the final call.</p>
                  </div>
                </div>
                <div class="stack">
                """,
                unsafe_allow_html=True,
            )
            for step in result.get("reasoning", []):
                st.markdown(f'<div class="reason-card">{step}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if retrieved_context:
                st.markdown(
                    """
                    <div class="section-head" style="margin-top:1.2rem;">
                      <div>
                        <h3 style="margin:0;">Retrieved Evidence</h3>
                        <p>Hybrid local and internet evidence injected before reasoning.</p>
                      </div>
                    </div>
                    <div class="stack">
                    """,
                    unsafe_allow_html=True,
                )
                for item in retrieved_context:
                    st.markdown(
                        f"""
                        <div class="evidence-card">
                          <h4>{item['title']}</h4>
                          <small style="display:block; margin-bottom:0.45rem; color:#215e53; font-weight:700; text-transform:uppercase; letter-spacing:0.04em;">
                            {"Web" if item.get("source_type") == "web" else "Local"} · {item.get("source", "Unknown source")}
                          </small>
                          <p>{item['content']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</section>", unsafe_allow_html=True)

        with right:
            st.markdown(
                """
                <section class="panel" style="margin-top:0;">
                  <div class="section-head">
                    <div>
                      <h3 style="margin:0;">Market Dashboard</h3>
                      <p>Price landscape, trend context, and signal output.</p>
                    </div>
                  </div>
                """,
                unsafe_allow_html=True,
            )

            tabs = st.tabs(["Price Landscape", "History Curve", "Signal Matrix"])

            with tabs[0]:
                if prices:
                    df = pd.DataFrame(prices)
                    best_price = df["price"].min()
                    colors = ["#c45a2a" if p == best_price else "#215e53" for p in df["price"]]
                    fig = go.Figure(
                        go.Bar(
                            x=df["retailer"],
                            y=df["price"],
                            marker=dict(color=colors, line=dict(color="rgba(23,20,17,0.10)", width=1)),
                            text=[f"${p:,.2f}" for p in df["price"]],
                            textposition="outside",
                        )
                    )
                    fig.update_layout(
                        title="Live retailer pricing",
                        height=360,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(255,255,255,0.34)",
                        font=dict(color="#171411", family="Manrope"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(title="Price (USD)", gridcolor="rgba(23,20,17,0.08)"),
                        margin=dict(l=10, r=10, t=50, b=10),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    stock_df = df[["retailer", "price", "stock"]].copy()
                    stock_df["price"] = stock_df["price"].map(lambda x: f"${x:,.2f}")
                    stock_df["stock"] = stock_df["stock"].map({
                        "in_stock": "In Stock",
                        "low_stock": "Low Stock",
                        "out_of_stock": "Out of Stock",
                    })
                    st.dataframe(stock_df, use_container_width=True, hide_index=True)

            with tabs[1]:
                if history:
                    hist_df = pd.DataFrame(history)
                    hist_df["date"] = pd.to_datetime(hist_df["date"])
                    best_price = min(r["price"] for r in prices) if prices else None
                    atl = hist_df["price"].min()

                    fig2 = go.Figure()
                    fig2.add_trace(
                        go.Scatter(
                            x=hist_df["date"],
                            y=hist_df["price"],
                            mode="lines",
                            line=dict(color="#215e53", width=3),
                            fill="tozeroy",
                            fillcolor="rgba(33,94,83,0.12)",
                            name="Price history",
                        )
                    )
                    if best_price:
                        fig2.add_hline(
                            y=best_price,
                            line_dash="dash",
                            line_color="#c45a2a",
                            annotation_text=f"Current best {format_money(best_price)}",
                            annotation_position="bottom right",
                        )
                    fig2.add_hline(
                        y=atl,
                        line_dash="dot",
                        line_color="#c89220",
                        annotation_text=f"ATL {format_money(atl)}",
                        annotation_position="top right",
                    )
                    fig2.update_layout(
                        title="90-day price history",
                        height=360,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(255,255,255,0.34)",
                        font=dict(color="#171411", family="Manrope"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(title="Price (USD)", gridcolor="rgba(23,20,17,0.08)"),
                        margin=dict(l=10, r=10, t=50, b=10),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            with tabs[2]:
                st.markdown(
                    f"""
                    <div class="signal-grid">
                      {signal_tile("All-time low", format_money(signals.get("all_time_low")))}
                      {signal_tile("90-day average", format_money(signals.get("avg_90d")))}
                      {signal_tile("% above ATL", f"{signals.get('pct_above_atl', 'N/A')}%")}
                      {signal_tile("14-day trend", f"{signals.get('14d_trend_pct', 0):+.1f}%")}
                      {signal_tile("Flash sale", "Yes" if signals.get("flash_sale_detected") else "No")}
                      {signal_tile("Low stock", "Yes" if signals.get("has_low_stock_warning") else "No")}
                    </div>
                    <div class="season-card"><strong>Seasonal context:</strong> {signals.get('seasonal_context', 'N/A')}</div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

elif run_btn:
    st.warning("Enter a product URL first.")

st.markdown(
    '<div class="footer-note">Price Drop Sniper Agent · LangGraph orchestration · retrieval-augmented decision flow</div>',
    unsafe_allow_html=True,
)
