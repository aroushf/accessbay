"""
AccessBay: How accessible are the Bay Area's essential places?

Streamlit app. Reads the files exported from the Colab notebook:
    data/places_app.parquet
    data/tracts_app.geojson

Optional visitor reports: set COMMUNITY_FORM_PREFILL and COMMUNITY_SHEET_CSV below.
"""
import html
import json
import os
import urllib.parse

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="AccessBay", layout="wide")

# ---------------------------------------------------------------------------
# Settings you may edit
# ---------------------------------------------------------------------------
FINDINGS = {
    "priority_tracts": "118",
    "priority_disabled": "79,724",
    "pharmacy_desert_disabled": "122,606",
    "outside_paratransit": "1,661",
    "mental_health_unknown": "22%",
    "health_care_unknown": "4%",
}

# Visitor reports (leave as "" to hide the feature).
# 1) Google Form "Get pre-filled link" URL, with the Place ID answer replaced by {place_id}
#    and the Place name answer replaced by {name}.
# 2) The linked Google Sheet, published to the web as CSV (File > Share > Publish to web > CSV).
COMMUNITY_FORM_PREFILL = ""
COMMUNITY_SHEET_CSV = ""

TOILET_GROUPS = {"Health care", "Mental health", "Gov & social services", "Parks & outdoors"}

BAND_ORDER = ["Highly accessible", "Partly accessible", "Limited accessibility", "Not enough info"]
BAND_MAP_COLORS = {
    "Highly accessible": [26, 133, 255],
    "Partly accessible": [255, 176, 0],
    "Limited accessibility": [212, 17, 89],
    "Not enough info": [150, 150, 150],
}
BAND_PILL = {  # background, text (both pass WCAG AA contrast)
    "Highly accessible": ("#0B5CAD", "#FFFFFF"),
    "Partly accessible": ("#FFB000", "#000000"),
    "Limited accessibility": ("#B00D4B", "#FFFFFF"),
    "Not enough info": ("#5F5F5F", "#FFFFFF"),
}
BAND_ICONS = {
    "Highly accessible": "🟦",
    "Partly accessible": "🟨",
    "Limited accessibility": "🟥",
    "Not enough info": "⬜",
}

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
LANGS = {"English": "en", "Español": "es", "中文": "zh"}

