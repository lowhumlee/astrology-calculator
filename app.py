"""
Traditional Astrology Chart Calculator — Streamlit UI
"""

import streamlit as st
import pandas as pd
import requests
import base64
import os
import tempfile
from datetime import date
from timezonefinder import TimezoneFinder
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

# ── Element / sign helpers ────────────────────────────────────────────────────
FIRE_SIGNS  = {"Aries", "Leo", "Sagittarius"}
EARTH_SIGNS = {"Taurus", "Virgo", "Capricorn"}
AIR_SIGNS   = {"Gemini", "Libra", "Aquarius"}
WATER_SIGNS = {"Cancer", "Scorpio", "Pisces"}

ELEMENT_COLOR = {
    **{s: "#e05555" for s in FIRE_SIGNS},
    **{s: "#999999" for s in EARTH_SIGNS},
    **{s: "#55aa55" for s in AIR_SIGNS},
    **{s: "#5599dd" for s in WATER_SIGNS},
}

DIGNITY_COLOR = {
    "Domicile":   "#69c17c",
    "Exaltation": "#69a8c1",
    "Triplicity": "#a069c1",
    "Term":       "#c19a69",
    "Face":       "#999999",
    "Peregrine":  "#c16969",
    "—":          "#555555",
}

def sign_html(sign: str) -> str:
    """Return coloured sign symbol + name."""
    color = ELEMENT_COLOR.get(sign, "#c8a96e")
    idx   = SIGNS.index(sign) if sign in SIGNS else 0
    return f'<span style="color:{color};font-weight:bold">{SIGN_SYMBOLS[idx]} {sign}</span>'

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0e0e1a; color: #e8d5a3; }
    h1,h2,h3 { color: #c8a96e; font-family: Georgia, serif; }
    .pcard {
        background: linear-gradient(135deg,#1a1a2e,#16213e);
        border: 1px solid #c8a96e33;
        border-radius: 8px;
        padding: 9px 13px;
        margin: 3px 0;
        font-size: 14px;
        line-height: 1.5;
    }
    .mbox {
        background: linear-gradient(135deg,#1a1a2e,#16213e);
        border: 1px solid #c8a96e44;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Geocoding ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def geocode(city: str):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 5},
            headers={"User-Agent": "TradAstroCalc/1.0"},
            timeout=10,
        )
        res = r.json()
        return res if res else None
    except Exception:
        return None

# ── Chart SVG (kerykeion, base64-embedded) ────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def make_svg_b64(year, month, day, hour, minute, lat, lng, tz_str, name):
    """
    Generate natal chart SVG via kerykeion (Regiomontanus, offline).
    Returns base64-encoded SVG string for embedding in an <img> tag,
    which bypasses Streamlit's HTML sanitiser stripping <style> blocks.
    """
    try:
        subj = AstrologicalSubject(
            name, year, month, day, hour, minute,
            lat=lat, lng=lng, tz_str=tz_str,
            online=False,
            houses_system_identifier="R",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            chart = KerykeionChartSVG(subj, chart_type="Natal", new_output_directory=tmpdir)
            chart.makeSVG()
            # Find generated file
            svg_files = [f for f in os.listdir(tmpdir) if f.endswith(".svg")]
            if not svg_files:
                return None
            with open(os.path.join(tmpdir, svg_files[0]), "rb") as f:
                raw = f.read()
        # Strip the leading HTML comment so we start at <svg
        svg_start = raw.find(b"<svg")
        if svg_start > 0:
            raw = raw[svg_start:]
        b64 = base64.b64encode(raw).decode()
        return b64
    except Exception as e:
        return None

# ── AstroSeek interactive page URL ───────────────────────────────────────────

def build_astroseek_page_url(chart) -> str:
    """
    Build the URL for the AstroSeek interactive birth chart page.
    This opens in a new browser tab — server hotlink protection doesn't apply.
    """
    y, mo, d = chart.birth_date.split("-")
    h, mi    = (chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00"))
    lat_d    = abs(int(chart.latitude))
    lat_m    = int((abs(chart.latitude) % 1) * 60)
    lat_s    = "0" if chart.latitude >= 0 else "1"
    lon_d    = abs(int(chart.longitude))
    lon_m    = int((abs(chart.longitude) % 1) * 60)
    lon_s    = "0" if chart.longitude >= 0 else "1"
    city_enc = chart.city.replace(" ", "+")

    return (
        "https://horoscopes.astro-seek.com/birth-chart-horoscope-online?"
        f"narozeni_den={int(d)}&narozeni_mesic={int(mo)}&narozeni_rok={y}"
        f"&narozeni_hodina={h}&narozeni_minuta={mi}"
        f"&narozeni_mesto_hidden={city_enc}"
        f"&narozeni_city={city_enc}"
        f"&narozeni_sirka_stupne={lat_d}&narozeni_sirka_minuty={lat_m}&narozeni_sirka_smer={lat_s}"
        f"&narozeni_delka_stupne={lon_d}&narozeni_delka_minuty={lon_m}&narozeni_delka_smer={lon_s}"
        f"&narozeni_timezone_form=auto&narozeni_timezone_dst_form=auto"
        f"&house_system=regiomontanus&v1=1"
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌙 Chart Data")
    st.markdown("---")

    person_name = st.text_input("Name (optional)", placeholder="e.g. John Smith")

    birth_date = st.date_input(
        "Date",
        value=date(1990, 6, 15),
        min_value=date(1600, 1, 1),
        max_value=date(2100, 12, 31),
    )

    st.markdown("**Time (local)**")
    tc1, tc2 = st.columns(2)
    with tc1:
        birth_hour   = st.number_input("Hour",   min_value=0, max_value=23, value=12, step=1, format="%d")
    with tc2:
        birth_minute = st.number_input("Min",    min_value=0, max_value=59, value=0,  step=1, format="%d")

    st.markdown("### 📍 Place")
    city_input = st.text_input("City", value="Varna, Bulgaria")

    selected_lat, selected_lon, selected_city, selected_tz = None, None, city_input, "UTC"

    if city_input:
        with st.spinner("Looking up…"):
            geo = geocode(city_input)
        if geo:
            if len(geo) > 1:
                opts = [r["display_name"][:55] for r in geo]
                idx  = st.selectbox("Select location", range(len(opts)), format_func=lambda i: opts[i])
            else:
                idx = 0
            selected_lat  = float(geo[idx]["lat"])
            selected_lon  = float(geo[idx]["lon"])
            selected_city = geo[idx]["display_name"].split(",")[0].strip()
            selected_tz   = TimezoneFinder().timezone_at(lat=selected_lat, lng=selected_lon) or "UTC"
            st.caption(f"📌 {selected_city} · {selected_lat:.3f}°, {selected_lon:.3f}° · {selected_tz}")
        else:
            st.warning("City not found — enter coordinates manually.")
            selected_lat  = st.number_input("Latitude",  value=43.2167, format="%.4f")
            selected_lon  = st.number_input("Longitude", value=27.9167, format="%.4f")
            selected_city = city_input
            selected_tz   = TimezoneFinder().timezone_at(lat=selected_lat, lng=selected_lon) or "UTC"

    st.markdown("---")
    calc_btn = st.button("✨ Calculate Chart", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚙️ Display")
    show_aspects  = st.checkbox("Aspects",      value=True)
    show_antiscia = st.checkbox("Antiscia",     value=True)
    show_arabic   = st.checkbox("Arabic Parts", value=True)

# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("# 🌙 Traditional Astrology Calculator")
st.markdown("*Regiomontanus · Traditional rulerships · Lilly & Frawley*")
st.markdown("---")

if "chart" not in st.session_state:
    st.session_state.chart = None

if calc_btn and selected_lat is not None:
    with st.spinner("Computing…"):
        try:
            ch = calculate_chart(
                name=person_name or "Native",
                year=birth_date.year, month=birth_date.month, day=birth_date.day,
                hour=int(birth_hour), minute=int(birth_minute),
                city=selected_city, lat=selected_lat, lon=selected_lon,
            )
            st.session_state.chart    = ch
            st.session_state.chart_tz = selected_tz
        except Exception as e:
            st.error(f"Calculation error: {e}")
            st.exception(e)

chart = st.session_state.get("chart")

if chart is None:
    st.markdown("""
    ### How to use
    1. Enter date, time (type hours/minutes directly), and city in the sidebar
    2. Click **Calculate Chart**
    3. View the chart wheel, dignities, aspects, and more

    *Accuracy: Swiss Ephemeris validated to <0.01° vs AstroSeek.*
    """)
    st.stop()

# ── Header metrics ────────────────────────────────────────────────────────────

st.markdown(f"## {chart.name}")
for col, label, val in zip(
    st.columns(4),
    ["Date", "Time (local)", "Ascendant", "MC"],
    [chart.birth_date,
     f"{chart.birth_time}  UTC{chart.utc_offset:+.1f}",
     chart.asc_dms, chart.mc_dms],
):
    with col:
        st.markdown(
            f'<div class="mbox"><div style="font-size:11px;color:#888">{label}</div>'
            f'<div style="font-size:15px;font-weight:bold;color:#c8a96e">{val}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("")

# ── Chart wheel + info ────────────────────────────────────────────────────────

col_info, col_wheel = st.columns([1, 2])

with col_info:
    st.markdown(f"""
- **Place:** {chart.city}
- **Lat/Lon:** {chart.latitude:.4f}° / {chart.longitude:.4f}°
- **Timezone:** {chart.timezone}
- **Chart:** {"☀️ Day" if chart.is_day_chart else "🌙 Night"}
- **Houses:** Regiomontanus
- **ASC:** {sign_html(chart.asc_sign)}
- **MC:** {sign_html(chart.mc_sign)}
""", unsafe_allow_html=True)

    # AstroSeek link
    ask_url = build_astroseek_page_url(chart)
    st.markdown(
        f'<a href="{ask_url}" target="_blank" style="'
        'display:inline-block;margin-top:8px;padding:7px 14px;'
        'background:#1a1a2e;border:1px solid #c8a96e88;border-radius:6px;'
        'color:#c8a96e;text-decoration:none;font-size:13px;">'
        '🔭 Open on AstroSeek ↗</a>',
        unsafe_allow_html=True,
    )

with col_wheel:
    tz  = st.session_state.get("chart_tz", "UTC")
    yy, mm, dd = chart.birth_date.split("-")
    hh, mmin   = (chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00"))

    with st.spinner("Rendering chart wheel…"):
        b64 = make_svg_b64(
            int(yy), int(mm), int(dd), int(hh), int(mmin),
            chart.latitude, chart.longitude, tz,
            chart.name,
        )

    if b64:
        st.markdown(
            f'<img src="data:image/svg+xml;base64,{b64}" '
            f'width="100%" style="max-width:680px;display:block;margin:auto;" '
            f'alt="Natal chart wheel"/>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("Chart wheel could not be generated.")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(
    ["🪐 Planets", "🏠 Houses & Lords", "⚡ Aspects", "📐 Parts & Antiscia"]
)

# ── Tab 1: Planets ────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Planetary Positions & Essential Dignities")
    st.caption("Traditional rulerships (Lilly) · Ptolemaic terms · Chaldean faces")

    rows = get_essential_dignities_table(chart)
    if rows:
        # Attach hidden element colour per row
        for row in rows:
            pname = row["Planet"].split(" ", 1)[-1]   # strip symbol
            p = chart.planets.get(pname)
            row["_sign"] = p.sign if p else ""

        df = pd.DataFrame(rows)

        def style_planets(row):
            n = len(row)
            styles = [""] * n
            cols_list = list(df.columns)
            dig_i  = cols_list.index("Dignity") if "Dignity" in cols_list else -1
            sign_i = cols_list.index("Sign")    if "Sign"    in cols_list else -1
            if dig_i >= 0:
                styles[dig_i] = f"color:{DIGNITY_COLOR.get(row['Dignity'], '#555')};font-weight:bold"
            if sign_i >= 0:
                styles[sign_i] = f"color:{ELEMENT_COLOR.get(row.get('_sign',''), '#c8a96e')};font-weight:bold"
            return styles

        display_cols = [c for c in df.columns if not c.startswith("_")]
        styled = (
            df[display_cols]
            .style.apply(style_planets, axis=1)
        )
        st.dataframe(styled, width="stretch", hide_index=True)

    # Compact inline legend — no separate header
    st.markdown(
        '<div style="margin-top:12px;font-size:13px;line-height:2">'
        '<b style="color:#aaa">Dignity:</b>&nbsp;'
        + "&nbsp; ".join(
            f'<span style="color:{c}">● {l}</span>'
            for l, c in DIGNITY_COLOR.items() if l != "—"
        )
        + "&nbsp;&nbsp;&nbsp; <b style='color:#aaa'>Element:</b>&nbsp;"
        + "&nbsp; ".join(
            f'<span style="color:{c}">■ {l}</span>'
            for l, c in [
                ("Fire", "#e05555"), ("Earth", "#999999"),
                ("Air", "#55aa55"),  ("Water", "#5599dd"),
            ]
        )
        + "</div>",
        unsafe_allow_html=True,
    )

# ── Tab 2: Houses & Lords ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### House Cusps & Traditional Lords")
    st.caption("Traditional rulerships only — Saturn rules Aquarius, Jupiter rules Pisces")

    rows = get_house_lords_table(chart)
    cols = st.columns(3)
    for i, row in enumerate(rows):
        with cols[i % 3]:
            lord = chart.planets.get(row["Lord"])
            sign = row["Sign"]
            sc   = ELEMENT_COLOR.get(sign, "#c8a96e")
            si   = SIGNS.index(sign) if sign in SIGNS else 0
            dig_c  = DIGNITY_COLOR.get(lord.dignity, "#aaa") if lord else "#aaa"
            dig_s  = f'<span style="color:{dig_c}">{lord.dignity}</span>' if lord else ""
            retro  = ' <span style="color:#c16969">℞</span>' if (lord and lord.retrograde) else ""
            st.markdown(
                f'<div class="pcard">'
                f'<b style="color:#c8a96e">H{row["House"]}</b>'
                f' <span style="color:{sc}">{SIGN_SYMBOLS[si]} {sign}</span><br>'
                f'<b>{row["Lord"]}</b>{retro} · {row["Lord Position"]}<br>'
                f'<small style="color:#aaa">H{row["Lord House"]} · {dig_s}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Tab 3: Aspects ────────────────────────────────────────────────────────────
with tab3:
    if show_aspects and chart.aspects:
        st.markdown("### Aspects")

        ASPECT_ICONS = {
            "Conjunction": "☌", "Opposition": "☍", "Trine": "△",
            "Square": "□", "Sextile": "✶", "Quincunx": "⚻", "Semi-sextile": "⚺",
        }
        ASPECT_TYPE_COLOR = {
            "Conjunction": "#c8a96e", "Opposition": "#c16969",
            "Trine": "#69c17c",       "Square": "#c16969",
            "Sextile": "#69a8c1",     "Quincunx": "#a069c1", "Semi-sextile": "#888",
        }

        cf1, cf2 = st.columns(2)
        with cf1:
            asp_filter = st.multiselect(
                "Aspect type",
                options=list(ASPECT_ICONS.keys()),
                default=["Conjunction", "Opposition", "Trine", "Square", "Sextile"],
            )
        with cf2:
            dir_filter = st.selectbox("Direction", ["All", "Applying only", "Separating only"])

        filtered = [a for a in chart.aspects if a["aspect"] in asp_filter]
        if dir_filter == "Applying only":
            filtered = [a for a in filtered if a["applying"]]
        elif dir_filter == "Separating only":
            filtered = [a for a in filtered if not a["applying"]]

        st.caption(
            f'{len(filtered)} aspects shown &nbsp;·&nbsp; '
            '<span style="color:#55aa55">▶ Applying</span> &nbsp; '
            '<span style="color:#c16969">◀ Separating</span>',
            unsafe_allow_html=True,
        )

        for asp in sorted(filtered, key=lambda x: x["orb"]):
            applying  = asp["applying"]
            dir_col   = "#55aa55" if applying else "#c16969"
            dir_lbl   = "▶ Applying" if applying else "◀ Separating"
            bdr_col   = "#55aa5555" if applying else "#c1696955"
            asp_col   = ASPECT_TYPE_COLOR.get(asp["aspect"], "#888")
            icon      = ASPECT_ICONS.get(asp["aspect"], "")
            p1 = chart.planets.get(asp["planet1"])
            p2 = chart.planets.get(asp["planet2"])
            s1 = (p1.symbol + " ") if p1 else ""
            s2 = (p2.symbol + " ") if p2 else ""
            # Sign colours for planet names
            c1s = ELEMENT_COLOR.get(p1.sign, "#e8d5a3") if p1 else "#e8d5a3"
            c2s = ELEMENT_COLOR.get(p2.sign, "#e8d5a3") if p2 else "#e8d5a3"
            st.markdown(
                f'<div class="pcard" style="border-color:{bdr_col}">'
                f'<span style="color:{asp_col};font-size:17px">{icon}</span> '
                f'<span style="color:{c1s}">{s1}{asp["planet1"]}</span>'
                f' <span style="color:{asp_col}"> {asp["aspect"]} </span>'
                f'<span style="color:{c2s}">{s2}{asp["planet2"]}</span>'
                f'&ensp;<span style="color:{dir_col};font-size:12px">{dir_lbl}</span>'
                f'&ensp;<span style="color:#666;font-size:12px">orb {asp["orb"]}°</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No aspects to display.")

# ── Tab 4: Arabic Parts & Antiscia ───────────────────────────────────────────
with tab4:
    if show_arabic:
        st.markdown("### Arabic Parts")
        st.caption("Day: Asc + ☽ − ☉ &nbsp;|&nbsp; Night: Asc + ☉ − ☽ &nbsp;(Lilly)")

        pof_dms   = _lon_to_dms(chart.part_of_fortune)
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

        st.markdown(
            f'<div class="pcard">'
            f'<b style="color:#c8a96e;font-size:15px">⊕ Part of Fortune</b><br>'
            f'<span style="font-size:20px">{pof_dms}</span>'
            f'&ensp;<span style="color:#aaa;font-size:13px">House {pof_house or "?"}'
            f' · {"Day formula" if chart.is_day_chart else "Night formula"}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if show_antiscia:
        st.markdown("---")
        st.markdown("### Antiscia")
        st.caption(
            "Mirror points across the Cancer/Capricorn solstice axis (Frawley ch. 7). "
            "Planets in conjunction or opposition by antiscion within 2° act on each other in a hidden way."
        )

        from engine import _aspect_angle
        plist = list(chart.planets.values())
        anti_contacts = []
        for i, p1 in enumerate(plist):
            for p2 in plist[i + 1:]:
                conj = _aspect_angle(p1.antiscion, p2.longitude)
                if conj <= 2.0:
                    anti_contacts.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion of 1": _lon_to_dms(p1.antiscion),
                        "Contact": "Conj",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{conj:.2f}°",
                    })
                opp = _aspect_angle((p1.antiscion + 180) % 360, p2.longitude)
                if opp <= 2.0:
                    anti_contacts.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion of 1": _lon_to_dms(p1.antiscion),
                        "Contact": "Oppo",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{opp:.2f}°",
                    })

        if anti_contacts:
            st.dataframe(pd.DataFrame(anti_contacts), width="stretch", hide_index=True)
        else:
            st.info("No antiscia contacts within 2° for this chart.")

        st.markdown("---")
        st.markdown("#### All Antiscia Positions")
        st.dataframe(
            pd.DataFrame([
                {
                    "Planet":         f"{p.symbol} {n}",
                    "Position":       p.dms,
                    "Antiscion":      _lon_to_dms(p.antiscion),
                    "Antiscion Sign": p.antiscion_sign,
                }
                for n, p in chart.planets.items()
            ]),
            width="stretch", hide_index=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#555;font-size:12px">'
    'Swiss Ephemeris · Regiomontanus houses · Chart: kerykeion · Sources: Lilly, Frawley'
    '</div>',
    unsafe_allow_html=True,
)
