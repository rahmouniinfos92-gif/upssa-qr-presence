FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
RUN pip install --no-cache-dir Pillow

# Copie des fichiers de l'application
COPY . /app

# Création des dossiers médias
RUN mkdir -p /app/qrcodes /app/passes

# Port par défaut (compatible Fly.io)
ENV PORT=8080
EXPOSE 8080

CMD ["python3", "start_server.py"]
