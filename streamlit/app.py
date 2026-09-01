import os
import re

import requests

import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

DIRECTION_PATTERN = re.compile(
    r"(Bike IN|Bike OUT|E-O|O-E|N-S|S-N|NE-SO|SO-NE|NO-SE|SE-NO)"
)

st.set_page_config(page_title="Paris Bike Traffic — Prédiction", layout="centered")
st.title("Paris Bike Traffic — Prédiction")
st.write("Prédiction du trafic cycliste horaire à Paris à partir d'un compteur, d'une date/heure et de conditions météo.")


@st.cache_data
def get_counters():
    response = requests.get(f"{API_BASE_URL}/get-counters")
    response.raise_for_status()
    return response.json()["counters"]


@st.cache_data
def get_best_model():
    response = requests.get(f"{API_BASE_URL}/best-model")
    response.raise_for_status()
    return response.json()["best_model"]


def extract_direction(nom_du_compteur: str) -> str:
    """
    Extrait le sens de la voie à partir du nom du compteur, selon la même
    règle que celle utilisée en prétraitement (scripts/preprocess.py).
    """
    match = DIRECTION_PATTERN.search(nom_du_compteur)
    return match.group(1) if match else ""


# Compteur et direction en dehors du formulaire : la direction dépend du
# compteur sélectionné, donc ces deux champs doivent réagir immédiatement
# (contrairement aux champs dans st.form, qui n'actualisent qu'à la soumission)
counters = get_counters()
nom_du_compteur = st.selectbox("Compteur", counters)

direction = extract_direction(nom_du_compteur)
st.write(f"Direction détectée : **{direction}**")

st.divider()

with st.form("predict_form"):
    st.subheader("Date et heure")
    col1, col2 = st.columns(2)
    with col1:
        annee = st.number_input("Année", min_value=2000, max_value=2100, value=2024)
        mois = st.number_input("Mois", min_value=1, max_value=12, value=1)
        jour_du_mois = st.number_input("Jour du mois", min_value=1, max_value=31, value=1)
        heure = st.number_input("Heure", min_value=0, max_value=23, value=8)
    with col2:
        jour_de_la_semaine = st.number_input("Jour de la semaine (0=lundi)", min_value=0, max_value=6, value=0)
        week_end = st.selectbox("Week-end ?", [0, 1])
        vacances = st.selectbox("Vacances ?", [0, 1])

    st.subheader("Historique du compteur")
    col3, col4 = st.columns(2)
    with col3:
        lag_1h = st.number_input("Comptage il y a 1h", value=50.0)
        lag_24h = st.number_input("Comptage il y a 24h", value=50.0)
    with col4:
        lag_168h = st.number_input("Comptage il y a 168h (7j)", value=50.0)
        roll_mean_3h = st.number_input("Moyenne mobile 3h", value=50.0)

    st.subheader("Météo")
    col5, col6 = st.columns(2)
    with col5:
        temperature = st.number_input("Température (°C)", value=15.0)
    with col6:
        precipitations = st.number_input("Précipitations (mm)", value=0.0, min_value=0.0)

    st.subheader("Modèle")
    model = st.selectbox("Modèle", ["lr", "rf", "lgbm", "xgb"], index=None, placeholder="Choisissez un modèle")

    best_model = get_best_model()
    st.caption(f"Modèle actuellement le plus performant en production : **{best_model}**")
    
    submitted = st.form_submit_button("Prédire")

if submitted:
    if model is None:
        st.error("Veuillez sélectionner un modèle.")
        st.stop()
    payload = {
        "nom_du_compteur": nom_du_compteur,
        "direction": direction,
        "annee": annee,
        "mois": mois,
        "jour_du_mois": jour_du_mois,
        "heure": heure,
        "jour_de_la_semaine": jour_de_la_semaine,
        "week_end": week_end,
        "vacances": vacances,
        "lag_1h": lag_1h,
        "lag_24h": lag_24h,
        "lag_168h": lag_168h,
        "roll_mean_3h": roll_mean_3h,
        "temperature": temperature,
        "precipitations": precipitations,
        "model": model,
    }

    try:
        response = requests.post(f"{API_BASE_URL}/predict", json=payload)
        response.raise_for_status()
        result = response.json()
        st.success(f"Prédiction ({result['model']}) : **{result['prediction']:.1f} vélos/heure**")
    except requests.exceptions.HTTPError:
        st.error(f"Erreur de l'API : {response.json().get('detail', response.text)}")
    except requests.exceptions.ConnectionError:
        st.error("Impossible de contacter l'API. Vérifiez que le service `api` est démarré.")