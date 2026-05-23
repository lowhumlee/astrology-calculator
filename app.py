"""
Traditional Astrology Chart Calculator
Streamlit UI — natal chart with inline SVG chart wheel via kerykeion.
"""

import streamlit as st
import pandas as pd
import requests
import os
import re
import tempfile
from datetime import date
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from engine import (
    calculate_chart, build_astroseek_url,
    get_essential_dignities_table, get_house_lords_table,
    _lon_to_dms, SIGNS, SIGN_SYMBOLS,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Traditional Astrology Calculator",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Element colours ──────────────────────────────────────────────────────────
FIRE_SIGNS  = {"Aries", "Leo", "Sagittarius"}
EARTH_SIGNS = {"Taurus", "Virgo", "Capricorn"}
AIR_SIGNS   = {"Gemini", "Libra", "Aquarius"}
WATER_SIGNS = {"Cancer", "Scorpio", "Pisces"}

ELEMENT_COLOR = {
    **{s: "#e05555" for s in FIRE_SIGNS},   # red
    **{s: "#888888" for s in EARTH_SIGNS},  # grey
    **{s: "#55aa55" for s in AIR_SIGNS},    # green
    **{s: "#5599dd" for s in WATER_SIGNS},  # blue
}

def sign_colored(sign: str) -> str:
    color = ELEMENT_COLOR.get(sign, "#c8a96e")
    idx = SIGNS.index(sign) if sign in SIGNS else 0
    return f'<span style="color:{color};font-weight:bold">{SIGN_SYMBOLS[idx]} {sign}</span>'

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
        padding: 10px 14px;
        margin: 3px 0;
        font-size: 14px;
    }
    .metric-container {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #c8a96e44;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: center;
    }
    /* kill streamlit's iframe border around SVG */
    iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Geocoding ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def geocode_city(city: str):
    """Nominatim geocode. Returns list of result dicts or None."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 5},
            headers={"User-Agent": "TradAstroCalc/1.0 (educational)"},
            timeout=10,
        )
        results = r.json()
        return results if results else None
    except Exception:
        return None

# ── SVG chart wheel via kerykeion ─────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def make_chart_svg(year, month, day, hour, minute, lat, lng, tz_str, name):
    """Generate natal chart SVG using kerykeion (Regiomontanus, offline)."""
    try:
        subject = AstrologicalSubject(
            name, year, month, day, hour, minute,
            lat=lat, lng=lng, tz_str=tz_str,
            online=False,
            houses_system_identifier="R",  # Regiomontanus
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            chart = KerykeionChartSVG(subject, chart_type="Natal", new_output_directory=tmpdir)
            chart.makeSVG()
            svg_path = os.path.join(tmpdir, f"{name} - Natal Chart.svg")
            if not os.path.exists(svg_path):
                # Try alternate filename
                for f in os.listdir(tmpdir):
                    if f.endswith(".svg"):
                        svg_path = os.path.join(tmpdir, f)
                        break
            with open(svg_path) as f:
                return f.read()
    except Exception as e:
        return None

# ── Sidebar — Input form ──────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌙 Chart Data")
    st.markdown("---")

    person_name = st.text_input("Name (optional)", value="", placeholder="e.g. John Smith")

    birth_date = st.date_input(
        "Date",
        value=date(1990, 6, 15),
        min_value=date(1600, 1, 1),
        max_value=date(2100, 12, 31),
    )

    st.markdown("**Time (local, HH:MM)**")
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        birth_hour = st.number_input("Hour", min_value=0, max_value=23, value=12, step=1, format="%d")
    with t_col2:
        birth_minute = st.number_input("Min", min_value=0, max_value=59, value=0, step=1, format="%d")

    st.markdown("### 📍 Place")
    city_input = st.text_input("City", value="Varna, Bulgaria",
                                placeholder="e.g. Paris, France")

    selected_lat, selected_lon, selected_city, selected_tz = None, None, city_input, None

    if city_input:
        with st.spinner("Looking up city…"):
            geo_results = geocode_city(city_input)

        if geo_results:
            if len(geo_results) > 1:
                options = [r["display_name"][:55] for r in geo_results]
                chosen_idx = st.selectbox("Select location", range(len(options)),
                                          format_func=lambda i: options[i])
            else:
                chosen_idx = 0
            selected_lat  = float(geo_results[chosen_idx]["lat"])
            selected_lon  = float(geo_results[chosen_idx]["lon"])
            selected_city = geo_results[chosen_idx]["display_name"].split(",")[0].strip()
            # Derive timezone from coords
            from timezonefinder import TimezoneFinder
            selected_tz = TimezoneFinder().timezone_at(lat=selected_lat, lng=selected_lon) or "UTC"
            st.caption(f"📌 {selected_city} · {selected_lat:.3f}°, {selected_lon:.3f}°  tz: {selected_tz}")
        else:
            st.warning("City not found — enter coordinates manually.")
            selected_lat  = st.number_input("Latitude",  value=43.2167, format="%.4f")
            selected_lon  = st.number_input("Longitude", value=27.9167, format="%.4f")
            selected_city = city_input
            from timezonefinder import TimezoneFinder
            selected_tz = TimezoneFinder().timezone_at(lat=selected_lat, lng=selected_lon) or "UTC"

    st.markdown("---")
    calculate_btn = st.button("✨ Calculate Chart", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚙️ Display")
    show_aspects   = st.checkbox("Aspects table",   value=True)
    show_antiscia  = st.checkbox("Antiscia",         value=True)
    show_arabic    = st.checkbox("Arabic Parts",     value=True)

# ── Compute ───────────────────────────────────────────────────────────────────

st.markdown("# 🌙 Traditional Astrology Calculator")
st.markdown("*Regiomontanus houses · Traditional rulerships · Essential dignities · Sources: Lilly, Frawley*")
st.markdown("---")

if "chart" not in st.session_state:
    st.session_state.chart = None

if calculate_btn and selected_lat is not None:
    with st.spinner("Computing chart…"):
        try:
            chart = calculate_chart(
                name=person_name or "Native",
                year=birth_date.year, month=birth_date.month, day=birth_date.day,
                hour=int(birth_hour), minute=int(birth_minute),
                city=selected_city,
                lat=selected_lat, lon=selected_lon,
            )
            st.session_state.chart      = chart
            st.session_state.chart_tz   = selected_tz
            st.session_state.chart_lat  = selected_lat
            st.session_state.chart_lon  = selected_lon
        except Exception as e:
            st.error(f"Calculation error: {e}")
            st.exception(e)

chart = st.session_state.get("chart")

if chart is None:
    st.markdown("""
    ### How to use
    1. Enter date, time (keyboard), and city in the sidebar
    2. Click **Calculate Chart**
    3. View the chart wheel, planetary positions, dignities, aspects, and more

    *Swiss Ephemeris accuracy — validated against AstroSeek to within 0.01°.*
    """)
    st.stop()

# ── Chart header metrics ──────────────────────────────────────────────────────

st.markdown(f"## {chart.name}")
c1, c2, c3, c4 = st.columns(4)
for col, label, val in [
    (c1, "Date",        chart.birth_date),
    (c2, "Time (local)", f"{chart.birth_time}  UTC{chart.utc_offset:+.1f}"),
    (c3, "Ascendant",   chart.asc_dms),
    (c4, "MC",          chart.mc_dms),
]:
    with col:
        st.markdown(f"""<div class="metric-container">
        <div style="font-size:11px;color:#888">{label}</div>
        <div style="font-size:15px;font-weight:bold;color:#c8a96e">{val}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Chart wheel + info ────────────────────────────────────────────────────────

