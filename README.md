# SigmaMD

A lightweight Markdown editor for Windows 11 with live Markdown preview and offline LaTeX rendering powered by KaTeX.

## Download

**[Download SigmaMD 1.0.0 for Windows (64-bit)](https://github.com/williamlisci/SigmaMD/releases/download/v1.0.0/SigmaMD-Setup-1.0.0.exe)**

Or visit the [Releases page](https://github.com/williamlisci/SigmaMD/releases) to see all versions.

Download the installer and run `SigmaMD-Setup-1.0.0.exe`. The application bundles its runtime and local KaTeX assets; Python is not required to use the installed application.

## Features

- Open, edit, and save `.md` and `.markdown` files.
- Live Markdown preview in a split-pane interface.
- Render LaTeX math using locally bundled KaTeX.
- Support common inline and display math delimiters: `$...$`, `\\(...\\)`, `$$...$$`, and `\\[...\\]`.
- Work offline for math rendering after installation.
- Warn before closing or replacing unsaved edits.

## Technology

- Python 3.15.2
- PySide6 and Qt WebEngine
- Python-Markdown
- PyMdown Extensions (Arithmatex)
- KaTeX
- PyInstaller
- Inno Setup

## Run from source

### Requirements

- Windows 11, 64-bit
- Python 3.15.2
- Git (optional)

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/williamlisci/SigmaMD.git
cd SigmaMD
```

Create and activate a virtual environment:

```powershell
py -3.15 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
```

Install dependencies and run the application:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Build the Windows application

Install PyInstaller in the active virtual environment, then run:

```powershell
python -m pip install pyinstaller
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

The application folder is generated under `dist/SigmaMD/`.

To create a Windows installer, open `SigmaMD.iss` with Inno Setup Compiler and compile it. The installer is configured to package the application folder from `dist/SigmaMD/`.

## KaTeX assets

SigmaMD includes local KaTeX files for offline math rendering. KaTeX is distributed under the MIT License; see [assets/katex/LICENSE](assets/katex/LICENSE).

## Acknowledgments

ChatGPT (OpenAI) assisted with project planning, implementation guidance, debugging, and documentation during development. The project owner reviewed and tested the application locally.

## License

SigmaMD's own source code is licensed under the [MIT License](LICENSE).

Third-party libraries and bundled assets remain subject to their respective licenses. See the license files and notices included with those components.
