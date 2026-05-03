import streamlit as st
from tabs.tab_demo import tab_demo
from tabs.tab_home import tab_home
from tabs.tab_presentation import tab_presentation

st.set_page_config(page_title="Trafic cycliste à Paris", layout="wide")

st.sidebar.image("streamlit/logo.png")

tabs = {"Accueil": tab_home, "Présentation": tab_presentation, "Démo": tab_demo}

tab_selection = st.sidebar.radio("", list(tabs.keys()))

tabs[tab_selection]()
