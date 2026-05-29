# Dependency Notes

## Python Dependencies

Background Remover depends on:

- `Flask`: local web app and HTTP endpoints
- `Pillow`: image loading, EXIF handling, and PNG output
- `rembg`: background segmentation API
- `onnxruntime`: local ONNX model execution backend used by `rembg`

The dependencies are declared in both `pyproject.toml` and `requirements.txt`.

## Model Fetching

The first request that removes a background may trigger `rembg` to download the selected model. The default model is `u2net`.

Set a different model with:

```bash
BACKGROUND_REMOVER_MODEL=u2netp background-remover
```

Windows PowerShell:

```powershell
$env:BACKGROUND_REMOVER_MODEL = "u2netp"
background-remover
```

## Platform Notes

Linux, macOS, and Windows are supported when compatible wheels are available for `onnxruntime` and the target Python version.

The common failure modes are:

- Python version too old
- unsupported CPU architecture for `onnxruntime`
- network blocked during dependency install
- network blocked during first model download
- old `pip` unable to resolve modern wheels

Run this before opening an issue:

```bash
python scripts/preflight.py
```

## GPU Support

This project uses CPU `onnxruntime` by default. GPU acceleration is intentionally not part of the default install because setup differs significantly by vendor, driver, CUDA version, and operating system.
