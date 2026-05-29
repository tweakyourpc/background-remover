# Project Notes

## Goal

Background Remover should stay a small utility that installs locally, runs in a browser, and keeps image processing on the user's machine.

## GitHub Readiness Checklist

- Add a license before public release.
- Add screenshots once the UI stabilizes.
- Test bootstrap on Linux, macOS, and Windows.
- Decide whether releases should ship source-only or packaged installers.
- Consider adding GitHub Actions for tests on all three operating systems.

## Future Packaging Options

The current project is a Python package with a console command. Possible next steps:

- `pipx install git+https://github.com/<owner>/background-remover`
- PyInstaller single-file builds
- Briefcase or Tauri shell for a desktop app
- Docker image for server-style local use
