# Docker

Background Remover can run fully inside Docker with no manual dependency installation on the host. The image includes all Python dependencies and pre-downloads the default rembg model at build time so the first run is fast.

## Start

**Using Docker Compose (recommended):**

```bash
git clone https://github.com/tweakyourpc/background-remover && cd background-remover
docker compose up -d
```

Open http://localhost:5050 in your browser.

**Using Docker directly:**

```bash
docker run -d \
  -p 5050:5050 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/uploads:/app/uploads \
  --name background-remover \
  ghcr.io/tweakyourpc/background-remover:latest
```

## Change the port

Edit `docker-compose.yml`:

```yaml
ports:
  - "7860:5050"
```

Then open http://localhost:7860.

## Use a different rembg model

Set the model via environment variable in `docker-compose.yml`:

```yaml
environment:
  - BACKGROUND_REMOVER_MODEL=u2net_human_seg
```

## Logs

```bash
docker compose logs -f
```

## Restart

```bash
docker compose restart
```

## Stop

```bash
docker compose down
```

## Notes

- `outputs` and `uploads` are mounted as volumes so processed files survive container restarts
- The model is baked into the image at build time so no download happens on first use
- HOST is set to `0.0.0.0` inside the container so Docker port mapping works correctly

## Platform notes

**Mac and Linux:** `docker compose up -d` works as-is from any terminal.

**Windows (PowerShell or CMD):** `docker compose up -d` works as-is. Docker Desktop for Windows handles path translation automatically.

**Note for `docker run` users:** On Windows CMD use `%cd%` instead of `$(pwd)`, and on PowerShell use `${PWD}`. Docker Compose with relative paths is recommended over `docker run` for this reason.