T = {
    "subtitle": {"en": "Accessibility of Bay Area essential services",
                 "es": "Accesibilidad de los servicios esenciales del Área de la Bahía",
                 "zh": "湾区基本服务场所的无障碍情况"},
    "lang": {"en": "Language", "es": "Idioma", "zh": "语言"},
    "howto_title": {"en": "How to use this site", "es": "Cómo usar este sitio", "zh": "使用说明"},
    "howto_body": {
        "en": "1. **Filter** by county and type of place below.\n"
              "2. Go to **Find a place**: browse the ranked list, or type a name or street to narrow it.\n"
              "3. **Click a row** to open that place's score card.\n"
              "4. Optional: open **Personalize** to rank places by what matters most to you.",
        "es": "1. **Filtre** por condado y tipo de lugar abajo.\n"
              "2. Vaya a **Buscar un lugar**: explore la lista o escriba un nombre o calle para acotarla.\n"
              "3. **Haga clic en una fila** para ver la ficha de ese lugar.\n"
              "4. Opcional: abra **Personalizar** para ordenar los lugares según lo que más le importa.",
        "zh": "1. 在下方按 **县** 和 **场所类型** 筛选。\n"
              "2. 打开 **查找场所**：浏览排名列表，或输入名称或街道缩小范围。\n"
              "3. **点击任意一行** 查看该场所的评分卡。\n"
              "4. 可选：打开 **个性化**，按您最在意的因素排序。"},
    "display": {"en": "Display", "es": "Pantalla", "zh": "显示"},
    "large_text": {"en": "Larger text", "es": "Texto más grande", "zh": "放大文字"},
    "high_contrast": {"en": "High contrast", "es": "Alto contraste", "zh": "高对比度"},
    "filters": {"en": "Filters", "es": "Filtros", "zh": "筛选"},
    "county": {"en": "County", "es": "Condado", "zh": "县"},
    "all_counties": {"en": "All counties", "es": "Todos los condados", "zh": "所有县"},
    "type": {"en": "Type of place", "es": "Tipo de lugar", "zh": "场所类型"},
    "all_types": {"en": "All types", "es": "Todos los tipos", "zh": "所有类型"},
    "rating": {"en": "Rating", "es": "Calificación", "zh": "评级"},
    "all_ratings": {"en": "All ratings", "es": "Todas", "zh": "所有评级"},
    "min_score": {"en": "Minimum AccessBay score", "es": "Puntuación mínima de AccessBay",
                  "zh": "AccessBay 最低分"},
    "personalize": {"en": "Personalize: what matters to me", "es": "Personalizar: lo que me importa",
                    "zh": "个性化：我在意什么"},
    "personalize_cap": {
        "en": "Changes the order places are listed in, using a personal **Your match** score. "
              "The official AccessBay score and rating stay the same for everyone.",
        "es": "Cambia el orden de la lista usando una puntuación personal, **Su coincidencia**. "
              "La puntuación oficial de AccessBay y la calificación no cambian.",
        "zh": "使用个人的 **匹配度** 分数改变列表顺序。AccessBay 官方评分和评级对所有人保持不变。"},
    "w_phys": {"en": "Physical access (entrance, parking, restroom)",
               "es": "Acceso físico (entrada, estacionamiento, baño)",
               "zh": "实体无障碍（入口、停车、卫生间）"},
    "w_transit": {"en": "Nearby transit", "es": "Transporte público cercano", "zh": "附近公共交通"},
    "w_para": {"en": "Inside ADA paratransit zone", "es": "Dentro de la zona de paratránsito ADA",
               "zh": "位于 ADA 辅助客运服务区内"},
    "w_hours": {"en": "Evening / weekend hours", "es": "Horario nocturno / fin de semana",
                "zh": "晚间 / 周末营业"},
    "zero_w": {"en": "All weights are zero. Using the default weights.",
               "es": "Todos los pesos son cero. Se usan los valores predeterminados.",
               "zh": "所有权重均为零，已使用默认权重。"},
    "n_match": {"en": "**{n}** places match your filters", "es": "**{n}** lugares coinciden con sus filtros",
                "zh": "**{n}** 个场所符合筛选条件"},
    "ranking_personal": {"en": "Ranking by **Your match** (personalized).",
                         "es": "Ordenado por **Su coincidencia** (personalizado).",
                         "zh": "按 **匹配度**（个性化）排序。"},
    "intro": {
        "en": "**Can Bay Area residents with disabilities reach and use the places they need?** "
              "Search any clinic, pharmacy, grocery store, school, government office or park to see how "
              "accessible it is and why.",
        "es": "**¿Pueden las personas con discapacidad del Área de la Bahía llegar a los lugares que necesitan y usarlos?** "
              "Busque cualquier clínica, farmacia, supermercado, escuela, oficina de gobierno o parque para ver "
              "qué tan accesible es y por qué.",
        "zh": "**湾区的残障居民能否到达并使用他们需要的场所？** "
              "搜索任何诊所、药房、超市、学校、政府办公室或公园，了解其无障碍程度及原因。"},
    "tab_find": {"en": "Find a place", "es": "Buscar un lugar", "zh": "查找场所"},
    "tab_map": {"en": "Map", "es": "Mapa", "zh": "地图"},
    "tab_hood": {"en": "Neighborhoods", "es": "Vecindarios", "zh": "社区"},
    "tab_dm": {"en": "For decision-makers", "es": "Para responsables de decisiones", "zh": "决策者专区"},
    "tab_about": {"en": "How it works", "es": "Cómo funciona", "zh": "工作原理"},
    "search_label": {"en": "Search by name, street or city (optional)",
                     "es": "Buscar por nombre, calle o ciudad (opcional)",
                     "zh": "按名称、街道或城市搜索（可选）"},
    "search_ph": {"en": "e.g. Walgreens, Telegraph Ave, dentist San Jose",
                  "es": "p. ej. Walgreens, Telegraph Ave, dentist San Jose",
                  "zh": "例如 Walgreens、Telegraph Ave、dentist San Jose"},
    "no_match": {"en": "No places match. Try fewer words, or loosen the filters in the sidebar.",
                 "es": "Ningún lugar coincide. Pruebe con menos palabras o amplíe los filtros.",
                 "zh": "没有匹配的场所。请减少关键词或放宽侧栏筛选条件。"},
    "res_filters": {"en": "**{n} places for your filters**", "es": "**{n} lugares según sus filtros**",
                    "zh": "**符合筛选条件的场所：{n} 个**"},
    "res_query": {"en": "**{n} places matching \"{q}\"**", "es": "**{n} lugares que coinciden con \"{q}\"**",
                  "zh": "**与\"{q}\"匹配的场所：{n} 个**"},
    "res_top": {"en": " (showing the top {k})", "es": " (se muestran los primeros {k})", "zh": "（显示前 {k} 个）"},
    "res_click": {"en": ". Click a row to open its score card.", "es": ". Haga clic en una fila para ver su ficha.",
                  "zh": "。点击任意一行查看评分卡。"},
    "click_hint": {"en": "Click any row above to see why a place got its score.",
                   "es": "Haga clic en una fila para ver por qué un lugar obtuvo su puntuación.",
                   "zh": "点击上方任意一行，查看该场所得分的原因。"},
    "col_name": {"en": "Name", "es": "Nombre", "zh": "名称"},
    "col_type": {"en": "Type", "es": "Tipo", "zh": "类型"},
    "col_city": {"en": "City", "es": "Ciudad", "zh": "城市"},
    "col_score": {"en": "AccessBay score", "es": "Puntuación AccessBay", "zh": "AccessBay 评分"},
    "col_match": {"en": "Your match", "es": "Su coincidencia", "zh": "匹配度"},
    "col_rating": {"en": "Rating", "es": "Calificación", "zh": "评级"},
    "confidence": {"en": "Confidence", "es": "Confianza", "zh": "可信度"},
    "match_help": {"en": "Based on your Personalize settings in the sidebar.",
                   "es": "Según su configuración en Personalizar.", "zh": "基于侧栏中的个性化设置。"},
    "in_short": {"en": "In short", "es": "En resumen", "zh": "简要说明"},
    "why": {"en": "Why this score", "es": "Por qué esta puntuación", "zh": "得分原因"},
    "breakdown": {"en": "Score breakdown", "es": "Desglose de la puntuación", "zh": "评分明细"},
    "b_phys": {"en": "Physical", "es": "Acceso físico", "zh": "实体无障碍"},
    "b_transit": {"en": "Transit", "es": "Transporte", "zh": "公共交通"},
    "b_para": {"en": "Paratransit", "es": "Paratránsito", "zh": "辅助客运"},
    "b_hours": {"en": "Hours", "es": "Horario", "zh": "营业时间"},
    "not_listed": {"en": "Not listed", "es": "No indicado", "zh": "未列出"},
    "priority_warn": {
        "en": "This place is in a **priority neighborhood**: a high share of residents with disabilities and "
              "few accessible essential services nearby.",
        "es": "Este lugar está en un **vecindario prioritario**: alta proporción de residentes con discapacidad "
              "y pocos servicios esenciales accesibles cerca.",
        "zh": "该场所位于 **优先关注社区**：残障居民比例高，附近无障碍基本服务少。"},
    "website": {"en": "Visit website", "es": "Visitar sitio web", "zh": "访问网站"},
    "phone": {"en": "Phone: {p}. Call ahead to confirm access details.",
              "es": "Teléfono: {p}. Llame antes para confirmar los detalles de acceso.",
              "zh": "电话：{p}。请提前致电确认无障碍细节。"},
    "fix_title": {"en": "Help improve this information", "es": "Ayude a mejorar esta información",
                  "zh": "帮助完善信息"},
    "fix_link": {"en": "Add or fix accessibility details on Google Maps",
                 "es": "Agregar o corregir datos de accesibilidad en Google Maps",
                 "zh": "在 Google 地图上添加或更正无障碍信息"},
    "fix_note": {
        "en": "On Google Maps, choose *Suggest an edit* and fill in the Accessibility section. This improves the "
              "listing for everyone; AccessBay shows the change after its next data refresh.",
        "es": "En Google Maps, elija *Sugerir un cambio* y complete la sección de Accesibilidad. Esto mejora la "
              "ficha para todos; AccessBay mostrará el cambio en la próxima actualización de datos.",
        "zh": "在 Google 地图上选择 *建议修改*，填写无障碍部分。这会为所有人改进该信息；AccessBay 将在下次数据更新后显示变化。"},
    "osm_link": {"en": "Add or fix details on OpenStreetMap", "es": "Agregar o corregir datos en OpenStreetMap",
                 "zh": "在 OpenStreetMap 上添加或更正信息"},
    "osm_note": {
        "en": "Park and outdoor details come from OpenStreetMap, a map built by volunteers. Anyone can add "
              "wheelchair access, accessible paths, restrooms and parking there.",
        "es": "Los datos de parques y aire libre vienen de OpenStreetMap, un mapa hecho por voluntarios. Cualquiera "
              "puede agregar accesibilidad, caminos, baños y estacionamiento.",
        "zh": "公园与户外信息来自志愿者共建的 OpenStreetMap。任何人都可以在上面补充轮椅通行、无障碍步道、卫生间和停车信息。"},
    "osm_source": {"en": "Source: © OpenStreetMap contributors", "es": "Fuente: © colaboradores de OpenStreetMap",
                   "zh": "来源：© OpenStreetMap 贡献者"},
    "report_link": {"en": "Been here? Report what you found", "es": "¿Ha estado aquí? Cuéntenos qué encontró",
                    "zh": "去过这里？报告您的实际情况"},
    "reports_title": {"en": "Visitor reports", "es": "Reportes de visitantes", "zh": "访客报告"},
    "reports_none": {"en": "No visitor reports yet.", "es": "Aún no hay reportes de visitantes.",
                     "zh": "暂无访客报告。"},
    "reports_note": {"en": "Reports come from visitors and are not verified. They do not change the score.",
                     "es": "Los reportes provienen de visitantes y no están verificados. No cambian la puntuación.",
                     "zh": "报告来自访客，未经核实，不影响评分。"},
    "reviews_title": {"en": "What reviewers say", "es": "Lo que dicen las reseñas", "zh": "评论摘录"},
    "reviews_cap": {
        "en": "Short excerpts from public Google reviews, shown in their original language. Reviews tend to come "
              "from very good or very bad visits, so they are shown for context only and do not affect the score. "
              "Reviewer names are not shown.",
        "es": "Fragmentos breves de reseñas públicas de Google, en su idioma original. Las reseñas suelen venir de "
              "visitas muy buenas o muy malas, por eso se muestran solo como contexto y no afectan la puntuación. "
              "No se muestran nombres.",
        "zh": "摘自 Google 公开评论，保留原文语言。评论多来自体验极好或极差的访客，因此仅供参考，不影响评分。不显示评论者姓名。"},
    "mentions_access": {"en": "mentions accessibility", "es": "menciona accesibilidad", "zh": "提及无障碍"},
    "stars": {"en": "{n} out of 5 stars", "es": "{n} de 5 estrellas", "zh": "5 星中的 {n} 星"},
    "alt_caption": {"en": "Black: selected place. Blue: highly accessible places of the same type nearby.",
                    "es": "Negro: lugar seleccionado. Azul: lugares del mismo tipo muy accesibles cerca.",
                    "zh": "黑色：所选场所。蓝色：附近同类高度无障碍场所。"},
    "alt_title": {"en": "Highly accessible {g} within 3 km", "es": "{g} muy accesibles a menos de 3 km",
                  "zh": "3 公里内高度无障碍的{g}"},
    "alt_none": {"en": "None found nearby.", "es": "No se encontraron cerca.", "zh": "附近未找到。"},
    "map_sample": {"en": "Showing a random {k} of {n} places. Use the sidebar filters to see every place in an area.",
                   "es": "Se muestran {k} de {n} lugares al azar. Use los filtros para ver todos los lugares de una zona.",
                   "zh": "随机显示 {n} 个场所中的 {k} 个。使用侧栏筛选可查看某区域的全部场所。"},
    "map_alt": {
        "en": "**Text summary of this map:** {n} places shown. {parts}. The Find a place tab lists the same "
              "places as text.",
        "es": "**Resumen en texto de este mapa:** {n} lugares. {parts}. La pestaña Buscar un lugar muestra los "
              "mismos lugares en texto.",
        "zh": "**地图文字摘要：** 共显示 {n} 个场所。{parts}。“查找场所”标签页以文字形式列出相同场所。"},
    "hood_title": {"en": "Where are disabled residents left out?",
                   "es": "¿Dónde quedan desatendidos los residentes con discapacidad?",
                   "zh": "残障居民在哪些地方被忽视？"},
    "k_priority": {"en": "Priority neighborhoods", "es": "Vecindarios prioritarios", "zh": "优先关注社区"},
    "k_priority_help": {
        "en": "Census tracts in the top 25% for share of disabled residents and the bottom 25% for accessible "
              "essential services nearby, ranked within urban and rural areas.",
        "es": "Zonas censales en el 25% superior de residentes con discapacidad y el 25% inferior de servicios "
              "esenciales accesibles cercanos, comparando zonas urbanas y rurales por separado.",
        "zh": "残障居民比例位于前 25%、附近无障碍基本服务位于后 25% 的人口普查区（城市与农村分别排名）。"},
    "k_disabled": {"en": "Disabled residents in them", "es": "Residentes con discapacidad en ellos",
                   "zh": "其中的残障居民"},
    "k_pharm": {"en": "Disabled residents with no pharmacy nearby",
                "es": "Residentes con discapacidad sin farmacia cercana", "zh": "附近没有药房的残障居民"},
    "k_pharm_help": {"en": "No pharmacy within 1 mile (urban) or 5 miles (rural).",
                     "es": "Ninguna farmacia a menos de 1 milla (urbano) o 5 millas (rural).",
                     "zh": "城市 1 英里内或农村 5 英里内没有药房。"},
    "k_para": {"en": "Essential places outside the ADA paratransit zone",
               "es": "Lugares esenciales fuera de la zona de paratránsito ADA",
               "zh": "位于 ADA 辅助客运服务区外的基本服务场所"},
    "hood_cap": {
        "en": "Darker purple: higher share of residents with a disability. Red outline: priority neighborhood.",
        "es": "Morado más oscuro: mayor proporción de residentes con discapacidad. Borde rojo: vecindario prioritario.",
        "zh": "紫色越深：残障居民比例越高。红色边框：优先关注社区。"},
    "hood_alt": {
        "en": "**Text summary of this map:** {n} priority neighborhoods, most in {top}. Their full list is in the "
              "table below and in the For decision-makers tab.",
        "es": "**Resumen en texto de este mapa:** {n} vecindarios prioritarios, la mayoría en {top}. La lista "
              "completa está en la tabla de abajo y en la pestaña Para responsables de decisiones.",
        "zh": "**地图文字摘要：** 共 {n} 个优先关注社区，主要位于 {top}。完整列表见下表及“决策者专区”。"},
    "by_county": {"en": "Priority neighborhoods by county", "es": "Vecindarios prioritarios por condado",
                  "zh": "各县优先关注社区"},
    "col_county": {"en": "County", "es": "Condado", "zh": "县"},
    "col_tracts": {"en": "Priority neighborhoods", "es": "Vecindarios prioritarios", "zh": "优先关注社区数"},
    "col_dis_res": {"en": "Residents with a disability", "es": "Residentes con discapacidad", "zh": "残障居民人数"},
    "found_title": {"en": "What we found", "es": "Lo que encontramos", "zh": "主要发现"},
    "found_body": {
        "en": "- Mental health providers are the least likely essential service to list any accessibility "
              "information ({mh} unknown, compared with {hc} for general health care).\n"
              "- Pharmacy deserts are mainly a **supply** problem: most affected residents have no pharmacy nearby "
              "at all, not one that simply fails to list its accessibility.\n"
              "- Missing accessibility information follows the *type* of place, not the neighborhood.",
        "es": "- Los proveedores de salud mental son el servicio esencial que menos informa sobre accesibilidad "
              "({mh} sin información, frente a {hc} en atención médica general).\n"
              "- Los desiertos de farmacias son sobre todo un problema de **oferta**: la mayoría de los residentes "
              "afectados no tiene ninguna farmacia cerca.\n"
              "- La falta de información depende del *tipo* de lugar, no del vecindario.",
        "zh": "- 心理健康服务机构是最少公布无障碍信息的基本服务（{mh} 信息缺失，普通医疗为 {hc}）。\n"
              "- 药房荒主要是 **供给** 问题：大多数受影响居民附近根本没有药房，而不只是药房未公布无障碍信息。\n"
              "- 无障碍信息缺失与场所 *类型* 有关，而与社区无关。"},
    "dm_title": {"en": "Turning the findings into action", "es": "De los hallazgos a la acción",
                 "zh": "将发现转化为行动"},
    "dm_intro": {
        "en": "For county ADA coordinators, public health departments, transit agencies and nonprofits. "
              "Both lists below can be downloaded and follow the filters in the sidebar.",
        "es": "Para coordinadores ADA de los condados, departamentos de salud pública, agencias de transporte y "
              "organizaciones sin fines de lucro. Ambas listas se pueden descargar y siguen los filtros laterales.",
        "zh": "面向各县 ADA 协调员、公共卫生部门、交通机构和非营利组织。以下两份列表均可下载，并随侧栏筛选更新。"},
    "dm_recs_title": {"en": "Recommendations", "es": "Recomendaciones", "zh": "建议"},
    "dm_recs": {
        "en": "1. **Bring pharmacy access to priority neighborhoods.** Most affected residents have no pharmacy "
              "nearby at all, so delivery, mail-order and mobile pharmacy programs will help more than new signage.\n"
              "2. **Run an accessibility listing drive, starting with mental health and government offices.** "
              "These are the least documented essential services. Use the outreach list below.\n"
              "3. **Review paratransit coverage** for the essential places that fall outside the ADA 3/4-mile zone, "
              "especially in Solano, Santa Clara and Sonoma counties.\n"
              "4. **Collect stop-level accessibility data.** Most transit stops do not record whether they are "
              "wheelchair accessible.",
        "es": "1. **Llevar acceso a farmacias a los vecindarios prioritarios.** La mayoría de los residentes "
              "afectados no tiene farmacia cerca; la entrega a domicilio, el correo y las farmacias móviles ayudan más "
              "que nuevos letreros.\n"
              "2. **Campaña para publicar información de accesibilidad, empezando por salud mental y oficinas de "
              "gobierno.** Son los servicios menos documentados. Use la lista de contacto de abajo.\n"
              "3. **Revisar la cobertura de paratránsito** para los lugares esenciales fuera de la zona ADA de 3/4 de "
              "milla, sobre todo en Solano, Santa Clara y Sonoma.\n"
              "4. **Recopilar datos de accesibilidad de las paradas.** La mayoría no indica si es accesible en silla de ruedas.",
        "zh": "1. **为优先关注社区提供药房服务。** 大多数受影响居民附近根本没有药房，送药上门、邮寄和流动药房比新增标识更有效。\n"
              "2. **开展无障碍信息登记行动，从心理健康机构和政府办公室开始。** 这些是信息最缺乏的基本服务，请使用下方联络名单。\n"
              "3. **审查辅助客运覆盖范围**，关注位于 ADA 3/4 英里服务区外的基本服务场所，尤其是 Solano、Santa Clara 和 Sonoma 县。\n"
              "4. **收集站点级无障碍数据。** 大多数公交站点未记录是否可供轮椅使用。"},
    "dm_tracts_title": {"en": "Priority neighborhoods", "es": "Vecindarios prioritarios", "zh": "优先关注社区"},
    "dm_tracts_cap": {"en": "Sorted by number of residents with a disability.",
                      "es": "Ordenados por número de residentes con discapacidad.", "zh": "按残障居民人数排序。"},
    "dm_dl_tracts": {"en": "Download priority neighborhoods (CSV)",
                     "es": "Descargar vecindarios prioritarios (CSV)", "zh": "下载优先关注社区（CSV）"},
    "dm_out_title": {"en": "Outreach list: places missing accessibility information",
                     "es": "Lista de contacto: lugares sin información de accesibilidad",
                     "zh": "联络名单：缺少无障碍信息的场所"},
    "dm_out_cap": {
        "en": "{n} essential places list some or none of their accessibility features. Mental health and government "
              "offices come first. Showing the first {k}; the download has all of them.",
        "es": "{n} lugares esenciales indican solo parte o ninguna de sus características de accesibilidad. Primero "
              "salud mental y oficinas de gobierno. Se muestran los primeros {k}; la descarga incluye todos.",
        "zh": "{n} 个基本服务场所仅列出部分或未列出无障碍设施。心理健康机构和政府办公室优先。此处显示前 {k} 个，下载文件包含全部。"},
    "dm_dl_out": {"en": "Download outreach list (CSV)", "es": "Descargar lista de contacto (CSV)",
                  "zh": "下载联络名单（CSV）"},
    "col_group": {"en": "Category", "es": "Categoría", "zh": "类别"},
    "col_address": {"en": "Address", "es": "Dirección", "zh": "地址"},
    "col_phone": {"en": "Phone", "es": "Teléfono", "zh": "电话"},
    "col_website": {"en": "Website", "es": "Sitio web", "zh": "网站"},
    "col_missing": {"en": "Missing information", "es": "Información faltante", "zh": "缺失信息"},
    "col_share": {"en": "Share with a disability (%)", "es": "Proporción con discapacidad (%)",
                  "zh": "残障比例（%）"},
    "col_acc_near": {"en": "Accessible essential places nearby", "es": "Lugares esenciales accesibles cerca",
                     "zh": "附近无障碍基本服务场所"},
    "col_main_city": {"en": "Main city", "es": "Ciudad principal", "zh": "主要城市"},
    "col_pharm_km": {"en": "Nearest accessible pharmacy (km)", "es": "Farmacia accesible más cercana (km)",
                     "zh": "最近的无障碍药房（公里）"},
    "col_food_km": {"en": "Nearest accessible grocery (km)", "es": "Supermercado accesible más cercano (km)",
                    "zh": "最近的无障碍超市（公里）"},
    "col_setting": {"en": "Setting", "es": "Entorno", "zh": "区域类型"},
    "col_tract": {"en": "Census tract", "es": "Zona censal", "zh": "人口普查区"},
    "about_score_title": {"en": "How the score works", "es": "Cómo funciona la puntuación", "zh": "评分方法"},
    "about_score": {
        "en": "| Part | Default points | What counts |\n|---|---|---|\n"
              "| Physical access | 5 | Confirmed wheelchair-accessible entrance, parking and restroom (restroom only where a public one is expected) |\n"
              "| Transit | 3 | Nearest usable stop: within 400 m = 3, 800 m = 2, 1.6 km = 1 |\n"
              "| Paratransit | 1 | Within 3/4 mile of fixed-route transit (the ADA paratransit zone) |\n"
              "| Hours | 1 | Open after 6 pm (0.5), open on weekends (0.5). Left out if hours are not listed |\n\n"
              "Features only earn points when **confirmed**, because the score answers *\"can I be sure I can get in?\"* "
              "Places with no accessibility information get no score instead of a zero. **Parks & outdoors** use "
              "OpenStreetMap data instead: marked wheelchair accessible (2), accessible path or trail (1.5), accessible "
              "restroom within 300 m (1) and accessible parking within 300 m (0.5), plus transit and paratransit. "
              "**Personalize** in the sidebar "
              "creates a separate *Your match* score and never changes the official score.\n\n"
              "**Confidence:** *Confirmed* means every relevant feature is listed, *Partial* means some are, "
              "*Unknown* means none are.",
        "es": "| Parte | Puntos | Qué cuenta |\n|---|---|---|\n"
              "| Acceso físico | 5 | Entrada, estacionamiento y baño accesibles en silla de ruedas y confirmados (baño solo donde se espera uno público) |\n"
              "| Transporte | 3 | Parada utilizable más cercana: hasta 400 m = 3, 800 m = 2, 1,6 km = 1 |\n"
              "| Paratránsito | 1 | A menos de 3/4 de milla del transporte de ruta fija (zona de paratránsito ADA) |\n"
              "| Horario | 1 | Abierto después de las 6 pm (0,5) y los fines de semana (0,5). Se omite si no hay horario |\n\n"
              "Las características solo suman puntos si están **confirmadas**, porque la puntuación responde a "
              "*\"¿puedo estar seguro de que podré entrar?\"* Los lugares sin información no reciben puntuación en lugar "
              "de un cero. **Personalizar** crea una puntuación aparte, *Su coincidencia*, y nunca cambia la oficial.\n\n"
              "**Confianza:** *Confirmada* = todas las características relevantes indicadas; *Parcial* = algunas; "
              "*Desconocida* = ninguna.",
        "zh": "| 部分 | 默认分值 | 计分依据 |\n|---|---|---|\n"
              "| 实体无障碍 | 5 | 已确认的轮椅无障碍入口、停车位和卫生间（仅在通常提供公共卫生间的场所计入卫生间） |\n"
              "| 公共交通 | 3 | 最近可用站点：400 米内 = 3，800 米内 = 2，1.6 公里内 = 1 |\n"
              "| 辅助客运 | 1 | 距固定线路公交 3/4 英里以内（ADA 辅助客运服务区） |\n"
              "| 营业时间 | 1 | 晚 6 点后营业（0.5）、周末营业（0.5）。未列出营业时间则不计入 |\n\n"
              "只有 **已确认** 的设施才计分，因为评分回答的是“我能否确定进得去？”。没有任何无障碍信息的场所不评分，而不是记为零分。"
              "侧栏中的 **个性化** 会生成单独的“匹配度”分数，不会改变官方评分。\n\n"
              "**可信度：** “已确认”表示所有相关设施均已列出；“部分”表示列出部分；“未知”表示均未列出。"},
    "sources_title": {"en": "Data sources", "es": "Fuentes de datos", "zh": "数据来源"},
    "sources": {
        "en": "- Google Maps Places and Reviews, Reddit posts: provided by Bright Data through The Bright Initiative\n"
              "- U.S. Census Bureau, American Community Survey 2023 5-year estimates, table S1810 (disability by tract)\n"
              "- U.S. Census Bureau, TIGER/Line 2023 census tracts\n"
              "- 511.org regional transit (GTFS) feed, including stop-level wheelchair boarding data\n"
              "- Parks, beaches, trails, restrooms and accessible parking: © OpenStreetMap contributors (ODbL)",
        "es": "- Google Maps Places y Reviews, publicaciones de Reddit: proporcionados por Bright Data a través de The Bright Initiative\n"
              "- Oficina del Censo de EE. UU., American Community Survey 2023 (5 años), tabla S1810 (discapacidad por zona censal)\n"
              "- Oficina del Censo de EE. UU., zonas censales TIGER/Line 2023\n"
              "- Datos de transporte regional de 511.org (GTFS), incluida la accesibilidad en silla de ruedas por parada\n"
              "- Parques, playas, senderos, baños y estacionamiento accesible: © colaboradores de OpenStreetMap (ODbL)",
        "zh": "- Google 地图场所与评论、Reddit 帖子：由 Bright Data 通过 The Bright Initiative 提供\n"
              "- 美国人口普查局 2023 年美国社区调查 5 年估计，表 S1810（按普查区统计残障情况）\n"
              "- 美国人口普查局 TIGER/Line 2023 普查区边界\n"
              "- 511.org 湾区公交（GTFS）数据，含站点轮椅上车信息\n"
              "- 公园、海滩、步道、卫生间和无障碍停车：© OpenStreetMap 贡献者（ODbL）"},
    "limits_title": {"en": "Limitations", "es": "Limitaciones", "zh": "局限性"},
    "limits": {
        "en": "- Accessibility tags are self-reported on Google and may be wrong or out of date. **Call ahead to confirm.**\n"
              "- The data mostly covers mobility access. Vision, hearing and cognitive access are barely recorded.\n"
              "- A missing tag does not mean a place is inaccessible, so places that never filled in their details may "
              "score lower than they deserve.\n"
              "- Distances are straight-line, not routes, and ignore hills, sidewalks and curb ramps.\n"
              "- The paratransit zone is measured from stops rather than routes.\n"
              "- Census tract estimates have wide margins of error.",
        "es": "- Las etiquetas de accesibilidad las publica cada negocio en Google y pueden estar equivocadas o desactualizadas. **Llame antes para confirmar.**\n"
              "- Los datos cubren sobre todo la movilidad. La accesibilidad visual, auditiva y cognitiva casi no se registra.\n"
              "- Que falte una etiqueta no significa que el lugar no sea accesible.\n"
              "- Las distancias son en línea recta y no consideran pendientes, aceras ni rampas.\n"
              "- La zona de paratránsito se mide desde las paradas y no desde las rutas.\n"
              "- Las estimaciones por zona censal tienen márgenes de error amplios.",
        "zh": "- 无障碍标签由商家在 Google 上自行填写，可能有误或过时。**请提前致电确认。**\n"
              "- 数据主要涵盖行动无障碍，视觉、听觉和认知无障碍信息很少。\n"
              "- 缺少标签不代表场所不无障碍，未填写信息的场所得分可能偏低。\n"
              "- 距离为直线距离，未考虑坡度、人行道和路缘坡道。\n"
              "- 辅助客运服务区按站点而非线路测算。\n"
              "- 普查区估计值误差范围较大。"},
    "a11y_title": {"en": "Accessibility of this site", "es": "Accesibilidad de este sitio", "zh": "本网站的无障碍设计"},
    "a11y": {
        "en": "- Available in English, Spanish and Chinese. Place names, categories and reviews stay as Google lists them.\n"
              "- **Larger text** and **High contrast** options in the sidebar.\n"
              "- Ratings always use a text label, never color alone, and the colors are chosen to be readable with color blindness.\n"
              "- Check and cross marks are announced to screen readers as \"Yes\" and \"No\".\n"
              "- Every map has a text summary, and the Find a place list holds the same information as text.\n"
              "- Each score card opens with a plain-language summary.\n"
              "- The site has no audio.",
        "es": "- Disponible en inglés, español y chino. Los nombres, categorías y reseñas se muestran como en Google.\n"
              "- Opciones de **Texto más grande** y **Alto contraste** en la barra lateral.\n"
              "- Las calificaciones siempre llevan texto, no solo color, y los colores son legibles con daltonismo.\n"
              "- Los lectores de pantalla anuncian las marcas como \"Sí\" y \"No\".\n"
              "- Cada mapa tiene un resumen en texto, y la lista de Buscar un lugar contiene la misma información.\n"
              "- Cada ficha empieza con un resumen en lenguaje sencillo.\n"
              "- El sitio no tiene audio.",
        "zh": "- 提供英文、西班牙文和中文。场所名称、类别和评论保持 Google 原文。\n"
              "- 侧栏提供 **放大文字** 和 **高对比度** 选项。\n"
              "- 评级始终带有文字标签，不只依靠颜色，所选颜色对色盲用户也清晰可辨。\n"
              "- 屏幕阅读器会将勾号和叉号读作“是”和“否”。\n"
              "- 每张地图都有文字摘要，“查找场所”列表以文字形式包含相同信息。\n"
              "- 每张评分卡开头都有简明说明。\n"
              "- 本网站没有音频内容。"},
    "footer": {"en": "Built for the 8th Annual Datathon for Social Good. No reviewer or Reddit usernames are shown.",
               "es": "Creado para el 8.º Datathon anual para el Bien Social. No se muestran nombres de usuarios.",
               "zh": "为第八届年度公益数据马拉松而建。不显示任何评论者或 Reddit 用户名。"},
    "yes": {"en": "Yes", "es": "Sí", "zh": "是"},
    "no": {"en": "No", "es": "No", "zh": "否"},
    "unknown": {"en": "Unknown", "es": "Desconocido", "zh": "未知"},
    "data_missing": {"en": "{f} not found.", "es": "No se encontró {f}.", "zh": "未找到 {f}。"},
}

