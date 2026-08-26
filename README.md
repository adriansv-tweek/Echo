# Echo

Echo is a small local Windows utility for storing and copying reusable, generic response templates. It exists to make repetitive customer-service replies faster: search for a template, copy it, and paste it yourself wherever you need it.

Echo is local-only. It has no network code, no accounts, no cloud sync of its own, and no integration with any work system. It does not send messages, does not paste for you, and does not record what you copy. The only thing it touches outside its own data file is the Windows clipboard.

## Features

- Search templates by title and keywords as you type
- Keyboard-first workflow: type, arrow keys, Enter, Enter
- Copies to the clipboard without a Copy button
- Add, edit, and delete templates in the GUI
- Runs in the system tray so the global shortcut is always available
- Global shortcut `Ctrl + Shift + .` opens and focuses Echo

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

Echo starts hidden in the system tray. Press `Ctrl + Shift + .` to open it.

## Keyboard workflow

1. Press `Ctrl + Shift + .` anywhere in Windows to open and focus Echo.
2. Type a search term. The search field is focused and ready immediately. An empty search shows no templates.
3. Use `Up` and `Down` to move through the matching templates.
4. Press `Enter` to select the highlighted template.
5. Press `Enter` again to copy it. Echo hides itself immediately.
6. Switch to your other application and paste with `Ctrl + V`.

Echo never pastes or types into another application. Copying to the clipboard is the last thing it does.

Other shortcuts:

- `Esc` — hide Echo and return to what you were doing
- `Ctrl + N` — new template (same window)
- `Ctrl + E` — edit the selected template (same window)
- `Ctrl + D` — delete the selected template
- `Ctrl + Enter` — save while editing

## Tray behaviour

Closing the window does not quit Echo — it only hides it, so `Ctrl + Shift + .` keeps working. The tray icon menu has:

- **Show Echo** — open and focus the window
- **Quit Echo** — actually shut Echo down

Quitting from the tray is the only way to stop Echo completely. Left-clicking the tray icon also opens the window.

If Echo is already running, starting it again activates the existing window instead of opening a second copy.

If another application already owns `Ctrl + Shift + .`, Echo shows a warning in the window and keeps working from the tray icon. To change the shortcut, edit the `HOTKEY_*` constants at the top of `src/hotkey.py`.

New and Edit switch the main window into an editing view. There is no separate editor window.

## Where templates are stored

Templates are stored in the repository, at:

```
data/templates.json
```

That file is tracked by Git, so the template library can be synchronized between computers by committing, pushing, and pulling this repository. Echo does not talk to GitHub itself — Git is the only sync mechanism.

You never need to edit the JSON by hand. Add, edit, and delete templates in the app; Echo writes the file for you.

If an older Echo version stored templates at `%APPDATA%\Echo\templates.json`, that file is copied into `data/templates.json` on first run **only when** `data/templates.json` does not already exist. An existing library is never overwritten.

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
├── data/
│   └── templates.json
├── src/
│   ├── main.py       startup, tray icon, single-instance, wiring
│   ├── ui.py         main window and inline template editor
│   ├── templates.py  template model, storage, search
│   ├── clipboard.py  clipboard copying
│   ├── hotkey.py     global shortcut via the Windows API
│   └── workflow.py   Enter and arrow-key selection helpers
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```
