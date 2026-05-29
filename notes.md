# Background Remover

Created: `2026-05-11T00:00:00Z`

## Notes

- Source of truth for the original behavior is the homelab Flask app at `http://192.168.1.49:5050/`.
- The local app adds:
  - `/health`
  - `/whoami`
  - `/api/jobs`
  - `/download/<job_id>`
  - recent job history
  - persistent input/output storage
  - a more explicit, status-rich UI
- The current UI keeps tuning simple with named edge presets:
  - `Balanced`
  - `Soft edges`
  - `Crisp edges`
- Uploads are removed automatically after processing.
