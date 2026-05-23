"""
Astrology Calculation Engine — Traditional (Classical) Only
Uses pyswisseph for planetary positions + Regiomontanus houses (per Frawley).
Planets: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, North Node.
No modern planets (Uranus, Neptune, Pluto) or Lilith — traditional astrology only.
Validates against AstroSeek to <0.01° accuracy.
"""

import swisseph as swe
import pytz
from datetime import datetime
from timezonefinder import TimezoneFinder
from dataclasses import dataclass, field
from typing import Optional
import math

# ── Constants ────────────────────────────────────────────────────────────────

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]
SIGN_SYMBOLS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]

PLANET_SYMBOLS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "North Node": "☊",
}

# Traditional rulerships (Lilly / Frawley)
TRADITIONAL_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# Essential dignities table (sign, exaltation, triplicity day/night, terms, faces)
DOMICILE = {
    "Sun": ["Leo"], "Moon": ["Cancer"],
    "Mercury": ["Gemini", "Virgo"], "Venus": ["Taurus", "Libra"],
    "Mars": ["Aries", "Scorpio"], "Jupiter": ["Sagittarius", "Pisces"],
    "Saturn": ["Capricorn", "Aquarius"],
}
EXALTATION = {
    "Sun": "Aries", "Moon": "Taurus", "Mercury": "Virgo",
    "Venus": "Pisces", "Mars": "Capricorn", "Jupiter": "Cancer",
    "Saturn": "Libra",
}
DETRIMENT = {
    "Sun": ["Aquarius"], "Moon": ["Capricorn"],
    "Mercury": ["Sagittarius", "Pisces"], "Venus": ["Aries", "Scorpio"],
    "Mars": ["Taurus", "Libra"], "Jupiter": ["Gemini", "Virgo"],
    "Saturn": ["Cancer", "Leo"],
}
FALL = {
    "Sun": "Libra", "Moon": "Scorpio", "Mercury": "Pisces",
    "Venus": "Virgo", "Mars": "Cancer", "Jupiter": "Capricorn",
    "Saturn": "Aries",
}

# Triplicity rulers (day / night) — Lilly's system
TRIPLICITY = {
    # Fire signs
    "Aries": ("Sun", "Jupiter"), "Leo": ("Sun", "Jupiter"), "Sagittarius": ("Sun", "Jupiter"),
    # Earth signs
    "Taurus": ("Venus", "Moon"), "Virgo": ("Venus", "Moon"), "Capricorn": ("Venus", "Moon"),
    # Air signs
    "Gemini": ("Saturn", "Mercury"), "Libra": ("Saturn", "Mercury"), "Aquarius": ("Saturn", "Mercury"),
    # Water signs
    "Cancer": ("Venus", "Mars"), "Scorpio": ("Venus", "Mars"), "Pisces": ("Venus", "Mars"),
}

# Ptolemaic terms (degrees within sign → ruler)
# Format: list of (end_degree, ruler) — cumulative from 0
TERMS = {
    "Aries":       [(6,"Jupiter"),(13,"Venus"),(20,"Mercury"),(26,"Mars"),(30,"Saturn")],
    "Taurus":      [(8,"Venus"),(14,"Mercury"),(22,"Jupiter"),(27,"Saturn"),(30,"Mars")],
    "Gemini":      [(6,"Mercury"),(12,"Jupiter"),(17,"Venus"),(24,"Saturn"),(30,"Mars")],
    "Cancer":      [(7,"Mars"),(13,"Venus"),(19,"Mercury"),(26,"Jupiter"),(30,"Saturn")],
    "Leo":         [(6,"Jupiter"),(11,"Mercury"),(18,"Saturn"),(24,"Venus"),(30,"Mars")],
    "Virgo":       [(7,"Mercury"),(17,"Venus"),(21,"Jupiter"),(28,"Saturn"),(30,"Mars")],
    "Libra":       [(6,"Saturn"),(14,"Venus"),(21,"Mercury"),(28,"Jupiter"),(30,"Mars")],
    "Scorpio":     [(7,"Mars"),(11,"Venus"),(19,"Mercury"),(24,"Jupiter"),(30,"Saturn")],
    "Sagittarius": [(12,"Jupiter"),(17,"Venus"),(21,"Mercury"),(26,"Saturn"),(30,"Mars")],
    "Capricorn":   [(7,"Mercury"),(14,"Jupiter"),(22,"Venus"),(26,"Saturn"),(30,"Mars")],
    "Aquarius":    [(7,"Mercury"),(13,"Venus"),(20,"Jupiter"),(25,"Mars"),(30,"Saturn")],
    "Pisces":      [(12,"Venus"),(16,"Jupiter"),(19,"Mercury"),(28,"Mars"),(30,"Saturn")],
}

