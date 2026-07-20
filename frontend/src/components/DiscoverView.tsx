import { useEffect, useMemo, useState } from 'react'
import type { DiscoverData, Property } from '../types'

interface Props {
  data: DiscoverData
  onBack: () => void
}

const BEDROOM_TYPES: { key: keyof Property['bedrooms']; label: string }[] = [
  { key: 'studio', label: 'Studio' },
  { key: 'one', label: '1 bed' },
  { key: 'two', label: '2 bed' },
  { key: 'three', label: '3 bed' },
  { key: 'four', label: '4 bed' },
]

function titleCase(text: string): string {
  return text.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
}

function bedroomSummary(p: Property): string {
  const parts = BEDROOM_TYPES.filter((b) => p.bedrooms[b.key] > 0).map(
    (b) => `${p.bedrooms[b.key]} ${b.label}`,
  )
  return parts.length ? parts.join(' · ') : 'Unit mix not reported'
}

// Keyless location preview: OpenStreetMap embed with a pin; the button opens
// Google Maps in a new tab, pin pre-placed at the exact coordinates.
function PropertyMap({ lat, lon, name, precise, precisionCode }: {
  lat: number; lon: number; name: string; precise: boolean; precisionCode: string
}) {
  const bbox = `${lon - 0.006},${lat - 0.004},${lon + 0.006},${lat + 0.004}`
  const embed = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`
  const gmaps = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`
  return (
    <div className="property-map">
      <iframe
        className="property-map-frame"
        title={`Map showing ${titleCase(name)}`}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
        src={embed}
      />
      <div className="property-map-row">
        <a className="btn-secondary btn-sm" href={gmaps} target="_blank" rel="noopener noreferrer">
          Open in Google Maps ↗
        </a>
        {!precise && (
          <span className="muted property-map-note">Approximate location (geocode precision {precisionCode}).</span>
        )}
      </div>
    </div>
  )
}

// Detail popup. Read-only; a source link is the only outbound action, opened by the renter.
function PropertyModal({ property, notice, onClose }: { property: Property; notice: string; onClose: () => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal discover-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="property-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="discover-modal-head">
          <h2 id="property-title">{titleCase(property.project_name)}</h2>
          <button type="button" className="btn-secondary btn-sm" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>

        <p className="availability-banner" role="note">
          <span className="availability-dot" aria-hidden="true" />
          Availability: Unknown — {notice}
        </p>

        <dl className="discover-detail-grid">
          <div><dt>Address</dt><dd>{titleCase(property.address)}, {titleCase(property.city)}, {property.state} {property.zip}</dd></div>
          <div><dt>Unit mix</dt><dd>{bedroomSummary(property)}</dd></div>
          <div><dt>Total units</dt><dd>{property.total_units ?? 'Not reported'}</dd></div>
          <div><dt>Low-income units</dt><dd>{property.low_income_units ?? 'Not reported'}</dd></div>
          <div><dt>Placed in service</dt><dd>{property.year_placed_in_service || 'Not reported'}</dd></div>
          <div><dt>Year allocated</dt><dd>{property.year_allocated || 'Not reported'}</dd></div>
          <div><dt>Metro (CBSA)</dt><dd>{property.cbsa_name}</dd></div>
          <div><dt>HUD ID</dt><dd>{property.hud_id}</dd></div>
        </dl>

        {property.latitude != null && property.longitude != null && (
          <PropertyMap
            lat={property.latitude}
            lon={property.longitude}
            name={property.project_name}
            precise={property.geocode_precision_code === 'R' || property.geocode_precision_code === '4'}
            precisionCode={property.geocode_precision_code}
          />
        )}

        {property.data_quality_flags.length > 0 && (
          <p className="discover-flags">
            Data-quality flags: {property.data_quality_flags.join(', ')}
          </p>
        )}

        <p className="discover-source">
          Retrieved {property.retrieved_utc}.{' '}
          <a href={property.source_url} target="_blank" rel="noopener noreferrer">View HUD source</a>
        </p>
      </div>
    </div>
  )
}

export default function DiscoverView({ data, onBack }: Props) {
  const [cityFilter, setCityFilter] = useState<string>('all')
  const [bedFilters, setBedFilters] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Property | null>(null)

  const cities = useMemo(
    () => Array.from(new Set(data.properties.map((p) => p.city))).sort(),
    [data.properties],
  )

  const filtered = useMemo(() => {
    return data.properties.filter((p) => {
      if (cityFilter !== 'all' && p.city !== cityFilter) return false
      if (bedFilters.size > 0 && ![...bedFilters].some((b) => p.bedrooms[b as keyof Property['bedrooms']] > 0)) {
        return false
      }
      if (query.trim()) {
        const q = query.trim().toLowerCase()
        if (!p.project_name.toLowerCase().includes(q) && !p.address.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [data.properties, cityFilter, bedFilters, query])

  function toggleBed(key: string) {
    setBedFilters((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function clearFilters() {
    setCityFilter('all')
    setBedFilters(new Set())
    setQuery('')
  }

  const hasFilters = cityFilter !== 'all' || bedFilters.size > 0 || query.trim() !== ''

  return (
    <section className="discover" aria-labelledby="discover-heading">
      <div className="discover-head">
        <div>
          <h2 id="discover-heading">Discover properties</h2>
          <p className="lede">{data.data_notice}</p>
        </div>
        <button type="button" className="btn-secondary" onClick={onBack}>Back to dashboard</button>
      </div>

      <div className="discover-layout">
        <aside className="discover-filters" aria-label="Filters">
          <h3 className="doc-title">Filters</h3>

          <label className="filter-label" htmlFor="discover-search">Search name or address</label>
          <input
            id="discover-search"
            className="discover-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Burbank"
          />

          <label className="filter-label" htmlFor="discover-city">City</label>
          <select id="discover-city" value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
            <option value="all">All cities</option>
            {cities.map((c) => (
              <option key={c} value={c}>{titleCase(c)}</option>
            ))}
          </select>

          <span className="filter-label">Has unit type</span>
          <div className="filter-checks">
            {BEDROOM_TYPES.map((b) => (
              <label key={b.key} className="filter-check">
                <input
                  type="checkbox"
                  checked={bedFilters.has(b.key)}
                  onChange={() => toggleBed(b.key)}
                />
                {b.label}
              </label>
            ))}
          </div>

          {hasFilters && (
            <button type="button" className="btn-secondary btn-sm" onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </aside>

        <div className="discover-results">
          <p className="discover-count" role="status">
            Showing {filtered.length} of {data.properties.length} properties
            {hasFilters && ' (filtered)'}
          </p>

          {filtered.length === 0 ? (
            <p className="muted">No properties match these filters. Clear them to see the full list.</p>
          ) : (
            <ul className="discover-grid">
              {filtered.map((p) => (
                <li key={p.hud_id}>
                  <button type="button" className="property-card" onClick={() => setSelected(p)}>
                    <span className="availability-chip">Availability: Unknown</span>
                    <span className="property-name">{titleCase(p.project_name)}</span>
                    <span className="property-loc muted">{titleCase(p.city)}, {p.state} {p.zip}</span>
                    <span className="property-beds">{bedroomSummary(p)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {selected && (
        <PropertyModal property={selected} notice={data.availability_notice} onClose={() => setSelected(null)} />
      )}
    </section>
  )
}
