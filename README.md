# Fedora Manager Pro

<div align="center">

![Fedora](https://img.shields.io/badge/Fedora-43-51A2DA?style=for-the-badge&logo=fedora&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-2E3440?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)

A colorful, modern, and practical **system command launcher** for Fedora (and Linux).

</div>

---

## ✨ Features

- **One-click command buttons** (left panel)
- **Category Tabs + Scroll** for large command lists
  - Category is inferred from command `name` prefix like `DNF:`, `WARP:`, `System:`
- **CRUD Command Manager** (add / edit / delete) stored in `commands.json`
- **Category dropdown** when adding/editing commands
- **Manual Command runner** (type a shell command and run)
  - `clear` / `cls` clears the log panel (terminal history)
- **Live log streaming** (stdout+stderr) into the app log area
- **Per-user persistence for builds (PyInstaller)**
  - No more “can’t save after build” issues

---

## 🧩 Project Structure

- `sm.py` — main GUI application
- `commands.json` — list of commands shown in the app
- `sm.spec` — PyInstaller spec (optional)

---

## 🚀 Run (Developer)

```bash
python3 sm.py
```

---

## 📦 Build (PyInstaller)

### Onefile (recommended)

```bash
pyinstaller --noconsole --onefile --add-data "commands.json:." sm.py
```

The binary will be in:

- `dist/sm`

> Tip: If you want a nicer binary name, rename it after build or change the PyInstaller command output name.

---

## 💾 Where commands are saved (Per-user)

When running from a **PyInstaller onefile build**, the bundled `commands.json` is extracted to a temp folder and is not suitable for writing.

So the app automatically uses a writable per-user config file:

- `$XDG_CONFIG_HOME/Service-APP-GUI/commands.json`
- or (default): `~/.config/Service-APP-GUI/commands.json`

On first run, the app copies the bundled `commands.json` to that location.

### Reset to defaults

Delete the per-user file and restart the app:

```bash
rm -f ~/.config/Service-APP-GUI/commands.json
```

---

## 🧾 commands.json format

```json
{
  "commands": [
    {
      "name": "DNF: Check Update",
      "command": "dnf check-update"
    },
    {
      "name": "WARP: Status",
      "command": "warp-cli status"
    }
  ]
}
```

### Category rules

- If `name` contains `:` then the part before `:` becomes the **Category Tab**.
  - Example: `DNF: Check Update` → category `DNF`
- If no `:` then it goes to category `General`.

---

## 🧠 Manual Command Runner

Use the **Manual Command** box above the log area.

Examples:

```bash
uname -a
rpm -qa | head
```

Special commands:

- `clear` / `cls` — clears the log history

---

## 🔒 Notes (Privileges)

Some commands may require admin privileges.

- Use `pkexec` in your command string when needed.
  - Example: `pkexec dnf upgrade -y`

---

## 🧰 Troubleshooting

### “Save doesn’t work after build”

This is expected if you try writing into the bundled file.

Solution: the app already saves per-user at:

- `~/.config/Service-APP-GUI/commands.json`

### “Installed Apps (Daftar) failed”

On some systems, package-manager commands may return non-zero even when output is useful.
This project uses a robust “installed packages” command in `commands.json`.

---

## 🗺️ Roadmap (optional)

- Optional: checkbox “Run as root (pkexec)” for manual runner
- Optional: export/import commands

---

## 📄 License

MIT
