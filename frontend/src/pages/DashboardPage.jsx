import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { getForecastKpis, getFutureForecast, runAlerts } from '../api/client'
import './DashboardPage.css'

const mockData = {
  fileName: 'retail_clean.csv',
  kpis: {
    total_sales: 47704512.0,
    forecast_direction: 'increasing',
    winner_model: 'lightgbm_global_lag',
    mae: 5.882,
  },
  alertsData: {
    alerts: [
      { product_id: 5,  product_name: 'Item 5',  alert_type: 'Sales Anomaly',  severity: 2.4, metric: 'Sales of 12 is 2.4 std devs below 90-day mean of 35.1' },
      { product_id: 1,  product_name: 'Item 1',  alert_type: 'Demand Decline', severity: 1.8, metric: 'Sales of 15 is 1.8 std devs below 90-day mean of 28.4' },
      { product_id: 41, product_name: 'Item 41', alert_type: 'Demand Decline', severity: 1.6, metric: 'Sales of 18 is 1.5 std devs below 90-day mean of 30.2' },
      { product_id: 15, product_name: 'Item 15', alert_type: 'Sales Anomaly',  severity: 2.1, metric: 'Sales of 58 is 2.1 std devs above 90-day mean of 31.2' },
      { product_id: 28, product_name: 'Item 28', alert_type: 'Sales Anomaly',  severity: 1.9, metric: 'Sales of 52 is 1.9 std devs above 90-day mean of 29.8' },
    ],
    total: 5
  },
  forecastChart: [
    { date: 'Aug', value: 3200 },
    { date: 'Sep', value: 2900 },
    { date: 'Oct', value: 3100 },
    { date: 'Nov', value: 2800 },
    { date: 'Dec', value: 3400 },
    { date: 'Jan', value: 3600 },
    { date: 'Feb', value: 3500 },
    { date: 'Mar', value: 3800 },
    { date: 'Apr', value: 4100 },
    { date: 'May', value: 4400 },
    { date: 'Jun', value: 4700 },
  ],
  topProducts: [
    { product: 'Item 15', total_sales: 1607442 },
    { product: 'Item 28', total_sales: 1604713 },
    { product: 'Item 13', total_sales: 1539621 },
    { product: 'Item 18', total_sales: 1538876 },
    { product: 'Item 25', total_sales: 1473334 },
  ],
  bottomProducts: [
    { product: 'Item 5',  total_sales: 335230 },
    { product: 'Item 1',  total_sales: 401384 },
    { product: 'Item 41', total_sales: 401759 },
    { product: 'Item 47', total_sales: 401781 },
    { product: 'Item 4',  total_sales: 401907 },
  ],
  categories: ['Electronics', 'Food', 'Clothing', 'Home'],
  stores: ['Store 1', 'Store 2', 'Store 3', 'Store 4', 'Store 5'],
}

const BAR_COLORS = [
  '#1565c0', '#1976d2', '#1e88e5', '#2196f3',
  '#42a5f5', '#0288d1', '#0097a7', '#00838f',
  '#006064', '#0d47a1'
]

