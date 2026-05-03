import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import pandas as pd
import streamlit as st


@st.cache_data
def load_raw_data_head(path, sep=";", n=5, **read_kwargs):
    return next(pd.read_csv(path, sep=sep, chunksize=n, **read_kwargs))


@st.cache_data(show_spinner="Calcul des taux de valeurs manquantes…")
def load_missing_rate(path, sep=";", chunksize=1_000_000, **read_kwargs):
    total_rows = 0
    null_counts = None

    for chunk in pd.read_csv(path, sep=sep, chunksize=chunksize, **read_kwargs):
        if null_counts is None:
            null_counts = chunk.isnull().sum()
        else:
            null_counts += chunk.isnull().sum()

        total_rows += len(chunk)

    missing_pct = (null_counts / total_rows * 100).round(2)

    return missing_pct.reset_index().rename(
        columns={"index": "Colonne", 0: "Taux des valeurs manquantes (%)"}
    )


def tab_presentation():
    tabs = st.tabs(
        [
            "🔍 Exploration des données",
            "📊 Visualisation",
            "🧹 Preprocessing",
            "🧠 Modélisation",
            "🏁 Conclusion",
        ]
    )

    with tabs[0]:
        st.markdown("## Exploration des données")

        with st.container(border=True):
            df_head = load_raw_data_head(
                path=Path(__file__).resolve().parent.parent.parent
                / "data"
                / "raw"
                / "comptage-velo-donnees-compteurs.csv"
            )

            st.dataframe(df_head, use_container_width=True, hide_index=True)

            st.write("""
            **Variables clés du jeu de données**
            - Le nom du compteur
            - Le site de comptage
            - Le volume de comptage horaire
            - La date et l’heure des mesures
            - La localisation des sites (coordonnées géographiques)
            """)

        with st.container(border=True):
            st.markdown("### Analyse des outliers")

            st.write("""
            - Présence de valeurs très élevées dans le jeu de données
            - Valeur maximale observée : 3070 vélos / heure
            - Seuil retenu : **1 500 vélos / heure**
            """)

            col1, col2 = st.columns([0.4, 0.6])

            with col1:
                img_path = (
                    Path(__file__).resolve().parent.parent.parent
                    / "reports"
                    / "figures"
                    / "histogram_comptage_horaire.png"
                )
                st.image(img_path, width=600)

            with col2:
                img_path = (
                    Path(__file__).resolve().parent.parent.parent
                    / "reports"
                    / "figures"
                    / "boxplot_comptage_horaire.png"
                )
                st.image(img_path, width=900)

        with st.container(border=True):
            st.markdown("### Vérification de doublons")

            st.write("""
            - Aucun doublon identifié dans le jeu de données
            """)

        with st.container(border=True):
            st.markdown("### Valeurs manquantes")

            st.write("""
            - Valeurs manquantes corrélées entre variables
            - Probable indisponibilité de certains compteurs
            """)

            df_missing_rate = load_missing_rate(
                path=Path(__file__).resolve().parent.parent.parent
                / "data"
                / "raw"
                / "comptage-velo-donnees-compteurs.csv",
                low_memory=False,
            )

            st.dataframe(df_missing_rate, use_container_width=False, hide_index=True)

        with st.container(border=True):
            st.markdown("### Limites du jeu de données")

            st.write("""
            - Pas de distinction entre vélos individuels → comptages multiples possibles
            - Périodes de fonctionnement hétérogènes des compteurs (installation, indisponibilités)
            """)

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "activity_rate_under_80pct.png"
            )
            st.image(img_path, width=600)

    with tabs[1]:
        st.markdown("## Visualisation")

        with st.container(border=True):
            st.markdown("### 1) Comptage total de vélos par jour")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "total_velos_par_jour.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Nombre total de passages de vélos par jour, tous compteurs confondus
            - Comptage de passages, pas de cyclistes uniques
            - Permet d’observer la **tendance globale**, les pics et les creux d’activité
            """)

        with st.container(border=True):
            st.markdown("### 2) Comptage total de vélos par mois")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "total_velos_par_mois.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Nombre total de passages de vélos par mois, tous compteurs confondus
            - Met en évidence les tendances saisonnières, en lissant les variations journalières
            """)

        with st.container(border=True):
            st.markdown("### 3) Moyenne des comptages horaires par jour")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "moyenne_velos_par_jour.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Moyenne des comptages horaires par compteur, calculée chaque jour
            - Mesure l’intensité moyenne du trafic cycliste par compteur
            - Réduit l’effet de la structure du réseau → Comparaisons temporelles plus pertinentes
            """)

        with st.container(border=True):
            st.markdown("### 4) Moyenne des comptages par heure de la journée")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "moyenne_velos_par_heure.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Moyenne des comptages horaires selon l’heure de la journée
            - Calculée sur l’ensemble des compteurs
            - Identification des heures de pointe et des périodes de faible activité nocturne
            """)

        with st.container(border=True):
            st.markdown("### 5) Moyenne des comptages par jour de la semaine")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "moyenne_velos_par_jour_de_semaine.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Moyenne des comptages horaires par jour de la semaine
            - Calculée sur l’ensemble des compteurs
            - Différences nettes entre jours ouvrés et week-ends
            """)

        with st.container(border=True):
            st.markdown("### 6) Top 10 des sites de comptage - Moyenne horaire")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "top_10_sites_moyenne_horaire.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Top 10 des sites de comptage selon la moyenne horaire des passages
            - Comparaison de l’activité moyenne entre sites
            """)

        with st.container(border=True):
            st.markdown("### 7) Comparaison de la moyenne horaire par site (Top 10)")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "top_10_sites_moyenne_par_heure.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Comparaison du profil horaire moyen des 10 sites les plus fréquentés
            - Intensité variable selon les sites, liée à la localisation et à l’usage
            """)

        with st.container(border=True):
            st.markdown("### 8) Intensité moyenne des comptages par site")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "intensite_moyenne_comptages_par_site.png"
            )
            st.image(img_path, use_container_width=True)

            st.write("""
            - Intensité moyenne des comptages par site, représentée par la taille des bulles
            - Forte concentration de l’activité sur certains axes structurants
            - Certains arrondissements sont peu ou pas couverts par des compteurs
            """)

    with tabs[2]:
        st.markdown("## Preprocessing")

        with st.expander("load_raw()"):
            st.code(
                '''
            def load_raw(velo_path = RAW_DATA_PATH, vacances_path = VACANCES_PATH, weather_path = WEATHER_PATH):
                """
                Cette fonction charge les fichiers sources et convertit les colonnes de dates en objets datetime.
                """
                # Importation du dataset principal
                df = pd.read_csv(velo_path, sep = ';')
            
                # Suppression des colonnes inutiles
                col_a_supprimer = ['Identifiant du compteur', 'Identifiant du site de comptage',
                                   "Date d'installation du site de comptage", 'Identifiant technique compteur', 'ID Photos',
                                   'test_lien_vers_photos_du_site_de_comptage_', 'id_photo_1', 'url_sites', 'type_dimage', 'mois_annee_comptage']
                df.drop(
                    col_a_supprimer,
                    axis = 1,
                    inplace = True
                )
                
                # Conversion de 'Date et heure de comptage' en format datetime et heure locale
                df['Date et heure de comptage'] = (pd.to_datetime(df['Date et heure de comptage'], utc = True).dt.tz_convert('Europe/Paris').
                    dt.tz_localize(None))
                
                # Importation du dataset relatif aux vacances scolaires
                df_vacances_scolaires = pd.read_csv(
                    vacances_path,
                    sep = ';',
                    parse_dates = ['Date'],
                    dayfirst = True,
                    encoding = 'latin-1'
                )
            
                # Importation du dataset avec des données météorologiques
                df_weather = pd.read_csv(weather_path, header = 2)
                df_weather['Date et heure de comptage'] = (pd.to_datetime(df_weather['time'], utc = True).dt.tz_convert('Europe/Paris')
                    .dt.tz_localize(None))
                df_weather.drop(
                    'time',
                    axis = 1,
                    inplace = True
                )
                df_weather = df_weather.rename(columns = {
                    'temperature_2m (°C)': 'Température (°C)',
                    'precipitation (mm)': 'Précipitations (mm)'
                })
                
                return df, df_vacances_scolaires, df_weather
            ''',
                language="python",
            )

        with st.expander("remove_outliers()"):
            st.code(
                """
            def remove_outliers(df):
                df = df[df['Comptage horaire'] < 1500]
                return df
            """,
                language="python",
            )

        with st.expander("deduplicate()"):
            st.code(
                """
            def deduplicate(df):
                df = df.drop_duplicates(subset = ['Nom du compteur', 'Date et heure de comptage'])
                return df
            """,
                language="python",
            )

        with st.expander("add_direction()"):
            st.code(
                '''
            def add_direction(df):
                """
                Cette fonction crée une colonne avec le sens de la voie.
                """
                df['Direction'] = df['Nom du compteur'].str.extract(r'(Bike IN|Bike OUT|E-O|O-E|N-S|S-N|NE-SO|SO-NE|NO-SE|SE-NO)')
                return df
            ''',
                language="python",
            )

        with st.expander("coordinates()"):
            st.code(
                '''
            def coordinates(df):
                """
                Cette fonction extrait la latitude et la longitude de la colonne 'Coordonnées géographiques' et les convertit en valeurs numériques.
                """
                df[['Latitude', 'Longitude']] = df['Coordonnées géographiques'].str.split(',', expand = True)
                df['Latitude'] = pd.to_numeric(df['Latitude'], errors = 'coerce')
                df['Longitude'] = pd.to_numeric(df['Longitude'], errors = 'coerce')
                df.drop(
                    'Coordonnées géographiques',
                    axis = 1,
                    inplace = True
                )
                return df
            ''',
                language="python",
            )

        with st.expander("add_weather_features()"):
            st.code(
                '''
            def add_weather_features(df, df_weather):
                """
                Cette fonction enrichit le dataset principal avec deux nouvelles colonnes: Température (°C) et Précipitations (mm)
                """
                df = df.merge(
                    df_weather,
                    on = 'Date et heure de comptage',
                    how = 'left'
                )
                return df
            ''',
                language="python",
            )

        with st.expander("fill_nan()"):
            st.code(
                '''
            def fill_nan(df):
                """
                Cette fonction a pour objectif de gérer les valeurs manquantes, notamment celles identifiées lors de l'exploration des données.
                """
                # Compléter les lignes vides dans la colonne 'Nom du site de comptage'
                replace_nan = {
                    "27 quai de la Tournelle": "27 quai de la Tournelle",
                    "Grande Armée": "10 avenue de la Grande Armée",
                    "Face au 48 quai de la marne": "Face au 48 quai de la marne",
                    "Pont des Invalides": "Pont des Invalides",
                    "Quai des Tuileries": "Quai des Tuileries",
                    "Totem 64 Rue de Rivoli": "Totem 64 Rue de Rivoli"
                }
                for value, remplacement in replace_nan.items():
                    mask = df['Nom du site de comptage'].isna() & df['Nom du compteur'].str.contains(value, na = False)
                    df.loc[mask, 'Nom du site de comptage'] = remplacement
            
                # Compléter les lignes vides dans la colonne 'Liens vers photo du site de comptage'
                df['Lien vers photo du site de comptage'] = (df.groupby('Nom du site de comptage')['Lien vers photo du site de comptage']
                    .transform(lambda row: row.ffill().bfill()))
            
                # Compléter les lignes potentiellement vides dans la colonne 'Direction'
                df['Direction'] = df['Direction'].fillna("N/A")
            
                # Compléter les lignes vides dans les colonnes 'Latitude' et 'Longitude'
                df['Latitude'] = df.groupby('Nom du site de comptage')['Latitude'].transform(lambda row: row.ffill().bfill())
                df['Longitude'] = df.groupby('Nom du site de comptage')['Longitude'].transform(lambda row: row.ffill().bfill())
            
                # Remplir les lignes vides dans les colonnes 'Température (°C)' et 'Précipitations (mm)' avec la moyenne du jour
                df['Date'] = df['Date et heure de comptage'].dt.date
                df_weather_means = df.groupby('Date')[['Température (°C)', 'Précipitations (mm)']].mean().rename(columns = {
                    'Température (°C)': 'Température_moy_jour',
                    'Précipitations (mm)': 'Précipitations_moy_jour'
                })
                df = df.merge(
                    df_weather_means,
                    on = 'Date',
                    how = 'left'
                )
                df['Température (°C)'] = df['Température (°C)'].fillna(df['Température_moy_jour'])
                df['Précipitations (mm)'] = df['Précipitations (mm)'].fillna(df['Précipitations_moy_jour'])
                df.drop(columns = ['Date', 'Température_moy_jour', 'Précipitations_moy_jour'], inplace = True)
            
                df = df.dropna(subset = ['Nom du compteur', 'Nom du site de comptage', 'Comptage horaire', 'Date et heure de comptage'])
            
                return df
            ''',
                language="python",
            )

        with st.expander("add_calendar_features"):
            st.code(
                '''
            def add_calendar_features(df, df_vacances_scolaires):
                """
                Cette fonction génère des features temporelles, ajoute un indicateur de vacances scolaires,
                puis crée des lags (1h, 24h, 168h) et une moyenne glissante sur 3 heures pour modéliser les effets temporels du comptage horaire.
                """
                # Création de variables calendaires à partir de la colonne 'Date et heure de comptage'
                df['Jour du mois'] = df['Date et heure de comptage'].dt.day
                df['Mois'] = df['Date et heure de comptage'].dt.month
                df['Année'] = df['Date et heure de comptage'].dt.year
                df['Heure'] = df['Date et heure de comptage'].dt.hour
                df['Jour de la semaine'] = df['Date et heure de comptage'].dt.dayofweek
                df['Week-end'] = (df['Date et heure de comptage'].dt.dayofweek >= 5).astype(int)
            
                # Création d'une variable 'Vacances'
                df['Date'] = pd.to_datetime(df['Date et heure de comptage']).dt.date
                df_vacances_scolaires['Date'] = pd.to_datetime(df_vacances_scolaires['Date'], dayfirst = True).dt.date
                vacances_set = set(df_vacances_scolaires['Date'])
                df['Vacances'] = (df['Date'].isin(vacances_set)).astype(int)
                df.drop(
                    ['Date'],
                    axis = 1,
                    inplace = True
                )
            
                # Création de variables de décalage (lags) et d'une moyenne glissante
                df = df.sort_values(['Nom du compteur', 'Date et heure de comptage']).copy()
            
                df['lag_1h'] = df.groupby('Nom du compteur')['Comptage horaire'].shift(1)
                df['lag_24h'] = df.groupby('Nom du compteur')['Comptage horaire'].shift(24)
                df['lag_168h'] = df.groupby('Nom du compteur')['Comptage horaire'].shift(168)
            
                df['roll_mean_3h'] = (
                    df.groupby('Nom du compteur')['Comptage horaire']
                        .shift(1)
                        .rolling(window = 3)
                        .mean()
                )
                
                return df
            ''',
                language="python",
            )

        with st.expander("overwrite_data()"):
            st.code(
                '''
            def overwrite_data(df):
                """
                Cette fonction harmonise les informations de trois sites spécifiques en leur attribuant un seul jeu de coordonnées et une seule photo.
                """
                liens_ref = {
                    'Pont National': 'https://filer.eco-counter-tools.com/file/2a/799b98880f593cad49159a30639b855596a7b8448fcb43d18a3eb2f84098772a/Y2H18086317_20200818152643.jpg',
                    'Pont de la Concorde': 'https://filer.eco-counter-tools.com/file/3c/6241728bed2f3a14a9c830b39e0e3989fdd95ea2385d05d300fb671a2edbd73c/Y2H20083602_20211005103137.jpg',
                    'Pont du Garigliano': 'https://filer.eco-counter-tools.com/file/45/80d66480bbd17c6f2408ee29594c5158d14b61e02adfd8612655ed223c798445/15977339543880.jpg'
                }
                for site, lien in liens_ref.items():
                    df.loc[df['Nom du site de comptage'] == site, ['Lien vers photo du site de comptage']] = lien
            
                coordonnees_ref = {
                    'Pont National': (48.82639, 2.38448),
                    'Pont de la Concorde': (48.86373, 2.31973),
                    'Pont du Garigliano': (48.83994, 2.26692)
                }
                for site, coordonnees in coordonnees_ref.items():
                    df.loc[df['Nom du site de comptage'] == site, ['Latitude', 'Longitude']] = coordonnees
            
                return df
            ''',
                language="python",
            )

        with st.expander("Pipeline du preprocessing"):
            st.code(
                """
            # Pipeline de prétraitement
            df, df_vacances_scolaires, df_weather = load_raw()
            df = remove_outliers(df)
            df = deduplicate(df)
            df = add_direction(df)
            df = coordinates(df)
            df = add_weather_features(df, df_weather)
            df = fill_nan(df)
            df = add_calendar_features(df, df_vacances_scolaires)
            df = overwrite_data(df)
            """,
                language="python",
            )

    with tabs[3]:
        st.markdown("## Modélisation")

        with st.container(border=True):
            st.write("""
            - Problème de regression supervisée
            - Variable cible : Comptage horaire
            - Features utilisés :
                - **Variables calendaires** : Année, Mois, Jour du mois, Jour de la semaine, Week-end, Vacances
                - **Variables temporelles** : Heure, lag_1h, lag_24h, lag_168h, roll_mean_3h
                - **Variables météorologiques** : Température (°C), Précipitations (mm)
                - **Variables spatiales** : Nom du compteur, Direction
            - Découpage temporel des données (pas de mélange passé / futur)
            - Modèles testés
                - Modèles simples de référence (baseline)
                - Modèles linéaires
                - Modèles non linéaires
            - Métriques d'évaluation
                - MAE : erreur moyenne en valeur absolue
                - RMSE : pénalisation des grandes erreurs
                - R2 : proportion de la variabilité des données expliquée par le modèle
            """)

        with st.container(border=True):
            st.markdown("### Modèles de référence")

            st.write("""
            - Modèles volontairement simples
            - Point de comparaison pour les modèles plus complexes
            - Basés sur les des valeurs passées : lag-1, lag-24 et lag-168
            """)

        with st.container(border=True):
            st.markdown("### Modèles linéaires")

            st.write("""
            - Modélisation d’une relation linéaire entre les variables explicatives et le comptage horaire
            - Utilisation de pénalités (Ridge, Lasso, ElasticNet)
            - Amélioration nette par rapport aux baselines
            - Incapacité à capturer des relations non linéaires complexes
            """)

            with st.expander("Afficher le code"):
                st.code(
                    """
                feature_cols_num = ['Année', 'Mois', 'Jour du mois', 'Heure', 'Jour de la semaine', 'Week-end', 'Vacances', 'lag_1h', 'lag_24h',
                                    'lag_168h', 'roll_mean_3h', 'Température (°C)', 'Précipitations (mm)']
                
                feature_cols_cat = ['Nom du compteur', 'Direction']
                
                for col in feature_cols_num:
                    df[col] = pd.to_numeric(df[col], errors = 'coerce')
                # Assure que toutes les colonnes numériques sont bien en format numérique
                
                df_clean = df.dropna(subset = feature_cols_num + feature_cols_cat + ['Comptage horaire']).copy()
                # Supprime les valeurs vides (en particulier celles des colonnes lag)
                
                df['Date et heure de comptage'] = pd.to_datetime(
                    df['Date et heure de comptage'], errors='coerce')
                # Convertit 'Date et heure de comptage' en format datetime
                
                df_clean = df_clean.sort_values('Date et heure de comptage')
                
                split = int(len(df_clean) * 0.8)
                train = df_clean.iloc[:split]
                test = df_clean.iloc[split:]
                # Sépare le dataset chronologiquement
                
                X_train = train[feature_cols_num + feature_cols_cat]
                y_train = train['Comptage horaire']
                X_test = test[feature_cols_num + feature_cols_cat]
                y_test = test['Comptage horaire']
                
                # Création d'un pipeline : on standardise les variables numériques et on convertit les variables catégorielles en vecteurs numériques.
                preprocess = ColumnTransformer(
                    transformers = [
                        #('num', 'passthrough', feature_cols_num),
                        ('num', StandardScaler(), feature_cols_num),
                        ('cat', OneHotEncoder(handle_unknown = 'ignore'), feature_cols_cat)
                    ],
                    remainder = 'drop'
                )
                
                model_lr = Pipeline(steps = [
                    ('prep', preprocess),
                    ('model', LinearRegression())
                ])
                
                model_lr.fit(X_train, y_train)
                pred_lr_test = model_lr.predict(X_test)
                
                mae_lr = mean_absolute_error(y_test, pred_lr_test)
                #rmse_lr = mean_squared_error(y_test, pred_lr, squared = False)
                rmse_lr = root_mean_squared_error(y_test, pred_lr_test)
                r2_lr_test = r2_score(y_test, pred_lr_test)
                
                pred_lr_train = model_lr.predict(X_train)
                r2_lr_train = r2_score(y_train, pred_lr_train)
                """,
                    language="python",
                )

        with st.container(border=True):
            st.markdown("### Random Forest")

            st.write("""
            - Ensemble de plusieurs arbres de décision
            - Capable de modéliser des relations non linéaires
            - Amélioration significative par rapport aux modèles linéaires
            - Temps d’entraînement plus élevé
            - Modèle moins explicable
            """)

            with st.expander("Afficher le code"):
                st.code(
                    """
                feature_cols_num = ['Année', 'Mois', 'Jour du mois', 'Heure', 'Jour de la semaine', 'Week-end', 'Vacances', 'lag_1h', 'lag_24h',
                                    'lag_168h', 'roll_mean_3h', 'Température (°C)', 'Précipitations (mm)']
                
                feature_cols_cat = ['Nom du compteur', 'Direction']
                
                for col in feature_cols_num:
                    df[col] = pd.to_numeric(df[col], errors = 'coerce')
                # Assure que toutes les colonnes numériques sont bien en format numérique
                
                df_clean = df.dropna(subset = feature_cols_num + feature_cols_cat + ['Comptage horaire']).copy()
                # Supprime les valeurs vides (en particulier celles des colonnes lag)
                
                df['Date et heure de comptage'] = pd.to_datetime(
                    df['Date et heure de comptage'], errors='coerce')
                # Convertit 'Date et heure de comptage' en format datetime
                
                df_clean = df_clean.sort_values('Date et heure de comptage')
                
                split = int(len(df_clean) * 0.8)
                train = df_clean.iloc[:split]
                test = df_clean.iloc[split:]
                # Sépare le dataset chronologiquement
                
                X_train = train[feature_cols_num + feature_cols_cat]
                y_train = train['Comptage horaire']
                X_test = test[feature_cols_num + feature_cols_cat]
                y_test = test['Comptage horaire']
                
                # Création d'un pipeline : on convertit les variables catégorielles en vecteurs numériques.
                preprocess = ColumnTransformer(
                    transformers = [
                        ('num', 'passthrough', feature_cols_num),
                        #('num', StandardScaler(), feature_cols_num), La standardisation des variables numériques n'est pas nécessaire pour Random Forest
                        ('cat', OneHotEncoder(handle_unknown = 'ignore'), feature_cols_cat)
                    ],
                    remainder = 'drop'
                )
                
                rf_tuned = RandomForestRegressor(
                    n_jobs = -1,
                    random_state = 42,
                    verbose = 0,
                    max_depth = 30,
                    min_samples_leaf = 5,
                    min_samples_split = 20,
                    max_features = 'sqrt',
                    n_estimators = 10
                )
                
                model_rf_tuned = Pipeline(steps = [
                    ('prep', preprocess),
                    ('model', rf_tuned)
                ])
                
                model_rf_tuned.fit(X_train, y_train)
                pred_rf_tuned_test = model_rf_tuned.predict(X_test)
                
                mae_rf_tuned = mean_absolute_error(y_test, pred_rf_tuned_test)
                rmse_rf_tuned = root_mean_squared_error(y_test, pred_rf_tuned_test)
                r2_rf_tuned_test = r2_score(y_test, pred_rf_tuned_test)
                
                pred_rf_tuned_train = model_rf_tuned.predict(X_train)
                r2_rf_tuned_train = r2_score(y_train, pred_rf_tuned_train)
                """,
                    language="python",
                )

        with st.container(border=True):
            st.markdown("### Modèles avancés")

            st.write("""
            - Modèles de Gradient Boosting (LightGBM & XGBoost) basés sur des arbres de décision
            - Construction séquentielle d’arbres pour corriger les erreurs précédentes
            - Capables de modéliser des relations non linéaires complexes
            - Meilleures performances globales observées
            - Interprétation moins intuitive que les modèles simples mais possible avec SHAP
            """)

            with st.expander("Afficher le code du preprocess"):
                st.code(
                    """
                feature_cols_num = ['Année', 'Mois', 'Jour du mois', 'Heure', 'Jour de la semaine', 'Week-end', 'Vacances', 'lag_1h', 'lag_24h',
                                    'lag_168h', 'roll_mean_3h', 'Température (°C)', 'Précipitations (mm)']
                
                feature_cols_cat = ['Nom du compteur', 'Direction']
                
                for col in feature_cols_num:
                    df[col] = pd.to_numeric(df[col], errors = 'coerce')
                # Assure que toutes les colonnes numériques sont bien en format numérique
                
                df_clean = df.dropna(subset = feature_cols_num + feature_cols_cat + ['Comptage horaire']).copy()
                # Supprime les valeurs vides (en particulier celles des colonnes lag)
                
                df['Date et heure de comptage'] = pd.to_datetime(
                    df['Date et heure de comptage'], errors='coerce')
                # Convertit 'Date et heure de comptage' en format datetime
                
                df_clean = df_clean.sort_values('Date et heure de comptage')
                
                split = int(len(df_clean) * 0.8)
                train = df_clean.iloc[:split]
                test = df_clean.iloc[split:]
                # Sépare le dataset chronologiquement
                
                X_train = train[feature_cols_num + feature_cols_cat]
                y_train = train['Comptage horaire']
                X_test = test[feature_cols_num + feature_cols_cat]
                y_test = test['Comptage horaire']
                
                preprocess = ColumnTransformer(
                    transformers = [
                        ('num', 'passthrough', feature_cols_num),
                        ('cat', OneHotEncoder(handle_unknown = 'ignore'), feature_cols_cat)
                    ],
                    remainder = 'drop'
                )
                """,
                    language="python",
                )

            with st.expander("Afficher le code pour LightGBM"):
                st.code(
                    """
                model_lgbm = Pipeline(steps = [
                    ('prep', preprocess),
                    ('model', LGBMRegressor(
                        n_estimators = 500,
                        learning_rate = 0.05,
                        num_leaves = 31,
                        subsample = 0.8,
                        colsample_bytree = 0.8,
                        random_state = 42,
                        n_jobs = -1))
                ])
                
                model_lgbm.fit(X_train, y_train)
                pred_lgbm_test = model_lgbm.predict(X_test)
                
                mae_lgbm = mean_absolute_error(y_test, pred_lgbm_test)
                rmse_lgbm = root_mean_squared_error(y_test, pred_lgbm_test)
                r2_lgbm_test = r2_score(y_test, pred_lgbm_test)
                
                pred_lgbm_train = model_lgbm.predict(X_train)
                r2_lgbm_train = r2_score(y_train, pred_lgbm_train)
                """,
                    language="python",
                )

            with st.expander("Afficher le code pour XGBoost"):
                st.code(
                    """
                model_xgb = Pipeline(steps = [
                    ('prep', preprocess),
                    ('model', XGBRegressor(
                        n_estimators = 500,
                        learning_rate = 0.05,
                        max_depth = 6,
                        subsample = 0.8,
                        colsample_bytree = 0.8,
                        reg_lambda = 1.0,
                        objective = 'reg:squarederror',
                        tree_method = 'hist',
                        random_state = 42,
                        n_jobs = -1))
                ])
                
                model_xgb.fit(X_train, y_train)
                pred_xgb_test = model_xgb.predict(X_test)
                
                mae_xgb = mean_absolute_error(y_test, pred_xgb_test)
                rmse_xgb = root_mean_squared_error(y_test, pred_xgb_test)
                r2_xgb_test = r2_score(y_test, pred_xgb_test)
                
                pred_xgb_train = model_xgb.predict(X_train)
                r2_xgb_train = r2_score(y_train, pred_xgb_train)
                """,
                    language="python",
                )

        with st.container(border=True):
            st.markdown("### Comparaison des modèles")

            metrics = pd.DataFrame(
                [
                    {"model": "Lag-1", "MAE": 29.36, "RMSE": 58.96, "R2": 70.4},
                    {"model": "Lag-24", "MAE": 25.75, "RMSE": 54.12, "R2": 75.1},
                    {"model": "Lag-168", "MAE": 24.02, "RMSE": 50.73, "R2": 78.2},
                    {
                        "model": "Régression linéaire",
                        "MAE": 20.94,
                        "RMSE": 37.70,
                        "R2": 89.5,
                    },
                    {"model": "Random Forest", "MAE": 16.11, "RMSE": 30.36, "R2": 93.2},
                    {"model": "LightGBM", "MAE": 13.61, "RMSE": 23.89, "R2": 95.8},
                    {"model": "XGBoost", "MAE": 13.52, "RMSE": 24.09, "R2": 95.7},
                ]
            )

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            fig.add_trace(
                go.Scatter(
                    x=metrics["model"],
                    y=metrics["MAE"],
                    mode="lines+markers",
                    name="MAE",
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=metrics["model"],
                    y=metrics["RMSE"],
                    mode="lines+markers",
                    name="RMSE",
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=metrics["model"],
                    y=metrics["R2"],
                    mode="lines+markers",
                    name="R² (%)",
                ),
                secondary_y=True,
            )

            fig.update_layout(
                xaxis_title="Modèle",
                legend_title="Métrique",
            )
            fig.update_yaxes(title_text="Erreur (MAE / RMSE) ↓", secondary_y=False)
            fig.update_yaxes(title_text="R² ↑", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Interprétabilité du modèle avec SHAP")

        with st.container(border=True):
            st.markdown("#### Importance des variables")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "shap_top_10_variables.png"
            )
            st.image(img_path, use_container_width=True)

        with st.container(border=True):
            st.markdown("#### Top 10 - Impact des variables")

            img_path = (
                Path(__file__).resolve().parent.parent.parent
                / "reports"
                / "figures"
                / "shap_impact_variables_top_10.png"
            )
            st.image(img_path, use_container_width=True)

    with tabs[4]:
        st.markdown("## Conclusion")

        with st.container(border=True):
            st.markdown("### Enseignements tirés de l’analyse exploratoire")
            st.write("""
            - Usage du vélo structuré et régulier
            - Heures de pointe marquées → déplacements quotidiens
            - Axes cyclables majeurs très fréquentés
            - Comportements homogènes à l’échelle de Paris
            - Données utiles pour le suivi, à interpréter avec prudence
            """)

        with st.container(border=True):
            st.markdown("### Bilan de la modélisation")

            st.write("""
            - Gain de performance progressif des modèles simples aux modèles avancés
            - Les modèles de type Gradient Boosting offrent les meilleures performances globales
            - Les variables temporelles et les lags sont les plus explicatives
            - Les variables externes ont un impact limité dans ce cadre
            - Modélisation dépendante de la qualité et de la continuité des données
            """)

        with st.container(border=True):
            st.markdown("### Pistes d'amélioration")

            st.write("""
            - Intégrer des données sur une période plus longue, couvrant plusieurs années
            - Prendre en compte les jours fériés et événements majeurs
            - Application Streamlit : intégrer SHAP dans le résultat des prédictions
            """)
