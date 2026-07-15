FROM python:3.12.3-slim

WORKDIR /app

# Installer les dépendances système nécessaires (libgomp pour LightGBM/XGBoost)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Installer Poetry
RUN pip install poetry==2.2.1

# Copier uniquement les fichiers de dépendances d'abord (meilleur cache Docker)
COPY pyproject.toml poetry.lock ./

# Installer les dépendances sans créer de venv (on est déjà isolés dans le conteneur)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copier le reste du code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]