function fmt(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`
  return `$${n}`
}

const HORIZONS = ['Next 30 days', 'Next 90 days', 'Next 6 months', 'Next 12 months']

const HORIZON_DAYS = {
  'Next 30 days': 30,
  'Next 90 days': 90,
  'Next 6 months': 180,
  'Next 12 months': 365,
}

function DashboardPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [activeTab, setActiveTab] = useState('overview')
  const [horizon, setHorizon] = useState('Next 90 days')
  const [selectedStores, setSelectedStores] = useState([])
  const [selectedCategories, setSelectedCategories] = useState([])
  const [selectedRegions, setSelectedRegions] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [filteredKpis, setFilteredKpis] = useState(null)
  const [filteredForecast, setFilteredForecast] = useState(null)
  const [filteredAlerts, setFilteredAlerts] = useState(null)
  const [isFiltering, setIsFiltering] = useState(false)

  const apiState = location.state
  const uploadedFile     = apiState?.file           ?? null
  const kpis             = filteredKpis             ?? apiState?.kpiData    ?? mockData.kpis
  const alertsData       = filteredAlerts           ?? apiState?.alertsData ?? mockData.alertsData
  const fileName         = apiState?.fileName       ?? mockData.fileName
  const csvData          = apiState?.csvData        ?? null
  const uniqueStores     = csvData?.uniqueStores    ?? mockData.stores
  const uniqueCategories = csvData?.uniqueCategories ?? mockData.categories
  const uniqueRegions    = csvData?.uniqueRegions   ?? []
  const rawRows          = csvData?.rawRows         ?? null

  // Guard — redirect if no file was uploaded
  useEffect(() => {
    if (!apiState) {
      navigate('/upload', { replace: true })
    }
  }, [])

  if (!apiState) return null

  // Filter raw CSV data on frontend instantly
  const filteredCSV = rawRows ? (() => {
    let filtered = rawRows

    if (selectedStores.length > 0) {
      filtered = filtered.filter(r => selectedStores.includes(String(r.store)))
    }
    if (selectedCategories.length > 0) {
      filtered = filtered.filter(r => selectedCategories.includes(r.category))
    }
    if (selectedRegions.length > 0) {
      filtered = filtered.filter(r => selectedRegions.includes(r.region))
    }

    const productSales = {}
    const storeSalesMap = {}
    const categorySalesMap = {}
    const monthlyTotal = {}

    filtered.forEach(row => {
      productSales[row.product] = (productSales[row.product] || 0) + row.sales
      storeSalesMap[row.store] = (storeSalesMap[row.store] || 0) + row.sales
      if (row.category) categorySalesMap[row.category] = (categorySalesMap[row.category] || 0) + row.sales
      if (row.date) monthlyTotal[row.date] = (monthlyTotal[row.date] || 0) + row.sales
    })

    const sortedProducts = Object.entries(productSales)
      .sort((a, b) => b[1] - a[1])
      .map(([product, total_sales]) => ({ product, total_sales }))

    return {
      topProducts: sortedProducts.slice(0, 10),
      bottomProducts: sortedProducts.slice(-5).reverse(),
      top10Products: sortedProducts.slice(0, 10),
      storeSales: Object.entries(storeSalesMap)
        .sort((a, b) => b[1] - a[1])
        .map(([store, total_sales]) => ({ store, total_sales })),
      categorySales: Object.entries(categorySalesMap)
        .sort((a, b) => b[1] - a[1])
        .map(([category, total_sales]) => ({ category, total_sales })),
      monthlyChart: Object.entries(monthlyTotal)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, total_sales]) => ({ date, total_sales })),
      totalRevenue: filtered.reduce((sum, r) => sum + r.sales, 0),
    }
  })() : null

  const hasActiveFilters = selectedStores.length > 0 ||
    selectedCategories.length > 0 ||
    selectedRegions.length > 0 ||
    horizon !== 'Next 90 days'

  // Re-call backend when filters or horizon change
  useEffect(() => {
    if (!uploadedFile) return

    setFilteredKpis(null)
    setFilteredForecast(null)

    // Only clear alerts if store or region changed
    if (selectedStores.length === 0 && selectedRegions.length === 0) {
      // Keep existing alerts when only category filter changes
    } else {
      setFilteredAlerts(null)
    }

    if (selectedStores.length > 0 || selectedCategories.length > 0 || horizon !== 'Next 90 days') {
      applyBackendFilters()
    } else if (selectedStores.length === 0 && selectedCategories.length === 0 && horizon === 'Next 90 days') {
      setFilteredAlerts(null)
    }
  }, [selectedStores, selectedCategories, horizon, selectedRegions])
  
  async function applyBackendFilters() {
    if (!uploadedFile) return
    setIsFiltering(true)

    const futureDays = HORIZON_DAYS[horizon] || 90
    const filters = {
      stores: selectedStores.map(s => parseInt(s)).filter(Boolean),
      categories: selectedCategories,
    }

    // Alerts only re-run when store or region changes
    // Category filter does NOT affect alerts — business wide warnings
    // should always show regardless of category view
    const alertFilters = {
      stores: selectedStores.map(s => parseInt(s)).filter(Boolean),
    }

    const onlyCategoryChanged = selectedStores.length === 0 &&
      selectedRegions.length === 0 &&
      selectedCategories.length > 0

    try {
      if (onlyCategoryChanged) {
        // Skip alerts re-call — keeps existing alerts and saves a backend call
        const [kpiResult, forecastResult] = await Promise.all([
          getForecastKpis(uploadedFile, 30, filters),
          getFutureForecast(uploadedFile, futureDays, { fast: true, filters }),
        ])
        setFilteredKpis(kpiResult)
        setFilteredForecast(forecastResult)
      } else {
        const [kpiResult, forecastResult, alertsResult] = await Promise.all([
          getForecastKpis(uploadedFile, 30, filters),
          getFutureForecast(uploadedFile, futureDays, { fast: true, filters }),
          runAlerts(uploadedFile, { filters: alertFilters }),
        ])
        setFilteredKpis(kpiResult)
        setFilteredForecast(forecastResult)
        setFilteredAlerts(alertsResult)
      }
    } catch (err) {
      console.error('Filter API error:', err)
    } finally {
      setIsFiltering(false)
    }
  }

  // Build forecast chart — SUM all predictions per month to match historical scale
  const forecastSource = filteredForecast ?? apiState?.forecastData
  const forecastChart = forecastSource?.forecast_records
    ? (() => {
        const records = forecastSource.forecast_records
        const byMonth = {}
        records.forEach(r => {
          const month = r.date.slice(0, 7)
          if (!byMonth[month]) byMonth[month] = { total: 0 }
          byMonth[month].total += r.prediction
        })
        const forecastPoints = Object.entries(byMonth)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([month, data]) => ({
            date: month,
            value: Math.round(data.total),
          }))

        // Bridge the gap — add last historical point as first forecast point
        const currentMonthlyChart = filteredCSV?.monthlyChart ?? csvData?.monthlyChart ?? []
        if (currentMonthlyChart.length > 0 && forecastPoints.length > 0) {
          const lastHistorical = currentMonthlyChart[currentMonthlyChart.length - 1]
          forecastPoints.unshift({
            date: lastHistorical.date,
            value: lastHistorical.total_sales,
          })
        }

        return forecastPoints
      })()
    : mockData.forecastChart

  const topProducts    = filteredCSV?.topProducts    ?? csvData?.topProducts    ?? mockData.topProducts
  const bottomProducts = filteredCSV?.bottomProducts ?? csvData?.bottomProducts ?? mockData.bottomProducts
  const top10Products  = filteredCSV?.top10Products  ?? csvData?.top10Products  ?? mockData.topProducts
  const storeSales     = filteredCSV?.storeSales     ?? csvData?.storeSales     ?? []
  const categorySales  = filteredCSV?.categorySales  ?? csvData?.categorySales  ?? []
  const monthlyChart   = filteredCSV?.monthlyChart   ?? csvData?.monthlyChart   ?? mockData.forecastChart

  const effectiveKpis = {
    ...kpis,
    total_sales: filteredCSV?.totalRevenue ?? kpis.total_sales,
  }

  const data = {
    ...mockData,
    kpis: effectiveKpis,
    alertsData,
    fileName,
    forecastChart,
    topProducts,
    bottomProducts,
    top10Products,
    storeSales,
    categorySales,
    monthlyChart,
    stores: uniqueStores,
    categories: uniqueCategories,
    regions: uniqueRegions,
  }

  function toggleStore(store) {
    setSelectedStores(prev =>
      prev.includes(store) ? prev.filter(s => s !== store) : [...prev, store]
    )
  }

  function toggleCategory(cat) {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    )
  }

  function toggleRegion(region) {
    setSelectedRegions(prev =>
      prev.includes(region) ? prev.filter(r => r !== region) : [...prev, region]
    )
  }

  function resetFilters() {
    setHorizon('Next 90 days')
    setSelectedStores([])
    setSelectedCategories([])
    setSelectedRegions([])
    setFilteredKpis(null)
    setFilteredForecast(null)
    setFilteredAlerts(null)
  }

  return (
    <div className="db">

      <div
        className={`db-sidebar-overlay ${sidebarOpen ? 'open' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`db-sidebar ${sidebarOpen ? 'open' : ''}`}>

        <div className="db-sidebar-logo" onClick={() => navigate('/')}>
          <img src="/logo.webp" alt="InventoryIQ" className="db-sidebar-logo-img" />
        </div>

        <div className="db-sidebar-section">
          <p className="db-sidebar-label">Menu</p>
          <nav className="db-nav">
            {[
              { id: 'overview', icon: '📊', label: 'Overview' },
              { id: 'products', icon: '🏆', label: 'Products' },
              { id: 'analysis', icon: '📈', label: 'Analysis' },
            ].map(item => (
              <button
                key={item.id}
                className={`db-nav-btn ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => { setActiveTab(item.id); setSidebarOpen(false) }}
              >
                <span className="db-nav-icon">{item.icon}</span>
                <span>{item.label}</span>
                {activeTab === item.id && <span className="db-nav-pip" />}
              </button>
            ))}
          </nav>
        </div>

        <div className="db-sidebar-section">
          <p className="db-sidebar-label">Forecast Horizon</p>
          <div className="db-radio-group">
            {HORIZONS.map(h => (
              <label key={h} className="db-radio-item">
                <input type="radio" name="horizon" value={h} checked={horizon === h} onChange={() => setHorizon(h)} />
                <span>{h}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="db-sidebar-section">
          <p className="db-sidebar-label">
            Stores
            {selectedStores.length > 0 && <span className="db-filter-count">{selectedStores.length}</span>}
          </p>
          <div className="db-checkbox-group">
            {data.stores.map(store => (
              <label key={store} className="db-checkbox-item">
                <input type="checkbox" checked={selectedStores.includes(String(store))} onChange={() => toggleStore(String(store))} />
                <span>{store}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="db-sidebar-section">
          <p className="db-sidebar-label">
            Categories
            {selectedCategories.length > 0 && <span className="db-filter-count">{selectedCategories.length}</span>}
          </p>
          <div className="db-checkbox-group">
            {data.categories.map(cat => (
              <label key={cat} className="db-checkbox-item">
                <input type="checkbox" checked={selectedCategories.includes(cat)} onChange={() => toggleCategory(cat)} />
                <span>{cat}</span>
              </label>
            ))}
          </div>
        </div>

        {uniqueRegions.length > 0 && (
          <div className="db-sidebar-section">
            <p className="db-sidebar-label">
              Regions
              {selectedRegions.length > 0 && <span className="db-filter-count">{selectedRegions.length}</span>}
            </p>
            <div className="db-checkbox-group">
              {uniqueRegions.map(region => (
                <label key={region} className="db-checkbox-item">
                  <input type="checkbox" checked={selectedRegions.includes(region)} onChange={() => toggleRegion(region)} />
                  <span>{region}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="db-sidebar-bottom">
          {hasActiveFilters && (
            <button className="db-reset-btn" onClick={resetFilters}>↺ Reset Filters</button>
          )}
          <div className="db-file-chip">
            <span>📄</span>
            <span className="db-file-name">{fileName}</span>
          </div>
          <button className="db-new-file" onClick={() => navigate('/upload')}>
            + Upload New File
          </button>
        </div>

      </aside>

      <div className="db-main">
        <header className="db-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button className="db-hamburger" onClick={() => setSidebarOpen(!sidebarOpen)}>☰</button>
            <div className="db-header-left">
              <h1 className="db-header-title">
                {activeTab === 'overview' && 'Dashboard Overview'}
                {activeTab === 'products' && 'Products'}
                {activeTab === 'analysis' && 'Analysis'}
              </h1>
              <p className="db-header-sub">
                {activeTab === 'overview' && 'Your retail performance at a glance'}
                {activeTab === 'products' && 'Top and bottom performing products'}
                {activeTab === 'analysis' && 'Category trends and store performance'}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {isFiltering && (
              <span style={{ fontSize: '0.78rem', color: '#8aaac8' }}>⟳ Updating...</span>
            )}
            <button className="db-ai-btn">✦ AI Summary</button>
          </div>
        </header>

        <div className="db-content">
          {activeTab === 'overview' && <OverviewTab data={data} horizon={horizon} isFiltering={isFiltering} />}
          {activeTab === 'products' && <ProductsTab data={data} isFiltering={isFiltering} />}
          {activeTab === 'analysis' && <AnalysisTab data={data} isFiltering={isFiltering} />}
        </div>
      </div>

    </div>
  )
}

// ── OVERVIEW ──────────────────────────────────────────────────────────────────
function OverviewTab({ data, horizon, isFiltering }) {
  const { kpis, alertsData, forecastChart, monthlyChart } = data
  const alerts = alertsData?.alerts ?? []

  const projectedRevenue = () => {
    const base = kpis.total_sales
    if (horizon === 'Next 30 days')   return fmt(base * 0.085)
    if (horizon === 'Next 90 days')   return fmt(base * 0.24)
    if (horizon === 'Next 6 months')  return fmt(base * 0.48)
    if (horizon === 'Next 12 months') return fmt(base * 0.95)
    return fmt(base * 0.24)
  }

  const combinedChart = (() => {
    const merged = {}
    monthlyChart.forEach(d => {
      merged[d.date] = { date: d.date, actual: d.total_sales ?? d.value ?? null, forecast: null }
    })
    forecastChart.forEach(d => {
      if (merged[d.date]) {
        // Bridge point — show both actual and forecast at the junction
        merged[d.date].forecast = d.value ?? null
      } else {
        merged[d.date] = { date: d.date, actual: null, forecast: d.value ?? null }
      }
    })
    return Object.values(merged).sort((a, b) => String(a.date).localeCompare(String(b.date)))
  })()

  return (
    <div className="tab">

      <div className="ai-insight">
        <span className="ai-insight-icon">✦</span>
        <span className="ai-insight-label">AI INSIGHT</span>
        <span className="ai-insight-text">
          Sales are {kpis.forecast_direction} — model accuracy MAE {kpis.mae ?? 'N/A'}. {alerts.length} products need your attention.
        </span>
        <button className="ai-insight-btn">Full Summary</button>
      </div>

      <div className="kpi-grid">
        <div className="kpi-hero">
          <div className="kpi-hero-bg" />
          <p className="kpi-hero-label">Total Revenue</p>
          <p className="kpi-hero-value">{fmt(kpis.total_sales)}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Sales Trend</p>
          <p className="kpi-value" style={{textTransform:'capitalize'}}>{kpis.forecast_direction}</p>
        </div>
        <div className="kpi-card" style={{
          background: (alertsData?.total ?? 0) === 0
            ? 'linear-gradient(135deg, #14532d 0%, #16a34a 100%)'
            : 'linear-gradient(135deg, #7f1d1d 0%, #ef4444 100%)',
          boxShadow: (alertsData?.total ?? 0) === 0
            ? '0 4px 16px rgba(22,163,74,0.4)'
            : '0 4px 16px rgba(239,68,68,0.4)'
        }}>
          <p className="kpi-label">Active Alerts</p>
          <p className="kpi-value">{alertsData?.total ?? 0}</p>
          <p className="kpi-delta" style={{ color: 'rgba(255,255,255,0.8)' }}>
            {(alertsData?.total ?? 0) === 0 ? '✅ All clear' : `⚠ ${alertsData?.total} need attention`}
          </p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Projected Revenue</p>
          <p className="kpi-value">{projectedRevenue()}</p>
          <p className="kpi-delta kpi-neutral">→ {horizon}</p>
        </div>
      </div>

      <div className="bottom-row">
        <div className="panel">
          <p className="panel-title">Sales Forecast</p>
          <p className="panel-sub">Historical performance vs projected growth</p>
          <div className="chart-legend">
            <span><span style={{display:'inline-block', width:8, height:8, borderRadius:'50%', background:'#1e3a5f', marginRight:4}} />Historical</span>
            <span><span style={{display:'inline-block', width:8, height:8, borderRadius:'50%', background:'#2196f3', marginRight:4}} />Forecast</span>
          </div>
          <div className={`chart-wrap ${isFiltering ? 'updating' : ''}`}>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={combinedChart} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} interval={Math.floor(combinedChart.length / 8)} />
                <YAxis tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={v => fmt(v)} width={60} />
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #dce3ed', borderRadius: 8, fontSize: 12 }}
                  formatter={(value, name) => [fmt(value), name === 'actual' ? '📊 Historical' : '📈 Forecast']}
                />
                <Line type="monotone" dataKey="actual" stroke="#1e3a5f" strokeWidth={2.5} dot={false} connectNulls={false} />
                <Line type="monotone" dataKey="forecast" stroke="#2196f3" strokeWidth={2.5} dot={false} strokeDasharray="5 5" connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header-row">
            <div>
              <p className="panel-title">Alert Center</p>
              <p className="panel-sub">{alertsData?.total ?? 0} active alerts</p>
            </div>
            <span className="badge-red">{alertsData?.total ?? 0} Active</span>
          </div>
          <div className="alert-list">
            {alerts.length === 0 ? (
              <p style={{color:'#8aaac8', fontSize:'0.82rem', padding:'1rem 0'}}>No alerts detected</p>
            ) : alerts.map((a, i) => {
              const isDown = a.metric?.includes('below')
              const cardColor = isDown ? '#fef2f2' : '#f0fdf4'
              const borderColor = isDown ? '#ef4444' : '#22c55e'
              const plainEnglish = isDown
                ? `⚠️ Sales have unexpectedly dropped — this item may need attention`
                : `✅ Sales have unexpectedly spiked — this item is performing above normal`
              return (
                <div key={i} className="alert-row" style={{ borderLeftColor: borderColor, backgroundColor: cardColor, borderRadius: '8px', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '1.1rem', flexShrink: 0, marginTop: '2px' }}>
                    {isDown ? '📉' : '📈'}
                  </span>
                  <div>
                    <p className="alert-name" style={{ color: isDown ? '#ef4444' : '#16a34a' }}>
                      {a.product_name} · {
                        !isDown && a.alert_type === 'Sales Anomaly' ? 'Demand Spike' :
                        isDown && a.alert_type === 'Sales Anomaly' ? 'Demand Drop' :
                        a.alert_type
                      }
                    </p>
                    <p className="alert-metric">{plainEnglish}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

    </div>
  )
}

// ── PRODUCTS ──────────────────────────────────────────────────────────────────
function ProductsTab({ data, isFiltering }) {
  const { topProducts, bottomProducts, top10Products } = data
  const chartData = top10Products.slice(0, 10).map(p => ({ name: p.product, revenue: p.total_sales })).reverse()

  return (
    <div className="tab">
      <div className="two-col">
        <div className="panel">
          <p className="panel-title">Top Performers</p>
          <p className="panel-sub">Products driving the most revenue</p>
          <div style={{marginTop: '1rem'}}>
            {topProducts.slice(0, 5).map((row, i) => (
              <div key={i} className="product-row">
                <div className="product-left">
                  <span className="rank rank-blue">{i + 1}</span>
                  <span className="product-name">{row.product}</span>
                </div>
                <span className="product-val val-blue">{fmt(row.total_sales)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <p className="panel-title">Underperformers</p>
          <p className="panel-sub">Products generating the least revenue</p>
          <div style={{marginTop: '1rem'}}>
            {bottomProducts.slice(0, 5).map((row, i) => (
              <div key={i} className="product-row">
                <div className="product-left">
                  <span className="rank rank-red">{i + 1}</span>
                  <span className="product-name">{row.product}</span>
                </div>
                <span className="product-val val-red">{fmt(row.total_sales)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <p className="panel-title">Top 10 Products by Revenue</p>
        <p className="panel-sub">Your highest earning products across all stores</p>
        <div className={`chart-wrap ${isFiltering ? 'updating' : ''}`}>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 10, right: 80, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={v => fmt(v)} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#1e3a5f', fontWeight: 500 }} axisLine={false} tickLine={false} width={160} interval={0} />
              <Tooltip
                contentStyle={{ background: '#fff', border: '1px solid #dce3ed', borderRadius: 8, fontSize: 12 }}
                formatter={(value, name, props) => [fmt(value), props.payload.name]}
                labelFormatter={() => ''}
              />
              <Bar dataKey="revenue" radius={[0, 4, 4, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ── ANALYSIS ──────────────────────────────────────────────────────────────────
function AnalysisTab({ data, isFiltering }) {
  const { categorySales, storeSales, monthlyChart } = data
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

  const yoyData = (() => {
    const byYearMonth = {}
    monthlyChart.forEach(d => {
      const year = d.date.slice(0, 4)
      const month = d.date.slice(5, 7)
      if (!byYearMonth[month]) byYearMonth[month] = { month }
      byYearMonth[month][year] = d.total_sales
    })
    return Object.values(byYearMonth).sort((a, b) => a.month.localeCompare(b.month))
  })()

  const years = [...new Set(monthlyChart.map(d => d.date.slice(0, 4)))].sort()

  return (
    <div className="tab">

      <div className="panel">
        <p className="panel-title">Year-over-Year Revenue Comparison</p>
        <p className="panel-sub">Monthly revenue compared across each year in your dataset</p>
        <div className={`chart-wrap ${isFiltering ? 'updating' : ''}`}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={yoyData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={m => MONTHS[parseInt(m) - 1]} />
              <YAxis tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={v => fmt(v)} width={60} />
              <Tooltip
                contentStyle={{ background: '#fff', border: '1px solid #dce3ed', borderRadius: 8, fontSize: 12 }}
                formatter={(value, name) => [fmt(value), name]}
                labelFormatter={m => MONTHS[parseInt(m) - 1]}
              />
              {years.map((year, i) => (
                <Line key={year} type="monotone" dataKey={year} stroke={BAR_COLORS[i % BAR_COLORS.length]} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} name={`${year}`} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <p className="panel-title">Revenue by Category</p>
          <p className="panel-sub">Total sales per category</p>
          {categorySales.length === 0 ? (
            <div className="chart-zone" style={{minHeight: '200px', marginTop: '1rem'}}>No category data in this dataset</div>
          ) : (
            <div className={`chart-wrap ${isFiltering ? 'updating' : ''}`}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={categorySales.map(c => ({ name: c.category, revenue: c.total_sales }))} margin={{ top: 10, right: 20, left: 10, bottom: 50 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} angle={-30} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={v => fmt(v)} width={60} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #dce3ed', borderRadius: 8, fontSize: 12 }} formatter={(value) => [fmt(value), 'Revenue']} />
                  <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
                    {categorySales.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="panel">
          <p className="panel-title">Store Comparison</p>
          <p className="panel-sub">Total revenue by store</p>
          {storeSales.length === 0 ? (
            <div className="chart-zone" style={{minHeight: '200px', marginTop: '1rem'}}>No store data in this dataset</div>
          ) : (
            <div className={`chart-wrap ${isFiltering ? 'updating' : ''}`}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={storeSales
                    .sort((a, b) => {
                      const numA = parseInt(String(a.store).replace(/\D/g, '')) || 0
                      const numB = parseInt(String(b.store).replace(/\D/g, '')) || 0
                      return numA - numB
                    })
                    .map(s => ({ name: `Store ${s.store}`, revenue: s.total_sales }))}
                  margin={{ top: 10, right: 20, left: 10, bottom: 50 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f8" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} angle={-30} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize: 10, fill: '#8aaac8' }} axisLine={false} tickLine={false} tickFormatter={v => fmt(v)} width={60} />
                  <Tooltip contentStyle={{ background: '#fff', border: '1px solid #dce3ed', borderRadius: 8, fontSize: 12 }} formatter={(value) => [fmt(value), 'Revenue']} />
                  <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
                    {storeSales.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DashboardPage