col_info, col_wheel = st.columns([1, 2])

with col_info:
    asc_sign = chart.asc_sign
    mc_sign  = chart.mc_sign
    st.markdown(f"""
- **Place:** {chart.city}
- **Lat/Lon:** {chart.latitude:.4f}° / {chart.longitude:.4f}°
- **Timezone:** {chart.timezone}
- **Chart:** {"☀️ Day" if chart.is_day_chart else "🌙 Night"}
- **Houses:** Regiomontanus
- **ASC sign:** {sign_colored(asc_sign)}
- **MC sign:** {sign_colored(mc_sign)}
- **JD:** {chart.julian_day:.4f}
""", unsafe_allow_html=True)

with col_wheel:
    tz = st.session_state.get("chart_tz", "UTC")
    lat = st.session_state.get("chart_lat", chart.latitude)
    lon = st.session_state.get("chart_lon", chart.longitude)
    h, m_str = chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00")
    y, mo, d = chart.birth_date.split("-")
    svg_data = make_chart_svg(
        int(y), int(mo), int(d), int(h), int(m_str),
        lat, lon, tz,
        chart.name,
    )
    if svg_data:
        st.markdown(
            f'<div style="width:100%;max-width:680px;margin:auto">{svg_data}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("Chart wheel could not be generated.")
        astroseek_url = build_astroseek_url(chart)
        st.markdown(f"[Open chart on AstroSeek ↗]({astroseek_url})", unsafe_allow_html=False)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["🪐 Planets", "🏠 Houses & Lords", "⚡ Aspects", "📐 Parts & Antiscia"])

