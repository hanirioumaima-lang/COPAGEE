# -*- coding: utf-8 -*-
"""
COPAG — Tableau de bord Logistique & Transport
Application Streamlit : nettoyage, KPI, visualisations, filtres, connexion.
Lancement :  streamlit run app.py
"""
import hashlib
import hmac
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------
DATA_PATH = Path(__file__).parent / "dataset.csv"

# Le code d'accès n'est pas stocké en clair : on compare des empreintes SHA-256.
CODE_HASH = hashlib.sha256("MIMA123@@".encode("utf-8")).hexdigest()

VERT_FONCE, VERT, VERT_CLAIR, VERT_PALE = "#1B5E20", "#2E7D32", "#66BB6A", "#C8E6C9"
PALETTE = ["#1B5E20", "#2E7D32", "#43A047", "#66BB6A", "#81C784", "#A5D6A7", "#C8E6C9"]

st.set_page_config(
    page_title="COPAG — Logistique & Transport",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = f"""
<style>
#MainMenu, footer {{visibility: hidden;}}
.block-container {{padding-top: 1.5rem; max-width: 1400px;}}
.bandeau {{
    background: linear-gradient(120deg, {VERT_FONCE} 0%, {VERT} 60%, {VERT_CLAIR} 100%);
    color: white; padding: 1.4rem 1.8rem; border-radius: 16px; margin-bottom: 1.2rem;
    box-shadow: 0 4px 14px rgba(27,94,32,.25);
}}
.bandeau h1 {{color: white; margin: 0; font-size: 1.9rem;}}
.bandeau p {{margin: .2rem 0 0 0; opacity: .92;}}
div[data-testid="stMetric"] {{
    background: #F1F8F2; border: 1px solid {VERT_PALE}; border-left: 6px solid {VERT};
    padding: .9rem 1rem; border-radius: 12px;
}}
div[data-testid="stMetricLabel"] p {{color: {VERT_FONCE}; font-weight: 600;}}
div[data-testid="stMetricValue"] {{color: {VERT_FONCE};}}
section[data-testid="stSidebar"] {{background: #E8F5E9; border-right: 1px solid {VERT_PALE};}}
.stTabs [data-baseweb="tab-list"] {{gap: 6px;}}
.stTabs [data-baseweb="tab"] {{background: #F1F8F2; border-radius: 10px 10px 0 0; padding: 8px 18px;}}
.stTabs [aria-selected="true"] {{background: {VERT}; color: white !important;}}
.stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {{
    background: {VERT}; color: white; border: none; border-radius: 10px; font-weight: 600;
}}
.stButton > button:hover, .stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {{background: {VERT_FONCE}; color: white;}}
.carte-info {{
    background: #F1F8F2; border-left: 6px solid {VERT}; padding: .8rem 1rem;
    border-radius: 10px; margin-bottom: .6rem;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# CONNEXION
# ----------------------------------------------------------------------------
def verifier_code(saisie: str) -> bool:
    empreinte = hashlib.sha256(saisie.encode("utf-8")).hexdigest()
    return hmac.compare_digest(empreinte, CODE_HASH)


def page_connexion():
    _, centre, _ = st.columns([1, 1.2, 1])
    with centre:
        st.markdown(
            '<div class="bandeau" style="text-align:center">'
            "<h1>🚚 COPAG</h1><p>Logistique & Transport — Espace sécurisé</p></div>",
            unsafe_allow_html=True,
        )
        with st.form("formulaire_connexion"):
            code = st.text_input("Code d'accès", type="password", placeholder="Saisissez votre code")
            valider = st.form_submit_button("Se connecter")
        if valider:
            if verifier_code(code):
                st.session_state["connecte"] = True
                st.rerun()
            else:
                st.error("Code d'accès incorrect. Veuillez réessayer.")


# ----------------------------------------------------------------------------
# NETTOYAGE DES DONNÉES
# ----------------------------------------------------------------------------
VITESSE_MAX_KMH = 120

COLONNES_NUM = [
    "o_lat", "o_lon", "d_lat", "d_lon", "distance_km", "planned_duration_min",
    "actual_duration_min", "delay_min", "on_time", "temperature_breach",
    "capacity_utilization", "fuel_liters", "co2_kg", "cost_mad", "quantity_tons",
    "lat", "lon",
]
COLONNES_TEXTE = [
    "shipment_id", "origin_hub", "origin_region", "destination_city",
    "destination_region", "mode", "product_category", "temperature_req",
]


def nettoyer(brut: pd.DataFrame):
    """Nettoie le jeu de données et renvoie (df_propre, rapport)."""
    rapport = {"lignes_initiales": len(brut), "etapes": []}
    df = brut.copy()

    def log(nom, nb, detail=""):
        rapport["etapes"].append({"Étape": nom, "Lignes concernées": int(nb), "Détail": detail})

    # 1. Espaces parasites dans les textes
    for c in COLONNES_TEXTE:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    log("Suppression des espaces parasites", 0, "Colonnes texte normalisées")

    # 2. Doublons
    n = df.duplicated().sum() + df.duplicated(subset="shipment_id").sum()
    df = df.drop_duplicates().drop_duplicates(subset="shipment_id")
    log("Suppression des doublons", n, "Doublons complets et identifiants répétés")

    # 3. Types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in COLONNES_NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    log("Conversion des types", 0, "Dates en datetime, colonnes numériques en nombres")

    # 4. Valeurs manquantes
    manquantes = df[["date"] + COLONNES_NUM].isna().any(axis=1).sum()
    df = df.dropna(subset=["date"] + COLONNES_NUM)
    log("Suppression des valeurs manquantes", manquantes, "Lignes incomplètes retirées")

    # 5. Valeurs impossibles
    invalide = (
        (df["distance_km"] <= 0) | (df["cost_mad"] <= 0) | (df["actual_duration_min"] <= 0)
        | (df["planned_duration_min"] <= 0) | (df["fuel_liters"] < 0) | (df["co2_kg"] < 0)
        | (df["quantity_tons"] <= 0)
    )
    df = df[~invalide]
    log("Suppression des valeurs impossibles", invalide.sum(), "Distances, durées, coûts ≤ 0")

    # 5 bis. Vitesses irréalistes pour un camion (> 120 km/h)
    vitesse = df["distance_km"] / (df["actual_duration_min"] / 60)
    trop_rapide = vitesse > VITESSE_MAX_KMH
    df = df[~trop_rapide]
    log("Suppression des vitesses irréalistes", trop_rapide.sum(),
        f"Vitesse moyenne > {VITESSE_MAX_KMH} km/h (durées réelles incohérentes)")

    # 6. Bornes de cohérence
    hors = (df["capacity_utilization"] > 1) | (df["capacity_utilization"] < 0)
    df["capacity_utilization"] = df["capacity_utilization"].clip(0, 1)
    df["on_time"] = df["on_time"].round().clip(0, 1).astype(int)
    df["temperature_breach"] = df["temperature_breach"].round().clip(0, 1).astype(int)
    log("Correction des taux et indicateurs", hors.sum(), "Capacité bornée entre 0 et 1, indicateurs 0/1")

    # 7. Variables dérivées
    df["vitesse_kmh"] = df["distance_km"] / (df["actual_duration_min"] / 60)
    df["cost_per_km"] = df["cost_mad"] / df["distance_km"]
    df["fuel_per_100km"] = df["fuel_liters"] / df["distance_km"] * 100
    df["lane"] = df["origin_hub"] + " → " + df["destination_city"]
    df["mois"] = df["date"].dt.to_period("M").dt.to_timestamp()
    log("Création de variables", 0, "vitesse_kmh, cost_per_km, fuel_per_100km, lane, mois")

    # 8. Valeurs atypiques (signalées, non supprimées : longues distances réelles)
    atypiques = {}
    for c in ["cost_mad", "fuel_liters", "co2_kg", "vitesse_kmh", "delay_min"]:
        q1, q3 = df[c].quantile([0.25, 0.75])
        iqr = q3 - q1
        atypiques[c] = int(((df[c] < q1 - 1.5 * iqr) | (df[c] > q3 + 1.5 * iqr)).sum())
    rapport["atypiques"] = atypiques

    df = df.sort_values("date").reset_index(drop=True)
    rapport["lignes_finales"] = len(df)
    return df, rapport


@st.cache_data(show_spinner="Chargement et nettoyage des données…")
def charger_donnees():
    brut = pd.read_csv(DATA_PATH)
    propre, rapport = nettoyer(brut)
    return brut, propre, rapport


# ----------------------------------------------------------------------------
# GRAPHIQUES (Matplotlib)
# ----------------------------------------------------------------------------
def nouvelle_figure(titre, xlabel="", ylabel="", taille=(6.4, 4.2)):
    fig, ax = plt.subplots(figsize=taille)
    ax.set_title(titre, fontsize=12, fontweight="bold", color=VERT_FONCE, loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    return fig, ax


def afficher(fig):
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def g_ponctualite(df):
    fig, ax = nouvelle_figure("Ponctualité quotidienne", "Date", "Taux à l'heure (%)")
    j = df.groupby("date")["on_time"].mean().mul(100)
    ax.plot(j.index, j.values, color=VERT_PALE, linewidth=0.8, label="Quotidien")
    ax.plot(j.index, j.rolling(14, min_periods=1).mean(), color=VERT_FONCE, linewidth=2.2,
            label="Moyenne mobile 14 j")
    ax.set_ylim(-5, 105)
    ax.legend(frameon=False, fontsize=8)
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    afficher(fig)


def g_top_routes(df):
    fig, ax = nouvelle_figure("Top 10 des routes par volume", "Nombre d'expéditions", "")
    t = df["lane"].value_counts().head(10).iloc[::-1]
    ax.barh(t.index, t.values, color=VERT)
    for i, v in enumerate(t.values):
        ax.text(v, i, f" {v}", va="center", fontsize=8)
    ax.grid(axis="y", visible=False)
    afficher(fig)


def g_boxplot_retards(df):
    fig, ax = nouvelle_figure("Retards par catégorie de produit", "Retard (minutes)", "")
    ordre = df.groupby("product_category")["delay_min"].median().sort_values().index.tolist()
    donnees = [df.loc[df["product_category"] == p, "delay_min"] for p in ordre]
    bp = ax.boxplot(donnees, vert=False, patch_artist=True,
                    medianprops={"color": VERT_FONCE, "linewidth": 2})
    for patch, c in zip(bp["boxes"], PALETTE):
        patch.set_facecolor(c)
        patch.set_alpha(0.85)
    ax.set_yticks(range(1, len(ordre) + 1))
    ax.set_yticklabels(ordre)
    afficher(fig)


def g_correlation(df):
    cols = ["distance_km", "delay_min", "on_time", "temperature_breach", "capacity_utilization",
            "fuel_liters", "co2_kg", "cost_mad", "quantity_tons", "vitesse_kmh"]
    corr = df[cols].corr()
    fig, ax = nouvelle_figure("Matrice de corrélation", taille=(6.4, 5))
    ax.grid(False)
    im = ax.imshow(corr.values, cmap="Greens", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(cols, fontsize=8)
    for i in range(len(cols)):
        for j in range(len(cols)):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                    color="white" if v > 0.6 else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    afficher(fig)


def g_cout_km_region(df):
    fig, ax = nouvelle_figure("Coût moyen par km selon la région", "MAD / km", "")
    t = df.groupby("destination_region")["cost_per_km"].mean().sort_values()
    ax.barh(t.index, t.values, color=VERT)
    for i, v in enumerate(t.values):
        ax.text(v, i, f" {v:.1f}", va="center", fontsize=8)
    ax.grid(axis="y", visible=False)
    afficher(fig)


def g_camembert(df):
    fig, ax = nouvelle_figure("Répartition des expéditions par produit")
    t = df["product_category"].value_counts()
    ax.pie(t.values, labels=t.index, autopct="%1.1f%%", startangle=90,
           colors=PALETTE[: len(t)], wedgeprops={"edgecolor": "white"},
           textprops={"fontsize": 8})
    ax.axis("equal")
    ax.grid(False)
    afficher(fig)


def g_scatter(df, y, titre, ylabel):
    fig, ax = nouvelle_figure(titre, "Distance (km)", ylabel)
    ax.scatter(df["distance_km"], df[y], alpha=0.55, color=VERT, s=18, edgecolor="white", linewidth=0.3)
    if len(df) > 2:
        a, b = np.polyfit(df["distance_km"], df[y], 1)
        x = np.linspace(df["distance_km"].min(), df["distance_km"].max(), 50)
        ax.plot(x, a * x + b, color=VERT_FONCE, linewidth=2)
    afficher(fig)


def g_histogramme_retards(df):
    fig, ax = nouvelle_figure("Distribution des retards", "Retard (minutes)", "Expéditions")
    ax.hist(df["delay_min"], bins=30, color=VERT, edgecolor="white")
    ax.axvline(0, color=VERT_FONCE, linestyle="--", linewidth=1.5)
    afficher(fig)


def g_rupture_froid(df):
    fig, ax = nouvelle_figure("Rupture de la chaîne du froid par produit", "", "Taux de rupture (%)")
    t = df.groupby("product_category")["temperature_breach"].mean().mul(100).sort_values(ascending=False)
    ax.bar(t.index, t.values, color=VERT)
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    afficher(fig)


def g_capacite_mode(df):
    fig, ax = nouvelle_figure("Utilisation moyenne de la capacité par mode", "", "Capacité utilisée (%)")
    t = df.groupby("mode")["capacity_utilization"].mean().mul(100)
    ax.bar(t.index, t.values, color=[VERT_FONCE, VERT_CLAIR][: len(t)], width=0.5)
    for i, v in enumerate(t.values):
        ax.text(i, v, f"{v:.1f} %", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, 100)
    afficher(fig)


def g_retard_region(df):
    fig, ax = nouvelle_figure("Retard moyen par région", "Minutes", "")
    t = df.groupby("destination_region")["delay_min"].mean().sort_values()
    ax.barh(t.index, t.values, color=VERT)
    ax.grid(axis="y", visible=False)
    afficher(fig)


def g_cout_produit(df):
    fig, ax = nouvelle_figure("Coût moyen par catégorie de produit", "", "MAD")
    t = df.groupby("product_category")["cost_mad"].mean().sort_values(ascending=False)
    ax.bar(t.index, t.values, color=VERT)
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    afficher(fig)


def g_vitesse_mode(df):
    fig, ax = nouvelle_figure("Vitesse moyenne par hub d'origine", "", "km/h")
    t = df.groupby("origin_hub")["vitesse_kmh"].mean()
    ax.bar(t.index, t.values, color=VERT, width=0.5)
    for i, v in enumerate(t.values):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    afficher(fig)


# ----------------------------------------------------------------------------
# CARTES
# ----------------------------------------------------------------------------
def carte_flotte(df):
    st.map(df.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]],
           color="#2E7D32", size=4000)


def carte_flux(df):
    import pydeck as pdk
    flux = (df.groupby(["origin_hub", "destination_city", "o_lat", "o_lon", "d_lat", "d_lon"])
              .size().reset_index(name="count"))
    arcs = pdk.Layer(
        "ArcLayer", data=flux,
        get_source_position=["o_lon", "o_lat"], get_target_position=["d_lon", "d_lat"],
        get_source_color=[27, 94, 32, 200], get_target_color=[129, 199, 132, 200],
        get_width="1 + count / 6", pickable=True,
    )
    vue = pdk.ViewState(latitude=31.5, longitude=-7.0, zoom=4.3, pitch=30)
    st.pydeck_chart(pdk.Deck(
        layers=[arcs], initial_view_state=vue,
        tooltip={"text": "{origin_hub} → {destination_city}\n{count} expéditions"},
    ))


# ----------------------------------------------------------------------------
# INTERPRÉTATION AUTOMATIQUE
# ----------------------------------------------------------------------------
def interpretations(df):
    cout_region = df.groupby("destination_region")["cost_per_km"].mean()
    retard_prod = df.groupby("product_category")["delay_min"].mean()
    ponctualite_reg = df.groupby("destination_region")["on_time"].mean() * 100
    co2_route = df.groupby("lane")["co2_kg"].sum()
    rupture = df.groupby("product_category")["temperature_breach"].mean() * 100
    top_route = df["lane"].value_counts()
    corr_dist_cout = df["distance_km"].corr(df["cost_mad"])

    return [
        f"**Ponctualité** : {df['on_time'].mean()*100:.1f} % des livraisons arrivent à l'heure. "
        f"La région la moins ponctuelle est **{ponctualite_reg.idxmin()}** ({ponctualite_reg.min():.1f} %).",
        f"**Retards** : le produit le plus en retard en moyenne est **{retard_prod.idxmax()}** "
        f"({retard_prod.max():.1f} min), le plus régulier est **{retard_prod.idxmin()}** ({retard_prod.min():.1f} min).",
        f"**Coûts** : la région la plus chère au kilomètre est **{cout_region.idxmax()}** "
        f"({cout_region.max():.2f} MAD/km) contre {cout_region.min():.2f} MAD/km pour **{cout_region.idxmin()}**. "
        f"L'écart entre régions est de {(cout_region.max()/cout_region.min()-1)*100:.1f} %.",
        f"**Routes critiques** : la route la plus utilisée est **{top_route.index[0]}** "
        f"({top_route.iloc[0]} expéditions). La route la plus émettrice de CO₂ est **{co2_route.idxmax()}** "
        f"({co2_route.max()/1000:.1f} t de CO₂ au total).",
        f"**Chaîne du froid** : {df['temperature_breach'].mean()*100:.1f} % des trajets subissent une rupture. "
        f"Le produit le plus touché est **{rupture.idxmax()}** ({rupture.max():.1f} %).",
        f"**Corrélations** : la distance explique fortement le coût (corrélation {corr_dist_cout:.2f}), "
        f"ainsi que le carburant et le CO₂ : optimiser les itinéraires et le taux de remplissage est le principal levier d'économie.",
    ]


# ----------------------------------------------------------------------------
# PAGES
# ----------------------------------------------------------------------------
def entete(titre, sous_titre):
    st.markdown(f'<div class="bandeau"><h1>{titre}</h1><p>{sous_titre}</p></div>', unsafe_allow_html=True)


def deux_colonnes(g1, g2, df):
    c1, c2 = st.columns(2)
    with c1:
        g1(df)
    with c2:
        g2(df)


def afficher_kpi(df):
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Expéditions", f"{len(df):,}".replace(",", " "))
    k2.metric("Taux à l'heure", f"{df['on_time'].mean()*100:.1f} %")
    k3.metric("Coût moyen", f"{df['cost_mad'].mean():,.0f} MAD".replace(",", " "))
    k4.metric("Carburant / trajet", f"{df['fuel_liters'].mean():.1f} L")
    k5.metric("CO₂ / trajet", f"{df['co2_kg'].mean():.1f} kg")
    k6, k7, k8, k9, k10 = st.columns(5)
    k6.metric("Distance moyenne", f"{df['distance_km'].mean():.0f} km")
    k7.metric("Vitesse moyenne", f"{df['vitesse_kmh'].mean():.1f} km/h")
    k8.metric("Coût / km", f"{df['cost_per_km'].mean():.2f} MAD")
    k9.metric("Retard moyen", f"{df['delay_min'].mean():.1f} min")
    k10.metric("Ruptures du froid", f"{df['temperature_breach'].mean()*100:.1f} %")


def page_dashboard(df):
    entete("📊 Tableau de bord", "Indicateurs clés et visualisations des opérations COPAG")
    afficher_kpi(df)
    st.write("")
    t1, t2, t3, t4, t5, t6 = st.tabs(
        ["Performance & routes", "Retards & corrélations", "Coûts & répartition",
         "Carburant & CO₂", "Cartes", "Interprétation"]
    )
    with t1:
        deux_colonnes(g_ponctualite, g_top_routes, df)
        deux_colonnes(g_retard_region, g_vitesse_mode, df)
    with t2:
        deux_colonnes(g_boxplot_retards, g_correlation, df)
        deux_colonnes(g_histogramme_retards, g_rupture_froid, df)
    with t3:
        deux_colonnes(g_cout_km_region, g_camembert, df)
        deux_colonnes(g_cout_produit, g_capacite_mode, df)
    with t4:
        c1, c2, c3 = st.columns(3)
        with c1:
            g_scatter(df, "cost_mad", "Distance et coût", "Coût (MAD)")
        with c2:
            g_scatter(df, "fuel_liters", "Distance et carburant", "Carburant (L)")
        with c3:
            g_scatter(df, "co2_kg", "Distance et CO₂", "CO₂ (kg)")
    with t5:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Positions de la flotte")
            carte_flotte(df)
        with c2:
            st.subheader("Flux entre hubs et villes")
            carte_flux(df)
    with t6:
        for texte in interpretations(df):
            st.markdown(f'<div class="carte-info">{texte}</div>', unsafe_allow_html=True)


def page_nettoyage(brut, propre, rapport):
    entete("🧹 Nettoyage des données", "Contrôle qualité appliqué avant toute analyse")
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes initiales", rapport["lignes_initiales"])
    c2.metric("Lignes conservées", rapport["lignes_finales"])
    c3.metric("Lignes retirées", rapport["lignes_initiales"] - rapport["lignes_finales"])

    st.subheader("Étapes appliquées")
    st.dataframe(pd.DataFrame(rapport["etapes"]), hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Valeurs manquantes (avant nettoyage)")
        manq = brut.isna().sum().rename("Manquantes").to_frame()
        st.dataframe(manq[manq["Manquantes"] > 0] if manq["Manquantes"].sum() else
                     pd.DataFrame({"Résultat": ["Aucune valeur manquante"]}))
    with c2:
        st.subheader("Valeurs atypiques détectées (méthode IQR)")
        st.dataframe(pd.Series(rapport["atypiques"], name="Nombre").to_frame())
        st.caption("Ces valeurs sont signalées mais conservées : elles correspondent à de longs trajets réels (ex. Dakhla, Laâyoune).")

    st.subheader("Statistiques descriptives (données nettoyées)")
    st.dataframe(propre.describe().T.round(2))


def page_donnees(df):
    entete("🗂️ Données", "Explorer et exporter les expéditions filtrées")
    cols = ["shipment_id", "date", "origin_hub", "destination_city", "destination_region", "mode",
            "product_category", "distance_km", "vitesse_kmh", "delay_min", "on_time",
            "fuel_liters", "co2_kg", "cost_mad", "quantity_tons"]
    recherche = st.text_input("Rechercher (identifiant, ville, produit…)")
    vue = df[cols]
    if recherche:
        masque = vue.astype(str).apply(lambda s: s.str.contains(recherche, case=False, na=False)).any(axis=1)
        vue = vue[masque]
    st.caption(f"{len(vue)} ligne(s)")
    st.dataframe(vue, hide_index=True)
    st.download_button("⬇️ Télécharger en CSV", vue.to_csv(index=False).encode("utf-8"),
                       "copag_donnees_filtrees.csv", "text/csv")


# ----------------------------------------------------------------------------
# PRINCIPAL
# ----------------------------------------------------------------------------
def filtrer(df):
    st.sidebar.markdown("### 🔎 Filtres")
    tout = "Toutes"

    region = st.sidebar.selectbox("Région de destination", [tout] + sorted(df["destination_region"].unique()))
    mode = st.sidebar.selectbox("Mode de transport", [tout] + sorted(df["mode"].unique()))
    produit = st.sidebar.selectbox("Catégorie de produit", [tout] + sorted(df["product_category"].unique()))
    hub = st.sidebar.selectbox("Hub d'origine", [tout] + sorted(df["origin_hub"].unique()))

    dmin, dmax = df["date"].min().date(), df["date"].max().date()
    periode = st.sidebar.date_input("Période", value=(dmin, dmax), min_value=dmin, max_value=dmax)

    f = df
    if region != tout:
        f = f[f["destination_region"] == region]
    if mode != tout:
        f = f[f["mode"] == mode]
    if produit != tout:
        f = f[f["product_category"] == produit]
    if hub != tout:
        f = f[f["origin_hub"] == hub]
    if isinstance(periode, (tuple, list)) and len(periode) == 2:
        f = f[(f["date"].dt.date >= periode[0]) & (f["date"].dt.date <= periode[1])]
    return f


def main():
    if not st.session_state.get("connecte"):
        page_connexion()
        return

    brut, propre, rapport = charger_donnees()

    st.sidebar.markdown("## 🚚 COPAG")
    page = st.sidebar.radio("Navigation", ["📊 Tableau de bord", "🧹 Nettoyage", "🗂️ Données"],
                            label_visibility="collapsed")
    st.sidebar.divider()

    if page == "🧹 Nettoyage":
        page_nettoyage(brut, propre, rapport)
    else:
        filtre = filtrer(propre)
        st.sidebar.caption(f"{len(filtre)} expédition(s) sélectionnée(s)")
        if filtre.empty:
            entete("Aucun résultat", "Aucune expédition ne correspond aux filtres choisis")
            st.warning("Modifiez les filtres dans la barre latérale.")
        elif page == "📊 Tableau de bord":
            page_dashboard(filtre)
        else:
            page_donnees(filtre)

    st.sidebar.divider()
    if st.sidebar.button("Se déconnecter"):
        st.session_state["connecte"] = False
        st.rerun()


if __name__ == "__main__":
    main()
