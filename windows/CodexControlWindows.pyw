from __future__ import annotations

import sys

from codexcontrol_windows.app import main as gui_main
from codexcontrol_windows.bridge_cli import dispatch


if __name__ == "__main__":
    raise SystemExit(dispatch(sys.argv[1:], sys.stdin, gui_main))
