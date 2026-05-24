"""
Traditional Astrology Chart Calculator — Streamlit UI
Horary / Natal · Lilly & Frawley · Regiomontanus
"""

import streamlit as st
import pandas as pd
import requests
import base64
import os
import re
import tempfile
from datetime import date
from timezonefinder import TimezoneFinder
from kerykeion import AstrologicalSubject, KerykeionChartSVG
from engine import (
    calculate_chart,
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

# ── Constants ─────────────────────────────────────────────────────────────────
FIRE_SIGNS  = {"Aries", "Leo", "Sagittarius"}
EARTH_SIGNS = {"Taurus", "Virgo", "Capricorn"}
AIR_SIGNS   = {"Gemini", "Libra", "Aquarius"}
WATER_SIGNS = {"Cancer", "Scorpio", "Pisces"}

ELEMENT_COLOR = {
    **{s: "#cc4444" for s in FIRE_SIGNS},
    **{s: "#888888" for s in EARTH_SIGNS},
    **{s: "#448844" for s in AIR_SIGNS},
    **{s: "#4477bb" for s in WATER_SIGNS},
}

DIGNITY_COLOR = {
    "Domicile":   "#aaaaaa",
    "Exaltation": "#cccccc",
    "Triplicity": "#999999",
    "Term":       "#777777",
    "Face":       "#666666",
    "Peregrine":  "#444444",
    "—":          "#333333",
}

ASPECT_ICONS = {
    "Conjunction": "☌", "Opposition": "☍", "Trine": "△",
    "Square": "□", "Sextile": "✶", "Quincunx": "⚻", "Semi-sextile": "⚺",
}
ASPECT_TYPE_COLOR = {
    "Conjunction": "#bbbbbb", "Opposition": "#888888",
    "Trine":       "#bbbbbb", "Square":     "#888888",
    "Sextile":     "#aaaaaa", "Quincunx":   "#777777",
    "Semi-sextile":"#666666",
}

# Only traditional 7 planets + North Node on the chart wheel
KERYKEION_POINTS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "True_North_Lunar_Node",
]
# Colors that indicate modern planets in kerykeion SVG lines — strip these
MODERN_PLANET_COLORS = [
    "chiron", "uranus", "neptune", "pluto",
    "mean-lilith", "true-lilith", "mean_lilith",
]

def sign_html(sign: str, with_name: bool = True) -> str:
    color = ELEMENT_COLOR.get(sign, "#aaaaaa")
    idx   = SIGNS.index(sign) if sign in SIGNS else 0
    sym   = SIGN_SYMBOLS[idx]
    text  = f"{sym} {sign}" if with_name else sym
    return f'<span style="color:{color}">{text}</span>'

