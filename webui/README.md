# Local Web UI

Install dependencies, then start the interface from the repository root:

```bash
python -m pip install -r requirements.txt
python -m webui.app
```

Open `http://127.0.0.1:5000` in a browser. The UI reads the latest
`daily_report.json` below the configured backup directory and reads the
existing application log file. Settings are stored in the repository's
`config.json` and are reloaded by the scheduler.
