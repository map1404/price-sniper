import { useMemo, useState } from "react";
import emlyonLogo from "./assets/emlyon-logo.svg";

const samples = [
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
  "Retrieving local and web buying guidance",
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

function HistoryChart({ points }) {
  const chartPoints = points
    .map((point) => ({
      date: point.date,
      price: Number(point.price)
    }))
    .filter((point) => Number.isFinite(point.price));

  if (chartPoints.length < 2) {
    return (
      <div className="history-empty">
        <strong>No chart available</strong>
        <span>At least two valid price points are needed to draw the 90-day trend.</span>
      </div>
    );
  }

  const width = 640;
  const height = 240;
  const padding = 18;
  const minPrice = Math.min(...chartPoints.map((point) => point.price));
  const maxPrice = Math.max(...chartPoints.map((point) => point.price));
  const priceRange = Math.max(maxPrice - minPrice, 1);
  const xStep = (width - padding * 2) / Math.max(chartPoints.length - 1, 1);

  const linePath = chartPoints
    .map((point, index) => {
      const x = padding + index * xStep;
      const y = height - padding - ((point.price - minPrice) / priceRange) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const areaPath = `${linePath} L ${padding + (chartPoints.length - 1) * xStep} ${height - padding} L ${padding} ${height - padding} Z`;
  const lowPoint = chartPoints.reduce((lowest, point) => (point.price < lowest.price ? point : lowest));
  const highPoint = chartPoints.reduce((highest, point) => (point.price > highest.price ? point : highest));
  const latestPoint = chartPoints[chartPoints.length - 1];

  const yLabels = [maxPrice, minPrice + priceRange / 2, minPrice];

  function pointPosition(point) {
    const index = chartPoints.findIndex(
      (entry) => entry.date === point.date && entry.price === point.price
    );
    return {
      x: padding + index * xStep,
      y: height - padding - ((point.price - minPrice) / priceRange) * (height - padding * 2)
    };
  }

  const lowCoords = pointPosition(lowPoint);
  const highCoords = pointPosition(highPoint);
  const latestCoords = pointPosition(latestPoint);

  return (
    <div className="history-chart-shell">
      <div className="history-chart-metrics">
        <article>
          <span>Low</span>
          <strong>{formatMoney(lowPoint.price)}</strong>
        </article>
        <article>
          <span>High</span>
          <strong>{formatMoney(highPoint.price)}</strong>
        </article>
        <article>
          <span>Latest</span>
          <strong>{formatMoney(latestPoint.price)}</strong>
        </article>
      </div>

      <div className="history-chart">
        <div className="history-y-axis">
          {yLabels.map((value) => (
            <span key={value}>{formatMoney(value)}</span>
          ))}
        </div>

        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="90-day price history chart">
          <defs>
            <linearGradient id="history-area-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(28, 102, 255, 0.30)" />
              <stop offset="100%" stopColor="rgba(28, 102, 255, 0.02)" />
            </linearGradient>
          </defs>

          {[0, 1, 2].map((index) => {
            const y = padding + ((height - padding * 2) / 2) * index;
            return <line key={index} x1={padding} y1={y} x2={width - padding} y2={y} />;
          })}

          <path d={areaPath} fill="url(#history-area-fill)" />
          <path d={linePath} className="history-line" pathLength="100" />

          <circle cx={lowCoords.x} cy={lowCoords.y} r="5" className="history-point low" />
          <circle cx={highCoords.x} cy={highCoords.y} r="5" className="history-point high" />
          <circle cx={latestCoords.x} cy={latestCoords.y} r="5.5" className="history-point latest" />
        </svg>
      </div>

      <div className="history-chart-foot">
        <span>{chartPoints[0].date}</span>
        <span>{latestPoint.date}</span>
      </div>
    </div>
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
      <div className="app-brand reveal reveal-1" aria-label="emlyon business school">
        <img src={emlyonLogo} alt="emlyon business school logo" className="app-brand-logo" />
        <div className="app-brand-copy">
          <span>Academic Partner</span>
          <strong>emlyon business school</strong>
        </div>
      </div>

      {page === "home" ? (
        <header className="hero reveal reveal-2">
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
                  <div className="report-hero">
                    {result.product_image_url ? (
                      <div className="product-image-frame">
                        <img
                          src={result.product_image_url}
                          alt={result.product_name || "Product"}
                          className="product-image"
                        />
                      </div>
                    ) : null}

                    <div>
                    <span className="eyebrow">Product intelligence report</span>
                    <h2 className="product-title">{result.product_name || "Product Analysis"}</h2>
                    <p className="product-url">{productUrl}</p>
                    </div>
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
                      Open product page ↗
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
                      <p>Hybrid local and internet evidence injected before reasoning.</p>
                    </div>
                  </div>
                  <div className="stack-list">
                    {result.retrieved_context?.length ? (
                      result.retrieved_context.map((item) => (
                        <article key={item.id} className="evidence-row">
                          <h4>{item.title}</h4>
                          <span className="evidence-meta">
                            {item.source_type === "web" ? "Web" : "Local"} · {item.source || "Unknown source"}
                          </span>
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
                      <h3>Price History</h3>
                      <p>Trend view of the 90-day price series instead of a point list.</p>
                    </div>
                  </div>
                  <HistoryChart points={historyPoints} />
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
