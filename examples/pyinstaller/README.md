# PyInstaller example

Freezes `../quickstart.py` into a single executable, to prove the SDK
(specifically `cryptography`'s compiled backend) survives a frozen build —
the single highest-value check before shipping to real users, since this
class of dependency can work fine under `python app.py` and only break once
frozen.

```bash
pip install pyinstaller
pyinstaller --onefile --collect-all cryptography ../quickstart.py
./dist/quickstart      # or dist\quickstart.exe on Windows
```

If you see `ModuleNotFoundError: _cffi_backend`, add
`--hidden-import=_cffi_backend` to the command above.

Run the frozen executable on a machine that does **not** have the dev
virtualenv on `PATH` — that's the actual test. If `activate()`/`verify()`
behave identically to the unfrozen script, packaging is solid.
