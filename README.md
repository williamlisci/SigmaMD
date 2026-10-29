# SigmaMD

A lightweight Markdown editor for Windows 11 with live Markdown preview and offline LaTeX rendering powered by KaTeX. SigmaMD supports opening a Markdown file passed by Windows when the file is associated with the app.

## Download

visit the [Releases page](https://github.com/williamlisci/SigmaMD/releases) to see all versions.

## Features

- Open, edit, and save `.md` and `.markdown` files.
- Automatically save changes to an open Markdown file after 5 seconds; toggle autosave from the **File** menu.
- Drag and drop local `.md` or `.markdown` files onto the editor or preview pane to open them.
- Live Markdown preview updates immediately as you edit.
- Synchronized scrolling: scroll either the editor or preview to follow the same relative position in the document.
- Editing while reading updates the preview in place without resetting its current scroll position.
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
  --icon "assets/SigmaMD.ico" `
  --collect-all pymdownx `
  --hidden-import pymdownx.arithmatex `
  --add-data "assets/katex:assets/katex" `
  --add-data "assets/SigmaMD.ico:assets" `
  main.py
```

The application folder is generated under `dist/SigmaMD/`.

Place your Windows icon at `assets/SigmaMD.ico` before building. To create a Windows installer, open `SigmaMD.iss` with Inno Setup Compiler and compile it. The installer expects that icon file and packages the application folder from `dist/SigmaMD/`.

## Open Markdown files by double-clicking

The installer registers SigmaMD as an available handler for `.md` and `.markdown` files. Windows 11 may require a one-time default-app selection:

1. Right-click a Markdown file and choose **Open with** → **Choose another app**.
2. Select **SigmaMD**. If needed, browse to the installed `SigmaMD.exe`.
3. Select **Always use this app to open .md files** and confirm.

If Windows continues opening another editor, go to **Settings → Apps → Default apps**, search for `.md`, and select SigmaMD. Repeat for `.markdown` if you use that extension.

## KaTeX assets

SigmaMD includes local KaTeX files for offline math rendering. KaTeX is distributed under the MIT License; see [assets/katex/LICENSE](assets/katex/LICENSE).

## Acknowledgments

ChatGPT (OpenAI) assisted with project planning, implementation guidance, debugging, and documentation during development. The project owner reviewed and tested the application locally.

## License

SigmaMD's own source code is licensed under the [MIT License](LICENSE).

Third-party libraries and bundled assets remain subject to their respective licenses. See the license files and notices included with those components.
