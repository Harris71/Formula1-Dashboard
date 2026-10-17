from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

from f1_tracker.config import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_SOFT,
    BG_DARK,
    BG_INPUT,
    BG_PANEL,
    BG_PANEL_2,
    BG_SIDEBAR,
    BORDER,
    BORDER_STRONG,
    FONT,
    FONT_FALLBACKS,
    ASSETS_DIR,
    FONTS_DIR,
    GOLD,
    INFO,
    SUCCESS,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    WARNING,
)

# Family actually in use after font loading (bundled font or a fallback).
ACTIVE_FONT = FONT


def _load_fonts() -> str:
    """Register bundled fonts and return the best available UI family."""
    if FONTS_DIR.is_dir():
        for path in sorted(FONTS_DIR.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(path))
    families = set(QFontDatabase.families())
    for family in (FONT, *FONT_FALLBACKS):
        if family in families:
            return family
    return QApplication.font().family()


def _icon_url(name: str) -> str:
    return (ASSETS_DIR / "icons" / name).as_posix()


def _qss(font: str) -> str:
    down = _icon_url("chevron-down.svg")
    up = _icon_url("chevron-up.svg")
    return f"""
* {{
    font-family: "{font}";
}}

QMainWindow, QStackedWidget, QWidget#root, QWidget#page {{
    background: {BG_DARK};
}}
QScrollArea, QScrollArea > QWidget > QWidget#scrollBody {{
    background: transparent;
    border: none;
}}

/* ---------------- Sidebar ---------------- */
QFrame#sidebar {{
    background: {BG_SIDEBAR};
    border: none;
    border-right: 1px solid {BORDER};
}}
QLabel#brandSubtitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    letter-spacing: 1px;
}}
QLabel#navHeading {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    padding-left: 14px;
}}
QLabel#sidebarFooter {{
    color: {TEXT_DIM};
    font-size: 10px;
}}
QPushButton#navButton {{
    text-align: left;
    padding-left: 14px;
    height: 44px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 10px;
    background: transparent;
    color: {TEXT_MUTED};
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#navButton:hover {{
    background: #1A212B;
    color: {TEXT};
}}
QPushButton#navButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_SOFT}, stop:1 {BG_PANEL_2});
    color: {TEXT};
    border-left: 3px solid {ACCENT};
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}}
QFrame#sidebarCard {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#sidebarCardTitle {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#sidebarCardValue {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 700;
}}
QLabel#sidebarCardCountdown {{
    color: {ACCENT_HOVER};
    font-size: 18px;
    font-weight: 800;
}}

/* ---------------- Typography ---------------- */
QLabel#pageTitle {{
    color: {TEXT};
    font-size: 30px;
    font-weight: 800;
}}
QLabel#pageKicker {{
    color: {ACCENT_HOVER};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
}}
QLabel#pageSubtitle {{
    color: {TEXT_MUTED};
    font-size: 14px;
}}
QLabel#sectionTitle {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#cardTitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#muted {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#value {{
    color: {TEXT};
    font-size: 24px;
    font-weight: 800;
}}
QLabel#valueSmall {{
    color: {TEXT};
    font-size: 17px;
    font-weight: 700;
}}
QLabel#heroInfo {{
    color: #BFC8D4;
    font-size: 14px;
}}
QLabel#heroTitle {{
    color: {TEXT};
    font-size: 38px;
    font-weight: 900;
}}
QLabel#countdownValue {{
    color: {TEXT};
    font-size: 40px;
    font-weight: 800;
}}
QLabel#countdownUnit {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#listPrimary {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#listSecondary {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#listValue {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 800;
}}
QLabel#positionBadge {{
    color: {TEXT_MUTED};
    font-size: 15px;
    font-weight: 800;
}}
QLabel#emptyState {{
    color: {TEXT_DIM};
    font-size: 14px;
}}

/* ---------------- Cards ---------------- */
QFrame#card {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#heroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #3A0B0E, stop:0.45 #1B1418, stop:1 {BG_PANEL});
    border: 1px solid #3A1F24;
    border-radius: 20px;
}}
QFrame#statCard {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#statCard:hover {{
    border-color: {BORDER_STRONG};
}}
QFrame#countdownBlock {{
    background: rgba(14, 17, 22, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
}}
QFrame#sessionTile {{
    background: rgba(14, 17, 22, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
}}
QFrame#sessionTileRace {{
    background: rgba(225, 6, 0, 0.18);
    border: 1px solid rgba(255, 24, 1, 0.45);
    border-radius: 10px;
}}
QFrame#sessionTileDone {{
    background: transparent;
    border: 1px dashed {BORDER};
    border-radius: 10px;
}}
QFrame#podiumCard {{
    background: {BG_PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QLabel#chip {{
    background: {BG_PANEL_2};
    color: #B7C0CC;
    border: 1px solid {BORDER};
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#chipAccent {{
    background: {ACCENT_SOFT};
    color: #FF6B6B;
    border: 1px solid #4A1E22;
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#chipSuccess {{
    background: #12261C;
    color: {SUCCESS};
    border: 1px solid #1E4430;
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#chipGold {{
    background: #2A2410;
    color: {GOLD};
    border: 1px solid #4A3F14;
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#chipInfo {{
    background: #102230;
    color: {INFO};
    border: 1px solid #1B3A52;
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#chipWarning {{
    background: #2C2312;
    color: {WARNING};
    border: 1px solid #4B3B1A;
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}

/* ---------------- Buttons ---------------- */
QPushButton {{
    background: {BG_PANEL_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: #2A3542;
    border-color: #3A4856;
}}
QPushButton:pressed {{
    background: {BG_PANEL};
}}
QPushButton:disabled {{
    background: #161C24;
    color: {TEXT_DIM};
    border-color: #1F2731;
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT_HOVER}, stop:1 #B80500);
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#primary:pressed {{
    background: #B80500;
}}
QPushButton#primary:disabled {{
    background: #3A1C1E;
    color: #8A6A6C;
}}
QPushButton#ghost {{
    background: transparent;
    border: 1px solid {BORDER_STRONG};
    color: #B7C0CC;
}}
QPushButton#ghost:hover {{
    border-color: {ACCENT};
    color: {TEXT};
    background: {ACCENT_SOFT};
}}
QPushButton#ghost:disabled {{
    border-color: #1F2731;
    color: {TEXT_DIM};
    background: transparent;
}}
QPushButton#quickAction {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
    color: {TEXT};
    font-size: 14px;
    font-weight: 700;
    text-align: left;
    padding: 14px 18px;
}}
QPushButton#quickAction:hover {{
    border-color: {ACCENT};
    background: #1C1A20;
}}
QPushButton#linkButton {{
    background: transparent;
    border: none;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 700;
    padding: 2px 4px;
}}
QPushButton#linkButton:hover {{
    color: {ACCENT_HOVER};
}}
QPushButton#linkButton:disabled {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
}}

/* ---------------- Inputs ---------------- */
QLineEdit, QSpinBox, QComboBox {{
    background: {BG_INPUT};
    border: 1px solid #2A3441;
    border-radius: 10px;
    padding: 7px 12px;
    color: {TEXT};
    font-size: 13px;
    min-height: 22px;
    selection-background-color: {ACCENT};
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: #3A4856;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    image: url("{down}");
    width: 12px;
    height: 12px;
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {BG_SIDEBAR};
    border: 1px solid #2A3441;
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
    outline: 0;
    padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 22px;
    border: none;
    background: transparent;
}}
QSpinBox::up-button {{
    subcontrol-position: top right;
    margin-top: 4px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: #1E2631;
    border-radius: 4px;
}}
QSpinBox::down-button {{
    subcontrol-position: bottom right;
    margin-bottom: 4px;
}}
QSpinBox {{
    padding-right: 26px;
}}
QSpinBox::up-arrow {{
    image: url("{up}");
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow {{
    image: url("{down}");
    width: 10px;
    height: 10px;
}}

/* ---------------- Tables ---------------- */
QTableWidget {{
    background: {BG_PANEL};
    alternate-background-color: #1A2029;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    gridline-color: transparent;
    selection-background-color: #26303C;
    selection-color: {TEXT};
    font-size: 13px;
    outline: 0;
}}
QTableWidget::item {{
    padding: 4px 10px;
    border: none;
}}
QTableWidget::item:hover {{
    background: #212A35;
}}
QHeaderView {{
    background: {BG_PANEL};
    border: none;
}}
QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER_STRONG};
    padding: 12px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QHeaderView::section:hover {{
    color: {TEXT};
}}
QTableCornerButton::section {{
    background: {BG_PANEL};
    border: none;
}}

/* ---------------- Tabs ---------------- */
QTabWidget::pane {{
    border: none;
    background: transparent;
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 10px 18px;
    margin-right: 4px;
    border-bottom: 3px solid transparent;
    font-size: 14px;
    font-weight: 700;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 3px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    border-bottom: 3px solid {BORDER_STRONG};
}}

/* ---------------- Misc ---------------- */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 14px;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_MUTED};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2A3441;
    min-height: 30px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3A4856;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #2A3441;
    min-width: 30px;
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}
QProgressBar {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    text-align: center;
    color: {TEXT};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B80500, stop:1 {ACCENT_HOVER});
    border-radius: 6px;
}}
QProgressBar#thinBar {{
    background: #232B35;
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}}
QProgressBar#thinBar::chunk {{
    border-radius: 3px;
}}
QSlider::groove:horizontal {{
    background: #232B35;
    height: 6px;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B80500, stop:1 {ACCENT_HOVER});
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {TEXT};
    border: 3px solid {ACCENT};
    width: 12px;
    height: 12px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:disabled {{
    background: {TEXT_DIM};
    border-color: {BORDER_STRONG};
}}
QToolTip {{
    background: {BG_PANEL_2};
    color: {TEXT};
    border: 1px solid #2A3441;
    padding: 6px;
    border-radius: 6px;
}}
QDialog, QMessageBox {{
    background: {BG_DARK};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QSplitter::handle {{
    background: {BORDER};
}}
QListWidget {{
    background: {BG_INPUT};
    border: 1px solid #202833;
    border-radius: 12px;
    color: {TEXT};
}}
QListWidget::item {{
    padding: 8px;
    border-radius: 8px;
}}
QListWidget::item:selected {{
    background: #232B36;
    color: {TEXT};
}}
QStatusBar {{
    background: {BG_SIDEBAR};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}
QStatusBar::item {{
    border: none;
}}
"""


def apply_theme(app: QApplication) -> None:
    global ACTIVE_FONT
    app.setStyle("Fusion")
    ACTIVE_FONT = _load_fonts()
    font = QFont(ACTIVE_FONT, 10)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    app.setPalette(_palette())
    app.setStyleSheet(_qss(ACTIVE_FONT))


def _palette() -> QPalette:
    """Dark base palette so anything QSS doesn't reach (auto-filled scroll
    contents, native dialogs, menus) never falls back to Fusion's light grey."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG_DARK,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: BG_INPUT,
        QPalette.ColorRole.AlternateBase: BG_PANEL,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: BG_PANEL_2,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: BG_PANEL_2,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
        QPalette.ColorRole.PlaceholderText: TEXT_DIM,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DIM))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_DIM))
    return palette
