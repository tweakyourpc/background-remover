FROM python:3.11-slim

ENV HOST=0.0.0.0 \
    PORT=5050 \
    BACKGROUND_REMOVER_MODEL=u2net

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir -e . \
    && python -c "from rembg import new_session; new_session('u2net')"

EXPOSE 5050

ENTRYPOINT ["background-remover"]
