# --- build ---

# Démarrage avec une image basique qui contient Python
FROM python:3.12.3-slim

# Configuration de la racine du projet au sein de Docker
WORKDIR /app

# Installe les dépendances système nécessaires (libgomp1 pour LightGBM/XGBoost)
# libgomp1 n'est pas un package Python --> installation en dehors de Poetry nécessaire
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==2.2.1

# Copie uniquement les fichiers de dépendances d'abord (meilleur cache Docker)
COPY pyproject.toml poetry.lock ./

# Installe les dépendances sans créer de venv (on est déjà isolés dans le conteneur)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copie le reste du code
COPY . .

# EXPOSE est purement indicatif
EXPOSE 8000

# --- run ---

# Démarre le serveur Uvicorn au lancement du conteneur, en exposant
# l'objet 'app' de api/main.py sur toutes les interfaces réseau (0.0.0.0)
# Le Port 8000 est nécessaire pour que le conteneur soit joignable de l'extérieur
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]