BAND_T = {
    "Highly accessible": {"en": "Highly accessible", "es": "Muy accesible", "zh": "高度无障碍"},
    "Partly accessible": {"en": "Partly accessible", "es": "Parcialmente accesible", "zh": "部分无障碍"},
    "Limited accessibility": {"en": "Limited accessibility", "es": "Accesibilidad limitada", "zh": "无障碍有限"},
    "Not enough info": {"en": "Not enough info", "es": "Información insuficiente", "zh": "信息不足"},
}
CONF_T = {
    "Confirmed": {"en": "Confirmed", "es": "Confirmada", "zh": "已确认"},
    "Partial": {"en": "Partial", "es": "Parcial", "zh": "部分"},
    "Unknown": {"en": "Unknown", "es": "Desconocida", "zh": "未知"},
}
GROUP_T = {
    "Health care": {"en": "Health care", "es": "Atención médica", "zh": "医疗保健"},
    "Mental health": {"en": "Mental health", "es": "Salud mental", "zh": "心理健康"},
    "Pharmacy": {"en": "Pharmacy", "es": "Farmacia", "zh": "药房"},
    "Food": {"en": "Food", "es": "Alimentos", "zh": "食品"},
    "Financial": {"en": "Financial", "es": "Servicios financieros", "zh": "金融服务"},
    "Gov & social services": {"en": "Gov & social services", "es": "Gobierno y servicios sociales",
                              "zh": "政府与社会服务"},
    "Education & child care": {"en": "Education & child care", "es": "Educación y cuidado infantil",
                               "zh": "教育与托儿"},
    "Recreation": {"en": "Recreation", "es": "Recreación", "zh": "休闲娱乐"},
    "Parks & outdoors": {"en": "Parks & outdoors", "es": "Parques y aire libre", "zh": "公园与户外"},
}
FEAT_T = {
    "entrance": {"en": "entrance", "es": "entrada", "zh": "入口"},
    "parking": {"en": "parking", "es": "estacionamiento", "zh": "停车位"},
    "toilet": {"en": "restroom", "es": "baño", "zh": "卫生间"},
    "seating": {"en": "seating", "es": "asientos", "zh": "座位"},
}
R = {  # reason sentences
    "feat_yes": {"en": "Wheelchair-accessible {f}", "es": "{F} accesible en silla de ruedas", "zh": "轮椅无障碍{f}"},
    "feat_no": {"en": "No wheelchair-accessible {f}", "es": "Sin {f} accesible en silla de ruedas", "zh": "没有轮椅无障碍{f}"},
    "feat_unk": {"en": "{F} accessibility not listed", "es": "No se indica si {f} es accesible", "zh": "未列出{f}是否无障碍"},
    "loop_yes": {"en": "Assistive hearing loop", "es": "Bucle de inducción auditiva", "zh": "助听感应环路"},
    "loop_no": {"en": "No assistive hearing loop", "es": "Sin bucle de inducción auditiva", "zh": "没有助听感应环路"},
    "stop_conf": {"en": "Wheelchair-accessible transit stop {d} away",
                  "es": "Parada de transporte accesible a {d}", "zh": "{d}外有轮椅无障碍公交站"},
    "stop_any": {"en": "Transit stop {d} away (stop accessibility not recorded)",
                 "es": "Parada de transporte a {d} (accesibilidad de la parada no registrada)",
                 "zh": "{d}外有公交站（未记录站点是否无障碍）"},
    "stop_far": {"en": "Nearest usable transit stop is {d} away",
                 "es": "La parada utilizable más cercana está a {d}", "zh": "最近的可用公交站在{d}外"},
    "para_in": {"en": "Inside the ADA paratransit zone", "es": "Dentro de la zona de paratránsito ADA",
                "zh": "位于 ADA 辅助客运服务区内"},
    "para_out": {"en": "Outside the ADA paratransit zone (over 3/4 mile from fixed-route transit)",
                 "es": "Fuera de la zona de paratránsito ADA (a más de 3/4 de milla del transporte de ruta fija)",
                 "zh": "位于 ADA 辅助客运服务区外（距固定线路公交超过 3/4 英里）"},
    "hours_unk": {"en": "Hours not listed", "es": "Horario no indicado", "zh": "未列出营业时间"},
    "eve_yes": {"en": "Open evenings (after 6 pm)", "es": "Abierto por la noche (después de las 6 pm)",
                "zh": "晚间营业（晚 6 点后）"},
    "eve_no": {"en": "Closes by 6 pm", "es": "Cierra antes de las 6 pm", "zh": "晚 6 点前关门"},
    "wkd_yes": {"en": "Open on weekends", "es": "Abierto los fines de semana", "zh": "周末营业"},
    "wkd_no": {"en": "Closed on weekends", "es": "Cerrado los fines de semana", "zh": "周末不营业"},
    # plain-language summary
    "s_ent_yes": {"en": "You can likely get in with a wheelchair.",
                  "es": "Probablemente pueda entrar en silla de ruedas.", "zh": "轮椅使用者很可能可以进入。"},
    "s_ent_no": {"en": "The entrance is listed as not wheelchair accessible.",
                 "es": "La entrada figura como no accesible en silla de ruedas.", "zh": "入口被标注为不可供轮椅进入。"},
    "s_ent_unk": {"en": "We don't know if the entrance is wheelchair accessible.",
                  "es": "No sabemos si la entrada es accesible en silla de ruedas.", "zh": "我们不确定入口是否可供轮椅进入。"},
    "s_wc_yes": {"en": "It lists an accessible restroom.", "es": "Indica un baño accesible.", "zh": "列有无障碍卫生间。"},
    "s_wc_unk": {"en": "Restroom access is not listed.", "es": "No indica si el baño es accesible.",
                 "zh": "未列出卫生间是否无障碍。"},
    "s_transit": {"en": "A transit stop is about a {m}-minute walk or roll away.",
                  "es": "Hay una parada de transporte a unos {m} minutos a pie o en silla de ruedas.",
                  "zh": "步行或乘轮椅约 {m} 分钟可到公交站。"},
    "s_transit_far": {"en": "Transit is far away (about {km} km).",
                      "es": "El transporte público queda lejos (unos {km} km).", "zh": "公共交通较远（约 {km} 公里）。"},
    "s_call": {"en": "Call ahead to confirm.", "es": "Llame antes para confirmar.", "zh": "请提前致电确认。"},
    # parks (OpenStreetMap)
    "p_all_yes": {"en": "Marked wheelchair accessible", "es": "Marcado como accesible en silla de ruedas",
                  "zh": "标注为轮椅无障碍"},
    "p_all_lim": {"en": "Marked partly wheelchair accessible", "es": "Marcado como parcialmente accesible",
                  "zh": "标注为部分轮椅无障碍"},
    "p_all_no": {"en": "Marked not wheelchair accessible", "es": "Marcado como no accesible en silla de ruedas",
                 "zh": "标注为轮椅不可进入"},
    "p_all_unk": {"en": "Overall wheelchair access not recorded", "es": "No se registra la accesibilidad general",
                  "zh": "未记录整体轮椅无障碍情况"},
    "p_trail_yes": {"en": "Wheelchair-accessible path or trail", "es": "Sendero o camino accesible en silla de ruedas",
                    "zh": "有轮椅无障碍步道"},
    "p_trail_lim": {"en": "Paths partly wheelchair accessible", "es": "Caminos parcialmente accesibles",
                    "zh": "步道部分无障碍"},
    "p_trail_no": {"en": "Paths marked not wheelchair accessible", "es": "Caminos marcados como no accesibles",
                   "zh": "步道标注为轮椅不可通行"},
    "p_trail_unk": {"en": "Path accessibility not recorded", "es": "No se registra la accesibilidad de los caminos",
                    "zh": "未记录步道无障碍情况"},
    "p_wc_yes": {"en": "Wheelchair-accessible restroom within 300 m", "es": "Baño accesible a menos de 300 m",
                 "zh": "300 米内有轮椅无障碍卫生间"},
    "p_wc_no": {"en": "Nearby restroom is not wheelchair accessible", "es": "El baño cercano no es accesible",
                "zh": "附近卫生间不可供轮椅使用"},
    "p_wc_unk": {"en": "No accessible restroom recorded nearby", "es": "No hay baño accesible registrado cerca",
                 "zh": "附近未记录无障碍卫生间"},
    "p_park_yes": {"en": "Accessible parking within 300 m", "es": "Estacionamiento accesible a menos de 300 m",
                   "zh": "300 米内有无障碍停车位"},
    "p_park_unk": {"en": "No accessible parking recorded nearby", "es": "No hay estacionamiento accesible registrado cerca",
                   "zh": "附近未记录无障碍停车位"},
    "ps_yes": {"en": "Volunteers have marked this place as wheelchair accessible.",
               "es": "Voluntarios marcaron este lugar como accesible en silla de ruedas.",
               "zh": "志愿者已将此处标注为轮椅无障碍。"},
    "ps_lim": {"en": "Volunteers have marked this place as partly wheelchair accessible.",
               "es": "Voluntarios marcaron este lugar como parcialmente accesible.",
               "zh": "志愿者已将此处标注为部分轮椅无障碍。"},
    "ps_no": {"en": "Volunteers have marked this place as not wheelchair accessible.",
              "es": "Voluntarios marcaron este lugar como no accesible en silla de ruedas.",
              "zh": "志愿者已将此处标注为轮椅不可进入。"},
    "ps_unk": {"en": "Overall wheelchair access has not been recorded.",
               "es": "No se ha registrado la accesibilidad general.", "zh": "尚未记录整体轮椅无障碍情况。"},
    "ps_trail": {"en": "It has a wheelchair-accessible path.", "es": "Tiene un camino accesible en silla de ruedas.",
                 "zh": "有轮椅无障碍步道。"},
    "ps_wc": {"en": "There is an accessible restroom nearby.", "es": "Hay un baño accesible cerca.",
              "zh": "附近有无障碍卫生间。"},
    "ps_check": {"en": "Check conditions before you go.", "es": "Revise las condiciones antes de ir.",
                 "zh": "出发前请确认现场情况。"},
}


