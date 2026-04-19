import { useMemo, useState } from "react";

const samples = [
  {
    label: "Sony Headphones",
    url: "https://www.amazon.com/dp/B09XS7JWHH"
  },
  {
    label: "AirPods Pro",
    url: "https://www.amazon.com/dp/B0BDHWDR12"
  },
  {
    label: "iPad Air",
    url: "https://www.bestbuy.com/site/apple-ipad-air/1234567.p"
  },
  {
    label: "PS5 Controller",
    url: "https://www.walmart.com/ip/PS5-DualSense/123456789"
  }
];

const stages = [
  "Identifying the product",
  "Scanning retailers for live pricing",
  "Building the 90-day context",
  "Computing price signals",
  "Retrieving local buying guidance",
  "Producing the verdict"
];

function formatMoney(value) {
  if (value === null || value === undefined || value === "" || value === "N/A") {
    return "N/A";
  }
  const number = Number(value);
  return Number.isNaN(number)
    ? String(value)
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD"
      }).format(number);
}

function verdictTone(verdict) {
  switch (verdict) {
    case "BUY NOW":
      return "buy";
    case "AVOID":
      return "avoid";
    default:
      return "wait";
  }
}

function SignalTile({ label, value }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function App() {
  const [page, setPage] = useState("home");
  const [productUrl, setProductUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusIndex, setStatusIndex] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const tone = verdictTone(result?.verdict);
  const sortedRetailers = result?.retailer_prices ?? [];
  const historyPoints = result?.price_history ?? [];

  const summary = useMemo(() => {
    const signals = result?.signals ?? {};
    return [
      {
        label: "Confidence",
        value: result ? `${result.confidence}%` : "N/A",
        note: "Confidence in the recommendation"
      },
      {
        label: "Best Live Price",
        value: result?.best_deal ? formatMoney(result.best_deal.price) : "N/A",
        note: result?.best_deal?.retailer ?? "No live winner"
      },
      {
        label: "Price Spread",
        value: signals.price_spread_pct !== undefined ? `${signals.price_spread_pct}%` : "N/A",
        note: "Gap between cheapest and priciest offer"
      },
      {
        label: "Stock Pressure",
        value: signals.has_low_stock_warning ? "High" : "Stable",
        note: signals.low_stock_retailers?.join(", ") || "Availability looks steady"
      }
    ];
  }, [result]);

  async function handleAnalyze(event) {
    event.preventDefault();
    if (!productUrl.trim()) {
      setError("Enter a product URL first.");
      return;
    }

    setError("");
    setResult(null);
    setIsLoading(true);
    setStatusIndex(0);

    let timer = window.setInterval(() => {
      setStatusIndex((current) => {
        if (current >= stages.length - 1) {
          window.clearInterval(timer);
          return current;
        }
        return current + 1;
      });
    }, 550);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_url: productUrl.trim() })
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Request failed");
      }

      setResult(payload);
      setStatusIndex(stages.length - 1);
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      window.clearInterval(timer);
      setIsLoading(false);
    }
  }

  return (
    <div className="app-shell">
      {page === "home" ? (
        <header className="hero">
          <div className="hero-copy">
            <span className="eyebrow">Price intelligence engine</span>
            <h1>Know when to buy. Skip when to wait.</h1>
            <p>
              A calm decision layer for shopping. Feed in a product URL and the system blends live
              retailer pricing, 90-day context, stock pressure, and retrieved guidance into one clear call.
            </p>
            <div className="hero-stats">
              <article>
                <span>Retailers</span>
                <strong>5-store scan</strong>
              </article>
              <article>
                <span>History</span>
                <strong>90-day context</strong>
              </article>
              <article>
                <span>Verdict</span>
                <strong>BUY / WAIT / AVOID</strong>
              </article>
            </div>
            <button className="cta-button" onClick={() => setPage("scan")}>
              Launch a Product Scan
            </button>
          </div>
          <aside className="hero-panel">
            <h3>What drives the call</h3>
            <div>
              <section>
                <strong>Price spread</strong>
                <span>See whether the cheapest live offer is truly exceptional.</span>
              </section>
              <section>
                <strong>Stock pressure</strong>
                <span>Scarcity raises the cost of waiting for a slightly better price.</span>
              </section>
              <section>
                <strong>Retrieved context</strong>
                <span>Local category guidance shapes the final recommendation.</span>
              </section>
            </div>
          </aside>
        </header>
      ) : (
        <>
          <section className="page-header reveal reveal-1">
            <button className="ghost-button" onClick={() => setPage("home")}>
              Back Home
            </button>
            <div>
              <span className="eyebrow">Scan page</span>
              <h2>Launch a Product Scan</h2>
              <p>Submit a URL and let the system move from scan to verdict with minimal noise.</p>
            </div>
          </section>

          <section className="panel scan-shell reveal reveal-2">
            <div className="panel-head">
              <div>
                <h2>Scan Input</h2>
                <p>Paste a live product URL or start with one of the sample products.</p>
              </div>
            </div>

            <form className="scan-form" onSubmit={handleAnalyze}>
              <input
                type="text"
                value={productUrl}
                onChange={(event) => setProductUrl(event.target.value)}
                placeholder="https://www.amazon.com/dp/B09XS7JWHH"
              />
              <button type="submit" disabled={isLoading}>
                {isLoading ? "Analyzing..." : "Analyze Price"}
              </button>
            </form>

            <div className="sample-list">
              {samples.map((sample) => (
                <button
                  key={sample.label}
                  className="sample-chip"
                  onClick={() => setProductUrl(sample.url)}
                  type="button"
                >
                  {sample.label}
                </button>
              ))}
            </div>

            {isLoading ? (
              <div className="status-panel">
                <div className="progress-bar">
                  <span style={{ width: `${((statusIndex + 1) / stages.length) * 100}%` }} />
                </div>
                <strong>{stages[statusIndex]}</strong>
                <p>The Python agent is running the full retrieval and reasoning pipeline.</p>
              </div>
            ) : null}

            {error ? <div className="error-banner">{error}</div> : null}
          </section>

          {result ? (
            <>
              {result.product_name === "Unknown Product" ? (
                <section className="error-banner reveal reveal-3">
                  Product not found. The result may be based on fallback or estimated data.
                </section>
              ) : null}

              <section className="panel report-overview reveal reveal-3">
                <div className="report-top">
                  <div>
                    <span className="eyebrow">Product intelligence report</span>
                    <h2 className="product-title">{result.product_name || "Product Analysis"}</h2>
                    <p className="product-url">{productUrl}</p>
                  </div>
                  <div className="retailer-strip">
                    {sortedRetailers.slice(0, 5).map((item) => (
                      <article key={`${item.retailer}-${item.price}`}>
                        <span>{item.retailer}</span>
                        <strong>{formatMoney(item.price)}</strong>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="summary-grid">
                  {summary.map((item) => (
                    <article key={item.label}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      <small>{item.note}</small>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel verdict-shell reveal reveal-4">
                <div className={`verdict-card tone-${tone}`}>
                  <span>Agent Recommendation</span>
                  <h2>{result.verdict}</h2>
                  <p>
                    {tone === "buy"
                      ? "The current setup clears the bar for action."
                      : tone === "avoid"
                        ? "This price profile is weak enough to avoid for now."
                        : "The setup is viable, but not compelling enough yet."}
                  </p>
                </div>

                {result.best_deal ? (
                  <section className="best-deal-card">
                    <span>Best current offer</span>
                    <strong>
                      {formatMoney(result.best_deal.price)} at {result.best_deal.retailer}
                    </strong>
                    <a href={result.best_deal.url} target="_blank" rel="noreferrer">
                      Open retailer ↗
                    </a>
                  </section>
                ) : null}
              </section>

              <section className="panel stacked-section reveal reveal-5">
                <div className="panel-head">
                  <div>
                    <h3>Retailer Prices</h3>
                    <p>Current offers ordered from the best live price upward.</p>
                  </div>
                </div>
                <div className="price-bars">
                  {sortedRetailers.map((item, index) => {
                    const maxPrice = Math.max(...sortedRetailers.map((entry) => entry.price));
                    const width = maxPrice ? (item.price / maxPrice) * 100 : 0;
                    return (
                      <article key={`${item.retailer}-${item.price}`} className="price-row">
                        <div className="price-copy">
                          <strong>{item.retailer}</strong>
                          <span>{item.stock.replaceAll("_", " ")}</span>
                        </div>
                        <div className="price-bar-track">
                          <span
                            className={index === 0 ? "bar-fill cheapest" : "bar-fill"}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <strong className="price-value">{formatMoney(item.price)}</strong>
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="panel stacked-section reveal reveal-6">
                <div className="panel-head">
                  <div>
                    <h3>Reasoning Trail</h3>
                    <p>How the system justified the final recommendation.</p>
                  </div>
                </div>
                <div className="stack-list">
                  {result.reasoning?.map((step, index) => (
                    <article key={`${index}-${step}`} className="reason-row">
                      {step}
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel stacked-section reveal reveal-7">
                <div className="panel-head">
                  <div>
                    <h3>Signal Matrix</h3>
                    <p>Key pricing indicators feeding the recommendation.</p>
                  </div>
                </div>
                <div className="signal-grid">
                  {[
                    ["All-time low", formatMoney(result.signals?.all_time_low)],
                    ["90-day average", formatMoney(result.signals?.avg_90d)],
                    ["% above ATL", `${result.signals?.pct_above_atl ?? "N/A"}%`],
                    ["14-day trend", `${result.signals?.["14d_trend_pct"] ?? 0}%`],
                    ["Flash sale", result.signals?.flash_sale_detected ? "Yes" : "No"],
                    ["Low stock", result.signals?.has_low_stock_warning ? "Yes" : "No"]
                  ].map(([label, value]) => (
                    <SignalTile key={label} label={label} value={value} />
                  ))}
                </div>
                <div className="season-card">
                  <strong>Seasonal context:</strong> {result.signals?.seasonal_context || "N/A"}
                </div>
              </section>

              <section className="panel dual-section reveal reveal-8">
                <div className="section-column">
                  <div className="panel-head">
                    <div>
                      <h3>Retrieved Evidence</h3>
                      <p>Local knowledge snippets injected before reasoning.</p>
                    </div>
                  </div>
                  <div className="stack-list">
                    {result.retrieved_context?.length ? (
                      result.retrieved_context.map((item) => (
                        <article key={item.id} className="evidence-row">
                          <h4>{item.title}</h4>
                          <p>{item.content}</p>
                        </article>
                      ))
                    ) : (
                      <article className="evidence-row muted-card">
                        <h4>No retrieved evidence</h4>
                        <p>No additional snippets were needed for this run.</p>
                      </article>
                    )}
                  </div>
                </div>

                <div className="section-column">
                  <div className="panel-head">
                    <div>
                      <h3>History Snapshot</h3>
                      <p>Recent points pulled from the 90-day price series.</p>
                    </div>
                  </div>
                  <div className="history-list">
                    {historyPoints.slice(-8).map((point) => (
                      <article key={`${point.date}-${point.price}`}>
                        <span>{point.date}</span>
                        <strong>{formatMoney(point.price)}</strong>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            </>
          ) : null}
        </>
      )}

      <footer className="footer-note">
        Price Drop Sniper · React frontend + Python API + retrieval-augmented decision flow
      </footer>
    </div>
  );
}

export default App;