# ── Tab 1: Planets & dignities ────────────────────────────────────────────────
with tab1:
    st.markdown("### Planetary Positions & Essential Dignities")
    st.caption("Traditional rulerships (Lilly) · Ptolemaic terms · Chaldean faces")

    dignity_colors = {
        "Domicile":   "#69c17c",
        "Exaltation": "#69a8c1",
        "Triplicity": "#a069c1",
        "Term":       "#c19a69",
        "Face":       "#999999",
        "Peregrine":  "#c16969",
        "—":          "#555555",
    }

    rows = get_essential_dignities_table(chart)
    if rows:
        # Enrich Sign column with element colour
        for row in rows:
            # Extract plain sign name from dms string like "10°04' ♑"
            planet = chart.planets.get(row["Planet"].split(" ", 1)[-1])
            if planet:
                color = ELEMENT_COLOR.get(planet.sign, "#c8a96e")
                row["Sign"] = f"{planet.dms}"   # keep dms but we'll color via styler
                row["_sign"] = planet.sign
                row["_color"] = color

        df = pd.DataFrame(rows)

        def style_row(row):
            styles = [""] * len(row)
            dig_idx = df.columns.get_loc("Dignity")
            sign_idx = df.columns.get_loc("Sign")
            dig_val = row["Dignity"]
            sign_val = row.get("_sign", "")
            styles[dig_idx] = f"color: {dignity_colors.get(dig_val, '#555')}; font-weight: bold"
            styles[sign_idx] = f"color: {ELEMENT_COLOR.get(sign_val, '#c8a96e')}; font-weight: bold"
            return styles

        display_cols = [c for c in df.columns if not c.startswith("_")]
        styled = df[display_cols].style.apply(
            lambda row: style_row(row) if True else [""] * len(row),
            axis=1,
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Legend")
    dig_cols = st.columns(6)
    for col, (label, color) in zip(dig_cols, dignity_colors.items()):
        with col:
            st.markdown(f'<span style="color:{color};font-weight:bold">● {label}</span>',
                        unsafe_allow_html=True)
    st.markdown("")
    elem_cols = st.columns(4)
    for col, (label, color) in zip(elem_cols, [
        ("🔥 Fire", "#e05555"), ("🌱 Earth", "#888888"),
        ("💨 Air", "#55aa55"),  ("💧 Water", "#5599dd"),
    ]):
        with col:
            st.markdown(f'<span style="color:{color};font-weight:bold">{label}</span>',
                        unsafe_allow_html=True)

# ── Tab 2: Houses & lords ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### House Cusps & Traditional Lords")
    st.caption("Lord = ruler of sign on house cusp · Traditional rulerships only")

    rows = get_house_lords_table(chart)

    cols = st.columns(3)
    for i, row in enumerate(rows):
        with cols[i % 3]:
            lord = chart.planets.get(row["Lord"])
            sign = row["Sign"]
            sign_color = ELEMENT_COLOR.get(sign, "#c8a96e")
            dignity_str = f"<span style='color:{dignity_colors.get(lord.dignity,'#aaa')}'>{lord.dignity}</span>" if lord else ""
            retro_str   = " <span style='color:#c16969'>℞</span>" if (lord and lord.retrograde) else ""
            st.markdown(f"""<div class="planet-card">
            <b style="color:#c8a96e">H{row['House']}</b>
            &nbsp;<span style="color:{sign_color};font-size:13px">{SIGN_SYMBOLS[SIGNS.index(sign)] if sign in SIGNS else ''} {sign}</span><br>
            <b>{row['Lord']}</b>{retro_str} · {row['Lord Position']}<br>
            <small style="color:#aaa">in H{row['Lord House']} · {dignity_str}</small>
            </div>""", unsafe_allow_html=True)

# ── Tab 3: Aspects ────────────────────────────────────────────────────────────
with tab3:
    if show_aspects and chart.aspects:
        st.markdown("### Aspects")
        st.caption(f"{len(chart.aspects)} aspects · "
                   "<span style='color:#55aa55'>■ Applying</span> &nbsp; "
                   "<span style='color:#c16969'>■ Separating</span>",
                   unsafe_allow_html=True)

        aspect_icons = {
            "Conjunction": "☌", "Opposition": "☍", "Trine": "△",
            "Square": "□", "Sextile": "✶", "Quincunx": "⚻", "Semi-sextile": "⚺",
        }
        aspect_type_colors = {
            "Conjunction": "#c8a96e", "Opposition": "#c16969",
            "Trine": "#69c17c", "Square": "#c16969",
            "Sextile": "#69a8c1", "Quincunx": "#a069c1", "Semi-sextile": "#888",
        }

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            aspect_filter = st.multiselect(
                "Aspect type",
                options=list(aspect_icons.keys()),
                default=["Conjunction", "Opposition", "Trine", "Square", "Sextile"],
            )
        with col_f2:
            app_filter = st.selectbox("Direction", ["All", "Applying only", "Separating only"])

        filtered = [a for a in chart.aspects if a["aspect"] in aspect_filter]
        if app_filter == "Applying only":
            filtered = [a for a in filtered if a["applying"]]
        elif app_filter == "Separating only":
            filtered = [a for a in filtered if not a["applying"]]

        for asp in sorted(filtered, key=lambda x: x["orb"]):
            icon         = aspect_icons.get(asp["aspect"], "")
            asp_color    = aspect_type_colors.get(asp["aspect"], "#888")
            applying     = asp["applying"]
            # Green card for applying, red-tinted for separating
            card_border  = "#55aa5566" if applying else "#c1696966"
            dir_color    = "#55aa55"   if applying else "#c16969"
            dir_label    = "▶ Applying" if applying else "◀ Separating"
            p1 = chart.planets.get(asp["planet1"])
            p2 = chart.planets.get(asp["planet2"])
            s1 = p1.symbol if p1 else ""
            s2 = p2.symbol if p2 else ""
            st.markdown(
                f'<div class="planet-card" style="border-color:{card_border}">'
                f'<span style="color:{asp_color};font-size:17px;margin-right:6px">{icon}</span>'
                f'<b>{s1} {asp["planet1"]}</b>'
                f' <span style="color:{asp_color}">{asp["aspect"]}</span> '
                f'<b>{s2} {asp["planet2"]}</b>'
                f'&nbsp;&nbsp;<span style="color:{dir_color};font-size:12px">{dir_label}</span>'
                f'&nbsp;<span style="color:#666;font-size:12px">orb {asp["orb"]}°</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    elif not chart.aspects:
        st.info("No aspects found.")
    else:
        st.info("Aspects display is off — enable in sidebar.")

# ── Tab 4: Arabic Parts & Antiscia ───────────────────────────────────────────
with tab4:
    if show_arabic:
        st.markdown("### Arabic Parts")
        st.caption("Day chart: Asc + ☽ – ☉ &nbsp;|&nbsp; Night chart: Asc + ☉ – ☽ &nbsp;(Lilly)")

        pof_dms = _lon_to_dms(chart.part_of_fortune)
        pof_house = None
        for i in range(12):
            cs = chart.house_cusps[i]
            ce = chart.house_cusps[(i + 1) % 12]
            lon = chart.part_of_fortune
            if ce < cs:
                if lon >= cs or lon < ce:
                    pof_house = i + 1; break
            else:
                if cs <= lon < ce:
                    pof_house = i + 1; break

        st.markdown(f"""<div class="planet-card">
        <b style="color:#c8a96e;font-size:15px">⊕ Part of Fortune</b><br>
        <b style="font-size:20px">{pof_dms}</b>
        &nbsp; <span style="color:#aaa;font-size:13px">House {pof_house or '?'}
        · {'Day formula' if chart.is_day_chart else 'Night formula'}</span>
        </div>""", unsafe_allow_html=True)

    if show_antiscia:
        st.markdown("---")
        st.markdown("### Antiscia")
        st.caption("Solstice-axis mirror points (Cancer/Capricorn axis) — Frawley ch. 7. "
                   "Planets conjunct/opposed within 2° influence each other in a hidden way.")

        from engine import _aspect_angle
        planet_list = list(chart.planets.values())
        antiscia_rows = []
        for i, p1 in enumerate(planet_list):
            for p2 in planet_list[i + 1:]:
                conj_arc = _aspect_angle(p1.antiscion, p2.longitude)
                if conj_arc <= 2.0:
                    antiscia_rows.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion": _lon_to_dms(p1.antiscion),
                        "Type": "Conj",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{conj_arc:.2f}°",
                    })
                opp_arc = _aspect_angle((p1.antiscion + 180) % 360, p2.longitude)
                if opp_arc <= 2.0:
                    antiscia_rows.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion": _lon_to_dms(p1.antiscion),
                        "Type": "Oppo",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{opp_arc:.2f}°",
                    })

        if antiscia_rows:
            st.dataframe(pd.DataFrame(antiscia_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No antiscia contacts within 2° for this chart.")

        st.markdown("---")
        st.markdown("#### All Antiscia Positions")
        anti_all = [
            {
                "Planet": f"{p.symbol} {pname}",
                "Position": p.dms,
                "Antiscion": _lon_to_dms(p.antiscion),
                "Antiscion Sign": p.antiscion_sign,
            }
            for pname, p in chart.planets.items()
        ]
        st.dataframe(pd.DataFrame(anti_all), use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#555;font-size:12px'>"
    "Swiss Ephemeris (pyswisseph) · Regiomontanus houses · "
    "Chart wheel: kerykeion · Sources: Lilly, Frawley"
    "</div>",
    unsafe_allow_html=True,
)
