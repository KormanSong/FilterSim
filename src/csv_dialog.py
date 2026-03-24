"""CSV 파일 열기 다이얼로그 — 파일 선택 + 열 선택 + 로드를 하나의 QDialog로 처리."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.csv_loader import read_headers


class CSVOpenDialog(QDialog):
    """CSV 파일 선택 + Time/Data 열 선택 + Load를 한 화면에서 처리하는 다이얼로그.

    사용법::

        dlg = CSVOpenDialog(parent, last_path="/prev/file.csv")
        if dlg.exec() == QDialog.Accepted:
            path = dlg.selected_path
            time_col = dlg.selected_time_col
            data_col = dlg.selected_data_col
    """

    def __init__(self, parent=None, last_path: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Open CSV")
        self.setMinimumWidth(420)

        self.selected_path: str = ""
        self.selected_time_col: str = ""
        self.selected_data_col: str = ""

        self._build_ui(last_path)

    def _build_ui(self, last_path: str) -> None:
        layout = QVBoxLayout(self)

        # ── File path row ──
        file_layout = QHBoxLayout()
        self._edit_path = QLineEdit()
        self._edit_path.setReadOnly(True)
        self._edit_path.setPlaceholderText("Select a CSV file...")
        if last_path:
            self._edit_path.setText(last_path)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._on_browse)
        file_layout.addWidget(self._edit_path, stretch=1)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        # ── Column selection ──
        form = QFormLayout()
        self._combo_time = QComboBox()
        self._combo_data = QComboBox()
        self._combo_time.setEnabled(False)
        self._combo_data.setEnabled(False)
        form.addRow("Time Column:", self._combo_time)
        form.addRow("Data Column:", self._combo_data)
        layout.addLayout(form)

        # ── Buttons ──
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        self._buttons.button(QDialogButtonBox.Ok).setText("Load")
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        # 이전 경로가 있으면 자동으로 헤더 읽기 시도
        if last_path:
            self._try_read_headers(last_path)

    def _on_browse(self) -> None:
        start_dir = ""
        current = self._edit_path.text()
        if current:
            parent = Path(current).parent
            if parent.exists():
                start_dir = str(parent)

        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", start_dir, "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        self._edit_path.setText(path)
        self._try_read_headers(path)

    def _clear_header_state(self) -> None:
        """현재 헤더/열 선택 상태를 비운다."""
        self._combo_time.clear()
        self._combo_data.clear()
        self._combo_time.setEnabled(False)
        self._combo_data.setEnabled(False)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)

    def _try_read_headers(self, path: str) -> None:
        """헤더 읽기 시도. 실패 시 콤보 비활성 유지."""
        try:
            headers = read_headers(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read CSV headers:\n{e}")
            self._clear_header_state()
            return

        if len(headers) < 2:
            QMessageBox.warning(self, "Warning", "CSV must have at least 2 columns.")
            self._clear_header_state()
            return

        self._combo_time.clear()
        self._combo_data.clear()
        self._combo_time.addItems(headers)
        self._combo_data.addItems(headers)

        if len(headers) >= 2:
            self._combo_data.setCurrentIndex(1)

        self._combo_time.setEnabled(True)
        self._combo_data.setEnabled(True)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)

    def _on_accept(self) -> None:
        time_col = self._combo_time.currentText()
        data_col = self._combo_data.currentText()

        if time_col == data_col:
            QMessageBox.warning(
                self, "Warning", "Time and Data columns must be different."
            )
            return

        self.selected_path = self._edit_path.text()
        self.selected_time_col = time_col
        self.selected_data_col = data_col
        self.accept()