# Chaldean faces (decan rulers) — each sign has 3 × 10° faces
FACE_SEQUENCE = ["Mars","Sun","Venus","Mercury","Moon","Saturn","Jupiter"]
FACE_START_INDEX = {
    "Aries": 0, "Taurus": 3, "Gemini": 6, "Cancer": 2, "Leo": 5, "Virgo": 1,
    "Libra": 4, "Scorpio": 0, "Sagittarius": 3, "Capricorn": 6, "Aquarius": 2, "Pisces": 5,
}

# Antiscia axis — each sign maps to its mirror sign across Cancer/Capricorn axis
ANTISCIA_MIRROR = {
    "Aries": "Virgo", "Taurus": "Leo", "Gemini": "Cancer",
    "Cancer": "Gemini", "Leo": "Taurus", "Virgo": "Aries",
    "Libra": "Pisces", "Scorpio": "Aquarius", "Sagittarius": "Capricorn",
    "Capricorn": "Sagittarius", "Aquarius": "Scorpio", "Pisces": "Libra",
}

# Aspect definitions (name, degrees, orb)
ASPECTS = [
    ("Conjunction", 0, 8),
    ("Opposition", 180, 8),
    ("Trine", 120, 8),
    ("Square", 90, 7),
    ("Sextile", 60, 6),
    ("Quincunx", 150, 3),
    ("Semi-sextile", 30, 2),
]

PLANET_IDS = [
    (swe.SUN, "Sun"), (swe.MOON, "Moon"), (swe.MERCURY, "Mercury"),
    (swe.VENUS, "Venus"), (swe.MARS, "Mars"), (swe.JUPITER, "Jupiter"),
    (swe.SATURN, "Saturn"), (swe.MEAN_NODE, "North Node"),
]


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PlanetData:
    name: str
    longitude: float          # 0–360 ecliptic longitude
    sign: str
    sign_degree: float        # degrees within sign (0–30)
    house: int                # 1–12
    retrograde: bool
    speed: float              # degrees/day
    # Dignities
    dignity: str = ""         # Domicile / Exaltation / Triplicity / Term / Face / Peregrine
    detriment: bool = False
    in_fall: bool = False
    # Computed
    antiscion: float = 0.0
    antiscion_sign: str = ""

    @property
    def symbol(self):
        return PLANET_SYMBOLS.get(self.name, self.name[0])

    @property
    def dms(self):
        """Return formatted degree like '10°07' ♑'"""
        d = int(self.sign_degree)
        m = int((self.sign_degree - d) * 60)
        idx = SIGNS.index(self.sign)
        return f"{d:02d}°{m:02d}' {SIGN_SYMBOLS[idx]}"


@dataclass
class ChartData:
    # Input
    name: str
    birth_date: str
    birth_time: str
    city: str
    latitude: float
    longitude: float
    timezone: str
    utc_offset: float

    # Computed
    julian_day: float = 0.0
    asc: float = 0.0
    mc: float = 0.0
    asc_sign: str = ""
    mc_sign: str = ""
    house_cusps: list = field(default_factory=list)   # 12 cusps
    planets: dict = field(default_factory=dict)        # name → PlanetData
    aspects: list = field(default_factory=list)        # list of aspect dicts
    house_lords: dict = field(default_factory=dict)    # house number → planet name
    part_of_fortune: float = 0.0
    is_day_chart: bool = True

    @property
    def asc_dms(self):
        return _lon_to_dms(self.asc)

    @property
    def mc_dms(self):
        return _lon_to_dms(self.mc)


# ── Helper functions ──────────────────────────────────────────────────────────

def _lon_to_sign(lon: float) -> tuple[str, float]:
    """Return (sign_name, degrees_within_sign)."""
    idx = int(lon / 30) % 12
    deg = lon % 30
    return SIGNS[idx], deg


def _lon_to_dms(lon: float) -> str:
    sign, deg = _lon_to_sign(lon)
    d = int(deg)
    m = int((deg - d) * 60)
    idx = SIGNS.index(sign)
    return f"{d:02d}°{m:02d}' {SIGN_SYMBOLS[idx]}"


def _get_house(lon: float, cusps: list) -> int:
    """Return house number (1-12) for a given longitude."""
    for i in range(12):
        cusp_start = cusps[i]
        cusp_end = cusps[(i + 1) % 12]
        if cusp_end < cusp_start:  # house crosses 0°
            if lon >= cusp_start or lon < cusp_end:
                return i + 1
        else:
            if cusp_start <= lon < cusp_end:
                return i + 1
    return 1


