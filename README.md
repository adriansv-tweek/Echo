# Echo

Echo is a small local Windows utility for storing and copying reusable, generic response templates. It exists to make repetitive customer-service replies faster: search for a template, copy it, and paste it yourself wherever you need it.

Echo is local-only. It has no network code, no accounts, no cloud sync, and no integration with any work system. It does not send messages, does not paste for you, and does not record what you copy. The only thing it touches outside its own data file is the Windows clipboard.

## Features

- Search templates by title and keywords as you type
- Keyboard-first workflow: type, arrow keys, Enter, Enter
- Copies to the clipboard without a Copy button
- Add, edit, and delete templates in the GUI
- Runs in the system tray so the global shortcut is always available
- Global shortcut `Ctrl + Shift + M` opens and focuses Echo

## Requirements

- Windows
- Python 3.10 or newer

Echo uses the Windows `RegisterHotKey` API for its global shortcut, so it is Windows-only by design.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The only dependency is `PySide6`. Everything else uses the Python standard library and the Windows API.

## Run

```bash
python src\main.py
```

Echo starts with its window open and an icon in the system tray.

## Keyboard workflow

1. Press `Ctrl + Shift + M` anywhere in Windows to open and focus Echo.
2. Type a search term. The search field is focused and ready immediately.
3. Use `Up` and `Down` to move through the matching templates.
4. Press `Enter` to select the highlighted template.
5. Press `Enter` again to copy it. The status line turns green and Echo hides itself.
6. Switch to your other application and paste with `Ctrl + V`.

Echo never pastes or types into another application. Copying to the clipboard is the last thing it does.

Other shortcuts:

- `Esc` — hide Echo and return to what you were doing
- `Ctrl + N` — new template
- `Ctrl + E` — edit the selected template
- `Ctrl + D` — delete the selected template
- `Ctrl + Enter` — save while in the template editor

## Tray behaviour

Closing the window does not quit Echo — it only hides it, so `Ctrl + Shift + M` keeps working. The tray icon menu has:

- **Show Echo** — open and focus the window
- **Quit Echo** — actually shut Echo down

Quitting from the tray is the only way to stop Echo completely. Left-clicking the tray icon also opens the window.

If another application already owns `Ctrl + Shift + M`, Echo shows a warning in the window and keeps working from the tray icon.

## Where templates are stored

Templates are stored outside the project folder, at:

```
%APPDATA%\Echo\templates.json
```

Keeping the data there means your personal template library can never be committed to git, and it survives deleting or re-cloning the repository. `data/` is also listed in `.gitignore` as a second safeguard; if you have an older `data\templates.json` from a previous version, it is copied to the new location automatically on first run.

The file looks like this:

```json
{
  "templates": [
    {
      "id": "a1b2c3d4",
      "title": "Template title",
      "keywords": ["keyword one", "keyword two"],
      "text": "Template body"
    }
  ]
}
```

You never need to edit it by hand — add, edit, and delete templates in the app.

Saving is atomic: Echo writes a temporary file and then replaces the original, and keeps the previous version as `templates.json.bak`. If the file is ever unreadable, Echo starts with an empty list, keeps a timestamped copy of the unreadable file next to it, and shows a warning in the window rather than crashing or discarding your data.

## What must never go in Echo

Echo is a library of **generic** templates only. Never store:

- Customer names, addresses, phone numbers, or email addresses
- Order numbers or case references
- Any other personal or customer information
- Credentials or internal system details

Write templates so they are reusable as-is, and fill in any specifics manually after pasting.

## Tests

```bash
python -m unittest discover tests
```

## Project structure

```
Echo/
├── src/
│   ├── main.py       startup, tray icon, wiring
│   ├── ui.py         main window and template editor
│   ├── templates.py  template model, storage, search
│   ├── clipboard.py  clipboard copying
│   └── hotkey.py     global Ctrl+Shift+M via the Windows API
├── tests/
│   └── test_templates.py
├── requirements.txt
├── .gitignore
└── README.md
```
