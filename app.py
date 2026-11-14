"""
AccessBay: How accessible are the Bay Area's essential places?
Streamlit app. Reads the files exported from the Colab notebook (Part 6):
    data/places_app.parquet
    data/tracts_app.geojson
"""
import json

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="AccessBay", page_icon="♿", layout="wide")

# ---------------------------------------------------------------------------
# Key numbers from the notebook (Parts 5 and 6). Update if you rerun anything.
# ---------------------------------------------------------------------------
FINDINGS = {
    "places_scored": "100,013",
    "priority_tracts": "118",
    "priority_disabled": "79,724",
    "pharmacy_desert_disabled": "122,606",
    "outside_paratransit": "1,661",
    "mental_health_unknown": "22%",
    "health_care_unknown": "4%",
}

BAND_COLORS = {  # colorblind-safe, always shown together with a text label
    "Highly accessible": [26, 133, 255],
    "Partly accessible": [255, 176, 0],
    "Limited accessibility": [212, 17, 89],
    "Not enough info": [150, 150, 150],
}
BAND_ICONS = {
    "Highly accessible": "🟦",
    "Partly accessible": "🟨",
    "Limited accessibility": "🟥",
    "Not enough info": "⬜",
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def load_places():
    df = pd.read_parquet("data/places_app.parquet")
    if "hours_known" not in df.columns:  # older export without hours columns
        df["hours_known"] = ~df["reasons_text"].str.contains("Hours not listed", na=False)
    df["hours_known"] = df["hours_known"].fillna(False).astype(bool)
    for c in ["name", "address", "city", "county", "category", "group"]:
        df[c] = df[c].fillna("")
    df["search_text"] = (df["name"] + " " + df["address"] + " " + df["category"]).str.lower()
    return df


@st.cache_data
def load_tracts():
    with open("data/tracts_app.geojson") as f:
        gj = json.load(f)
    vals = [ft["properties"].get("pct_disabled") for ft in gj["features"]]
    vals = [v for v in vals if v is not None]
    lo, hi = np.percentile(vals, 5), np.percentile(vals, 95)
    for ft in gj["features"]:
        p = ft["properties"]
        v = p.get("pct_disabled")
        if v is None:
            p["fill"] = [220, 220, 220, 120]
        else:
            t = float(np.clip((v - lo) / (hi - lo), 0, 1))
            p["fill"] = [int(240 - 150 * t), int(235 - 190 * t), int(250 - 110 * t), 170]
        p["line"] = [212, 17, 89, 255] if p.get("priority_tract") else [255, 255, 255, 60]
        p["line_w"] = 60 if p.get("priority_tract") else 5
        p["pct_txt"] = "n/a" if v is None else f"{v:.1f}%"
        p["priority_txt"] = "Yes" if p.get("priority_tract") else "No"
    return gj


def rescore(df, w_phys, w_transit, w_hours, w_para):
    """Recompute the 0 to 10 score with user weights (same rule as the notebook)."""
    earned = (df["physical_score"] / 5 * w_phys
              + df["transit_score"] / 3 * w_transit
              + df["paratransit_pt"] * w_para
              + df["hours_score"] * w_hours * df["hours_known"])
    possible = w_phys + w_transit + w_para + w_hours * df["hours_known"]
    score = (10 * earned / possible.replace(0, np.nan)).round(1)
    score[df["physical_score"].isna()] = np.nan
    return score


def band(s):
    if pd.isna(s):
        return "Not enough info"
    if s >= 8:
        return "Highly accessible"
    if s >= 5:
        return "Partly accessible"
    return "Limited accessibility"


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


places = load_places()

# ---------------------------------------------------------------------------
# Sidebar: what matters to me + filters
# ---------------------------------------------------------------------------
st.sidebar.title("♿ AccessBay")
st.sidebar.caption("Accessibility of Bay Area essential services")

with st.sidebar.expander("How to use this site", expanded=True):
    st.markdown(
        """
1. **Filter** by county and type of place below.
2. Go to **Find a place**: browse the ranked list, or type a name or street to narrow it.
3. **Click a row** to open that place's score card.
4. Optional: open **Personalize** to rank places by what matters most to you.
"""
    )

st.sidebar.subheader("Filters")
counties = sorted(c for c in places["county"].unique() if c)
groups = sorted(g for g in places["group"].unique() if g)
sel_counties = st.sidebar.multiselect("County", counties, placeholder="All counties")
sel_groups = st.sidebar.multiselect("Type of place", groups, placeholder="All types")
sel_bands = st.sidebar.multiselect("Rating", list(BAND_COLORS.keys()), placeholder="All ratings")
min_score = st.sidebar.slider("Minimum AccessBay score", 0.0, 10.0, 0.0, 0.5)

with st.sidebar.expander("Personalize: what matters to me"):
    st.caption(
        "Changes the order places are listed in, using a personal **Your match** score. "
        "The official AccessBay score and rating stay the same for everyone."
    )
    w_phys = st.slider("Physical access (entrance, parking, restroom)", 0, 10, 5)
    w_transit = st.slider("Nearby transit", 0, 10, 3)
    w_para = st.slider("Inside ADA paratransit zone", 0, 10, 1)
    w_hours = st.slider("Evening / weekend hours", 0, 10, 1)

DEFAULT_W = (5, 3, 1, 1)
if w_phys + w_transit + w_para + w_hours == 0:
    st.sidebar.warning("All weights are zero. Using the default weights.")
    w_phys, w_transit, w_para, w_hours = DEFAULT_W
personalized = (w_phys, w_transit, w_para, w_hours) != DEFAULT_W

places["score"] = places["total_score"]                       # official, fixed
places["band_now"] = places["score"].apply(band)
places["match"] = rescore(places, w_phys, w_transit, w_hours, w_para)

view = places
if sel_counties:
    view = view[view["county"].isin(sel_counties)]
if sel_groups:
    view = view[view["group"].isin(sel_groups)]
if sel_bands:
    view = view[view["band_now"].isin(sel_bands)]
if min_score > 0:
    view = view[view["score"] >= min_score]

st.sidebar.caption(f"**{len(view):,}** places match your filters")
if personalized:
    st.sidebar.caption("Ranking by **Your match** (personalized).")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("AccessBay")
st.markdown(
    "**Can Bay Area residents with disabilities reach and use the places they need?** "
    "Search any clinic, pharmacy, grocery store, school, government office or park to see "
    "how accessible it is and why."
)

tab_find, tab_map, tab_hood, tab_about = st.tabs(
    ["🔎 Find a place", "🗺️ Map", "🏘️ Neighborhoods", "ℹ️ How it works"]
)

# ---------------------------------------------------------------------------
# Tab 1: search + score card
# ---------------------------------------------------------------------------
with tab_find:
    q = st.text_input("Search by name, street or city (optional)",
                      placeholder="e.g. Walgreens, Telegraph Ave, dentist San Jose")
    hits = view
    for t in q.lower().split():
        hits = hits[hits["search_text"].str.contains(t, regex=False)]

    sort_col = "match" if personalized else "score"
    hits = hits.sort_values([sort_col, "reviews_count"], ascending=[False, False], na_position="last")
    MAX_ROWS = 200
    shown = hits.head(MAX_ROWS)

    if shown.empty:
        st.warning("No places match. Try fewer words, or loosen the filters in the sidebar.")
    else:
        what = f'matching "{q.strip()}"' if q.strip() else "for your filters"
        st.markdown(f"**{len(hits):,} places {what}**"
                    + (f" (showing the top {MAX_ROWS})" if len(hits) > MAX_ROWS else "")
                    + ". Click a row to open its score card.")
        table = pd.DataFrame({
            "Name": shown["name"],
            "Type": shown["category"],
            "City": shown["city"],
            "AccessBay score": shown["score"],
            "Rating": shown["band_now"].map(lambda b: f"{BAND_ICONS[b]} {b}"),
        })
        if personalized:
            table.insert(3, "Your match", shown["match"])
        event = st.dataframe(
            table, hide_index=True, width="stretch", height=300,
            on_select="rerun", selection_mode="single-row", key="results",
            column_config={
                "AccessBay score": st.column_config.NumberColumn(format="%.1f"),
                "Your match": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        rows = event.selection.rows if event is not None else []
        if not rows:
            st.info("Click any row above to see why a place got its score.")
        else:
            r = places.loc[shown.index[rows[0]]]
            st.divider()
            left, right = st.columns([3, 2])
            with left:
                st.subheader(r["name"])
                st.caption(f"{r['category']} · {r['address'].replace(', United States', '')}")

                color = "#%02x%02x%02x" % tuple(BAND_COLORS[r["band_now"]])
                st.markdown(
                    f"<span style='background:{color};color:white;padding:4px 12px;border-radius:14px;"
                    f"font-weight:600'>{r['band_now']}</span>"
                    f"&nbsp;&nbsp;<span style='color:#555'>Confidence: <b>{r['confidence']}</b></span>",
                    unsafe_allow_html=True,
                )
                st.write("")
                c1, c2 = st.columns(2)
                c1.metric("AccessBay score", "—" if pd.isna(r["score"]) else f"{r['score']:.1f} / 10")
                if personalized:
                    c2.metric("Your match", "—" if pd.isna(r["match"]) else f"{r['match']:.1f} / 10",
                              help="Based on your Personalize settings in the sidebar.")

                st.markdown("**Why this score**")
                for line in str(r["reasons_text"]).split(" | "):
                    if line.startswith("✓"):
                        st.markdown(f":blue[{line}]")
                    elif line.startswith("✗"):
                        st.markdown(f":red[{line}]")
                    else:
                        st.markdown(f":gray[{line}]")

                st.markdown("**Score breakdown**")
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Physical", "—" if pd.isna(r["physical_score"]) else f"{r['physical_score']:.1f}/5")
                b2.metric("Transit", f"{int(r['transit_score'])}/3")
                b3.metric("Paratransit", f"{int(r['paratransit_pt'])}/1")
                b4.metric("Hours", f"{r['hours_score']:.1f}/1" if r["hours_known"] else "not listed")

                if pd.notna(r.get("priority_tract")) and bool(r.get("priority_tract")):
                    st.warning(
                        "This place is in a **priority neighborhood**: a high share of residents "
                        "with disabilities and few accessible essential services nearby."
                    )
                if pd.notna(r.get("open_website")) and str(r.get("open_website")).startswith("http"):
                    st.markdown(f"[Visit website]({r['open_website']})")
                if pd.notna(r.get("phone_number")):
                    st.caption(f"Phone: {r['phone_number']} · Call ahead to confirm access details.")

            with right:
                d = haversine_m(r["lat"], r["lon"], places["lat"].values, places["lon"].values)
                alt = places[(places["group"] == r["group"]) & (d <= 3000) & (d > 0)].copy()
                alt["dist_m"] = d[places.index.get_indexer(alt.index)]
                alt = alt[alt["score"] >= 8].sort_values(["score", "dist_m"], ascending=[False, True]).head(5)

                pts = pd.DataFrame([{"lat": r["lat"], "lon": r["lon"], "name": r["name"],
                                     "color": [0, 0, 0], "radius": 60}])
                if not alt.empty:
                    pts = pd.concat([pts, alt.assign(color=[BAND_COLORS["Highly accessible"]] * len(alt),
                                                     radius=40)[["lat", "lon", "name", "color", "radius"]]])
                st.pydeck_chart(pdk.Deck(
                    map_provider="carto", map_style="light",
                    initial_view_state=pdk.ViewState(latitude=r["lat"], longitude=r["lon"], zoom=13),
                    layers=[pdk.Layer("ScatterplotLayer", pts, get_position="[lon, lat]",
                                      get_fill_color="color", get_radius="radius", pickable=True)],
                    tooltip={"text": "{name}"},
                ), height=320)
                st.caption("Black: selected place. Blue: highly accessible alternatives nearby.")

                st.markdown(f"**Highly accessible {r['group'].lower()} within 3 km**")
                if alt.empty:
                    st.caption("None found nearby.")
                else:
                    for _, a in alt.iterrows():
                        st.markdown(f"- **{a['name']}** · {a['score']:.1f}/10 · {a['dist_m'] / 1000:.1f} km")

# ---------------------------------------------------------------------------
# Tab 2: map of all places
# ---------------------------------------------------------------------------
with tab_map:
    MAX_POINTS = 40_000
    m = view.dropna(subset=["lat", "lon"])
    if len(m) > MAX_POINTS:
        st.caption(f"Showing a random {MAX_POINTS:,} of {len(m):,} places. "
                   "Use the sidebar filters to see all places in an area.")
        m = m.sample(MAX_POINTS, random_state=0)
    m = m[["lat", "lon", "name", "group", "band_now", "score"]].copy()
    m["color"] = m["band_now"].map(BAND_COLORS)
    m["score_txt"] = m["score"].apply(lambda s: "not enough info" if pd.isna(s) else f"{s:.1f}/10")

    st.pydeck_chart(pdk.Deck(
        map_provider="carto", map_style="light",
        initial_view_state=pdk.ViewState(latitude=37.75, longitude=-122.2, zoom=8.5),
        layers=[pdk.Layer("ScatterplotLayer", m, get_position="[lon, lat]", get_fill_color="color",
                          get_radius=60, radius_min_pixels=2, radius_max_pixels=8, pickable=True,
                          opacity=0.8)],
        tooltip={"html": "<b>{name}</b><br/>{group}<br/>{band_now}: {score_txt}"},
    ), height=600)
    st.markdown(" · ".join(f"{BAND_ICONS[b]} {b}" for b in BAND_COLORS))

    counts = view["band_now"].value_counts(normalize=True).reindex(BAND_COLORS.keys()).fillna(0)
    cols = st.columns(4)
    for col, (b, share) in zip(cols, counts.items()):
        col.metric(f"{BAND_ICONS[b]} {b}", f"{share:.0%}")

# ---------------------------------------------------------------------------
# Tab 3: neighborhoods (need vs supply)
# ---------------------------------------------------------------------------
with tab_hood:
    st.subheader("Where are disabled residents left out?")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Priority neighborhoods", FINDINGS["priority_tracts"],
              help="Census tracts in the top 25% for share of disabled residents and the bottom 25% "
                   "for accessible essential services nearby (ranked within urban and rural areas).")
    k2.metric("Disabled residents in them", FINDINGS["priority_disabled"])
    k3.metric("Disabled residents with no pharmacy nearby", FINDINGS["pharmacy_desert_disabled"],
              help="No pharmacy within 1 mile (urban) or 5 miles (rural).")
    k4.metric("Essential places outside ADA paratransit zone", FINDINGS["outside_paratransit"])

    try:
        gj = load_tracts()
        st.pydeck_chart(pdk.Deck(
            map_provider="carto", map_style="light",
            initial_view_state=pdk.ViewState(latitude=37.8, longitude=-122.2, zoom=8.3),
            layers=[pdk.Layer("GeoJsonLayer", gj, get_fill_color="properties.fill",
                              get_line_color="properties.line", get_line_width="properties.line_w",
                              line_width_min_pixels=1, pickable=True, stroked=True, filled=True)],
            tooltip={"html": "<b>{county}</b> county tract<br/>Residents with a disability: {pct_txt}"
                             "<br/>Priority neighborhood: {priority_txt}"},
        ), height=600)
        st.caption("Darker purple = higher share of residents with a disability. "
                   "Red outline = priority neighborhood (high need, low accessible supply).")

        props = pd.DataFrame([f["properties"] for f in gj["features"]])
        by_county = (props[props["priority_tract"] == True]
                     .groupby("county").agg(tracts=("GEOID", "count"), disabled_residents=("pop_disabled", "sum"))
                     .sort_values("tracts", ascending=False))
        by_county["disabled_residents"] = by_county["disabled_residents"].astype(int)
        st.markdown("**Priority neighborhoods by county**")
        st.dataframe(by_county, width="stretch")
    except FileNotFoundError:
        st.error("data/tracts_app.geojson not found.")

    st.markdown(
        f"""
**What we found**
- Mental health providers are the least likely essential service to list any accessibility
  information ({FINDINGS['mental_health_unknown']} unknown, compared with {FINDINGS['health_care_unknown']}
  for general health care).
- Pharmacy deserts are mainly a **supply** problem: most affected residents have no pharmacy nearby at all,
  not one that simply fails to list its accessibility.
- Missing accessibility information follows the *type* of place, not the neighborhood.
"""
    )

# ---------------------------------------------------------------------------
# Tab 4: method, sources, limitations
# ---------------------------------------------------------------------------
with tab_about:
    st.subheader("How the score works")
    st.markdown(
        """
| Part | Default points | What counts |
|---|---|---|
| Physical access | 5 | Confirmed wheelchair-accessible entrance, parking and restroom (restroom only where a public one is expected) |
| Transit | 3 | Nearest usable stop: within 400 m = 3, 800 m = 2, 1.6 km = 1 |
| Paratransit | 1 | Within 3/4 mile of fixed-route transit (the ADA paratransit zone) |
| Hours | 1 | Open after 6 pm (0.5), open on weekends (0.5). Left out if hours are not listed |

Features only earn points when **confirmed**, because the score answers *"can I be sure I can get in?"*
Places with no accessibility information get no score instead of a zero.
Use **Personalize** in the sidebar to rank places by what matters to you. This creates a separate *Your match* score and never changes the official AccessBay score.

**Confidence:** *Confirmed* = every relevant feature is listed. *Partial* = some are.
*Unknown* = none are.
"""
    )
    st.subheader("Data sources")
    st.markdown(
        """
- Google Maps Places and Reviews, Reddit posts: provided by Bright Data through The Bright Initiative
- U.S. Census Bureau, American Community Survey 2023 5-year estimates, table S1810 (disability by tract)
- U.S. Census Bureau, TIGER/Line 2023 census tracts
- 511.org regional transit (GTFS) feed, including stop-level wheelchair boarding data
"""
    )
    st.subheader("Limitations")
    st.markdown(
        """
- Accessibility tags are self-reported on Google and may be wrong or out of date. **Call ahead to confirm.**
- The data mostly covers mobility access. Vision, hearing and cognitive access are barely recorded.
- A missing tag does not mean a place is inaccessible, so small businesses that never filled in their
  details may score lower than they deserve.
- Distances are straight-line, not routes, and ignore hills, sidewalks and curb ramps.
- The paratransit zone is measured from stops rather than routes.
- Census tract estimates have wide margins of error.
"""
    )
    st.caption("Built for the 8th Annual Datathon for Social Good. No reviewer or Reddit usernames are shown.")