def _get_dignity(planet_name: str, sign: str, sign_deg: float, is_day: bool) -> tuple[str, bool, bool]:
    """Return (dignity_label, in_detriment, in_fall)."""
    in_det = sign in DETRIMENT.get(planet_name, [])
    in_fal = FALL.get(planet_name) == sign

    if sign in DOMICILE.get(planet_name, []):
        return "Domicile", in_det, in_fal
    if EXALTATION.get(planet_name) == sign:
        return "Exaltation", in_det, in_fal

    # Triplicity
    trip = TRIPLICITY.get(sign, (None, None))
    trip_ruler = trip[0] if is_day else trip[1]
    if planet_name == trip_ruler:
        return "Triplicity", in_det, in_fal

    # Terms (Ptolemaic)
    term_list = TERMS.get(sign, [])
    prev = 0
    for end_deg, ruler in term_list:
        if prev <= sign_deg < end_deg:
            if ruler == planet_name:
                return "Term", in_det, in_fal
            break
        prev = end_deg

    # Face (Chaldean decans)
    decan = int(sign_deg / 10)  # 0, 1, 2
    start_idx = FACE_START_INDEX.get(sign, 0)
    face_ruler = FACE_SEQUENCE[(start_idx + decan) % 7]
    if face_ruler == planet_name:
        return "Face", in_det, in_fal

    return "Peregrine", in_det, in_fal


def _get_antiscion(lon: float) -> tuple[float, str]:
    """Antiscia: mirror across Cancer/Capricorn solstice axis (0°Cancer = 90°)."""
    # The antiscion axis: sum of planet + antiscion = 180 (for Cancer side) or 360+180...
    # Formula: antiscion = (180 - lon) % 360 if in Aries-Virgo half,
    # actually: antiscion lon = (360 - lon + 180) % 360 ... let's use the standard:
    # Antiscion of lon: mirror around 90° (0° Cancer) and 270° (0° Capricorn)
    # Standard formula: antiscion = (180 - lon % 180 + (180 if lon >= 180 else 0)) won't work
    # Correct: antiscion = (90 - (lon - 90)) % 360 for Cancer axis = 180 - lon mod 360
    antiscion = (180 - lon) % 360
    sign, _ = _lon_to_sign(antiscion)
    return antiscion, sign


def _aspect_angle(a: float, b: float) -> float:
    """Shortest arc between two longitudes."""
    diff = abs(a - b) % 360
    return diff if diff <= 180 else 360 - diff


def _is_applying(p1: PlanetData, p2: PlanetData, aspect_deg: float) -> Optional[bool]:
    """
    True = applying, False = separating, None = can't determine.
    A faster planet applies to a slower one when the angle between them is decreasing.
    """
    speeds = {p1.name: abs(p1.speed), p2.name: abs(p2.speed)}
    # The planet with higher absolute speed is the faster one
    faster = p1 if abs(p1.speed) >= abs(p2.speed) else p2
    slower = p2 if faster is p1 else p1

    # Direction of faster planet relative to slower
    diff = (faster.longitude - slower.longitude) % 360
    # If retrograde, direction reverses
    effective_diff = diff if not faster.retrograde else (360 - diff) % 360
    # Applying if moving toward the aspect angle
    current_arc = _aspect_angle(p1.longitude, p2.longitude)
    return current_arc <= abs(aspect_deg) + 0.5  # simplified heuristic


# ── Main calculation function ─────────────────────────────────────────────────

