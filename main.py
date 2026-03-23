import sys

from src.scipy_preload import preload_scipy_dependencies

preload_scipy_dependencies()

from PySide6.QtWidgets import QApplication

from src.main_window import create_main_window


def main():
    app = QApplication(sys.argv)
    window = create_main_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
