from __future__ import annotations

import argparse

from codexcontrol_windows.app import CodexControlWindowsApp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()

    app = CodexControlWindowsApp(start_hidden=True)
    if app._initial_refresh_job is not None:
        app.root.after_cancel(app._initial_refresh_job)
        app._initial_refresh_job = None
    app.root.after(max(100, int(args.duration * 1000)), app.quit)
    app.run()


if __name__ == "__main__":
    main()