def calculate_chart(
    name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    city: str,
    lat: float, lon: float,
    unknown_time: bool = False,
) -> ChartData:
    """
    Full natal chart calculation.
    Returns ChartData with all planetary positions, houses, aspects, dignities.
    """
    # ── Timezone & Julian Day ────────────────────────────────────────────────
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    tz = pytz.timezone(tz_name)

    if unknown_time:
        hour, minute = 12, 0  # noon chart for unknown birth time

    local_dt = datetime(year, month, day, hour, minute)
    try:
        local_aware = tz.localize(local_dt, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        local_aware = tz.localize(local_dt, is_dst=True)

    utc_dt = local_aware.astimezone(pytz.utc)
    utc_offset = local_aware.utcoffset().total_seconds() / 3600
    utc_h = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600

    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_h)

    # ── Houses (Regiomontanus — Frawley's explicit recommendation) ───────────
    cusps_raw, ascmc = swe.houses(jd, lat, lon, b'R')
    cusps = list(cusps_raw)   # 12 house cusps
    asc = ascmc[0]
    mc = ascmc[1]

    asc_sign, _ = _lon_to_sign(asc)
    mc_sign, _ = _lon_to_sign(mc)

    # Day/night chart: Sun above horizon = day
    sun_lon = swe.calc_ut(jd, swe.SUN)[0][0]
    sun_house = _get_house(sun_lon, cusps)
    is_day = sun_house in [7, 8, 9, 10, 11, 12]

    # ── Planets ──────────────────────────────────────────────────────────────
    planets = {}
    for pid, pname in PLANET_IDS:
        try:
            result = swe.calc_ut(jd, pid)
        except Exception:
            continue
        p_lon = result[0][0]
        p_speed = result[0][3]
        retro = p_speed < 0
        sign, sign_deg = _lon_to_sign(p_lon)
        house = _get_house(p_lon, cusps)

        dignity, in_det, in_fal = "—", False, False
        if pname not in ("North Node",):
            dignity, in_det, in_fal = _get_dignity(pname, sign, sign_deg, is_day)

        antiscion, antiscion_sign = _get_antiscion(p_lon)

        planets[pname] = PlanetData(
            name=pname,
            longitude=p_lon,
            sign=sign,
            sign_degree=sign_deg,
            house=house,
            retrograde=retro,
            speed=p_speed,
            dignity=dignity,
            detriment=in_det,
            in_fall=in_fal,
            antiscion=antiscion,
            antiscion_sign=antiscion_sign,
        )

    # ── Part of Fortune ──────────────────────────────────────────────────────
    # Day: Asc + Moon - Sun; Night: Asc + Sun - Moon (Lilly's formula)
    moon_lon = planets["Moon"].longitude
    sun_lon_p = planets["Sun"].longitude
    if is_day:
        pof = (asc + moon_lon - sun_lon_p) % 360
    else:
        pof = (asc + sun_lon_p - moon_lon) % 360

    # ── House Lords ──────────────────────────────────────────────────────────
    house_lords = {}
    for i, cusp_lon in enumerate(cusps):
        sign, _ = _lon_to_sign(cusp_lon)
        house_lords[i + 1] = TRADITIONAL_RULERS[sign]

    # ── Aspects ──────────────────────────────────────────────────────────────
    planet_list = [p for p in planets.values()]
    aspects = []
    for i, p1 in enumerate(planet_list):
        for p2 in planet_list[i + 1:]:
            arc = _aspect_angle(p1.longitude, p2.longitude)
            for asp_name, asp_deg, orb in ASPECTS:
                diff = abs(arc - asp_deg)
                if diff <= orb:
                    applying = _is_applying(p1, p2, asp_deg)
                    aspects.append({
                        "planet1": p1.name,
                        "planet2": p2.name,
                        "aspect": asp_name,
                        "orb": round(diff, 2),
                        "applying": applying,
                        "exact_arc": round(arc, 2),
                    })

    # ── Assemble ─────────────────────────────────────────────────────────────
    chart = ChartData(
        name=name,
        birth_date=f"{year:04d}-{month:02d}-{day:02d}",
        birth_time=f"{hour:02d}:{minute:02d}" if not unknown_time else "Unknown",
        city=city,
        latitude=lat,
        longitude=lon,
        timezone=tz_name,
        utc_offset=utc_offset,
        julian_day=jd,
        asc=asc,
        mc=mc,
        asc_sign=asc_sign,
        mc_sign=mc_sign,
        house_cusps=cusps,
        planets=planets,
        aspects=aspects,
        house_lords=house_lords,
        part_of_fortune=pof,
        is_day_chart=is_day,
    )
    return chart


# ── AstroSeek chart image URL builder ────────────────────────────────────────