# ── Monochrome CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Base */
    html, body, .stApp { background:#111111; color:#cccccc; font-family: 'Georgia', serif; }
    h1,h2,h3,h4 { color:#eeeeee; font-weight:normal; letter-spacing:.03em; }
    hr { border-color:#333333; }

    /* Sidebar */
    [data-testid="stSidebar"] { background:#181818; border-right:1px solid #2a2a2a; }
    [data-testid="stSidebar"] label { color:#aaaaaa !important; font-size:13px; }

    /* Metric boxes */
    .mbox {
        background:#1a1a1a;
        border:1px solid #333333;
        border-radius:4px;
        padding:9px 14px;
        text-align:center;
        margin-bottom:6px;
    }
    .mbox .label { font-size:11px; color:#666666; text-transform:uppercase; letter-spacing:.08em; }
    .mbox .value { font-size:15px; color:#dddddd; margin-top:3px; }

    /* Planet / aspect cards */
    .pcard {
        background:#161616;
        border:1px solid #2a2a2a;
        border-left:3px solid #333333;
        border-radius:3px;
        padding:7px 12px;
        margin:2px 0;
        font-size:13px;
        line-height:1.6;
    }
    .pcard.applying  { border-left-color:#448844; }
    .pcard.separating{ border-left-color:#884444; }

    /* Dataframe */
    .stDataFrame { border:1px solid #2a2a2a; border-radius:3px; }

    /* Buttons */
    .stButton > button {
        background:#1e1e1e; color:#cccccc;
        border:1px solid #444444; border-radius:3px;
    }
    .stButton > button:hover { border-color:#888888; color:#ffffff; }

    /* External link button */
    .ext-link {
        display:inline-block; padding:7px 16px;
        background:#1a1a1a; border:1px solid #444444;
        border-radius:3px; color:#aaaaaa;
        text-decoration:none; font-size:13px;
        letter-spacing:.03em;
    }
    .ext-link:hover { border-color:#aaaaaa; color:#dddddd; }
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

# ── SVG chart wheel ───────────────────────────────────────────────────────────

def _strip_modern_lines(svg: str) -> str:
    """Remove <line> elements that use modern-planet CSS colour variables."""
    out = []
    for line in svg.split("\n"):
        ll = line.lower()
        if "<line" in ll and any(m in ll for m in MODERN_PLANET_COLORS):
            continue
        out.append(line)
    return "\n".join(out)

@st.cache_data(ttl=600, show_spinner=False)
def make_svg_b64(year, month, day, hour, minute, lat, lng, tz_str, name):
    """
    Generate natal chart SVG (Regiomontanus, traditional planets only).
    Returned as base64 for <img> embedding — bypasses Streamlit's HTML sanitiser.
    """
    try:
        subj = AstrologicalSubject(
            name, year, month, day, hour, minute,
            lat=lat, lng=lng, tz_str=tz_str,
            online=False,
            houses_system_identifier="R",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            chart = KerykeionChartSVG(
                subj,
                chart_type="Natal",
                new_output_directory=tmpdir,
                active_points=KERYKEION_POINTS,
            )
            chart.makeSVG()
            svg_files = [f for f in os.listdir(tmpdir) if f.endswith(".svg")]
            if not svg_files:
                return None
            with open(os.path.join(tmpdir, svg_files[0])) as f:
                svg_text = f.read()

        # Strip leading HTML comment, keep from <svg onwards
        svg_start = svg_text.find("<svg")
        if svg_start > 0:
            svg_text = svg_text[svg_start:]

        # Remove stray aspect lines for modern planets
        svg_text = _strip_modern_lines(svg_text)

        return base64.b64encode(svg_text.encode()).decode()
    except Exception:
        return None

# ── AstroSeek horary URL ──────────────────────────────────────────────────────

def build_astroseek_horary_url(chart) -> str:
    """Traditional horary chart on AstroSeek (opens in new tab)."""
    y, mo, d = chart.birth_date.split("-")
    h, mi    = (chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00"))
    lat_d = abs(int(chart.latitude));  lat_m = int((abs(chart.latitude) % 1) * 60)
    lon_d = abs(int(chart.longitude)); lon_m = int((abs(chart.longitude) % 1) * 60)
    lat_s = "0" if chart.latitude  >= 0 else "1"
    lon_s = "0" if chart.longitude >= 0 else "1"
    city_enc = chart.city.replace(" ", "+")

    return (
        "https://horoscopes.astro-seek.com/calculate-traditional-chart/?"
        "horary=1&tradicni=1&chiron_asp=on&send_calculation=1"
        f"&narozeni_den={int(d)}&narozeni_mesic={int(mo)}&narozeni_rok={y}"
        f"&narozeni_hodina={h.zfill(2)}&narozeni_minuta={mi.zfill(2)}&narozeni_sekunda=00"
        f"&narozeni_city={city_enc}"
        f"&narozeni_mesto_hidden={city_enc}"
        f"&narozeni_stat_hidden=&narozeni_podstat_kratky_hidden="
        f"&narozeni_sirka_stupne={lat_d}&narozeni_sirka_minuty={lat_m}&narozeni_sirka_smer={lat_s}"
        f"&narozeni_delka_stupne={lon_d}&narozeni_delka_minuty={lon_m}&narozeni_delka_smer={lon_s}"
        "&narozeni_timezone_form=auto&narozeni_timezone_dst_form=auto"
        "&house_system=regiomontanus&aya=&terms=&house_system2="
        "&hid_fortune=1&hid_fortune_check=on&hid_spirit=1&hid_syzygy=1"
        "&hid_uzel=1&hid_uzel_check=on"
        "&custom_aya_zmena_smer=0&custom_aya_zmena_stupne=00"
        "&custom_aya_zmena_minuty=00&custom_aya_zmena_vteriny=00"
        "&custom_aya_vlastni_smer=0&custom_aya_vlastni_stupne=00"
        "&custom_aya_vlastni_minuty=00&custom_aya_vlastni_vteriny=00"
        "&tolerance=1"
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Chart Data")
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
        birth_hour   = st.number_input("Hour", min_value=0, max_value=23, value=12, step=1, format="%d")
    with tc2:
        birth_minute = st.number_input("Min",  min_value=0, max_value=59, value=0,  step=1, format="%d")

    st.markdown("### Place")
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
            st.caption(f"{selected_city} · {selected_lat:.3f}°, {selected_lon:.3f}°")
            st.caption(f"tz: {selected_tz}")
        else:
            st.warning("City not found — enter coordinates manually.")
            selected_lat  = st.number_input("Latitude",  value=43.2167, format="%.4f")
            selected_lon  = st.number_input("Longitude", value=27.9167, format="%.4f")
            selected_city = city_input
            selected_tz   = TimezoneFinder().timezone_at(lat=selected_lat, lng=selected_lon) or "UTC"

    st.markdown("---")
    calc_btn = st.button("Calculate Chart", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("**Display**")
    show_aspects  = st.checkbox("Aspects",      value=True)
    show_antiscia = st.checkbox("Antiscia",     value=True)
    show_arabic   = st.checkbox("Arabic Parts", value=True)

# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("# Traditional Astrology Calculator")
st.markdown("*Regiomontanus · Seven planets · Lilly & Frawley*")
st.markdown("---")

if "chart" not in st.session_state:
    st.session_state.chart = None

if calc_btn and selected_lat is not None:
    with st.spinner("Computing…"):
        try:
            ch = calculate_chart(
                name=person_name or "Chart",
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
    **How to use**

    1. Enter date, time, and city in the sidebar
    2. Click **Calculate Chart**
    3. View the chart wheel, dignities, aspects, and more

    *Swiss Ephemeris · accuracy <0.01° vs AstroSeek*
    """)
    st.stop()

# ── Header metrics ────────────────────────────────────────────────────────────

st.markdown(f"### {chart.name}")
for col, label, val in zip(
    st.columns(4),
    ["Date", "Time · UTC offset", "Ascendant", "Midheaven"],
    [chart.birth_date,
     f"{chart.birth_time}  ({chart.utc_offset:+.1f}h)",
     chart.asc_dms, chart.mc_dms],
):
    with col:
        st.markdown(
            f'<div class="mbox"><div class="label">{label}</div>'
            f'<div class="value">{val}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("")

# ── Chart wheel + info ────────────────────────────────────────────────────────

col_info, col_wheel = st.columns([1, 2])

with col_info:
    st.markdown(
        f"**Place:** {chart.city}  \n"
        f"**Lat/Lon:** {chart.latitude:.4f}° / {chart.longitude:.4f}°  \n"
        f"**Timezone:** {chart.timezone}  \n"
        f"**Chart:** {'Day' if chart.is_day_chart else 'Night'}  \n"
        f"**Houses:** Regiomontanus  \n"
        f"**ASC sign:** {sign_html(chart.asc_sign)}  \n"
        f"**MC sign:** {sign_html(chart.mc_sign)}",
        unsafe_allow_html=True,
    )
    st.markdown("")

    ask_url = build_astroseek_horary_url(chart)
    st.markdown(
        f'<a class="ext-link" href="{ask_url}" target="_blank">Open on AstroSeek ↗</a>',
        unsafe_allow_html=True,
    )

with col_wheel:
    tz  = st.session_state.get("chart_tz", "UTC")
    yy, mm, dd = chart.birth_date.split("-")
    hh, mmin   = (chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00"))

    with st.spinner("Rendering chart wheel…"):
        b64 = make_svg_b64(
            int(yy), int(mm), int(dd), int(hh), int(mmin),
            chart.latitude, chart.longitude, tz, chart.name,
        )

    if b64:
        # Full-width, no max-width cap — make it big
        st.markdown(
            f'<img src="data:image/svg+xml;base64,{b64}" '
            f'style="width:100%;display:block;" alt="Chart wheel"/>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("Chart wheel could not be generated.")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(
    ["Planets", "Houses & Lords", "Aspects", "Parts & Antiscia"]
)

# ── Tab 1: Planets ────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Planetary Positions & Essential Dignities")

    rows = get_essential_dignities_table(chart)
    if rows:
        for row in rows:
            pname = row["Planet"].split(" ", 1)[-1]
            p = chart.planets.get(pname)
            row["_sign"] = p.sign if p else ""

        df = pd.DataFrame(rows)
        display_cols = [c for c in df.columns if not c.startswith("_")]

        def style_planets(row):
            styles = [""] * len(row)
            cols_list = list(df[display_cols].columns)
            if "Dignity" in cols_list:
                i = cols_list.index("Dignity")
                styles[i] = f"color:{DIGNITY_COLOR.get(row.get('Dignity','—'), '#555')}"
            if "Sign" in cols_list:
                i = cols_list.index("Sign")
                sign = row.get("_sign", "")
                styles[i] = f"color:{ELEMENT_COLOR.get(sign, '#aaa')}"
            return styles

        styled = df[display_cols].style.apply(
            lambda row: style_planets(row), axis=1
        )
        st.dataframe(styled, width="stretch", hide_index=True)

    # Inline legend — single row, no header clutter
    st.markdown(
        '<div style="margin-top:10px;font-size:12px;color:#666;line-height:2">'
        '<span style="color:#999">Dignity:</span> '
        + " · ".join(f'<span style="color:{c}">{l}</span>' for l, c in DIGNITY_COLOR.items() if l != "—")
        + ' &emsp; <span style="color:#999">Sign element:</span> '
        + " · ".join(
            f'<span style="color:{c}">{l}</span>'
            for l, c in [("Fire ♈♌♐","#cc4444"),("Earth ♉♍♑","#888888"),
                         ("Air ♊♎♒","#448844"),("Water ♋♏♓","#4477bb")]
        )
        + '</div>',
        unsafe_allow_html=True,
    )

# ── Tab 2: Houses & Lords ─────────────────────────────────────────────────────
with tab2:
    st.markdown("### House Cusps & Traditional Lords")
    st.caption("Saturn rules Aquarius · Jupiter rules Pisces")

    rows = get_house_lords_table(chart)
    cols3 = st.columns(3)
    for i, row in enumerate(rows):
        with cols3[i % 3]:
            lord  = chart.planets.get(row["Lord"])
            sign  = row["Sign"]
            sc    = ELEMENT_COLOR.get(sign, "#888")
            si    = SIGNS.index(sign) if sign in SIGNS else 0
            dig_c = DIGNITY_COLOR.get(lord.dignity, "#666") if lord else "#666"
            dig_s = f'<span style="color:{dig_c}">{lord.dignity}</span>' if lord else "—"
            retro = ' <span style="color:#884444">℞</span>' if (lord and lord.retrograde) else ""
            st.markdown(
                f'<div class="pcard">'
                f'<span style="color:#888">H{row["House"]}</span>'
                f' <span style="color:{sc}">{SIGN_SYMBOLS[si]} {sign}</span><br>'
                f'<b style="color:#dddddd">{row["Lord"]}</b>{retro}'
                f' <span style="color:#555">·</span> {row["Lord Position"]}<br>'
                f'<small style="color:#555">H{row["Lord House"]} · {dig_s}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Tab 3: Aspects ────────────────────────────────────────────────────────────
with tab3:
    # Filter to only planet-to-planet aspects (both parties must be in our planet dict)
    planet_names = set(chart.planets.keys())
    planet_aspects = [
        a for a in chart.aspects
        if a["planet1"] in planet_names and a["planet2"] in planet_names
    ]

    if show_aspects and planet_aspects:
        st.markdown("### Aspects")
        st.caption(
            "Applying = green border · Separating = red border"
        )

        cf1, cf2 = st.columns(2)
        with cf1:
            asp_filter = st.multiselect(
                "Aspect type",
                options=list(ASPECT_ICONS.keys()),
                default=["Conjunction", "Opposition", "Trine", "Square", "Sextile"],
            )
        with cf2:
            dir_filter = st.selectbox("Direction", ["All", "Applying only", "Separating only"])

        filtered = [a for a in planet_aspects if a["aspect"] in asp_filter]
        if dir_filter == "Applying only":
            filtered = [a for a in filtered if a["applying"]]
        elif dir_filter == "Separating only":
            filtered = [a for a in filtered if not a["applying"]]

        st.caption(f"{len(filtered)} aspects shown")

        for asp in sorted(filtered, key=lambda x: x["orb"]):
            applying = asp["applying"]
            css_cls  = "applying" if applying else "separating"
            dir_col  = "#448844" if applying else "#884444"
            dir_lbl  = "▶" if applying else "◀"
            asp_col  = ASPECT_TYPE_COLOR.get(asp["aspect"], "#888")
            icon     = ASPECT_ICONS.get(asp["aspect"], "")
            p1 = chart.planets.get(asp["planet1"])
            p2 = chart.planets.get(asp["planet2"])
            c1 = ELEMENT_COLOR.get(p1.sign, "#ccc") if p1 else "#ccc"
            c2 = ELEMENT_COLOR.get(p2.sign, "#ccc") if p2 else "#ccc"
            s1 = f"{p1.symbol} " if p1 else ""
            s2 = f"{p2.symbol} " if p2 else ""
            st.markdown(
                f'<div class="pcard {css_cls}">'
                f'<span style="color:{asp_col};font-size:15px">{icon}</span> '
                f'<span style="color:{c1}">{s1}{asp["planet1"]}</span>'
                f' <span style="color:{asp_col}">{asp["aspect"]}</span> '
                f'<span style="color:{c2}">{s2}{asp["planet2"]}</span>'
                f'&ensp;<span style="color:{dir_col};font-size:12px">{dir_lbl}</span>'
                f'&ensp;<span style="color:#555;font-size:12px">orb {asp["orb"]}°</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No planet-to-planet aspects to display.")

# ── Tab 4: Arabic Parts & Antiscia ───────────────────────────────────────────
with tab4:
    if show_arabic:
        st.markdown("### Arabic Parts")
        st.caption("Day: Asc + Moon − Sun · Night: Asc + Sun − Moon (Lilly)")

        pof_dms   = _lon_to_dms(chart.part_of_fortune)
        pof_house = None
        for i in range(12):
            cs  = chart.house_cusps[i]
            ce  = chart.house_cusps[(i + 1) % 12]
            lon = chart.part_of_fortune
            if ce < cs:
                if lon >= cs or lon < ce:
                    pof_house = i + 1; break
            else:
                if cs <= lon < ce:
                    pof_house = i + 1; break

        st.markdown(
            f'<div class="pcard">'
            f'<span style="color:#888">⊕ Part of Fortune</span><br>'
            f'<b style="font-size:16px;color:#dddddd">{pof_dms}</b>'
            f'&ensp;<span style="color:#555;font-size:12px">'
            f'House {pof_house or "?"} · '
            f'{"Day" if chart.is_day_chart else "Night"} formula</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if show_antiscia:
        st.markdown("---")
        st.markdown("### Antiscia")
        st.caption("Mirror points across the Cancer/Capricorn solstice axis (Frawley). Orb ≤ 2°.")

        from engine import _aspect_angle
        plist = list(chart.planets.values())
        anti_contacts = []
        for i, p1 in enumerate(plist):
            for p2 in plist[i + 1:]:
                conj = _aspect_angle(p1.antiscion, p2.longitude)
                if conj <= 2.0:
                    anti_contacts.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion": _lon_to_dms(p1.antiscion),
                        "Contact": "Conj",
                        "Planet 2": f"{p2.symbol} {p2.name} ({p2.dms})",
                        "Orb": f"{conj:.2f}°",
                    })
                opp = _aspect_angle((p1.antiscion + 180) % 360, p2.longitude)
                if opp <= 2.0:
                    anti_contacts.append({
                        "Planet 1": f"{p1.symbol} {p1.name} ({p1.dms})",
                        "Antiscion": _lon_to_dms(p1.antiscion),
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
                {"Planet": f"{p.symbol} {n}", "Position": p.dms,
                 "Antiscion": _lon_to_dms(p.antiscion), "Antiscion Sign": p.antiscion_sign}
                for n, p in chart.planets.items()
            ]),
            width="stretch", hide_index=True,
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#444;font-size:11px">'
    'Swiss Ephemeris · Regiomontanus · kerykeion · Lilly · Frawley'
    '</div>',
    unsafe_allow_html=True,
)