def t(key, **kw):
    s = T[key][LANG]
    return s.format(**kw) if kw else s


def tr(table, key):
    return table.get(key, {}).get(LANG, key)


def dist_txt(m):
    m = float(m)
    if LANG == "zh":
        return f"{int(round(m))} 米" if m < 1000 else f"{m / 1000:.1f} 公里"
    return f"{int(round(m))} m" if m < 1000 else f"{m / 1000:.1f} km"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
PLACE_COLS = ["place_id", "name", "category", "group", "address", "city", "county", "lat", "lon",
              "reviews_count", "phone_number", "open_website",
              "entrance", "parking", "toilet", "seating", "hearing_loop", "trail",
              "physical_score", "transit_score", "hours_score", "paratransit_pt", "total_score", "confidence",
              "dist_usable_stop_m", "dist_confirmed_stop_m", "in_paratransit", "priority_tract",
              "hours_known", "open_evening", "open_weekend", "review_samples", "source", "osm_url"]


@st.cache_resource(max_entries=1)   # one shared copy for all visitors; never copied per click
def load_places(mtime):
    import pyarrow.parquet as pq
    have = set(pq.read_schema("data/places_app.parquet").names)
    df = pd.read_parquet("data/places_app.parquet", columns=[c for c in PLACE_COLS if c in have])
    defaults = {"trail": "unknown", "source": "Google Maps", "osm_url": None, "review_samples": None,
                "hours_known": False, "open_evening": False, "open_weekend": False, "in_paratransit": False,
                "entrance": "unknown", "parking": "unknown", "toilet": "unknown", "seating": "unknown",
                "hearing_loop": "unknown", "priority_tract": None}
    for c, v in defaults.items():
        if c not in df.columns:
            df[c] = v
    for c in ["hours_known", "open_evening", "open_weekend", "in_paratransit"]:
        df[c] = df[c].fillna(False).astype(bool)
    for c in ["entrance", "parking", "toilet", "seating", "hearing_loop", "trail"]:
        df[c] = df[c].fillna("unknown")
    df["source"] = df["source"].fillna("Google Maps")
    for c in ["name", "address", "city", "county", "category", "group"]:
        df[c] = df[c].fillna("")
    df["search_text"] = (df["name"] + " " + df["address"] + " " + df["category"]).str.lower()
    df["score"] = df["total_score"]
    df["band_now"] = df["score"].apply(band)
    for c in ["category", "group", "city", "county", "confidence", "band_now", "source",
              "entrance", "parking", "toilet", "seating", "hearing_loop", "trail"]:
        df[c] = df[c].astype("category")
    for c in ["lat", "lon", "physical_score", "transit_score", "hours_score", "total_score", "score",
              "dist_usable_stop_m", "dist_confirmed_stop_m"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    return df.reset_index(drop=True)


@st.cache_resource(max_entries=3)
def styled_tracts(mtime, lang):
    with open("data/tracts_app.geojson") as f:
        gj = json.load(f)
    return style_tracts(gj, lang)


def style_tracts(gj, lang):
    vals = [ft["properties"].get("pct_disabled") for ft in gj["features"]]
    vals = [v for v in vals if v is not None]
    lo, hi = np.percentile(vals, 5), np.percentile(vals, 95)
    yes, no = T["yes"][lang], T["no"][lang]
    for ft in gj["features"]:
        p = ft["properties"]
        v = p.get("pct_disabled")
        if v is None:
            p["fill"] = [220, 220, 220, 120]
        else:
            k = float(np.clip((v - lo) / (hi - lo), 0, 1))
            p["fill"] = [int(240 - 150 * k), int(235 - 190 * k), int(250 - 110 * k), 170]
        p["line"] = [176, 13, 75, 255] if p.get("priority_tract") else [255, 255, 255, 60]
        p["line_w"] = 60 if p.get("priority_tract") else 5
        p["pct_txt"] = "n/a" if v is None else f"{v:.1f}%"
        p["priority_txt"] = yes if p.get("priority_tract") else no
    return gj


@st.cache_data(ttl=60)
def load_reports(url):
    if not url:
        return pd.DataFrame()
    try:
        return pd.read_csv(url)
    except Exception:
        return pd.DataFrame()


def rescore(df, w_phys, w_transit, w_hours, w_para):
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


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------
def stat_cards(items):
    """items: list of (label, value, help_or_None). Labels wrap instead of being cut off."""
    cards = []
    for label, value, help_ in items:
        h = f"<div class='ab-help'>{html.escape(help_)}</div>" if help_ else ""
        cards.append(f"<div class='ab-card'><div class='ab-label'>{html.escape(label)}</div>"
                     f"<div class='ab-value'>{html.escape(str(value))}</div>{h}</div>")
    st.markdown(f"<div class='ab-cards'>{''.join(cards)}</div>", unsafe_allow_html=True)


def reason_line(kind, text):
    sym = {"yes": "✓", "no": "✗", "unk": "?"}[kind]
    sr = {"yes": t("yes"), "no": t("no"), "unk": t("unknown")}[kind]
    return (f"<div class='ab-reason ab-{kind}'><span aria-hidden='true' class='ab-sym'>{sym}</span>"
            f"<span class='sr-only'>{sr}: </span>{html.escape(text)}</div>")


def park_reasons(r):
    out = []
    lvl = {"yes": ("yes", "yes"), "limited": ("unk", "lim"), "no": ("no", "no")}
    k, sfx = lvl.get(r["entrance"], ("unk", "unk"))
    out.append((k, R[f"p_all_{sfx}"][LANG]))
    k, sfx = lvl.get(r["trail"], ("unk", "unk"))
    out.append((k, R[f"p_trail_{sfx}"][LANG]))
    k, sfx = {"yes": ("yes", "yes"), "no": ("no", "no")}.get(r["toilet"], ("unk", "unk"))
    out.append((k, R[f"p_wc_{sfx}"][LANG]))
    out.append(("yes", R["p_park_yes"][LANG]) if r["parking"] == "yes" else ("unk", R["p_park_unk"][LANG]))
    return out


def build_reasons(r):
    out = []
    if r["source"] == "OpenStreetMap":
        out = park_reasons(r)
    for f in ([] if r["source"] == "OpenStreetMap" else ["entrance", "toilet", "parking", "seating"]):
        status = r[f]
        if f == "toilet" and r["group"] not in TOILET_GROUPS and status == "unknown":
            continue
        if f == "seating" and status == "unknown":
            continue
        fl = tr(FEAT_T, f)
        Fl = fl[:1].upper() + fl[1:]
        if status == "yes":
            out.append(("yes", R["feat_yes"][LANG].format(f=fl, F=Fl)))
        elif status == "no":
            out.append(("no", R["feat_no"][LANG].format(f=fl, F=Fl)))
        else:
            out.append(("unk", R["feat_unk"][LANG].format(f=fl, F=Fl)))
    if r["hearing_loop"] == "yes":
        out.append(("yes", R["loop_yes"][LANG]))
    elif r["hearing_loop"] == "no":
        out.append(("no", R["loop_no"][LANG]))

    d_conf, d_use = r.get("dist_confirmed_stop_m"), r.get("dist_usable_stop_m")
    if pd.notna(d_conf) and d_conf <= 800:
        out.append(("yes", R["stop_conf"][LANG].format(d=dist_txt(d_conf))))
    elif pd.notna(d_use) and d_use <= 800:
        out.append(("yes", R["stop_any"][LANG].format(d=dist_txt(d_use))))
    elif pd.notna(d_use):
        out.append(("no", R["stop_far"][LANG].format(d=dist_txt(d_use))))
    out.append(("yes", R["para_in"][LANG]) if r["in_paratransit"] else ("no", R["para_out"][LANG]))
    if r["source"] == "OpenStreetMap":
        return out
    if not r["hours_known"]:
        out.append(("unk", R["hours_unk"][LANG]))
    else:
        out.append(("yes", R["eve_yes"][LANG]) if r["open_evening"] else ("no", R["eve_no"][LANG]))
        out.append(("yes", R["wkd_yes"][LANG]) if r["open_weekend"] else ("no", R["wkd_no"][LANG]))
    return out


def plain_summary(r):
    if r["source"] == "OpenStreetMap":
        parts = [R[{"yes": "ps_yes", "limited": "ps_lim", "no": "ps_no"}.get(r["entrance"], "ps_unk")][LANG]]
        if r["trail"] == "yes":
            parts.append(R["ps_trail"][LANG])
        if r["toilet"] == "yes":
            parts.append(R["ps_wc"][LANG])
        d = r.get("dist_usable_stop_m")
        if pd.notna(d):
            parts.append(R["s_transit"][LANG].format(m=max(1, int(round(d / 75)))) if d <= 1600
                         else R["s_transit_far"][LANG].format(km=f"{d / 1000:.1f}"))
        parts.append(R["ps_check"][LANG])
        return " ".join(parts)
    parts = [R[{"yes": "s_ent_yes", "no": "s_ent_no"}.get(r["entrance"], "s_ent_unk")][LANG]]
    if r["group"] in TOILET_GROUPS:
        parts.append(R["s_wc_yes" if r["toilet"] == "yes" else "s_wc_unk"][LANG])
    d = r.get("dist_usable_stop_m")
    if pd.notna(d):
        if d <= 1600:
            parts.append(R["s_transit"][LANG].format(m=max(1, int(round(d / 75)))))
        else:
            parts.append(R["s_transit_far"][LANG].format(km=f"{d / 1000:.1f}"))
    parts.append(R["s_call"][LANG])
    return " ".join(parts)


def pill(b):
    bg, fg = BAND_PILL[b]
    return (f"<span class='ab-pill' style='background:{bg};color:{fg}'>{html.escape(tr(BAND_T, b))}</span>")


def stars_txt(n):
    try:
        n = int(round(float(n)))
    except (TypeError, ValueError):
        return "", ""
    n = max(0, min(5, n))
    return "★" * n + "☆" * (5 - n), t("stars", n=n)


def show_reviews(r):
    raw = r.get("review_samples")
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or raw == "":
        return
    try:
        items = json.loads(raw)
    except Exception:
        return
    if not items:
        return
    st.markdown(f"**{t('reviews_title')}**")
    blocks = []
    for it in items:
        stars, sr = stars_txt(it.get("stars"))
        tag = f" · {t('mentions_access')}" if it.get("access") else ""
        blocks.append(
            f"<div class='ab-review'><span aria-hidden='true' class='ab-stars'>{stars}</span>"
            f"<span class='sr-only'>{html.escape(sr)}</span>"
            f"<span class='ab-tag'>{html.escape(tag)}</span><br/>{html.escape(str(it.get('text', '')))}</div>")
    st.markdown("".join(blocks), unsafe_allow_html=True)
    st.caption(t("reviews_cap"))


def show_reports(r):
    if not COMMUNITY_FORM_PREFILL and not COMMUNITY_SHEET_CSV:
        return
    st.markdown(f"**{t('reports_title')}**")
    rep = load_reports(COMMUNITY_SHEET_CSV)
    pid_col = next((c for c in rep.columns if "place id" in c.lower()), None) if not rep.empty else None
    mine = rep[rep[pid_col].astype(str) == str(r["place_id"])] if pid_col else pd.DataFrame()
    if mine.empty:
        st.caption(t("reports_none"))
    else:
        skip = {pid_col} | {c for c in mine.columns if "place name" in c.lower()}
        for _, row in mine.tail(3).iloc[::-1].iterrows():
            bits = [f"**{html.escape(str(c))}:** {html.escape(str(v))}" for c, v in row.items()
                    if c not in skip and pd.notna(v) and str(v).strip()]
            st.markdown("<div class='ab-review'>" + "<br/>".join(bits) + "</div>", unsafe_allow_html=True)
    if COMMUNITY_FORM_PREFILL:
        link = COMMUNITY_FORM_PREFILL.format(place_id=urllib.parse.quote(str(r["place_id"])),
                                             name=urllib.parse.quote(str(r["name"])))
        st.link_button(t("report_link"), link)
    st.caption(t("reports_note"))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("AccessBay")
lang_name = st.sidebar.selectbox("Language / Idioma / 语言", list(LANGS.keys()))
LANG = LANGS[lang_name]
st.sidebar.caption(t("subtitle"))

with st.sidebar.expander(t("display")):
    large = st.checkbox(t("large_text"))
    contrast = st.checkbox(t("high_contrast"))

with st.sidebar.expander(t("howto_title"), expanded=True):
    st.markdown(t("howto_body"))

# ---------------------------------------------------------------------------
# Styles (base + optional larger text / high contrast)
# ---------------------------------------------------------------------------
css = """
<style>
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
*:focus-visible{outline:3px solid #0B5CAD !important;outline-offset:2px}
.ab-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:6px 0 14px}
.ab-card{background:rgba(127,127,127,0.06);border-radius:10px;padding:10px 14px}
.ab-label{font-size:0.9rem;color:#444;line-height:1.3;white-space:normal}
.ab-value{font-size:1.9rem;font-weight:600;line-height:1.25;margin-top:2px}
.ab-help{font-size:0.8rem;color:#555;margin-top:4px;line-height:1.3}
.ab-pill{display:inline-block;padding:4px 12px;border-radius:14px;font-weight:600}
.ab-reason{margin:3px 0;line-height:1.45}
.ab-sym{display:inline-block;width:1.3em;font-weight:700}
.ab-yes .ab-sym{color:#0B5CAD}.ab-no .ab-sym{color:#B00D4B}.ab-unk .ab-sym{color:#5F5F5F}
.ab-review{border-left:3px solid #bbb;padding:4px 12px;margin:6px 0;line-height:1.45}
.ab-stars{color:#8a6d00}.ab-tag{color:#555;font-size:0.85em}
.ab-summary{background:rgba(11,92,173,0.08);border-radius:8px;padding:10px 14px;margin:8px 0;line-height:1.5}
</style>
"""
if large:
    css += """<style>
.stApp p,.stApp li,.stApp label,.stApp .ab-reason,.stApp .ab-review,.stApp .ab-summary,
.stApp [data-testid="stMarkdownContainer"]{font-size:1.25rem !important;line-height:1.6 !important}
.stApp .ab-label{font-size:1.1rem !important}.stApp .ab-value{font-size:2.3rem !important}
</style>"""
if contrast:
    css += """<style>
.stApp,.stApp [data-testid="stSidebar"]{background:#FFFFFF !important}
.stApp p,.stApp li,.stApp label,.stApp span,.stApp div,.stApp h1,.stApp h2,.stApp h3,.stApp small,
.stApp [data-testid="stCaptionContainer"]{color:#000000 !important}
.stApp a{color:#0033CC !important;text-decoration:underline !important}
.ab-card{background:#FFFFFF !important;border:2px solid #000 !important}
.ab-review{border-left:4px solid #000 !important}
.ab-summary{background:#FFFFFF !important;border:2px solid #000 !important}
.ab-pill{border:2px solid #000}
</style>"""
st.markdown(css, unsafe_allow_html=True)

places = load_places(os.path.getmtime("data/places_app.parquet"))

# ---------------------------------------------------------------------------
# Sidebar filters + personalize
# ---------------------------------------------------------------------------
st.sidebar.subheader(t("filters"))
counties = sorted(c for c in places["county"].cat.categories if c)
groups = sorted(g for g in places["group"].cat.categories if g)
sel_counties = st.sidebar.multiselect(t("county"), counties, placeholder=t("all_counties"))
sel_groups = st.sidebar.multiselect(t("type"), groups, placeholder=t("all_types"),
                                    format_func=lambda g: tr(GROUP_T, g))
sel_bands = st.sidebar.multiselect(t("rating"), BAND_ORDER, placeholder=t("all_ratings"),
                                   format_func=lambda b: tr(BAND_T, b))
min_score = st.sidebar.slider(t("min_score"), 0.0, 10.0, 0.0, 0.5)

with st.sidebar.expander(t("personalize")):
    st.caption(t("personalize_cap"))
    w_phys = st.slider(t("w_phys"), 0, 10, 5)
    w_transit = st.slider(t("w_transit"), 0, 10, 3)
    w_para = st.slider(t("w_para"), 0, 10, 1)
    w_hours = st.slider(t("w_hours"), 0, 10, 1)

DEFAULT_W = (5, 3, 1, 1)
if w_phys + w_transit + w_para + w_hours == 0:
    st.sidebar.warning(t("zero_w"))
    w_phys, w_transit, w_para, w_hours = DEFAULT_W
personalized = (w_phys, w_transit, w_para, w_hours) != DEFAULT_W

score = places["score"]
match = rescore(places, w_phys, w_transit, w_hours, w_para) if personalized else score

mask = np.ones(len(places), dtype=bool)
if sel_counties:
    mask = mask & places["county"].isin(sel_counties).to_numpy()
if sel_groups:
    mask = mask & places["group"].isin(sel_groups).to_numpy()
if sel_bands:
    mask = mask & places["band_now"].isin(sel_bands).to_numpy()
if min_score > 0:
    mask = mask & (score >= min_score).to_numpy()
n_view = int(mask.sum())

st.sidebar.markdown(t("n_match", n=f"{n_view:,}"))
if personalized:
    st.sidebar.caption(t("ranking_personal"))

# ---------------------------------------------------------------------------
# Header + tabs
# ---------------------------------------------------------------------------
st.title("AccessBay")
st.markdown(t("intro"))

tab_find, tab_map, tab_hood, tab_dm, tab_about = st.tabs(
    [t("tab_find"), t("tab_map"), t("tab_hood"), t("tab_dm"), t("tab_about")])

# ---------------------------------------------------------------------------
# Find a place
# ---------------------------------------------------------------------------
with tab_find:
    q = st.text_input(t("search_label"), placeholder=t("search_ph"))
    m_find = mask.copy()
    if q.strip():
        st_text = places["search_text"]
        for word in q.lower().split():
            m_find = m_find & st_text.str.contains(word, regex=False).to_numpy()
    idx = np.flatnonzero(m_find)
    n_hits = len(idx)
    order = np.lexsort((-places["reviews_count"].values[idx],
                        -np.nan_to_num(match.values[idx], nan=-1)))
    MAX_ROWS = 200
    top = idx[order[:MAX_ROWS]]
    shown = places.loc[top, ["name", "category", "city", "score", "band_now"]].copy()
    shown["match"] = match.values[top]

    if shown.empty:
        st.warning(t("no_match"))
    else:
        head = t("res_query", n=f"{n_hits:,}", q=q.strip()) if q.strip() else t("res_filters", n=f"{n_hits:,}")
        if n_hits > MAX_ROWS:
            head += t("res_top", k=MAX_ROWS)
        st.markdown(head + t("res_click"))

        table = pd.DataFrame({
            t("col_name"): shown["name"],
            t("col_type"): shown["category"],
            t("col_city"): shown["city"],
            t("col_score"): shown["score"],
            t("col_rating"): shown["band_now"].astype(str).map(lambda b: f"{BAND_ICONS[b]} {tr(BAND_T, b)}"),
        })
        if personalized:
            table.insert(3, t("col_match"), shown["match"])
        event = st.dataframe(
            table, hide_index=True, width="stretch", height=300,
            on_select="rerun", selection_mode="single-row", key="results",
            column_config={t("col_score"): st.column_config.NumberColumn(format="%.1f"),
                           t("col_match"): st.column_config.NumberColumn(format="%.1f")},
        )
        rows = event.selection.rows if event is not None else []
        if not rows:
            st.info(t("click_hint"))
        else:
            r = places.loc[shown.index[rows[0]]].copy()
            r["match"] = match.loc[shown.index[rows[0]]]
            st.divider()
            left, right = st.columns([3, 2])
            with left:
                st.subheader(r["name"])
                st.caption(f"{r['category']} · {r['address'].replace(', United States', '')}")
                if r["source"] == "OpenStreetMap":
                    st.caption(t("osm_source"))
                st.markdown(f"{pill(r['band_now'])}&nbsp;&nbsp;{t('confidence')}: "
                            f"<b>{html.escape(tr(CONF_T, r['confidence']))}</b>", unsafe_allow_html=True)

                cards = [(t("col_score"), "—" if pd.isna(r["score"]) else f"{r['score']:.1f} / 10", None)]
                if personalized:
                    cards.append((t("col_match"), "—" if pd.isna(r["match"]) else f"{r['match']:.1f} / 10",
                                  t("match_help")))
                stat_cards(cards)

                st.markdown(f"<div class='ab-summary'><b>{t('in_short')}:</b> "
                            f"{html.escape(plain_summary(r))}</div>", unsafe_allow_html=True)

                st.markdown(f"**{t('why')}**")
                st.markdown("".join(reason_line(k, txt) for k, txt in build_reasons(r)), unsafe_allow_html=True)

                st.markdown(f"**{t('breakdown')}**")
                stat_cards([
                    (t("b_phys"), "—" if pd.isna(r["physical_score"]) else f"{r['physical_score']:.1f} / 5", None),
                    (t("b_transit"), f"{r['transit_score']:.1f} / 3", None),
                    (t("b_para"), f"{r['paratransit_pt']:.1f} / 1", None),
                ] + ([] if r["source"] == "OpenStreetMap" else [
                    (t("b_hours"), f"{r['hours_score']:.1f} / 1" if r["hours_known"] else t("not_listed"), None)]))

                if pd.notna(r.get("priority_tract")) and bool(r.get("priority_tract")):
                    st.warning(t("priority_warn"))

                links = []
                if pd.notna(r.get("open_website")) and str(r.get("open_website")).startswith("http"):
                    links.append(f"[{t('website')}]({r['open_website']})")
                if links:
                    st.markdown(" · ".join(links))
                if pd.notna(r.get("phone_number")):
                    st.caption(t("phone", p=r["phone_number"]))

                show_reviews(r)
                show_reports(r)

                st.markdown(f"**{t('fix_title')}**")
                if r["source"] == "OpenStreetMap" and isinstance(r.get("osm_url"), str):
                    st.link_button(t("osm_link"), r["osm_url"])
                    st.caption(t("osm_note"))
                else:
                    gmaps = f"https://www.google.com/maps/place/?q=place_id:{urllib.parse.quote(str(r['place_id']))}"
                    st.link_button(t("fix_link"), gmaps)
                    st.caption(t("fix_note"))

            with right:
                d = haversine_m(r["lat"], r["lon"], places["lat"].values, places["lon"].values)
                same = (places["group"] == r["group"]).values & (d <= 3000) & (d > 0) & (score.values >= 8)
                alt = places.loc[same, ["name", "score", "lat", "lon"]].copy()
                alt["dist_m"] = d[same]
                alt = alt.sort_values(["score", "dist_m"], ascending=[False, True]).head(5)

                pts = pd.DataFrame([{"lat": float(r["lat"]), "lon": float(r["lon"]), "name": r["name"],
                                     "color": [0, 0, 0], "radius": 60}])
                if not alt.empty:
                    pts = pd.concat([pts, alt.assign(color=[BAND_MAP_COLORS["Highly accessible"]] * len(alt),
                                                     radius=40)[["lat", "lon", "name", "color", "radius"]]])
                st.pydeck_chart(pdk.Deck(
                    map_provider="carto", map_style="light",
                    initial_view_state=pdk.ViewState(latitude=float(r["lat"]), longitude=float(r["lon"]), zoom=13),
                    layers=[pdk.Layer("ScatterplotLayer", pts, get_position="[lon, lat]",
                                      get_fill_color="color", get_radius="radius", pickable=True)],
                    tooltip={"text": "{name}"},
                ), height=320)
                st.caption(t("alt_caption"))

                st.markdown(f"**{t('alt_title', g=tr(GROUP_T, r['group']).lower() if LANG != 'zh' else tr(GROUP_T, r['group']))}**")
                if alt.empty:
                    st.caption(t("alt_none"))
                else:
                    for _, a in alt.iterrows():
                        st.markdown(f"- **{a['name']}** · {a['score']:.1f}/10 · {dist_txt(a['dist_m'])}")

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
with tab_map:
    MAX_POINTS = 25_000
    midx = np.flatnonzero(mask)
    total = len(midx)
    if total > MAX_POINTS:
        st.caption(t("map_sample", k=f"{MAX_POINTS:,}", n=f"{total:,}"))
        midx = np.random.default_rng(0).choice(midx, MAX_POINTS, replace=False)
    m = places.loc[midx, ["lat", "lon", "name", "band_now", "score"]].copy()
    m["band_now"] = m["band_now"].astype(str)
    m["color"] = m["band_now"].map(BAND_MAP_COLORS)
    m["band_txt"] = m["band_now"].map(lambda b: tr(BAND_T, b))
    m["score_txt"] = m["score"].apply(lambda s: "—" if pd.isna(s) else f"{s:.1f}/10")

    st.pydeck_chart(pdk.Deck(
        map_provider="carto", map_style="light",
        initial_view_state=pdk.ViewState(latitude=37.75, longitude=-122.2, zoom=8.5),
        layers=[pdk.Layer("ScatterplotLayer", m, get_position="[lon, lat]", get_fill_color="color",
                          get_radius=60, radius_min_pixels=2, radius_max_pixels=8, pickable=True, opacity=0.8)],
        tooltip={"html": "<b>{name}</b><br/>{band_txt}: {score_txt}"},
    ), height=600)

    shares = places.loc[mask, "band_now"].astype(str).value_counts(normalize=True).reindex(BAND_ORDER).fillna(0)
    stat_cards([(f"{BAND_ICONS[b]} {tr(BAND_T, b)}", f"{s:.0%}", None) for b, s in shares.items()])
    parts = "; ".join(f"{tr(BAND_T, b)}: {s:.0%}" for b, s in shares.items())
    st.markdown(t("map_alt", n=f"{total:,}", parts=parts))

# ---------------------------------------------------------------------------
# Neighborhoods
# ---------------------------------------------------------------------------
props = pd.DataFrame()
try:
    gj = styled_tracts(os.path.getmtime("data/tracts_app.geojson"), LANG)
    props = pd.DataFrame([f["properties"] for f in gj["features"]])
except FileNotFoundError:
    gj = None

with tab_hood:
    st.subheader(t("hood_title"))
    stat_cards([
        (t("k_priority"), FINDINGS["priority_tracts"], t("k_priority_help")),
        (t("k_disabled"), FINDINGS["priority_disabled"], None),
        (t("k_pharm"), FINDINGS["pharmacy_desert_disabled"], t("k_pharm_help")),
        (t("k_para"), FINDINGS["outside_paratransit"], None),
    ])
    if gj is None:
        st.error(t("data_missing", f="data/tracts_app.geojson"))
    else:
        st.pydeck_chart(pdk.Deck(
            map_provider="carto", map_style="light",
            initial_view_state=pdk.ViewState(latitude=37.8, longitude=-122.2, zoom=8.3),
            layers=[pdk.Layer("GeoJsonLayer", gj, get_fill_color="properties.fill",
                              get_line_color="properties.line", get_line_width="properties.line_w",
                              line_width_min_pixels=1, pickable=True, stroked=True, filled=True)],
            tooltip={"html": f"<b>{{county}}</b><br/>{t('col_share')}: {{pct_txt}}"
                             f"<br/>{t('k_priority')}: {{priority_txt}}"},
        ), height=600)
        st.caption(t("hood_cap"))

        pr = props[props["priority_tract"] == True]
        by_county = (pr.groupby("county")
                     .agg(n=("GEOID", "count"), dis=("pop_disabled", "sum"))
                     .sort_values("n", ascending=False).reset_index())
        top = ", ".join(by_county["county"].head(2).tolist())
        st.markdown(t("hood_alt", n=len(pr), top=top))

        st.markdown(f"**{t('by_county')}**")
        st.dataframe(
            by_county.rename(columns={"county": t("col_county"), "n": t("col_tracts"), "dis": t("col_dis_res")}),
            hide_index=True, width="stretch",
            column_config={t("col_tracts"): st.column_config.NumberColumn(format="localized"),
                           t("col_dis_res"): st.column_config.NumberColumn(format="localized")},
        )

    st.markdown(f"**{t('found_title')}**")
    st.markdown(t("found_body", mh=FINDINGS["mental_health_unknown"], hc=FINDINGS["health_care_unknown"]))

# ---------------------------------------------------------------------------
# For decision-makers
# ---------------------------------------------------------------------------
GROUP_PRIORITY = ["Mental health", "Gov & social services", "Health care", "Pharmacy", "Food",
                  "Education & child care", "Financial"]


@st.cache_data(max_entries=4)
def outreach_csv(mtime, counties_sel, groups_sel, lang):
    return outreach_table(mtime, counties_sel, groups_sel, lang).to_csv(index=False).encode("utf-8-sig")


@st.cache_data(max_entries=6)
def outreach_table(mtime, counties_sel, groups_sel, lang):
    p = load_places(mtime)
    keep = (~p["group"].isin(["Recreation", "Parks & outdoors"])).to_numpy() & (p["confidence"] != "Confirmed").to_numpy()
    if counties_sel:
        keep = keep & p["county"].isin(counties_sel).to_numpy()
    if groups_sel:
        keep = keep & p["group"].isin(groups_sel).to_numpy()
    out = p.loc[keep, ["name", "group", "category", "county", "address", "phone_number", "open_website",
                       "entrance", "parking", "toilet"]]
    grp = out["group"].astype(str)
    parts = []
    for f in ["entrance", "parking", "toilet"]:
        need = (out[f].astype(str) == "unknown").to_numpy(copy=True)
        if f == "toilet":
            need = need & grp.isin(TOILET_GROUPS).to_numpy()
        parts.append(np.where(need, FEAT_T[f][lang], ""))
    missing = [", ".join(x for x in trio if x) for trio in zip(*parts)]
    rank = grp.map({g: i for i, g in enumerate(GROUP_PRIORITY)}).fillna(99).values
    tbl = pd.DataFrame({
        T["col_name"][lang]: out["name"].values,
        T["col_group"][lang]: [GROUP_T.get(g, {}).get(lang, g) for g in grp],
        T["col_type"][lang]: out["category"].astype(str).values,
        T["col_county"][lang]: out["county"].astype(str).values,
        T["col_address"][lang]: out["address"].str.replace(", United States", "", regex=False).values,
        T["col_phone"][lang]: out["phone_number"].values,
        T["col_website"][lang]: out["open_website"].values,
        T["col_missing"][lang]: missing,
        "_rank": rank,
    })
    tbl = tbl.sort_values(["_rank", T["col_county"][lang], T["col_name"][lang]]).drop(columns="_rank")
    return tbl.reset_index(drop=True)


with tab_dm:
    st.subheader(t("dm_title"))
    st.markdown(t("dm_intro"))
    st.markdown(f"**{t('dm_recs_title')}**")
    st.markdown(t("dm_recs"))

    # Priority neighborhoods
    st.markdown(f"### {t('dm_tracts_title')}")
    if not props.empty:
        pr = props[props["priority_tract"] == True].copy()
        if sel_counties:
            pr = pr[pr["county"].isin(sel_counties)]
        cols = {"GEOID": t("col_tract"), "county": t("col_county")}
        if "main_city" in pr.columns:
            cols["main_city"] = t("col_main_city")
        cols.update({"setting": t("col_setting"), "pop_disabled": t("col_dis_res"),
                     "pct_disabled": t("col_share"), "acc_nearby": t("col_acc_near")})
        if "dist_acc_pharmacy_m" in pr.columns:
            pr["dist_acc_pharmacy_m"] = (pr["dist_acc_pharmacy_m"] / 1000).round(1)
            cols["dist_acc_pharmacy_m"] = t("col_pharm_km")
        if "dist_acc_food_m" in pr.columns:
            pr["dist_acc_food_m"] = (pr["dist_acc_food_m"] / 1000).round(1)
            cols["dist_acc_food_m"] = t("col_food_km")
        tract_tbl = (pr.sort_values("pop_disabled", ascending=False)[list(cols)]
                     .rename(columns=cols))
        st.caption(t("dm_tracts_cap"))
        st.dataframe(tract_tbl, hide_index=True, width="stretch", height=300,
                     column_config={t("col_dis_res"): st.column_config.NumberColumn(format="localized"),
                                    t("col_share"): st.column_config.NumberColumn(format="%.1f")})
        st.download_button(t("dm_dl_tracts"), tract_tbl.to_csv(index=False).encode("utf-8-sig"),
                           file_name="accessbay_priority_neighborhoods.csv", mime="text/csv")

    # Outreach list
    st.markdown(f"### {t('dm_out_title')}")
    out_tbl = outreach_table(os.path.getmtime("data/places_app.parquet"), tuple(sel_counties), tuple(sel_groups), LANG)
    SHOW = 300
    st.caption(t("dm_out_cap", n=f"{len(out_tbl):,}", k=min(SHOW, len(out_tbl))))
    st.dataframe(out_tbl.head(SHOW), hide_index=True, width="stretch", height=320,
                 column_config={t("col_website"): st.column_config.LinkColumn()})
    st.download_button(t("dm_dl_out"), outreach_csv(os.path.getmtime("data/places_app.parquet"),
                                                    tuple(sel_counties), tuple(sel_groups), LANG),
                       file_name="accessbay_outreach_list.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# How it works
# ---------------------------------------------------------------------------
with tab_about:
    st.subheader(t("about_score_title"))
    st.markdown(t("about_score"))
    st.subheader(t("sources_title"))
    st.markdown(t("sources"))
    st.subheader(t("limits_title"))
    st.markdown(t("limits"))
    st.subheader(t("a11y_title"))
    st.markdown(t("a11y"))
    st.caption(t("footer"))
