# AccessBay

**Can Bay Area residents with disabilities reach and use the places they need?**

AccessBay scores more than 100,000 Bay Area essential services and outdoor spaces (clinics, pharmacies, grocery stores, government offices, schools, parks and beaches) on how accessible they are, explains every score in plain language, and shows which neighborhoods are left out.

**Live website:** [`accessbay website`](https://accessbay.streamlit.app/)
**Notebook:** [`accessbay_analysis.ipynb`](accessbay_analysis.ipynb)

Built for the 8th Annual Datathon for Social Good (Open Track).

---

## Key findings

1. **118 priority neighborhoods.** Census tracts with a top-quartile share of disabled residents and bottom-quartile access to accessible essential services are home to **79,724 disabled residents**, concentrated in Contra Costa and Solano counties.
2. **Pharmacy deserts are a supply problem.** **122,606 disabled residents** have no pharmacy within 1 mile (urban) or 5 miles (rural). Only 13,569 live near a pharmacy that simply does not list its accessibility.
3. **Mental health care is the least documented.** 22% of mental health providers list no accessibility information, compared with 4% of general health care providers.
4. **Missing information is not missing ramps.** In a Street View spot check, all 16 visible tagged entrances were step-free or ramped, and 8 of 9 untagged ones looked accessible too.
5. **Star ratings don't tell you if you can get in.** Only about 1% of reviews mention accessibility. Those that do average 1.89 stars (vs 3.33 overall), and half also talk about how staff treated people.
6. **Parks and outdoors:** confirmed wheelchair accessible in OpenStreetMap, and 71% of census tracts (474,178 disabled residents) have no confirmed accessible park or trail nearby. Most of this is missing information, not confirmed barriers.
7. **1,661 essential places** sit outside the ADA paratransit zone (more than 3/4 mile from fixed-route transit).

## What the website does

- **Find a place:** browse or search, then open a score card with a plain-language summary, the reasons behind the score, review excerpts and highly accessible alternatives nearby.
- **Map** of every place, colored by rating, with a text summary.
- **Neighborhoods:** where disabled residents live compared with where accessible services are.
- **For decision-makers:** recommendations plus downloadable lists of priority neighborhoods and of places missing accessibility information (an outreach list).
- **Personalize:** reweight what matters to you without changing the official score.
- **Visitor reports and edit links** so the information can improve over time.
- **Accessible by design:** English, Spanish and Chinese; larger text and high contrast options; screen-reader labels; text summaries for maps; ratings never rely on color alone.

## How the score works (0 to 10)

| Part | Points | What counts |
|---|---|---|
| Physical access | 5 | Confirmed wheelchair-accessible entrance, parking and restroom (restroom only where a public one is expected) |
| Transit | 3 | Nearest usable stop within 400 m = 3, 800 m = 2, 1.6 km = 1 |
| Paratransit | 1 | Inside the ADA 3/4-mile paratransit zone |
| Hours | 1 | Open after 6 pm (0.5) and on weekends (0.5); left out when hours are not listed |

Features only earn points when confirmed. Places with no accessibility information are shown as "Not enough info" instead of scoring zero. Parks and outdoor spaces use OpenStreetMap features instead (marked accessible, accessible paths, restrooms and parking).

## Data

| Data | Source | Used for |
|---|---|---|
| Google Maps Places (~147k raw rows) | Bright Data / The Bright Initiative (datathon) | Places, accessibility tags, hours, coordinates |
| Google Maps Reviews | Bright Data / The Bright Initiative (datathon) | Review excerpts and lived-experience themes |
| ACS 2023 5-year, table S1810 | U.S. Census Bureau API | Disability rate by census tract |
| TIGER/Line 2023 tracts | U.S. Census Bureau | Tract boundaries |
| Regional GTFS feed | 511.org | Transit stops and wheelchair boarding |
| Parks, beaches, trails, restrooms, accessible parking | © OpenStreetMap contributors (ODbL), via `osmnx` | Parks & outdoors |

## How to reproduce

1. Open `accessbay_analysis.ipynb` in Google Colab.
2. Add the datathon dataset folder to your Google Drive and set the file paths in the **Paths** cell.
3. Get two free API keys and store them as Colab secrets (key icon in the sidebar):
   - `CENSUS_KEY` from https://api.census.gov/data/key_signup.html
   - `API_511` from https://511.org/open-data/token
4. Run **Runtime → Run all**. The notebook writes `places_app.parquet` and `tracts_app.geojson` to `AccessBay/processed/`. The OpenStreetMap download takes 10 to 25 minutes the first time.

To run the website locally:
```bash
pip install -r requirements.txt
streamlit run app.py
```
The app reads `data/places_app.parquet` and `data/tracts_app.geojson`.

## Repository

```
app.py                     Streamlit website
requirements.txt           Python packages for the website
accessbay_analysis.ipynb   Full analysis, from raw data to website files
data/places_app.parquet    Scored places (website input)
data/tracts_app.geojson    Census tracts with need vs. supply (website input)
```

## Limitations

- Accessibility tags are self-reported on Google and may be out of date; OpenStreetMap coverage for parks is volunteer-driven and incomplete.
- A missing tag does not mean a place is inaccessible.
- The data mostly covers mobility. Vision, hearing and cognitive access are barely recorded.
- Distances are straight-line and ignore hills, sidewalks and curb ramps.
- 68% of transit stops do not record wheelchair boarding; unknown stops are treated as usable.
- Census tract estimates have wide margins of error.
- Reviews skew toward very good or very bad experiences and are mostly from hotels and travel businesses.

See section 10 of the notebook for the full list.

## Ethics

- No reviewer names or photos are stored or shown. Only short review excerpts are quoted.
- A low score can reflect missing information rather than a real barrier, so the site shows confidence levels, and the recommendation is to help businesses list their features rather than to avoid them.
- Visitor reports are labeled unverified and never change the official score.
- API keys are kept in Colab secrets, not in the code.
