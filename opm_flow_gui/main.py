"""Entry point for the OPM Flow GUI application."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from opm_flow_gui.gui.main_window import MainWindow
from opm_flow_gui.gui.styles import apply_style


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("OPM Flow GUI")
    app.setOrganizationName("OPMFlowGUI")

    apply_style(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
