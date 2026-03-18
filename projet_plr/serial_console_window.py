"""
serial_console_window.py
========================
Fenêtre indépendante pour la console série (debug µC).
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel
)
from PySide6.QtCore import Qt


class SerialConsoleWindow(QMainWindow):
    """Fenêtre flottante pour visualiser et envoyer des commandes série."""

    def __init__(self, hardware_manager, parent=None):
        super().__init__(parent)
        self.hardware = hardware_manager
        self.setWindowTitle("Console Série (Debug µC)")
        self.setMinimumSize(600, 350)
        self.resize(700, 450)
        # Garder la fenêtre au-dessus sans bloquer la principale
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        # --- Console d'affichage ---
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color:#1e1e1e; color:#00ff00; "
            "font-family:Consolas,monospace; font-size:12px; "
            "border:1px solid #333;"
        )
        self.console.setPlaceholderText("Les messages série TX/RX apparaîtront ici...")
        layout.addWidget(self.console, 1)

        # --- Barre d'envoi ---
        hl_send = QHBoxLayout()
        self.txt_cmd = QLineEdit()
        self.txt_cmd.setPlaceholderText("Ex: !version=0;  ou  !marche IR=1;")
        self.txt_cmd.setStyleSheet(
            "background:#2d2d2d; color:#fff; font-family:Consolas,monospace; "
            "font-size:12px; padding:5px; border:1px solid #555; border-radius:3px;"
        )
        self.txt_cmd.returnPressed.connect(self._send_cmd)
        self.btn_send = QPushButton("Envoyer")
        self.btn_send.setStyleSheet(
            "background:#0d6efd;color:white;padding:5px 14px;"
            "border-radius:3px;font-weight:bold;"
        )
        self.btn_send.clicked.connect(self._send_cmd)
        self.btn_clear = QPushButton("Effacer")
        self.btn_clear.setStyleSheet(
            "background:#6c757d;color:white;padding:5px 10px;border-radius:3px;"
        )
        self.btn_clear.clicked.connect(self.console.clear)
        hl_send.addWidget(self.txt_cmd, 1)
        hl_send.addWidget(self.btn_send)
        hl_send.addWidget(self.btn_clear)
        layout.addLayout(hl_send)

        # --- Connecter les signaux série ---
        self.hardware.serial_tx.connect(self.log_tx)
        self.hardware.serial_rx.connect(self.log_rx)
        self.hardware.serial_raw.connect(self.log_raw)

    def log_tx(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.console.append(f'<span style="color:#ff9800;">[{ts}] TX &rarr; {msg}</span>')
        self._scroll_bottom()

    def log_rx(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.console.append(f'<span style="color:#4caf50;">[{ts}] RX &larr; {msg}</span>')
        self._scroll_bottom()

    def log_raw(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.console.append(f'<span style="color:#888888;">[{ts}] RAW {msg}</span>')
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send_cmd(self):
        cmd = self.txt_cmd.text().strip()
        if not cmd:
            return
        if not self.hardware.is_connected or not self.hardware.worker:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.console.append(f'<span style="color:#f44336;">[{ts}] ERREUR : Non connecté</span>')
            return
        self.hardware.worker.send(cmd)
        self.txt_cmd.clear()

    def closeEvent(self, event):
        # Masquer au lieu de détruire, pour pouvoir ré-ouvrir
        self.hide()
        event.ignore()
