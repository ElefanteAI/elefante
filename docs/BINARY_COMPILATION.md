# Compilation Instructions for Elefante Client

This guide is strictly oriented forward toward preparing the Zero-Dependency binary for Elefante. This is the **Indispensible Proof Mechanism** ensuring no one needs `pip` to test Elefante on their system.

## Setup PyInstaller

Activate your virtual environment, and install Pyinstaller natively:

```bash
source .venv/bin/activate
pip install pyinstaller
```

## Compilation

Execute to generate the target binary package:

```bash
pyinstaller elefante.spec
```

The executable standalone binary will be created in `./dist/elefante/elefante`. Provide a zip of `dist/elefante` folder as the core download on the landing page going forward.
