FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/ /app/frontend/
RUN npm install && npm run build

FROM python:3.11-slim AS server
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl unixodbc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY ether_ghost /app/ether_ghost
COPY run_ether_ghost.py /app/run_ether_ghost.py
COPY --from=frontend /app/frontend/dist /app/ether_ghost/public
ENV PYTHONUNBUFFERED=1
ENV ETHER_GHOST_VERSION=0.2.2
EXPOSE 8022
CMD ["python","-m","ether_ghost","--host","0.0.0.0","--port","8022","--no-browser"]
