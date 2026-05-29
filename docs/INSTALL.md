# Install Guide

Background Remover is a Python app. The installer story is intentionally simple: create a virtual environment, install the package, run the command.

## Requirements

- Python 3.10 or newer
- `pip`
- Internet access during first install
- Internet access during first model fetch unless model files are pre-cached

## Linux

```bash
python3 scripts/bootstrap.py
. .venv/bin/activate
background-remover
```

## macOS

```bash
python3 scripts/bootstrap.py
. .venv/bin/activate
background-remover
```

If `python3` is missing, install Python from python.org, Homebrew, or your preferred package manager.

## Windows

```powershell
py scripts/bootstrap.py
.venv\Scripts\Activate.ps1
background-remover
```

If script activation is blocked, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the virtual environment again.

## Network Binding

By default, Background Remover binds to `127.0.0.1` so only the local machine can reach it. Set `HOST=0.0.0.0` only when you intentionally want other devices on your network to connect.

## Custom Port

```bash
HOST=127.0.0.1 PORT=7860 background-remover
```

```powershell
$env:HOST = "127.0.0.1"
$env:PORT = "7860"
background-remover
```
