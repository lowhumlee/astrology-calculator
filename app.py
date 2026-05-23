"""
Traditional Astrology Chart Calculator
Streamlit UI — natal chart with AstroSeek chart image.
"""

import streamlit as st
import pandas as pd
import requests
from datetime import date, time
import json
import os
from engine import (
    calculate_chart, build_astroseek_url,
    get_essential_dignities_table, get_house_lords_table,
    _lon_to_dms, SIGNS, SIGN_SYMBOLS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Traditional Astrology Calculator",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e0e1a; }
    .stApp { background-color: #0e0e1a; color: #e8d5a3; }
    h1, h2, h3 { color: #c8a96e; font-family: 'Georgia', serif; }
    .planet-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #c8a96e33;
        border-radius: 8px;
        padding: 12px;
        margin: 4px 0;
    }
    .dignity-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .domicile { background: #1a472a; color: #69c17c; }
    .exaltation { background: #1a2a47; color: #69a8c1; }
    .triplicity { background: #2a1a47; color: #a069c1; }
    .term { background: #472a1a; color: #c19a69; }
    .face { background: #1a1a1a; color: #999; }
    .peregrine { background: #3a1a1a; color: #c16969; }
    .stDataFrame { background: #1a1a2e; }
    .metric-container {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #c8a96e44;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Geocoding ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def geocode_city(city: str) -> dict | None:
    """Geocode using Nominatim (OSM). Returns dict with lat, lon, display_name."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 5}
        headers = {"User-Agent": "TraditionalAstrologyApp/1.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        results = r.json()
        return results if results else None
    except Exception:
        return None

# ── Sidebar — Input form ──────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⭐ Birth Data")
    st.markdown("---")

    person_name = st.text_input("Name (optional)", value="", placeholder="e.g. John Smith")

    col1, col2 = st.columns(2)
    with col1:
        birth_date = st.date_input(
            "Birth Date",
            value=date(1990, 6, 15),
            min_value=date(1800, 1, 1),
            max_value=date(2100, 12, 31),
        )
    with col2:
        unknown_time = st.checkbox("Time unknown", value=False)
        if not unknown_time:
            birth_time = st.time_input("Birth Time (local)", value=time(12, 0))
        else:
            birth_time = time(12, 0)
            st.caption("Noon chart will be used.")

    st.markdown("### 📍 Birth Place")
    city_input = st.text_input("City", value="Varna, Bulgaria")

    geo_results = None
    selected_lat, selected_lon, selected_city = None, None, city_input

    if city_input:
        geo_results = geocode_city(city_input)
        if geo_results:
            options = [r["display_name"][:60] for r in geo_results]
            if len(options) > 1:
                chosen = st.selectbox("Select location", options)
                idx = options.index(chosen)
            else:
                idx = 0
                st.caption(f"📌 {geo_results[0]['display_name'][:60]}")
            selected_lat = float(geo_results[idx]["lat"])
            selected_lon = float(geo_results[idx]["lon"])
            selected_city = geo_results[idx]["display_name"].split(",")[0]
        else:
            st.warning("City not found. Enter coordinates manually.")
            selected_lat = st.number_input("Latitude", value=43.2167, format="%.4f")
            selected_lon = st.number_input("Longitude", value=27.9167, format="%.4f")
            selected_city = city_input

    st.markdown("---")
    calculate_btn = st.button("✨ Calculate Chart", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚙️ Options")
    show_aspects = st.checkbox("Show aspects table", value=True)
    show_antiscia = st.checkbox("Show antiscia", value=True)
    show_arabic_parts = st.checkbox("Show Arabic Parts", value=True)

# ── Main area ────────────────────────────────────────────────────────────────

st.markdown("# 🌙 Traditional Astrology Calculator")
st.markdown("*Regiomontanus houses · Traditional rulerships · Essential dignities*")
st.markdown("*Sources: Lilly, Frawley*")
st.markdown("---")

if "chart" not in st.session_state:
    st.session_state.chart = None

if calculate_btn and selected_lat is not None:
    with st.spinner("Computing chart..."):
        try:
            chart = calculate_chart(
                name=person_name or "Native",
                year=birth_date.year,
                month=birth_date.month,
                day=birth_date.day,
                hour=birth_time.hour,
                minute=birth_time.minute,
                city=selected_city,
                lat=selected_lat,
                lon=selected_lon,
                unknown_time=unknown_time,
            )
            st.session_state.chart = chart
            st.session_state.astroseek_url = build_astroseek_url(chart)
        except Exception as e:
            st.error(f"Calculation error: {e}")
            st.exception(e)

chart = st.session_state.get("chart")

if chart is None:
    st.markdown("""
    ### How to use
    1. Enter birth date, time, and city in the sidebar
    2. Click **Calculate Chart**
    3. View planetary positions, dignities, house lords, and the chart wheel

    ---
    *This calculator uses the Swiss Ephemeris (pyswisseph) for sub-arcminute accuracy,
    validated against AstroSeek to within 0.01°.*
    """)
    st.stop()

# ── Chart header ─────────────────────────────────────────────────────────────

st.markdown(f"## {chart.name}")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="metric-container">
    <div style="font-size:11px;color:#888">Date</div>
    <div style="font-size:16px;font-weight:bold;color:#c8a96e">{chart.birth_date}</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-container">
    <div style="font-size:11px;color:#888">Time (local)</div>
    <div style="font-size:16px;font-weight:bold;color:#c8a96e">{chart.birth_time} UTC{chart.utc_offset:+.1f}</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="metric-container">
    <div style="font-size:11px;color:#888">Ascendant</div>
    <div style="font-size:16px;font-weight:bold;color:#c8a96e">{chart.asc_dms}</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="metric-container">
    <div style="font-size:11px;color:#888">Midheaven (MC)</div>
    <div style="font-size:16px;font-weight:bold;color:#c8a96e">{chart.mc_dms}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

col_info, col_chart = st.columns([1, 2])
with col_info:
    st.markdown(f"""
    - **Place:** {chart.city}
    - **Lat/Lon:** {chart.latitude:.4f}° / {chart.longitude:.4f}°
    - **Timezone:** {chart.timezone}
    - **Chart type:** {"☀️ Day chart" if chart.is_day_chart else "🌙 Night chart"}
    - **House system:** Regiomontanus
    - **Julian Day:** {chart.julian_day:.4f}
    """)

with col_chart:
    url = st.session_state.get("astroseek_url", "")
    if url:
        st.image(url, caption="Chart wheel (AstroSeek)", use_container_width=True)
        with st.expander("🔗 Chart image URL"):
            st.code(url, language="text")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["🪐 Planets", "🏠 Houses & Lords", "⚡ Aspects", "📐 Arabic Parts & Antiscia"])

# ── Tab 1: Planets ────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Planetary Positions & Essential Dignities")
    st.caption("House system: Regiomontanus · Rulerships: Traditional (Lilly)")

    dignity_colors = {
        "Domicile": "#69c17c", "Exaltation": "#69a8c1",
        "Triplicity": "#a069c1", "Term": "#c19a69",
        "Face": "#999999", "Peregrine": "#c16969", "—": "#555",
    }

    rows = get_essential_dignities_table(chart)
    if rows:
        df = pd.DataFrame(rows)

        def color_dignity(val):
            c = dignity_colors.get(val, "#555")
            return f"color: {c}; font-weight: bold"

        styled = df.style.applymap(color_dignity, subset=["Dignity"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Dignity Legend")
    cols = st.columns(6)
    labels = [("Domicile", "#69c17c"), ("Exaltation", "#69a8c1"), ("Triplicity", "#a069c1"),
              ("Term", "#c19a69"), ("Face", "#999"), ("Peregrine", "#c16969")]
    for col, (label, color) in zip(cols, labels):
        with col:
            st.markdown(f'<span style="color:{color};font-weight:bold">● {label}</span>', unsafe_allow_html=True)

# ── Tab 2: Houses & Lords ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### House Cusps & Traditional Lords")
    st.caption("Lord = ruling planet of sign on house cusp (Lilly's traditional rulerships)")

    rows = get_house_lords_table(chart)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    # Visual house summary
    st.markdown("#### House Lord Overview")
    cols = st.columns(4)
    for i, row in enumerate(rows):
        with cols[i % 4]:
            lord = chart.planets.get(row["Lord"])
            dignity_str = f" · {lord.dignity}" if lord else ""
            retro_str = " ℞" if (lord and lord.retrograde) else ""
            st.markdown(f"""<div class="planet-card">
            <b style="color:#c8a96e">House {row['House']}</b><br>
            <span style="font-size:12px;color:#888">{row['Sign']}</span><br>
            <b>{row['Lord']}</b>{retro_str}<br>
            <span style="font-size:11px;color:#aaa">{row['Lord Position']} · H{row['Lord House']}{dignity_str}</span>
            </div>""", unsafe_allow_html=True)

# ── Tab 3: Aspects ────────────────────────────────────────────────────────────
with tab3:
    if show_aspects and chart.aspects:
        st.markdown("### Aspects")
        st.caption(f"Total aspects found: {len(chart.aspects)}")

        aspect_icons = {
            "Conjunction": "☌", "Opposition": "☍", "Trine": "△",
            "Square": "□", "Sextile": "✶", "Quincunx": "⚻", "Semi-sextile": "⚺",
        }
        aspect_colors = {
            "Conjunction": "#c8a96e", "Opposition": "#c16969",
            "Trine": "#69c17c", "Square": "#c16969",
            "Sextile": "#69a8c1", "Quincunx": "#a069c1", "Semi-sextile": "#888",
        }

        # Filter controls
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            aspect_filter = st.multiselect(
                "Filter by aspect",
                options=list(aspect_icons.keys()),
                default=["Conjunction", "Opposition", "Trine", "Square", "Sextile"],
            )
        with col_f2:
            app_filter = st.selectbox("Applying/Separating", ["All", "Applying only", "Separating only"])

        filtered = [a for a in chart.aspects if a["aspect"] in aspect_filter]
        if app_filter == "Applying only":
            filtered = [a for a in filtered if a["applying"]]
        elif app_filter == "Separating only":
            filtered = [a for a in filtered if not a["applying"]]

        for asp in sorted(filtered, key=lambda x: x["orb"]):
            icon = aspect_icons.get(asp["aspect"], "")
            color = aspect_colors.get(asp["aspect"], "#888")
            app_label = "▶ Applying" if asp["applying"] else "◀ Separating"
            p1 = chart.planets.get(asp["planet1"])
            p2 = chart.planets.get(asp["planet2"])
            s1 = p1.symbol if p1 else ""
            s2 = p2.symbol if p2 else ""
            st.markdown(
                f'<div class="planet-card">'
                f'<span style="color:{color};font-size:18px">{icon}</span> '
                f'<b>{s1} {asp["planet1"]}</b> {asp["aspect"]} <b>{s2} {asp["planet2"]}</b>'
                f' &nbsp; <span style="color:#888;font-size:12px">orb {asp["orb"]}° · {app_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No aspects to display.")

# ── Tab 4: Arabic Parts & Antiscia ───────────────────────────────────────────
with tab4:
    if show_arabic_parts:
        st.markdown("### Arabic Parts")
        st.caption("Traditional formula: Day charts Asc + Moon – Sun; Night charts Asc + Sun – Moon (Lilly)")

        pof_sign, pof_deg = chart.part_of_fortune, chart.part_of_fortune
        pof_dms = _lon_to_dms(chart.part_of_fortune)
        pof_house = None
        for i in range(12):
            next_i = (i + 1) % 12
            cs = chart.house_cusps[i]
            ce = chart.house_cusps[next_i]
            lon = chart.part_of_fortune
            if ce < cs:
                if lon >= cs or lon < ce:
                    pof_house = i + 1; break
            else:
                if cs <= lon < ce:
                    pof_house = i + 1; break

        st.markdown(f"""<div class="planet-card">
        <b style="color:#c8a96e">⊕ Part of Fortune</b><br>
        <b style="font-size:18px">{pof_dms}</b><br>
        <span style="color:#aaa">House {pof_house or '?'} · {'Day formula' if chart.is_day_chart else 'Night formula'}</span>
        </div>""", unsafe_allow_html=True)

    if show_antiscia:
        st.markdown("---")
        st.markdown("### Antiscia")
        st.caption("Mirror points across the Cancer/Capricorn solstice axis (Frawley ch. 7)")
        st.caption("Planets in close conjunction/opposition by antiscion (within 2°) influence each other in a hidden way.")

        antiscia_rows = []
        planet_list = list(chart.planets.values())
        for i, p1 in enumerate(planet_list):
            for p2 in planet_list[i + 1:]:
                from engine import _aspect_angle
                arc = _aspect_angle(p1.antiscion, p2.longitude)
                if arc <= 2.0:
                    antiscia_rows.append({
                        "Planet 1": f"{p1.symbol} {p1.name}",
                        "Antiscion": _lon_to_dms(p1.antiscion),
                        "↔": "conj",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{arc:.2f}°",
                    })
                arc2 = _aspect_angle(p1.antiscion, p2.longitude)
                # Also check opposition by antiscion
                opp_arc = _aspect_angle((p1.antiscion + 180) % 360, p2.longitude)
                if opp_arc <= 2.0:
                    antiscia_rows.append({
                        "Planet 1": f"{p1.symbol} {p1.name}",
                        "Antiscion": _lon_to_dms(p1.antiscion),
                        "↔": "oppo",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{opp_arc:.2f}°",
                    })

        if antiscia_rows:
            df_anti = pd.DataFrame(antiscia_rows)
            st.dataframe(df_anti, use_container_width=True, hide_index=True)
        else:
            st.info("No antiscia conjunctions/oppositions within 2° orb for this chart.")

        st.markdown("---")
        st.markdown("#### All Antiscia Positions")
        anti_all = []
        for pname, p in chart.planets.items():
            anti_all.append({
                "Planet": f"{p.symbol} {pname}",
                "Position": p.dms,
                "Antiscion": _lon_to_dms(p.antiscion),
                "Antiscion Sign": p.antiscion_sign,
            })
        st.dataframe(pd.DataFrame(anti_all), use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#555;font-size:12px'>"
    "Calculations: Swiss Ephemeris (pyswisseph) · House system: Regiomontanus · "
    "Chart image: AstroSeek · Sources: William Lilly, John Frawley"
    "</div>",
    unsafe_allow_html=True,
)