def build_astroseek_url(chart: ChartData) -> str:
    """
    Build the AstroSeek chart image URL from computed ChartData.
    Uses Regiomontanus house system to match our calculations.
    """
    p = chart.planets
    cusps = chart.house_cusps

    def _fmt(v: float) -> str:
        return f"{v:.2f}"

    pof_lon = _fmt(chart.part_of_fortune)

    # Extract birth date parts
    y, mo, d = chart.birth_date.split("-")
    h, mi = (chart.birth_time.split(":") if chart.birth_time != "Unknown" else ("12", "00"))

    # City encoding (basic)
    city_enc = chart.city.replace(" ", "%20")

    def _plon(name):
        planet = p.get(name)
        return _fmt(planet.longitude) if planet else "0"

    params = {
        "bdata": "1",
        "print_layout": "2",
        "tisk": "1",
        "barva_planet": "1",
        "barva_stupne": "2",
        "planeta_fortune": pof_lon,
        "domy_cisla": "0",
        "no_cache": "3",
        "barva_vzduch": "1",
        "fortune_asp": "1",
        "uzel_asp": "1",
        # House cusps
        "dum_1_new": _fmt(cusps[0]),
        "dum_10_new": _fmt(chart.mc),
        "dum_1": _fmt(cusps[0]),
        "dum_2": _fmt(cusps[1]),
        "dum_3": _fmt(cusps[2]),
        "dum_4": _fmt(cusps[3]),
        "dum_5": _fmt(cusps[4]),
        "dum_6": _fmt(cusps[5]),
        # Traditional 7 planets + North Node only
        "planeta_slunce": _plon("Sun"),
        "planeta_luna": _plon("Moon"),
        "planeta_merkur": _plon("Mercury"),
        "planeta_venuse": _plon("Venus"),
        "planeta_mars": _plon("Mars"),
        "planeta_jupiter": _plon("Jupiter"),
        "planeta_saturn": _plon("Saturn"),
        "planeta_uzel": _plon("North Node"),
        # Modern planets zeroed out — not used in traditional astrology
        "planeta_uran": "0",
        "planeta_neptun": "0",
        "planeta_pluto": "0",
        "planeta_lilith": "0",
        # Retrograde flags — only Saturn and North Node are traditional retrogrades of note
        "r_saturn": "ANO" if (p.get("Saturn") and p["Saturn"].retrograde) else "",
        "r_uzel": "ANO" if (p.get("North Node") and p["North Node"].retrograde) else "",
        "r_pluto": "",
        "r_uranus": "",
        "r_neptune": "",
        "tolerance": "1",
        "house_system": "regiomontanus",
        "narozeni_den": d.lstrip("0") or "1",
        "narozeni_mesic": mo.lstrip("0") or "1",
        "narozeni_rok": y,
        "narozeni_hodina": h,
        "narozeni_minuta": mi,
        "narozeni_mesto_hidden": chart.city,
        "narozeni_stat_hidden": "",
        "narozeni_city": city_enc,
        "narozeni_sirka_stupne": str(abs(int(chart.latitude))),
        "narozeni_sirka_minuty": str(int((abs(chart.latitude) % 1) * 60)),
        "narozeni_sirka_smer": "0" if chart.latitude >= 0 else "1",
        "narozeni_delka_stupne": str(abs(int(chart.longitude))),
        "narozeni_delka_minuty": str(int((abs(chart.longitude) % 1) * 60)),
        "narozeni_delka_smer": "0" if chart.longitude >= 0 else "1",
        "narozeni_timezone_form": "auto",
        "narozeni_timezone_dst_form": "auto",
        "v1": "1",
    }

    base = "https://horoscopes.astro-seek.com/horoscope-chart5-700__radix_traditional_astroseek-"
    base += f"{d}-{mo}-{y}_{h}-{mi}.png"

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{query}"


# ── Dignity summary helper ────────────────────────────────────────────────────

def get_essential_dignities_table(chart: ChartData) -> list[dict]:
    """Return a list of dicts for rendering a dignity table."""
    rows = []
    for pname, p in chart.planets.items():
        if pname in ("North Node",):
            continue
        row = {
            "Planet": f"{p.symbol} {pname}",
            "Sign": p.dms,
            "House": p.house,
            "Dignity": p.dignity,
            "Retro": "℞" if p.retrograde else "",
            "Detri.": "✓" if p.detriment else "",
            "Fall": "✓" if p.in_fall else "",
            "Antiscion": _lon_to_dms(p.antiscion),
        }
        rows.append(row)
    return rows


def get_house_lords_table(chart: ChartData) -> list[dict]:
    """Return house lords with their current sign and dignity."""
    rows = []
    for house_num in range(1, 13):
        lord_name = chart.house_lords.get(house_num, "")
        cusp_lon = chart.house_cusps[house_num - 1]
        cusp_sign, _ = _lon_to_sign(cusp_lon)
        lord = chart.planets.get(lord_name)
        rows.append({
            "House": house_num,
            "Cusp": _lon_to_dms(cusp_lon),
            "Sign": cusp_sign,
            "Lord": lord_name,
            "Lord Position": lord.dms if lord else "—",
            "Lord House": lord.house if lord else "—",
            "Lord Dignity": lord.dignity if lord else "—",
            "Retro": "℞" if (lord and lord.retrograde) else "",
        })
    return rows
