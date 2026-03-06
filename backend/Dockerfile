FROM python:3.12-slim-bookworm

WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installer Chromium + toutes ses dépendances système via Playwright
RUN playwright install chromium --with-deps

# Copier le code source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
