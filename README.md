
# SigmaMD

A lightweight Markdown editor for Windows with offline LaTeX math rendering.

## Features

- Open, edit, and save Markdown files.
- Live Markdown preview.
- Render LaTeX math expressions using KaTeX.
- Offline math rendering with locally bundled KaTeX assets.
- Split-pane editor and preview.
- Windows executable and installer support.

## Technology Stack

- Python 3.15.2
- PySide6
- Qt WebEngine
- Python-Markdown
- PyMdown Extensions (Arithmatex)
- KaTeX
- PyInstaller
- Inno Setup

## Requirements

- Windows 11, 64-bit
- Python 3.15.2 for running from source

## Run from Source

Create and activate a virtual environment:

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run SigmaMD:

```powershell
python main.py
```

## Build the Windows Application

```powershell
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name SigmaMD `
  --collect-all pymdownx `
  --hidden-import pymdownx.arithmatex `
  --add-data "assets/katex:assets/katex" `
  main.py
```

The application will be generated in `dist/SigmaMD/`.

## KaTeX Assets

SigmaMD bundles KaTeX locally to render mathematical expressions without requiring an Internet connection.

KaTeX is distributed under the MIT License. See `assets/katex/LICENSE`.

## License

No