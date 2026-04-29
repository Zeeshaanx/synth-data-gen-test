# NeMo Data Designer — Synth Data Gen

A FastAPI gateway on top of NVIDIA NeMo Microservices with a web UI for synthetic data generation, PostgreSQL job persistence, and CSV download.

---

## Two ways to run this

### Option A — From the AMI (prod / handoff)
Launch the shared AMI in any AWS account. Everything is pre-installed and starts automatically on boot. Open the IP in a browser.

### Option B — From the repo (dev / testing)

**Requirements:** Fresh Ubuntu 22.04 EC2, `r5.large` or larger, 100GB storage, ports 22 + 80 open.

```bash
git clone https://github.com/YOUR_ORG/synth-data-gen.git
cd synth-data-gen
chmod +x setup.sh
./setup.sh
```

That's it. The script handles everything:
- Swap, Docker, system packages
- PostgreSQL 16 (Docker, systemd-managed, data persisted to `/opt/synth-postgres/data`)
- NeMo Microservices (pulls Docker images, configures, starts)
- Python venv + all dependencies
- FastAPI service (systemd)
- Nginx reverse proxy

**Runtime: 20–40 minutes** (NeMo Docker images are large).

When it finishes it prints your URLs:

```
Frontend:  http://<IP>/synth-data-gen/data_generation/v1/home
Jobs UI:   http://<IP>/synth-data-gen/data_generation/v1/jobs/ui
API:       http://<IP>/synth-data-gen/data_generation/v1/create
Health:    http://<IP>/synth-data-gen/ok
```

---

## Baking the AMI (after setup.sh completes)

1. AWS Console → EC2 → select the instance → **Actions → Image and templates → Create image**
2. Name it `synth-data-gen-vX`
3. Share it with the target AWS account: **AMI → Actions → Edit AMI permissions → Add account ID**

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/synth-data-gen/data_generation/v1/create` | Submit a full generation job |
| `POST` | `/synth-data-gen/data_generation/v1/preview` | Fast preview (≤100 records) |
| `GET`  | `/synth-data-gen/data_generation/v1/jobs/{job_id}` | Poll job status |
| `GET`  | `/synth-data-gen/data_generation/v1/jobs/ui` | Jobs history UI (PostgreSQL) |
| `GET`  | `/synth-data-gen/data_generation/v1/home` | Submission frontend |
| `GET`  | `/synth-data-gen/data_generation/v1/download/{job_id}` | Download generated CSV |
| `GET`  | `/synth-data-gen/ok` | Health check |

---

## Troubleshooting

```bash
# FastAPI logs
sudo journalctl -u nemo_data_designer -n 50 --no-pager

# PostgreSQL logs
sudo journalctl -u synth_postgres -n 30 --no-pager

# NeMo logs
sudo journalctl -u nemo-data-designer -n 50 --no-pager

# Nginx logs
sudo tail -30 /var/log/nginx/error.log
```

---

## CI/CD (internal deploys)

GitHub Actions → Terraform → Ansible pipeline in `.github/workflows/deploy.yml`.
Requires GitHub secrets: `WLD_TOKEN`, `EC2_SSH_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PG_PASSWORD`.
