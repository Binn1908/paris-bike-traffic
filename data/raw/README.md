# Dossier `data`

Le dossier data contient toutes les données utilisées dans le cadre du projet **Trafic cycliste à Paris**.

## Structure

- `raw/` – Données brutes originales
- `processed/` – Jeu de données final prêt pour la modélisation

## Données brutes

### comptage-velo-donnees-compteurs.csv

Ce fichier est trop volumineux pour être stocké sur GitHub. Il doit être **téléchargé manuellement** depuis le portail open data de la Ville de Paris :

[Comptage vélo - Données compteurs](https://opendata.paris.fr/explore/dataset/comptage-velo-donnees-compteurs)

Une fois téléchargé, placez le fichier dans le dossier `data/raw/`.

### vacances-scolaires-2023-2026.csv

Fichier inclus dans le dépôt. Source : données gouvernementales françaises.

### open-meteo-48.82N2.29E43m.csv

Fichier inclus dans le dépôt. Données météorologiques horaires (température, précipitations) pour Paris, générées via la plateforme [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api?latitude=48.8534&longitude=2.3488&start_date=2024-01-01&hourly=temperature_2m,precipitation#settings).