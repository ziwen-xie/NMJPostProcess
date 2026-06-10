import sys
import os
from pathlib import Path
import traceback
import copy

# GUI Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox,
    QCheckBox, QProgressBar, QScrollArea, QMessageBox, QSplitter,
    QFrame, QSizePolicy, QStackedWidget, QSpinBox, QComboBox,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QGraphicsEllipseItem, QGraphicsSimpleTextItem,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool, QRectF, QPointF, QEvent
from PyQt6.QtGui import QPixmap, QColor, QPainter, QImage, QPen, QBrush, QFont


# Scientific Imports
import matplotlib.pyplot as plt

# --- IMPORT YOUR SOURCE FILE ---
try:
    import BatchProcess as bp
except ImportError:
    print("Error: Could not import 'BatchProcess.py'. Make sure it is in the same directory.")
    sys.exit(1)

# Optional OCR support
try:
    import pytesseract
    from PIL import Image as PILImage
    HAS_OCR = True
    # Set Tesseract binary path on Windows if not in PATH
    _tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(_tess_path):
        pytesseract.pytesseract.tesseract_cmd = _tess_path
except ImportError:
    HAS_OCR = False


# ==========================================
# 0. HELPER CLASSES
# ==========================================

class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""
    clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.image_path = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if self.image_path:
            self.clicked.emit(self.image_path)
        super().mousePressEvent(event)


class ResultCard(QWidget):
    """
    A Compound Widget that holds:
    1. Clickable Image
    2. Filename/Condition Label
    """
    card_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # 1. Image Area
        self.img_lbl = ClickableLabel()
        self.img_lbl.setFixedSize(200, 140)
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_lbl.setObjectName("imgSlot")
        self.img_lbl.setText("Waiting...")
        self.img_lbl.clicked.connect(self.emit_click)

        # 2. Text Label
        self.text_lbl = QLabel("")
        self.text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_lbl.setStyleSheet("color: #aaa; font-size: 11px; font-weight: bold;")
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setFixedWidth(200)

        self.layout.addWidget(self.img_lbl)
        self.layout.addWidget(self.text_lbl)
        self.layout.addStretch()

    def emit_click(self, path):
        self.card_clicked.emit(path)

    def set_data(self, img_path, text, is_error=False):
        self.img_lbl.image_path = img_path

        if is_error:
            self.img_lbl.setText("ERROR")
            self.img_lbl.setStyleSheet(
                "border: 2px solid #ff5555; color: #ff5555; background-color: #1b1e2b; border-radius: 10px;")
            self.text_lbl.setText(text)
            self.text_lbl.setStyleSheet("color: #ff5555; font-size: 11px;")
        else:
            pix = QPixmap(img_path)
            if not pix.isNull():
                self.img_lbl.setPixmap(pix.scaled(
                    self.img_lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            self.img_lbl.setStyleSheet("border: 2px solid #50fa7b; background-color: #1b1e2b; border-radius: 10px;")
            self.text_lbl.setText(text)
            self.text_lbl.setStyleSheet("color: #e0e0e0; font-size: 11px;")

    def reset(self):
        self.img_lbl.clear()
        self.img_lbl.setText("Waiting...")
        self.img_lbl.image_path = None
        self.img_lbl.setStyleSheet(
            "border: 2px dashed #363b52; background-color: #1b1e2b; border-radius: 10px; color: #555;")
        self.text_lbl.setText("")


class ImageWindow(QMainWindow):
    """A separate window to view the image scaled to fit."""

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.setWindowTitle(os.path.basename(image_path))
        self.resize(1000, 700)
        self.setStyleSheet("background-color: #1b1e2b;")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none;")
        self.setCentralWidget(scroll_area)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: transparent;")
        self.lbl_image.setScaledContents(False)  # We'll handle scaling manually

        # Load original pixmap
        self.original_pixmap = QPixmap(image_path)
        if not self.original_pixmap.isNull():
            # Scale to fit window initially
            self.scale_image_to_fit()

        scroll_area.setWidget(self.lbl_image)

    def scale_image_to_fit(self):
        """Scale image to fit window while maintaining aspect ratio"""
        if self.original_pixmap.isNull():
            return

        # Get available size (window size minus margins)
        available_size = self.size()
        available_width = available_size.width() - 40  # Leave some margin
        available_height = available_size.height() - 80  # Leave some margin

        # Scale pixmap to fit while maintaining aspect ratio
        scaled_pixmap = self.original_pixmap.scaled(
            available_width,
            available_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_image.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Handle window resize to rescale image"""
        super().resizeEvent(event)
        self.scale_image_to_fit()


# ==========================================
# 1. ANALYSIS WORKER
# ==========================================
class WorkerSignals(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str, str)


class AnalysisWorker(QRunnable):
    def __init__(self, file_path, config, output_dir=None):
        super().__init__()
        self.file_path = Path(file_path)
        self.config = config
        self.output_dir = Path(output_dir) if output_dir else self.file_path.parent
        self.signals = WorkerSignals()

    def run(self):
        try:
            local_cfg = copy.copy(self.config)
            local_cfg.csv_path = str(self.file_path)

            if local_cfg.stim_preset_infer_from_name:
                bp.apply_inferred_stim_preset(local_cfg, name_hint=self.file_path.name)

            # Create file-specific output folder
            file_output_dir = self.output_dir / self.file_path.stem
            file_output_dir.mkdir(parents=True, exist_ok=True)

            # Set all output paths
            local_cfg.out_fig = str(file_output_dir / "deltaF_F_plot_all.png")
            local_cfg.out_csv = str(file_output_dir / "dff_table.csv")
            local_cfg.out_spike_csv = str(file_output_dir / "spike_summary.csv")
            local_cfg.out_spike_stats_csv = str(file_output_dir / "spike_baseline_stats.csv")
            local_cfg.out_spike_latency_stats_csv = str(file_output_dir / "spike_latency_stats.csv")
            local_cfg.out_spike_latency_detailed_csv = str(file_output_dir / "spike_latency_detailed.csv")
            local_cfg.out_fig_spiking_only = str(file_output_dir / "deltaF_F_spiking_only.png")

            # Run full analysis pipeline (this saves all outputs)
            print(f"\n{'='*60}")
            print(f"Processing: {self.file_path.name}")
            print(f"Spike latency calculation: {'ENABLED' if local_cfg.calculate_spike_latencies else 'DISABLED'}")
            if not local_cfg.calculate_spike_latencies:
                print("WARNING: Spike latency is DISABLED - no latency files will be created!")
                print("To enable: Go to Settings -> Check 'Calculate spike latencies'")
            print(f"Output folder: {file_output_dir}")
            print(f"Stimulation windows: {local_cfg.stim_windows}")
            print(f"{'='*60}\n")

            dff_table, fig_all, fig_spk = bp.run(local_cfg)

            # Verify latency files were created if enabled
            if local_cfg.calculate_spike_latencies:
                latency_file = file_output_dir / "spike_latency_detailed.csv"
                if latency_file.exists():
                    print(f"[OK] Spike latency file created: {latency_file}")
                else:
                    print(f"[WARNING] Spike latency file NOT created (no valid spikes found)")

            plt.close(fig_all)
            if fig_spk is not None:
                plt.close(fig_spk)

            self.signals.finished.emit(str(self.file_path), local_cfg.out_fig)

        except Exception as e:
            err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
            self.signals.error.emit(str(self.file_path), err_msg)


# ==========================================
# 2. SETTINGS PAGE
# ==========================================
class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.batch_ref = None  # set by MainWindow after both pages exist
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        # Title row with save/load buttons
        title_row = QHBoxLayout()
        lbl_title = QLabel("Advanced Configuration")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        title_row.addWidget(lbl_title)
        title_row.addStretch()

        self.btn_save_config = QPushButton("Save Config")
        self.btn_save_config.setFixedHeight(32)
        self.btn_save_config.setFixedWidth(110)
        self.btn_save_config.clicked.connect(self.save_config)

        self.btn_load_config = QPushButton("Load Config")
        self.btn_load_config.setFixedHeight(32)
        self.btn_load_config.setFixedWidth(110)
        self.btn_load_config.clicked.connect(self.load_config)

        title_row.addWidget(self.btn_save_config)
        title_row.addWidget(self.btn_load_config)
        layout.addLayout(title_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)

        # --- Group 1: File & ROI ---
        grp_roi = QGroupBox("File Structure")
        form_roi = QFormLayout()

        self.inputs['roi_key'] = QLineEdit("ROI")
        self.inputs['time_col'] = QLineEdit("Axis [s]")
        self.inputs['skip_row'] = QCheckBox("Skip First Row")
        self.inputs['skip_row'].setChecked(True)

        form_roi.addRow("ROI Search Key:", self.inputs['roi_key'])
        form_roi.addRow("Time Column:", self.inputs['time_col'])
        form_roi.addRow("", self.inputs['skip_row'])

        grp_roi.setLayout(form_roi)
        content_layout.addWidget(grp_roi)

        # --- Group 2: Baseline & Calculation ---
        grp_calc = QGroupBox("Baseline & Calculation")
        form_calc = QFormLayout()

        self.inputs['base_start'] = QSpinBox()
        self.inputs['base_start'].setRange(0, 5000)
        self.inputs['base_start'].setValue(10)

        self.inputs['base_end'] = QSpinBox()
        self.inputs['base_end'].setRange(0, 5000)
        self.inputs['base_end'].setValue(20)

        self.inputs['base_window'] = QDoubleSpinBox()
        self.inputs['base_window'].setRange(1.0, 500.0)
        self.inputs['base_window'].setValue(15.0)
        self.inputs['base_window'].setSuffix(" s")

        self.inputs['percentile'] = QDoubleSpinBox()
        self.inputs['percentile'].setRange(1.0, 100.0)
        self.inputs['percentile'].setValue(8.0)
        self.inputs['percentile'].setSuffix(" %")

        form_calc.addRow("Baseline Index Start:", self.inputs['base_start'])
        form_calc.addRow("Baseline Index End:", self.inputs['base_end'])
        form_calc.addRow("Window Half-Size:", self.inputs['base_window'])
        form_calc.addRow("Percentile:", self.inputs['percentile'])

        grp_calc.setLayout(form_calc)
        content_layout.addWidget(grp_calc)

        # --- Group 2b: Shared Baseline Options ---
        grp_shared_base = QGroupBox("Shared Baseline Options")
        form_shared_base = QFormLayout()

        self.inputs['baseline_mode'] = QComboBox()
        self.inputs['baseline_mode'].addItems([
            "Standard (per-file)",
            "Shared from Control files",
            "Shared per Condition"
        ])
        self.inputs['baseline_mode'].setCurrentIndex(0)

        self.inputs['baseline_start_frame'] = QSpinBox()
        self.inputs['baseline_start_frame'].setRange(0, 1000)
        self.inputs['baseline_start_frame'].setValue(10)

        self.inputs['baseline_end_frame'] = QSpinBox()
        self.inputs['baseline_end_frame'].setRange(1, 1000)
        self.inputs['baseline_end_frame'].setValue(30)  # Changed default to 30

        self.inputs['control_pattern'] = QLineEdit("Ctrl1")  # Changed default to "Ctrl1"

        form_shared_base.addRow("Baseline Mode:", self.inputs['baseline_mode'])
        form_shared_base.addRow("Shared Start Frame:", self.inputs['baseline_start_frame'])
        form_shared_base.addRow("Shared End Frame:", self.inputs['baseline_end_frame'])
        form_shared_base.addRow("Control File Pattern:", self.inputs['control_pattern'])

        info_label = QLabel(
            "<small><b>Standard:</b> Each file uses its own baseline<br>"
            "<b>Shared from Control:</b> Use Ctrl files' baseline for all files<br>"
            "<b>Shared per Condition:</b> Use first file of each condition as baseline</small>"
        )
        info_label.setStyleSheet("color: #aaa; padding: 5px;")
        info_label.setWordWrap(True)
        form_shared_base.addRow("", info_label)

        grp_shared_base.setLayout(form_shared_base)
        content_layout.addWidget(grp_shared_base)

        # --- Group 3: Advanced Spike Detection ---
        grp_spike = QGroupBox("Advanced Spike Detection")
        form_spike = QFormLayout()

        self.inputs['min_dist'] = QDoubleSpinBox()
        self.inputs['min_dist'].setValue(3.0)  # Changed default to 3.0
        self.inputs['min_dist'].setSpecialValueText("None")

        self.inputs['width_thr'] = QDoubleSpinBox()
        self.inputs['width_thr'].setRange(0.01, 10.0)
        self.inputs['width_thr'].setValue(2.0)  # Changed default to 2.0
        self.inputs['width_thr'].setSingleStep(0.1)

        # Changed from checkbox to combobox for exclude stim options
        self.inputs['exclude_stim'] = QComboBox()
        self.inputs['exclude_stim'].addItems([
            "Don't exclude spikes in stim windows",
            "Exclude all spikes in stim windows",
            "Exclude only in blue files"
        ])
        self.inputs['exclude_stim'].setCurrentIndex(0)  # Default: don't exclude

        self.inputs['calc_latencies'] = QCheckBox("Calculate spike latencies")
        self.inputs['calc_latencies'].setChecked(True)  # Default to enabled
        self.inputs['calc_latencies'].setStyleSheet("font-weight: bold; color: #ffa500;")

        # Add status label (default to enabled since checkbox is checked)
        self.latency_status_label = QLabel("ENABLED - Latency files will be created")
        self.latency_status_label.setStyleSheet("color: #5fd75f; font-size: 11px; font-weight: bold; margin-left: 20px;")
        self.inputs['calc_latencies'].toggled.connect(self.update_latency_status)

        self.inputs['latency_method'] = QComboBox()
        self.inputs['latency_method'].addItem("Nearest Latency", "nearest")
        self.inputs['latency_method'].addItem("First-spike Latency", "first_spike")
        self.inputs['latency_method'].addItem("Stim Onset Latency", "stim_onset")
        self.inputs['latency_method'].addItem("GLM (Point-process)", "glm")
        self.inputs['latency_method'].setCurrentIndex(0)

        self.inputs['max_latency_window'] = QDoubleSpinBox()
        self.inputs['max_latency_window'].setRange(0.0, 100.0)
        self.inputs['max_latency_window'].setValue(0.0)
        self.inputs['max_latency_window'].setSpecialValueText("None")
        self.inputs['max_latency_window'].setSuffix(" s")

        form_spike.addRow("Min Spike Distance (s):", self.inputs['min_dist'])
        form_spike.addRow("Min Width (s):", self.inputs['width_thr'])
        form_spike.addRow("Exclude Spikes in Stim:", self.inputs['exclude_stim'])
        form_spike.addRow("", self.inputs['calc_latencies'])
        form_spike.addRow("", self.latency_status_label)
        form_spike.addRow("Latency Method:", self.inputs['latency_method'])
        form_spike.addRow("Max Latency Window (s):", self.inputs['max_latency_window'])

        grp_spike.setLayout(form_spike)
        content_layout.addWidget(grp_spike)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

    def update_latency_status(self, checked):
        """Update the visual status indicator for spike latency"""
        if checked:
            self.latency_status_label.setText("✓ ENABLED - Latency files will be created")
            self.latency_status_label.setStyleSheet("color: #5fd75f; font-size: 11px; font-weight: bold; margin-left: 20px;")
        else:
            self.latency_status_label.setText("⚠️ DISABLED - No latency files will be created")
            self.latency_status_label.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold; margin-left: 20px;")

    def _collect_config_dict(self):
        """Collect all configuration values into a serialisable dict."""
        cfg = {}

        # --- Settings page inputs ---
        s = self.inputs
        cfg['roi_key'] = s['roi_key'].text()
        cfg['time_col'] = s['time_col'].text()
        cfg['skip_row'] = s['skip_row'].isChecked()

        cfg['base_start'] = s['base_start'].value()
        cfg['base_end'] = s['base_end'].value()
        cfg['base_window'] = s['base_window'].value()
        cfg['percentile'] = s['percentile'].value()

        cfg['baseline_mode'] = s['baseline_mode'].currentIndex()
        cfg['baseline_start_frame'] = s['baseline_start_frame'].value()
        cfg['baseline_end_frame'] = s['baseline_end_frame'].value()
        cfg['control_pattern'] = s['control_pattern'].text()

        cfg['min_dist'] = s['min_dist'].value()
        cfg['width_thr'] = s['width_thr'].value()
        cfg['exclude_stim'] = s['exclude_stim'].currentIndex()
        cfg['calc_latencies'] = s['calc_latencies'].isChecked()
        cfg['latency_method'] = s['latency_method'].currentIndex()
        cfg['max_latency_window'] = s['max_latency_window'].value()

        # --- Quick config inputs (from BatchAnalysisPage) ---
        if self.batch_ref is not None:
            b = self.batch_ref.inputs
            cfg['preset'] = b['preset'].text()
            cfg['infer_name'] = b['infer_name'].isChecked()
            cfg['sigma'] = b['sigma'].value()
            cfg['bg_col'] = b['bg_col'].text()
            cfg['auto_ylim'] = b['auto_ylim'].isChecked()
            cfg['ylim_max'] = b['ylim_max'].value()

        return cfg

    def _apply_config_dict(self, cfg):
        """Apply a config dict to all GUI widgets."""
        s = self.inputs

        # --- Settings page ---
        if 'roi_key' in cfg:
            s['roi_key'].setText(cfg['roi_key'])
        if 'time_col' in cfg:
            s['time_col'].setText(cfg['time_col'])
        if 'skip_row' in cfg:
            s['skip_row'].setChecked(cfg['skip_row'])

        if 'base_start' in cfg:
            s['base_start'].setValue(cfg['base_start'])
        if 'base_end' in cfg:
            s['base_end'].setValue(cfg['base_end'])
        if 'base_window' in cfg:
            s['base_window'].setValue(cfg['base_window'])
        if 'percentile' in cfg:
            s['percentile'].setValue(cfg['percentile'])

        if 'baseline_mode' in cfg:
            s['baseline_mode'].setCurrentIndex(cfg['baseline_mode'])
        if 'baseline_start_frame' in cfg:
            s['baseline_start_frame'].setValue(cfg['baseline_start_frame'])
        if 'baseline_end_frame' in cfg:
            s['baseline_end_frame'].setValue(cfg['baseline_end_frame'])
        if 'control_pattern' in cfg:
            s['control_pattern'].setText(cfg['control_pattern'])

        if 'min_dist' in cfg:
            s['min_dist'].setValue(cfg['min_dist'])
        if 'width_thr' in cfg:
            s['width_thr'].setValue(cfg['width_thr'])
        if 'exclude_stim' in cfg:
            s['exclude_stim'].setCurrentIndex(cfg['exclude_stim'])
        if 'calc_latencies' in cfg:
            s['calc_latencies'].setChecked(cfg['calc_latencies'])
        if 'latency_method' in cfg:
            s['latency_method'].setCurrentIndex(cfg['latency_method'])
        if 'max_latency_window' in cfg:
            s['max_latency_window'].setValue(cfg['max_latency_window'])

        # --- Quick config ---
        if self.batch_ref is not None:
            b = self.batch_ref.inputs
            if 'preset' in cfg:
                b['preset'].setText(cfg['preset'])
            if 'infer_name' in cfg:
                b['infer_name'].setChecked(cfg['infer_name'])
            if 'sigma' in cfg:
                b['sigma'].setValue(cfg['sigma'])
            if 'bg_col' in cfg:
                b['bg_col'].setText(cfg['bg_col'])
            if 'auto_ylim' in cfg:
                b['auto_ylim'].setChecked(cfg['auto_ylim'])
            if 'ylim_max' in cfg:
                b['ylim_max'].setValue(cfg['ylim_max'])

    def save_config(self):
        """Save current configuration to a JSON file."""
        import json
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration",
            "nmj_config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            cfg = self._collect_config_dict()
            with open(path, 'w') as f:
                json.dump(cfg, f, indent=2)
            QMessageBox.information(self, "Success", f"Configuration saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config:\n{e}")

    def load_config(self):
        """Load configuration from a JSON file."""
        import json
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, 'r') as f:
                cfg = json.load(f)
            self._apply_config_dict(cfg)
            QMessageBox.information(self, "Success",
                                    f"Configuration loaded from:\n{path}\n\n"
                                    f"{len(cfg)} settings applied.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config:\n{e}")


# ==========================================
# 3. BATCH ANALYSIS PAGE
# ==========================================
class BatchAnalysisPage(QWidget):
    def __init__(self, settings_page_ref):
        super().__init__()
        self.settings_ref = settings_page_ref
        self.threadpool = QThreadPool()
        self.file_paths = []
        self.processed_count = 0
        self.result_cards = []  # List of ResultCard widgets
        self.popups = []

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setHandleWidth(10)
        main_layout.addWidget(top_splitter, stretch=2)

        # 1. FILE CARD
        card_files = QFrame()
        card_files.setObjectName("card")
        card_files_layout = QVBoxLayout(card_files)

        lbl_files = QLabel("1. Data Files")
        lbl_files.setObjectName("cardTitle")

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        btn_box = QHBoxLayout()
        self.btn_add = QPushButton("+ Add CSV")
        self.btn_add.clicked.connect(self.add_files)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("dangerBtn")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_box.addWidget(self.btn_add)
        btn_box.addWidget(self.btn_clear)

        card_files_layout.addWidget(lbl_files)
        card_files_layout.addLayout(btn_box)
        card_files_layout.addWidget(self.file_list)

        top_splitter.addWidget(card_files)

        # 2. CONFIG CARD
        card_config = QFrame()
        card_config.setObjectName("card")
        card_config_layout = QVBoxLayout(card_config)

        lbl_config = QLabel("2. Quick Configuration")
        lbl_config.setObjectName("cardTitle")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(10, 10, 10, 10)

        self.inputs = {}

        # --- Page 1 Inputs ---
        self.inputs['preset'] = QLineEdit("20s")
        self.inputs['infer_name'] = QCheckBox("Infer from Filename")
        self.inputs['infer_name'].setChecked(True)
        self.inputs['sigma'] = QDoubleSpinBox()
        self.inputs['sigma'].setValue(5.0)

        self.inputs['bg_col'] = QLineEdit("ROI.01 []")

        self.inputs['auto_ylim'] = QCheckBox("Use Auto Y-Limits")
        self.inputs['auto_ylim'].setChecked(True)  # Changed default to True
        self.inputs['auto_ylim'].toggled.connect(self.toggle_ylim)

        self.inputs['ylim_max'] = QDoubleSpinBox()
        self.inputs['ylim_max'].setRange(0.01, 100.0)
        self.inputs['ylim_max'].setValue(0.3)
        self.inputs['ylim_max'].setSingleStep(0.1)

        form.addRow("Stim Preset:", self.inputs['preset'])
        form.addRow("", self.inputs['infer_name'])
        form.addRow("Spike Sigma:", self.inputs['sigma'])

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        form.addRow(line)

        form.addRow("BG Column:", self.inputs['bg_col'])
        form.addRow("", self.inputs['auto_ylim'])
        form.addRow("Max Y-Limit:", self.inputs['ylim_max'])

        card_config_layout.addWidget(lbl_config)
        card_config_layout.addLayout(form)
        card_config_layout.addStretch()

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.btn_run = QPushButton("START BATCH")
        self.btn_run.setObjectName("actionBtn")
        self.btn_run.setMinimumHeight(50)
        self.btn_run.clicked.connect(self.run_analysis)

        card_config_layout.addWidget(self.progress)
        card_config_layout.addWidget(self.btn_run)

        top_splitter.addWidget(card_config)
        top_splitter.setSizes([400, 600])

        # 3. RESULTS DASHBOARD
        card_results = QFrame()
        card_results.setObjectName("card")
        card_results_layout = QVBoxLayout(card_results)

        lbl_res = QLabel("3. Results Dashboard")
        lbl_res.setObjectName("cardTitle")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(15)
        scroll.setWidget(grid_widget)

        # Generate Cards instead of just labels
        self.result_cards = []
        for r in range(5):
            for c in range(6):
                card = ResultCard()
                card.card_clicked.connect(self.open_image_viewer)
                self.grid_layout.addWidget(card, r, c)
                self.result_cards.append(card)

        card_results_layout.addWidget(lbl_res)
        card_results_layout.addWidget(scroll)

        main_layout.addWidget(card_results, stretch=3)

    # -- Logic Methods --
    def toggle_ylim(self, checked):
        self.inputs['ylim_max'].setEnabled(not checked)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select CSV", "", "CSV (*.csv)")
        for f in files:
            if f not in self.file_paths:
                self.file_paths.append(f)
                self.file_list.addItem(os.path.basename(f))

    def clear_files(self):
        self.file_paths = []
        self.file_list.clear()
        self.reset_grid()

    def reset_grid(self):
        for card in self.result_cards:
            card.reset()

    def get_config(self):
        try:
            cfg = bp.Config()

            cfg.stim_preset = self.inputs['preset'].text()
            cfg.stim_preset_infer_from_name = self.inputs['infer_name'].isChecked()
            cfg.spike_z_sigma = self.inputs['sigma'].value()
            cfg.bg_column_name = self.inputs['bg_col'].text()

            cfg.use_auto_ylim = self.inputs['auto_ylim'].isChecked()
            if not cfg.use_auto_ylim:
                cfg.ylim_max = self.inputs['ylim_max'].value()
                cfg.ylim_min = 0.0

            s_in = self.settings_ref.inputs
            cfg.roi_key = s_in['roi_key'].text()
            cfg.time_col = s_in['time_col'].text()
            cfg.skip_first_row = s_in['skip_row'].isChecked()

            cfg.baseline_index_start = s_in['base_start'].value()
            cfg.baseline_index_end = s_in['base_end'].value()
            cfg.baseline_window_half_s = s_in['base_window'].value()
            cfg.baseline_percentile = s_in['percentile'].value()

            min_dist = s_in['min_dist'].value()
            cfg.min_spike_distance_s = min_dist if min_dist > 0 else None
            cfg.width_threshold_s = s_in['width_thr'].value()

            # Map combobox index to exclude mode
            exclude_modes = ["none", "all", "blue"]
            cfg.exclude_spikes_in_stim = exclude_modes[s_in['exclude_stim'].currentIndex()]

            cfg.calculate_spike_latencies = s_in['calc_latencies'].isChecked()
            cfg.latency_method = s_in['latency_method'].currentData()
            max_lat = s_in['max_latency_window'].value()
            cfg.max_latency_window_s = max_lat if max_lat > 0 else None

            # Shared baseline options
            baseline_mode_idx = s_in['baseline_mode'].currentIndex()
            baseline_modes = ["standard", "shared_control", "shared_per_condition"]
            cfg.baseline_mode = baseline_modes[baseline_mode_idx]
            cfg.shared_baseline_start_frame = s_in['baseline_start_frame'].value()
            cfg.shared_baseline_end_frame = s_in['baseline_end_frame'].value()
            cfg.control_file_pattern = s_in['control_pattern'].text()

            presets = {
                "20s": [(30, 50), (80, 100), (130, 150)],
                "10s": [(30, 40), (70, 80), (110, 120)],
                "5s": [(30, 35), (65, 70), (100, 105)]
            }
            if cfg.stim_preset in presets:
                cfg.stim_windows = presets[cfg.stim_preset]

            return cfg
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            traceback.print_exc()
            return None

    def run_analysis(self):
        if not self.file_paths: return
        cfg = self.get_config()
        if not cfg: return

        # CHECK: Warn user if spike latency is disabled
        if not cfg.calculate_spike_latencies:
            reply = QMessageBox.warning(
                self,
                "Spike Latency Disabled",
                "⚠️ Spike latency calculation is currently DISABLED.\n\n"
                "No spike_latency_*.csv files will be created.\n\n"
                "To enable:\n"
                "1. Go to Settings page\n"
                "2. Check ☑ 'Calculate spike latencies'\n"
                "3. Return here and click START BATCH again\n\n"
                "Do you want to continue without spike latency?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Create timestamped output folder
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use first file's parent directory as base
        base_dir = Path(self.file_paths[0]).parent
        output_dir = base_dir / f"analysis_output_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.current_output_dir = output_dir
        print(f"\nCreated output directory: {output_dir}")
        print(f"Spike latency calculation: {'ENABLED ✓' if cfg.calculate_spike_latencies else 'DISABLED ✗'}")
        print(f"Baseline mode: {cfg.baseline_mode}")

        # Compute shared baseline if needed
        if cfg.baseline_mode == "shared_control":
            print("\nComputing shared baseline from control files...")
            control_files = bp.identify_control_files(self.file_paths, cfg.control_file_pattern)
            if not control_files:
                QMessageBox.warning(
                    self,
                    "No Control Files Found",
                    f"No files matching pattern '{cfg.control_file_pattern}' found.\n\n"
                    f"Baseline mode: Shared from Control\n"
                    f"Files checked: {len(self.file_paths)}\n\n"
                    "Please check your control file pattern or select a different baseline mode."
                )
                return
            cfg.shared_baseline_values = bp.compute_shared_baseline_from_files(control_files, cfg)

        elif cfg.baseline_mode == "shared_per_condition":
            print("\nComputing shared baseline per condition...")
            first_files_dict = bp.identify_first_files_per_condition(self.file_paths)
            if not first_files_dict:
                QMessageBox.warning(
                    self,
                    "No First Files Found",
                    "Could not identify first files for any condition.\n\n"
                    "Files should end with '1' or have no number suffix.\n"
                    "Example: 20s1.csv, 10s1.csv, Ctrl.csv"
                )
                return
            first_files = list(first_files_dict.values())
            cfg.shared_baseline_values = bp.compute_shared_baseline_from_files(first_files, cfg)

        self.btn_run.setEnabled(False)
        self.btn_run.setText("PROCESSING...")
        self.reset_grid()
        self.processed_count = 0
        self.progress.setMaximum(len(self.file_paths))
        self.progress.setValue(0)

        for f_path in self.file_paths:
            worker = AnalysisWorker(f_path, cfg, output_dir)
            worker.signals.finished.connect(self.on_finished)
            worker.signals.error.connect(self.on_error)
            self.threadpool.start(worker)

    def on_finished(self, f_path, img_path):
        self.processed_count += 1
        self.progress.setValue(self.processed_count)

        idx = self.processed_count - 1
        if idx < len(self.result_cards):
            card = self.result_cards[idx]
            # Set image AND text (Filename)
            card.set_data(img_path, os.path.basename(f_path), is_error=False)

        if self.processed_count == len(self.file_paths): self.finish_all()

    def on_error(self, f_path, msg):
        self.processed_count += 1
        self.progress.setValue(self.processed_count)
        print(f"Error processing {f_path}: {msg}")

        idx = self.processed_count - 1
        if idx < len(self.result_cards):
            card = self.result_cards[idx]
            card.set_data(None, os.path.basename(f_path), is_error=True)

        if self.processed_count == len(self.file_paths): self.finish_all()

    def finish_all(self):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("START BATCH")

    def open_image_viewer(self, image_path):
        viewer = ImageWindow(image_path)
        viewer.show()
        self.popups.append(viewer)


# ==========================================
# 4. SPIKE LATENCY REVIEW PAGE
# ==========================================
class SpikeLatencyReviewPage(QWidget):
    """
    Page for reviewing individual spike latencies with plots.
    Users can select/deselect spikes to include in final analysis.
    """
    @staticmethod
    def extract_condition_group(condition_name):
        """Extract condition group from condition name.

        Ctrl / Ctrl1 → 'Ctrl'  (no-light control)
        Ctrl2, Ctrl3, … → 'Far Light Control'  (second control group)
        Other trailing digits are stripped to form the group name.
        """
        import re
        # Handle Ctrl variants: Ctrl and Ctrl1 stay as "Ctrl",
        # Ctrl2+ are "Far Light Control"
        ctrl_match = re.match(r'^Ctrl(\d*)$', condition_name, re.IGNORECASE)
        if ctrl_match:
            num = ctrl_match.group(1)
            if num == '' or num == '1':
                return 'Ctrl'
            return 'Far Light Control'
        match = re.match(r'^([a-zA-Z0-9]+?)\d+$', condition_name)
        if match:
            return match.group(1)
        match = re.match(r'^(\d+)-\d+$', condition_name)
        if match:
            return match.group(1)
        return condition_name

    # ── grouped colour defaults ───────────────────────────────────────────
    #   Conditions within the same experimental variable share a hue family
    #   so viewers can instantly see which parameter is being varied.
    _COND_GROUP_COLORS = {
        # Duration group  →  blue ramp (light → dark)
        "5s":               "#9ECAE1",   # light steel-blue
        "10s":              "#3182BD",   # medium cobalt-blue
        "20s":              "#08306B",   # deep navy

        # Power group  →  orange-red ramp
        "1mW":              "#FDAE6B",   # pale amber
        "2mW":              "#D94801",   # burnt-orange

        # Frequency group  →  green ramp
        "2Hz":              "#74C476",   # medium green
        "5Hz":              "#005A32",   # deep forest-green

        # Control group  →  neutral greys
        "Ctrl":             "#636363",   # dark charcoal-grey
        "Far Light Control":"#BDBDBD",   # light silver-grey
    }
    # Fallback colours for any condition not in the table above
    _FALLBACK_COLORS = [
        "#7B4FD6", "#C2185B", "#00838F", "#F57F17",
        "#4527A0", "#2E7D32", "#AD1457", "#0277BD",
    ]

    def __init__(self):
        super().__init__()
        self.latency_data = []  # List of dicts with spike info
        self.dff_data = None  # DataFrame with ΔF/F traces
        self.checkboxes = []
        self.spike_widgets = []  # Parallel list of QFrame widgets for visibility toggling
        self.excluded_hidden = False  # Track hide/show state
        # User-overridden colours (persisted only for the session)
        self._custom_cond_colors: dict = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Title + action buttons row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        lbl_title = QLabel("Spike Latency Review")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        lbl_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(lbl_title, 1)

        self.btn_load = QPushButton("Load Data")
        self.btn_load.setFixedHeight(32)
        self.btn_load.clicked.connect(self.load_latency_data)

        self.btn_append_data = QPushButton("Append Data")
        self.btn_append_data.setFixedHeight(32)
        self.btn_append_data.clicked.connect(self.append_latency_data)
        self.btn_append_data.setEnabled(False)

        header_layout.addWidget(self.btn_load)
        header_layout.addWidget(self.btn_append_data)
        layout.addLayout(header_layout)

        # Main horizontal split: left filters | right spike list
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        # ===== LEFT PANEL: Filters =====
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMaximumWidth(320)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        # --- Condition Filter ---
        grp_cond = QGroupBox("Filter by Condition")
        cond_layout = QVBoxLayout()
        cond_btn_layout = QHBoxLayout()
        btn_sel_all_cond = QPushButton("All")
        btn_sel_all_cond.setFixedHeight(26)
        btn_sel_all_cond.clicked.connect(lambda: self.list_conditions.selectAll())
        btn_desel_all_cond = QPushButton("None")
        btn_desel_all_cond.setFixedHeight(26)
        btn_desel_all_cond.clicked.connect(lambda: self.list_conditions.clearSelection())
        cond_btn_layout.addWidget(btn_sel_all_cond)
        cond_btn_layout.addWidget(btn_desel_all_cond)

        # Quick-select buttons
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(3)
        for pat in ["10s", "20s", "5s", "2Hz", "5Hz", "Ctrl"]:
            btn = QPushButton(pat)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 9px; padding: 1px 4px;")
            btn.clicked.connect(lambda _, p=pat: self._quick_select_conditions(p))
            quick_layout.addWidget(btn)

        self.list_conditions = QListWidget()
        self.list_conditions.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_conditions.setMinimumHeight(80)
        self.list_conditions.itemSelectionChanged.connect(self.apply_filters)
        cond_layout.addLayout(cond_btn_layout)
        cond_layout.addLayout(quick_layout)
        cond_layout.addWidget(self.list_conditions)
        grp_cond.setLayout(cond_layout)

        # --- ROI Filter ---
        grp_roi = QGroupBox("Filter by ROI")
        roi_layout = QVBoxLayout()
        roi_btn_layout = QHBoxLayout()
        btn_sel_all_roi = QPushButton("All")
        btn_sel_all_roi.setFixedHeight(26)
        btn_sel_all_roi.clicked.connect(lambda: self.list_rois.selectAll())
        btn_desel_all_roi = QPushButton("None")
        btn_desel_all_roi.setFixedHeight(26)
        btn_desel_all_roi.clicked.connect(lambda: self.list_rois.clearSelection())
        roi_btn_layout.addWidget(btn_sel_all_roi)
        roi_btn_layout.addWidget(btn_desel_all_roi)

        self.list_rois = QListWidget()
        self.list_rois.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_rois.setMinimumHeight(80)
        self.list_rois.itemSelectionChanged.connect(self.apply_filters)
        roi_layout.addLayout(roi_btn_layout)
        roi_layout.addWidget(self.list_rois)
        grp_roi.setLayout(roi_layout)

        # --- Spike Actions ---
        grp_actions = QGroupBox("Spike Selection")
        actions_layout = QVBoxLayout()

        self.btn_select_all = QPushButton("Check All Visible")
        self.btn_select_all.setFixedHeight(30)
        self.btn_select_all.clicked.connect(self.select_all)

        self.btn_deselect_all = QPushButton("Uncheck All Visible")
        self.btn_deselect_all.setFixedHeight(30)
        self.btn_deselect_all.clicked.connect(self.deselect_all)

        self.btn_hide_excluded = QPushButton("Hide Excluded")
        self.btn_hide_excluded.setFixedHeight(30)
        self.btn_hide_excluded.clicked.connect(self.toggle_hide_excluded)
        self.btn_hide_excluded.setEnabled(False)

        self.btn_exclude_high_latency = QPushButton("Apply Exclusion Rules")
        self.btn_exclude_high_latency.setFixedHeight(30)
        self.btn_exclude_high_latency.clicked.connect(self.exclude_high_latency)
        self.btn_exclude_high_latency.setEnabled(False)

        # Rule 1: Exclude latency > max
        rule1_row = QHBoxLayout()
        self.chk_exclude_max = QCheckBox("Exclude latency >")
        self.chk_exclude_max.setChecked(True)
        self.chk_exclude_max.setStyleSheet("color: #ccc; font-size: 11px;")
        self.spin_max_latency_exclude = QDoubleSpinBox()
        self.spin_max_latency_exclude.setRange(0.1, 9999.0)
        self.spin_max_latency_exclude.setDecimals(1)
        self.spin_max_latency_exclude.setValue(60.0)
        self.spin_max_latency_exclude.setSuffix(" s")
        self.spin_max_latency_exclude.setFixedHeight(26)
        self.spin_max_latency_exclude.setFixedWidth(80)
        rule1_row.addWidget(self.chk_exclude_max)
        rule1_row.addWidget(self.spin_max_latency_exclude)
        rule1_row.addStretch()

        # Rule 2: Exclude latency in range (light leakage from next stim)
        rule2_row = QHBoxLayout()
        self.chk_exclude_range = QCheckBox("Exclude latency")
        self.chk_exclude_range.setChecked(True)
        self.chk_exclude_range.setStyleSheet("color: #ccc; font-size: 11px;")
        self.spin_range_lo = QDoubleSpinBox()
        self.spin_range_lo.setRange(0.0, 9999.0)
        self.spin_range_lo.setDecimals(1)
        self.spin_range_lo.setValue(20.0)
        self.spin_range_lo.setSuffix(" s")
        self.spin_range_lo.setFixedHeight(26)
        self.spin_range_lo.setFixedWidth(75)
        lbl_to = QLabel("–")
        lbl_to.setStyleSheet("color: #ccc; font-size: 11px;")
        self.spin_range_hi = QDoubleSpinBox()
        self.spin_range_hi.setRange(0.0, 9999.0)
        self.spin_range_hi.setDecimals(1)
        self.spin_range_hi.setValue(22.0)
        self.spin_range_hi.setSuffix(" s")
        self.spin_range_hi.setFixedHeight(26)
        self.spin_range_hi.setFixedWidth(75)
        rule2_row.addWidget(self.chk_exclude_range)
        rule2_row.addWidget(self.spin_range_lo)
        rule2_row.addWidget(lbl_to)
        rule2_row.addWidget(self.spin_range_hi)
        rule2_row.addStretch()

        self.btn_save = QPushButton("Save Filtered Data")
        self.btn_save.setFixedHeight(30)
        self.btn_save.clicked.connect(self.save_filtered_data)
        self.btn_save.setEnabled(False)

        actions_layout.addWidget(self.btn_select_all)
        actions_layout.addWidget(self.btn_deselect_all)
        actions_layout.addLayout(rule1_row)
        actions_layout.addLayout(rule2_row)
        actions_layout.addWidget(self.btn_exclude_high_latency)
        actions_layout.addWidget(self.btn_hide_excluded)
        actions_layout.addWidget(self.btn_save)
        grp_actions.setLayout(actions_layout)

        # --- Plot Settings ---
        grp_plot_settings = QGroupBox("Plot Settings")
        plot_settings_layout = QVBoxLayout()

        self.chk_auto_ylim = QCheckBox("Auto Y-Limit")
        self.chk_auto_ylim.setChecked(True)
        self.chk_auto_ylim.stateChanged.connect(self._toggle_ylim_mode)

        ylim_row = QHBoxLayout()
        self.lbl_ylim = QLabel("Y Max:")
        self.lbl_ylim.setStyleSheet("color: #888; font-size: 11px;")
        self.spin_ylim = QDoubleSpinBox()
        self.spin_ylim.setRange(0.01, 99999.0)
        self.spin_ylim.setDecimals(2)
        self.spin_ylim.setValue(100.0)
        self.spin_ylim.setSuffix("")
        self.spin_ylim.setFixedHeight(28)
        self.spin_ylim.setEnabled(False)
        ylim_row.addWidget(self.lbl_ylim)
        ylim_row.addWidget(self.spin_ylim)

        self.btn_refresh_ylim = QPushButton("Refresh Spike Plots")
        self.btn_refresh_ylim.setFixedHeight(28)
        self.btn_refresh_ylim.clicked.connect(self._refresh_spike_plots)
        self.btn_refresh_ylim.setEnabled(False)

        plot_settings_layout.addWidget(self.chk_auto_ylim)
        plot_settings_layout.addLayout(ylim_row)
        plot_settings_layout.addWidget(self.btn_refresh_ylim)
        grp_plot_settings.setLayout(plot_settings_layout)

        # --- Analysis ---
        grp_analysis = QGroupBox("Analysis")
        analysis_layout = QVBoxLayout()

        self.btn_summary = QPushButton("Summary Stats")
        self.btn_summary.setFixedHeight(30)
        self.btn_summary.clicked.connect(self.generate_summary_stats)
        self.btn_summary.setEnabled(False)

        self.btn_categorize_condition = QPushButton("Categorize by Condition")
        self.btn_categorize_condition.setFixedHeight(30)
        self.btn_categorize_condition.clicked.connect(self.categorize_by_condition)
        self.btn_categorize_condition.setEnabled(False)

        self.btn_categorize_roi = QPushButton("Categorize by ROI")
        self.btn_categorize_roi.setFixedHeight(30)
        self.btn_categorize_roi.clicked.connect(self.categorize_by_roi)
        self.btn_categorize_roi.setEnabled(False)

        self.btn_bar_plot = QPushButton("Latency Bar Plot")
        self.btn_bar_plot.setFixedHeight(30)
        self.btn_bar_plot.clicked.connect(self.generate_bar_plot_with_significance)
        self.btn_bar_plot.setEnabled(False)

        self.btn_spike_count_bar = QPushButton("Spike Count Bar Plot")
        self.btn_spike_count_bar.setFixedHeight(30)
        self.btn_spike_count_bar.clicked.connect(self.generate_spike_count_bar_plot)
        self.btn_spike_count_bar.setEnabled(False)

        self.btn_export_spike_count = QPushButton("Export Spike Count CSV")
        self.btn_export_spike_count.setFixedHeight(30)
        self.btn_export_spike_count.clicked.connect(self.export_spike_count_csv)
        self.btn_export_spike_count.setEnabled(False)

        self.btn_per_roi_condition = QPushButton("Per-ROI Condition Plot")
        self.btn_per_roi_condition.setFixedHeight(30)
        self.btn_per_roi_condition.clicked.connect(self.generate_per_roi_condition_plot)
        self.btn_per_roi_condition.setEnabled(False)

        self.btn_per_roi_spike_count = QPushButton("Per-ROI Spike Count Plot")
        self.btn_per_roi_spike_count.setFixedHeight(30)
        self.btn_per_roi_spike_count.clicked.connect(self.generate_per_roi_spike_count_plot)
        self.btn_per_roi_spike_count.setEnabled(False)

        self.btn_spike_amplitude = QPushButton("Spike Amplitude Plot")
        self.btn_spike_amplitude.setFixedHeight(30)
        self.btn_spike_amplitude.clicked.connect(self.generate_spike_amplitude_plot)
        self.btn_spike_amplitude.setEnabled(False)

        self.btn_per_roi_amplitude = QPushButton("Per-ROI Amplitude Plot")
        self.btn_per_roi_amplitude.setFixedHeight(30)
        self.btn_per_roi_amplitude.clicked.connect(self.generate_per_roi_amplitude_plot)
        self.btn_per_roi_amplitude.setEnabled(False)

        analysis_layout.addWidget(self.btn_summary)
        analysis_layout.addWidget(self.btn_categorize_condition)
        analysis_layout.addWidget(self.btn_categorize_roi)
        analysis_layout.addWidget(self.btn_bar_plot)
        analysis_layout.addWidget(self.btn_spike_count_bar)
        analysis_layout.addWidget(self.btn_export_spike_count)
        analysis_layout.addWidget(self.btn_per_roi_condition)
        analysis_layout.addWidget(self.btn_per_roi_spike_count)
        analysis_layout.addWidget(self.btn_spike_amplitude)
        analysis_layout.addWidget(self.btn_per_roi_amplitude)
        grp_analysis.setLayout(analysis_layout)

        # --- Publication Plots ---
        grp_pub = QGroupBox("Publication Plots")
        pub_layout = QVBoxLayout()

        self.btn_violin_latency = QPushButton("Violin Plot — Latency")
        self.btn_violin_latency.setFixedHeight(28)
        self.btn_violin_latency.clicked.connect(lambda: self._generate_violin_plot("latency"))
        self.btn_violin_latency.setEnabled(False)

        self.btn_violin_amplitude = QPushButton("Violin Plot — Amplitude")
        self.btn_violin_amplitude.setFixedHeight(28)
        self.btn_violin_amplitude.clicked.connect(lambda: self._generate_violin_plot("amplitude"))
        self.btn_violin_amplitude.setEnabled(False)

        self.btn_violin_count = QPushButton("Violin Plot — Event Count")
        self.btn_violin_count.setFixedHeight(28)
        self.btn_violin_count.clicked.connect(lambda: self._generate_violin_plot("event_count"))
        self.btn_violin_count.setEnabled(False)

        self.btn_roidetail_latency = QPushButton("ROI Detail — Latency")
        self.btn_roidetail_latency.setFixedHeight(28)
        self.btn_roidetail_latency.clicked.connect(lambda: self._generate_roi_detail_plot("latency"))
        self.btn_roidetail_latency.setEnabled(False)

        self.btn_roidetail_amplitude = QPushButton("ROI Detail — Amplitude")
        self.btn_roidetail_amplitude.setFixedHeight(28)
        self.btn_roidetail_amplitude.clicked.connect(lambda: self._generate_roi_detail_plot("amplitude"))
        self.btn_roidetail_amplitude.setEnabled(False)

        self.btn_roidetail_count = QPushButton("ROI Detail — Event Count")
        self.btn_roidetail_count.setFixedHeight(28)
        self.btn_roidetail_count.clicked.connect(lambda: self._generate_roi_detail_plot("event_count"))
        self.btn_roidetail_count.setEnabled(False)

        pub_layout.addWidget(self.btn_violin_latency)
        pub_layout.addWidget(self.btn_violin_amplitude)
        pub_layout.addWidget(self.btn_violin_count)
        pub_layout.addWidget(self.btn_roidetail_latency)
        pub_layout.addWidget(self.btn_roidetail_amplitude)
        pub_layout.addWidget(self.btn_roidetail_count)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #555;")
        pub_layout.addWidget(sep2)

        lbl_bar = QLabel("Colored Bar Plots (Boss Edition)")
        lbl_bar.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px 0px;")
        pub_layout.addWidget(lbl_bar)

        self.btn_barplot_latency = QPushButton("Bar Plot — Latency")
        self.btn_barplot_latency.setFixedHeight(28)
        self.btn_barplot_latency.clicked.connect(lambda: self._generate_pub_bar_plot("latency"))
        self.btn_barplot_latency.setEnabled(False)

        self.btn_barplot_amplitude = QPushButton("Bar Plot — Amplitude")
        self.btn_barplot_amplitude.setFixedHeight(28)
        self.btn_barplot_amplitude.clicked.connect(lambda: self._generate_pub_bar_plot("amplitude"))
        self.btn_barplot_amplitude.setEnabled(False)

        self.btn_barplot_count = QPushButton("Bar Plot — Event Count")
        self.btn_barplot_count.setFixedHeight(28)
        self.btn_barplot_count.clicked.connect(lambda: self._generate_pub_bar_plot("event_count"))
        self.btn_barplot_count.setEnabled(False)

        pub_layout.addWidget(self.btn_barplot_latency)
        pub_layout.addWidget(self.btn_barplot_amplitude)
        pub_layout.addWidget(self.btn_barplot_count)

        self.btn_edit_colors = QPushButton("Edit Condition Colors...")
        self.btn_edit_colors.setFixedHeight(28)
        self.btn_edit_colors.clicked.connect(self._open_color_editor)
        self.btn_edit_colors.setEnabled(False)
        pub_layout.addWidget(self.btn_edit_colors)
        grp_pub.setLayout(pub_layout)

        left_layout.addWidget(grp_cond)
        left_layout.addWidget(grp_roi)
        left_layout.addWidget(grp_actions)
        left_layout.addWidget(grp_plot_settings)
        left_layout.addWidget(grp_analysis)
        left_layout.addWidget(grp_pub)
        left_layout.addStretch()

        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)

        # ===== RIGHT PANEL: Spike list =====
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        self.lbl_status = QLabel("No data loaded")
        self.lbl_status.setStyleSheet("color: #aaa; font-size: 12px;")
        right_layout.addWidget(self.lbl_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.content_widget)
        right_layout.addWidget(scroll)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def load_latency_data(self):
        """Load spike latency data from all subfolders in analysis output directory"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Analysis Output Folder (e.g., analysis_output_YYYYMMDD_HHMMSS/)",
            ""
        )

        if not folder_path:
            return

        try:
            import pandas as pd
            import numpy as np

            parent_folder = Path(folder_path)

            # Find all subfolders
            subfolders = [f for f in parent_folder.iterdir() if f.is_dir()]

            if not subfolders:
                QMessageBox.critical(
                    self,
                    "No Subfolders Found",
                    f"No subfolders found in:\n{parent_folder}\n\n"
                    "Make sure you selected the correct analysis output folder."
                )
                return

            # Check for filtered file at parent level
            use_filtered = False
            filtered_file = parent_folder / "spike_latency_detailed_filtered.csv"
            if filtered_file.exists():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Filtered Data Available")
                msg_box.setText(
                    f"A filtered latency file was found:\n{filtered_file.name}\n\n"
                    "Would you like to load the filtered (previously reviewed) data\n"
                    "or the original raw data?"
                )
                btn_filtered = msg_box.addButton("Load Filtered", QMessageBox.ButtonRole.YesRole)
                btn_raw = msg_box.addButton("Load Raw", QMessageBox.ButtonRole.NoRole)
                msg_box.setDefaultButton(btn_filtered)
                msg_box.exec()
                if msg_box.clickedButton() == btn_filtered:
                    use_filtered = True

            print(f"\n{'='*60}")
            print(f"Loading spike latency data from: {parent_folder}")
            print(f"Mode: {'FILTERED' if use_filtered else 'RAW'}")
            print(f"Found {len(subfolders)} subfolders")
            print(f"{'='*60}\n")

            # Storage for all data
            all_latency_data = []
            all_dff_data = {}  # Dict mapping condition -> DataFrame
            loaded_conditions = []
            skipped_folders = []

            if use_filtered:
                # Load from single filtered CSV at parent level
                try:
                    df_filtered = pd.read_csv(filtered_file)
                    if df_filtered.empty:
                        QMessageBox.warning(self, "Warning",
                                            "Filtered file is empty. Loading raw data instead.")
                        use_filtered = False
                    else:
                        required_cols = ["ROI", "spike_time_s", "latency_s",
                                         "stim_window_start_s", "stim_window_end_s", "condition"]
                        if not all(col in df_filtered.columns for col in required_cols):
                            QMessageBox.warning(self, "Warning",
                                                "Filtered file has invalid columns. Loading raw data instead.")
                            use_filtered = False
                        else:
                            all_latency_data = df_filtered.to_dict('records')
                            loaded_conditions = list(df_filtered['condition'].unique())
                            print(f"[OK] Loaded {len(all_latency_data)} filtered spikes "
                                  f"from {len(loaded_conditions)} conditions")
                except Exception as e:
                    QMessageBox.warning(self, "Warning",
                                        f"Failed to load filtered file:\n{e}\n\nLoading raw data instead.")
                    use_filtered = False

            # Load dff_table.csv from all subfolders (always needed for amplitude lookup)
            for subfolder in subfolders:
                condition_name = subfolder.name
                dff_file = subfolder / "dff_table.csv"
                if dff_file.exists():
                    try:
                        all_dff_data[condition_name] = pd.read_csv(dff_file)
                    except Exception:
                        pass

            if not use_filtered:
                # Loop through all subfolders for raw latency data
                for subfolder in subfolders:
                    condition_name = subfolder.name
                    latency_file = subfolder / "spike_latency_detailed.csv"
                    dff_file = subfolder / "dff_table.csv"

                    # Check if required files exist
                    if not latency_file.exists():
                        print(f"[SKIP] {condition_name}: spike_latency_detailed.csv not found")
                        skipped_folders.append((condition_name, "latency file missing"))
                        continue

                    if not dff_file.exists():
                        print(f"[SKIP] {condition_name}: dff_table.csv not found")
                        skipped_folders.append((condition_name, "dff_table.csv missing"))
                        continue

                    # Load latency data
                    try:
                        df_latency = pd.read_csv(latency_file)

                        # Check if file is empty
                        if df_latency.empty:
                            print(f"[SKIP] {condition_name}: No spike latency data (empty file)")
                            skipped_folders.append((condition_name, "empty latency file"))
                            continue

                        # Validate columns
                        required_cols = ["ROI", "spike_time_s", "latency_s",
                                         "stim_window_start_s", "stim_window_end_s"]
                        if not all(col in df_latency.columns for col in required_cols):
                            print(f"[SKIP] {condition_name}: Invalid column format")
                            skipped_folders.append((condition_name, "invalid columns"))
                            continue

                        # Add condition name to each row
                        for row_dict in df_latency.to_dict('records'):
                            row_dict['condition'] = condition_name
                            all_latency_data.append(row_dict)

                        loaded_conditions.append(condition_name)
                        print(f"[OK] {condition_name}: Loaded {len(df_latency)} spikes")

                    except Exception as e:
                        print(f"[ERROR] {condition_name}: {str(e)}")
                        skipped_folders.append((condition_name, str(e)))
                        continue

            # Check if any data was loaded
            if not all_latency_data:
                error_msg = f"No valid spike latency data found in any subfolder.\n\n"
                error_msg += f"Checked {len(subfolders)} subfolders in:\n{parent_folder}\n\n"
                if skipped_folders:
                    error_msg += "Skipped folders:\n"
                    for cond, reason in skipped_folders:
                        error_msg += f"  • {cond}: {reason}\n"
                error_msg += "\nMake sure:\n"
                error_msg += "1. Spike latency calculation was ENABLED during processing\n"
                error_msg += "2. The analysis completed successfully\n"
                error_msg += "3. Files contain valid spike data"

                QMessageBox.critical(self, "No Data Loaded", error_msg)
                return

            # Store all data
            self.latency_data = all_latency_data
            self.dff_data_dict = all_dff_data  # Store as dict instead of single DataFrame
            self.csv_path = str(parent_folder)

            # Clear existing content
            self.clear_content()

            # Create spike review items
            for idx, row in enumerate(self.latency_data):
                item_widget = self.create_spike_item(idx, row)
                self.content_layout.addWidget(item_widget)
                self.spike_widgets.append(item_widget)

            # Populate filter lists
            self._populate_filter_lists()

            self.btn_save.setEnabled(True)
            self.btn_exclude_high_latency.setEnabled(True)
            self.btn_summary.setEnabled(True)
            self.btn_categorize_condition.setEnabled(True)
            self.btn_categorize_roi.setEnabled(True)
            self.btn_bar_plot.setEnabled(True)
            self.btn_spike_count_bar.setEnabled(True)
            self.btn_export_spike_count.setEnabled(True)
            self.btn_per_roi_condition.setEnabled(True)
            self.btn_per_roi_spike_count.setEnabled(True)
            self.btn_spike_amplitude.setEnabled(True)
            self.btn_per_roi_amplitude.setEnabled(True)
            self.btn_violin_latency.setEnabled(True)
            self.btn_violin_amplitude.setEnabled(True)
            self.btn_violin_count.setEnabled(True)
            self.btn_roidetail_latency.setEnabled(True)
            self.btn_roidetail_amplitude.setEnabled(True)
            self.btn_roidetail_count.setEnabled(True)
            self.btn_barplot_latency.setEnabled(True)
            self.btn_barplot_amplitude.setEnabled(True)
            self.btn_barplot_count.setEnabled(True)
            self.btn_edit_colors.setEnabled(True)
            self.btn_append_data.setEnabled(True)
            self.btn_hide_excluded.setEnabled(True)
            self.btn_refresh_ylim.setEnabled(True)

            data_type = "filtered" if use_filtered else "raw"
            status_msg = f"Loaded {len(all_latency_data)} {data_type} spike events from {len(loaded_conditions)} conditions"
            if skipped_folders:
                status_msg += f" ({len(skipped_folders)} skipped)"
            self.lbl_status.setText(status_msg)
            self.lbl_status.setStyleSheet("color: #5fd75f; font-size: 12px;")

            print(f"\n{'='*60}")
            print(f"Successfully loaded {len(all_latency_data)} {data_type} spike events")
            print(f"Conditions loaded: {', '.join(loaded_conditions)}")
            if skipped_folders:
                print(f"Skipped folders: {', '.join(cond for cond, _ in skipped_folders)}")
            print(f"{'='*60}\n")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")
            traceback.print_exc()

    def create_spike_item(self, idx, row):
        """Create a widget for a single spike with plot and checkbox"""
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        item = QFrame()
        item.setFrameShape(QFrame.Shape.Box)
        item.setStyleSheet("background-color: #1e222d; border: 1px solid #3a3f4b; border-radius: 8px; padding: 10px;")

        item_layout = QHBoxLayout(item)

        # Left side: Checkbox and info
        left_layout = QVBoxLayout()

        checkbox = QCheckBox(f"Include spike {idx + 1}")
        checkbox.setChecked(True)
        checkbox.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        self.checkboxes.append(checkbox)

        condition_name = row.get('condition', 'Unknown')
        info_text = f"""
        <b>Condition:</b> {condition_name}<br>
        <b>ROI:</b> {row['ROI']}<br>
        <b>Spike Time:</b> {row['spike_time_s']:.3f} s<br>
        <b>Latency:</b> {row['latency_s']:.3f} s<br>
        <b>Stim Window:</b> [{row['stim_window_start_s']:.1f}, {row['stim_window_end_s']:.1f}] s
        """

        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #ccc; font-size: 12px;")

        left_layout.addWidget(checkbox)
        left_layout.addWidget(info_label)
        left_layout.addStretch()

        # Right side: Plot with actual spike waveform
        plot_label = QLabel()
        plot_label.setFixedSize(450, 200)
        plot_label.setStyleSheet("background-color: #2a2e3a; border: 1px solid #3a3f4b; border-radius: 5px;")

        # Create visualization with actual ΔF/F trace
        try:
            fig, ax = plt.subplots(figsize=(4.5, 2), dpi=100)
            fig.patch.set_facecolor('#2a2e3a')
            ax.set_facecolor('#2a2e3a')

            stim_start = row['stim_window_start_s']
            stim_end = row['stim_window_end_s']
            spike_time = row['spike_time_s']
            roi_name = row['ROI']

            # Define time window to display
            # Fixed range: 10s before stim start, 80s after stim start (for comparison)
            time_range = [stim_start - 10, stim_start + 80]

            # Plot actual ΔF/F trace if data is available
            condition_name = row.get('condition', None)
            if condition_name and hasattr(self, 'dff_data_dict') and condition_name in self.dff_data_dict:
                dff_data = self.dff_data_dict[condition_name]
                time_col = "Time (s)"
                if time_col in dff_data.columns and roi_name in dff_data.columns:
                    time_data = dff_data[time_col].values
                    dff_values = dff_data[roi_name].values

                    # Filter to time window
                    mask = (time_data >= time_range[0]) & (time_data <= time_range[1])
                    time_plot = time_data[mask]
                    dff_plot = dff_values[mask]

                    if len(time_plot) > 0:
                        # Plot the actual ΔF/F trace
                        ax.plot(time_plot, dff_plot, color='#4a9eff', linewidth=1.5,
                                label='ΔF/F', zorder=1)

                        # Mark the spike point
                        spike_idx = np.argmin(np.abs(time_data - spike_time))
                        if mask[spike_idx]:
                            ax.plot(spike_time, dff_values[spike_idx], 'o',
                                    color='orange', markersize=8,
                                    markeredgecolor='black', markeredgewidth=1,
                                    label='Spike', zorder=3)

            # Draw stim window as shaded region
            ax.axvspan(stim_start, stim_end, color='red', alpha=0.2,
                       label='Stim Window', zorder=0)

            # Mark stim end
            ax.axvline(stim_end, color='red', linestyle='--', linewidth=1.5,
                       alpha=0.7, zorder=2)

            # Annotate latency with arrow
            y_pos = ax.get_ylim()[1] * 0.85
            ax.annotate('', xy=(spike_time, y_pos), xytext=(stim_end, y_pos),
                        arrowprops=dict(arrowstyle='<->', color='cyan', lw=2))
            ax.text((stim_end + spike_time) / 2, y_pos * 1.1,
                    f'Latency: {row["latency_s"]:.2f}s',
                    ha='center', color='cyan', fontsize=10, fontweight='bold')

            ax.set_xlim(time_range)
            # Apply manual Y-limit if set
            if not self.chk_auto_ylim.isChecked():
                ax.set_ylim(bottom=ax.get_ylim()[0], top=self.spin_ylim.value())
            ax.set_xlabel('Time (s)', color='white', fontsize=10)
            ax.set_ylabel('ΔF/F', color='white', fontsize=10)
            ax.tick_params(colors='white', labelsize=9)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('white')
            ax.spines['bottom'].set_color('white')
            ax.legend(loc='upper left', fontsize=8, framealpha=0.9,
                     facecolor='#2a2e3a', edgecolor='white')
            ax.grid(True, alpha=0.2, color='white')

            # Save to temporary file with unique name
            temp_path = Path(f"temp_spike_plot_{idx}.png")
            fig.savefig(temp_path, dpi=100, bbox_inches='tight', facecolor='#2a2e3a')
            plt.close(fig)

            # Load into label
            pixmap = QPixmap(str(temp_path))
            plot_label.setPixmap(pixmap.scaled(
                plot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))

            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

        except Exception as e:
            plot_label.setText(f"Plot error: {str(e)}")
            plot_label.setStyleSheet("color: #ff5555; background-color: #2a2e3a; padding: 10px;")
            print(f"Error creating plot for spike {idx}: {e}")
            traceback.print_exc()

        item_layout.addLayout(left_layout, stretch=1)
        item_layout.addWidget(plot_label, stretch=2)

        return item

    def clear_content(self):
        """Clear all spike items from content area"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.checkboxes.clear()
        self.spike_widgets.clear()
        self.excluded_hidden = False
        self.btn_hide_excluded.setText("Hide Excluded")

    def select_all(self):
        """Check all visible spike checkboxes"""
        for cb, widget in zip(self.checkboxes, self.spike_widgets):
            if widget.isVisible():
                cb.setChecked(True)

    def deselect_all(self):
        """Uncheck all visible spike checkboxes"""
        for cb, widget in zip(self.checkboxes, self.spike_widgets):
            if widget.isVisible():
                cb.setChecked(False)

    def exclude_high_latency(self):
        """Uncheck visible spikes matching enabled exclusion rules."""
        apply_max = self.chk_exclude_max.isChecked()
        apply_range = self.chk_exclude_range.isChecked()

        if not apply_max and not apply_range:
            self.lbl_status.setText("No exclusion rules enabled")
            self.lbl_status.setStyleSheet("color: #f0c674; font-size: 12px;")
            return

        max_thr = self.spin_max_latency_exclude.value()
        range_lo = self.spin_range_lo.value()
        range_hi = self.spin_range_hi.value()

        count_max = 0
        count_range = 0
        for idx, (cb, widget) in enumerate(zip(self.checkboxes, self.spike_widgets)):
            if widget.isVisible() and cb.isChecked():
                latency = float(self.latency_data[idx].get('latency_s', 0))
                if apply_max and latency > max_thr:
                    cb.setChecked(False)
                    count_max += 1
                elif apply_range and range_lo <= latency <= range_hi:
                    cb.setChecked(False)
                    count_range += 1

        parts = []
        if apply_max:
            parts.append(f"{count_max} with latency > {max_thr:.1f}s")
        if apply_range:
            parts.append(f"{count_range} in range {range_lo:.1f}–{range_hi:.1f}s")
        self.lbl_status.setText(f"Excluded: {', '.join(parts)}")
        self.lbl_status.setStyleSheet("color: #f0c674; font-size: 12px;")

    def _toggle_ylim_mode(self):
        """Enable/disable the manual Y-limit spin box."""
        manual = not self.chk_auto_ylim.isChecked()
        self.spin_ylim.setEnabled(manual)
        self.lbl_ylim.setStyleSheet(
            "color: white; font-size: 11px;" if manual else "color: #888; font-size: 11px;")

    def _refresh_spike_plots(self):
        """Re-render all spike item plots with current Y-limit settings."""
        if not self.latency_data:
            return

        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        count = 0
        for idx, (row, widget) in enumerate(zip(self.latency_data, self.spike_widgets)):
            # Find the QLabel used for the plot (second widget in the item layout)
            item_layout = widget.layout()
            if item_layout is None or item_layout.count() < 2:
                continue
            plot_label = item_layout.itemAt(1).widget()
            if not isinstance(plot_label, QLabel):
                continue

            try:
                fig, ax = plt.subplots(figsize=(4.5, 2), dpi=100)
                fig.patch.set_facecolor('#2a2e3a')
                ax.set_facecolor('#2a2e3a')

                stim_start = row['stim_window_start_s']
                stim_end = row['stim_window_end_s']
                spike_time = row['spike_time_s']
                roi_name = row['ROI']
                time_range = [stim_start - 10, stim_start + 80]

                condition_name = row.get('condition', None)
                if condition_name and hasattr(self, 'dff_data_dict') and condition_name in self.dff_data_dict:
                    dff_data = self.dff_data_dict[condition_name]
                    time_col = "Time (s)"
                    if time_col in dff_data.columns and roi_name in dff_data.columns:
                        time_data = dff_data[time_col].values
                        dff_values = dff_data[roi_name].values
                        mask = (time_data >= time_range[0]) & (time_data <= time_range[1])
                        time_plot = time_data[mask]
                        dff_plot = dff_values[mask]
                        if len(time_plot) > 0:
                            ax.plot(time_plot, dff_plot, color='#4a9eff', linewidth=1.5,
                                    label='\u0394F/F', zorder=1)
                            spike_idx = np.argmin(np.abs(time_data - spike_time))
                            if mask[spike_idx]:
                                ax.plot(spike_time, dff_values[spike_idx], 'o',
                                        color='orange', markersize=8,
                                        markeredgecolor='black', markeredgewidth=1,
                                        label='Spike', zorder=3)

                ax.axvspan(stim_start, stim_end, color='red', alpha=0.2,
                           label='Stim Window', zorder=0)
                ax.axvline(stim_end, color='red', linestyle='--', linewidth=1.5,
                           alpha=0.7, zorder=2)

                y_pos = ax.get_ylim()[1] * 0.85
                ax.annotate('', xy=(spike_time, y_pos), xytext=(stim_end, y_pos),
                            arrowprops=dict(arrowstyle='<->', color='cyan', lw=2))
                ax.text((stim_end + spike_time) / 2, y_pos * 1.1,
                        f'Latency: {row["latency_s"]:.2f}s',
                        ha='center', color='cyan', fontsize=10, fontweight='bold')

                ax.set_xlim(time_range)
                if not self.chk_auto_ylim.isChecked():
                    ax.set_ylim(bottom=ax.get_ylim()[0], top=self.spin_ylim.value())
                ax.set_xlabel('Time (s)', color='white', fontsize=10)
                ax.set_ylabel('\u0394F/F', color='white', fontsize=10)
                ax.tick_params(colors='white', labelsize=9)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('white')
                ax.spines['bottom'].set_color('white')
                ax.legend(loc='upper left', fontsize=8, framealpha=0.9,
                         facecolor='#2a2e3a', edgecolor='white')
                ax.grid(True, alpha=0.2, color='white')

                temp_path = Path(f"temp_spike_refresh_{idx}.png")
                fig.savefig(temp_path, dpi=100, bbox_inches='tight', facecolor='#2a2e3a')
                plt.close(fig)

                pixmap = QPixmap(str(temp_path))
                plot_label.setPixmap(pixmap.scaled(
                    plot_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                if temp_path.exists():
                    temp_path.unlink()
                count += 1

            except Exception as e:
                print(f"Error refreshing spike plot {idx}: {e}")
                plt.close('all')

        self.lbl_status.setText(f"Refreshed {count} spike plots")
        self.lbl_status.setStyleSheet("color: #5fd75f; font-size: 12px;")

    def append_latency_data(self):
        """Load additional spike latency data from another folder and append to existing list"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Additional Analysis Output Folder to Append",
            ""
        )

        if not folder_path:
            return

        try:
            import pandas as pd

            parent_folder = Path(folder_path)
            subfolders = [f for f in parent_folder.iterdir() if f.is_dir()]

            if not subfolders:
                QMessageBox.critical(
                    self, "No Subfolders Found",
                    f"No subfolders found in:\n{parent_folder}"
                )
                return

            print(f"\n{'='*60}")
            print(f"Appending spike latency data from: {parent_folder}")
            print(f"Found {len(subfolders)} subfolders")
            print(f"{'='*60}\n")

            new_latency_data = []
            loaded_conditions = []
            skipped_folders = []

            for subfolder in subfolders:
                condition_name = subfolder.name
                latency_file = subfolder / "spike_latency_detailed.csv"
                dff_file = subfolder / "dff_table.csv"

                if not latency_file.exists():
                    skipped_folders.append((condition_name, "latency file missing"))
                    continue
                if not dff_file.exists():
                    skipped_folders.append((condition_name, "dff_table.csv missing"))
                    continue

                try:
                    df_latency = pd.read_csv(latency_file)
                    if df_latency.empty:
                        skipped_folders.append((condition_name, "empty latency file"))
                        continue

                    required_cols = ["ROI", "spike_time_s", "latency_s",
                                     "stim_window_start_s", "stim_window_end_s"]
                    if not all(col in df_latency.columns for col in required_cols):
                        skipped_folders.append((condition_name, "invalid columns"))
                        continue

                    df_dff = pd.read_csv(dff_file)

                    for row_dict in df_latency.to_dict('records'):
                        row_dict['condition'] = condition_name
                        new_latency_data.append(row_dict)

                    # Merge dff data (add or update condition)
                    if not hasattr(self, 'dff_data_dict'):
                        self.dff_data_dict = {}
                    self.dff_data_dict[condition_name] = df_dff

                    loaded_conditions.append(condition_name)
                    print(f"[OK] {condition_name}: Loaded {len(df_latency)} spikes")

                except Exception as e:
                    skipped_folders.append((condition_name, str(e)))
                    continue

            if not new_latency_data:
                QMessageBox.warning(
                    self, "No Data Found",
                    "No valid spike latency data found in the selected folder."
                )
                return

            # Append to existing data and create widgets
            start_idx = len(self.latency_data)
            self.latency_data.extend(new_latency_data)

            # If hidden mode is active, reset to show all
            if self.excluded_hidden:
                self.excluded_hidden = False
                self.btn_hide_excluded.setText("Hide Excluded")
                for w in self.spike_widgets:
                    w.setVisible(True)

            for i, row in enumerate(new_latency_data):
                idx = start_idx + i
                item_widget = self.create_spike_item(idx, row)
                self.content_layout.addWidget(item_widget)
                self.spike_widgets.append(item_widget)

            # Refresh filter lists to include new conditions/ROIs
            self._populate_filter_lists()

            status_msg = f"Total: {len(self.latency_data)} spikes (appended {len(new_latency_data)} from {len(loaded_conditions)} conditions)"
            self.lbl_status.setText(status_msg)
            self.lbl_status.setStyleSheet("color: #5fd75f; font-size: 12px;")

            print(f"\nAppended {len(new_latency_data)} spikes. Total now: {len(self.latency_data)}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to append data:\n{str(e)}")
            traceback.print_exc()

    def toggle_hide_excluded(self):
        """Toggle visibility of unchecked (excluded) spikes in the list"""
        if not self.spike_widgets:
            return

        self.excluded_hidden = not self.excluded_hidden
        self.btn_hide_excluded.setText("Show All" if self.excluded_hidden else "Hide Excluded")
        self.apply_filters()

    def _quick_select_conditions(self, pattern):
        """Quick-select conditions matching a pattern"""
        self.list_conditions.clearSelection()
        for i in range(self.list_conditions.count()):
            item = self.list_conditions.item(i)
            if pattern.lower() in item.text().lower():
                item.setSelected(True)

    def _populate_filter_lists(self):
        """Populate condition and ROI filter lists from loaded data"""
        conditions = sorted(set(row.get('condition', '') for row in self.latency_data))
        rois = sorted(set(row.get('ROI', '') for row in self.latency_data))

        self.list_conditions.blockSignals(True)
        self.list_rois.blockSignals(True)

        self.list_conditions.clear()
        for cond in conditions:
            self.list_conditions.addItem(str(cond))
        self.list_conditions.selectAll()

        self.list_rois.clear()
        for roi in rois:
            self.list_rois.addItem(str(roi))
        self.list_rois.selectAll()

        self.list_conditions.blockSignals(False)
        self.list_rois.blockSignals(False)

    def apply_filters(self):
        """Show/hide spike widgets based on selected conditions and ROIs"""
        if not self.spike_widgets:
            return

        selected_conds = set(item.text() for item in self.list_conditions.selectedItems())
        selected_rois = set(item.text() for item in self.list_rois.selectedItems())

        visible_count = 0
        for idx, (widget, row) in enumerate(zip(self.spike_widgets, self.latency_data)):
            cond_match = str(row.get('condition', '')) in selected_conds
            roi_match = str(row.get('ROI', '')) in selected_rois
            show = cond_match and roi_match
            # Also respect hide-excluded toggle
            if show and self.excluded_hidden and not self.checkboxes[idx].isChecked():
                show = False
            widget.setVisible(show)
            if show:
                visible_count += 1

        self.lbl_status.setText(f"Showing {visible_count}/{len(self.spike_widgets)} spikes")

    def generate_summary_stats(self):
        """Generate summary statistics table for selected spikes grouped by condition"""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd

        # Filter data based on checkboxes
        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]

        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            # Get parent folder (analysis_output_YYYYMMDD_HHMMSS)
            parent_folder = Path(self.csv_path)

            # Group by condition and ROI, calculate statistics
            stats_rows = []

            # For each condition
            condition_groups = df.groupby('condition')
            for condition_name, condition_df in condition_groups:
                # For each ROI within this condition
                roi_groups = condition_df.groupby('ROI')
                for roi_name, roi_df in roi_groups:
                    n_spikes = len(roi_df)
                    avg_latency = roi_df['latency_s'].mean()
                    median_latency = roi_df['latency_s'].median()
                    std_latency = roi_df['latency_s'].std()

                    stats_rows.append({
                        'Condition': condition_name,
                        'ROI': roi_name,
                        'Spike_Count': n_spikes,
                        'Avg_Latency_s': avg_latency,
                        'Median_Latency_s': median_latency,
                        'Std_Latency_s': std_latency
                    })

                # Add condition total
                condition_total_spikes = len(condition_df)
                condition_avg_latency = condition_df['latency_s'].mean()
                condition_median_latency = condition_df['latency_s'].median()
                condition_std_latency = condition_df['latency_s'].std()

                stats_rows.append({
                    'Condition': condition_name,
                    'ROI': f'[{condition_name} TOTAL]',
                    'Spike_Count': condition_total_spikes,
                    'Avg_Latency_s': condition_avg_latency,
                    'Median_Latency_s': condition_median_latency,
                    'Std_Latency_s': condition_std_latency
                })

            # Calculate overall statistics across ALL conditions
            total_spikes = len(filtered_data)
            overall_avg_latency = df['latency_s'].mean()
            overall_median_latency = df['latency_s'].median()
            overall_std_latency = df['latency_s'].std()

            # Add overall row
            stats_rows.append({
                'Condition': 'ALL',
                'ROI': 'OVERALL',
                'Spike_Count': total_spikes,
                'Avg_Latency_s': overall_avg_latency,
                'Median_Latency_s': overall_median_latency,
                'Std_Latency_s': overall_std_latency
            })

            stats_df = pd.DataFrame(stats_rows)

            # Save to CSV in parent folder
            save_path = parent_folder / "spike_latency_summary_stats.csv"
            stats_df.to_csv(save_path, index=False)

            # Create display message
            display_text = "Summary Statistics (All Conditions)\n"
            display_text += "=" * 70 + "\n\n"

            display_text += f"{'Condition':<12} {'ROI':<18} {'Spikes':<8} {'Avg Lat(s)':<12} {'Med Lat(s)':<12}\n"
            display_text += "-" * 70 + "\n"

            current_condition = None
            for _, row in stats_df.iterrows():
                condition = row['Condition']
                roi = row['ROI']
                count = int(row['Spike_Count'])
                avg = row['Avg_Latency_s']
                med = row['Median_Latency_s']

                # Add separator between conditions
                if current_condition is not None and condition != current_condition:
                    display_text += "\n"
                current_condition = condition

                # Highlight totals
                if 'TOTAL' in str(roi) or roi == 'OVERALL':
                    display_text += "-" * 70 + "\n"
                    display_text += f"{condition:<12} {roi:<18} {count:<8} {avg:<12.3f} {med:<12.3f}\n"
                    if roi == 'OVERALL':
                        display_text += "=" * 70 + "\n"
                else:
                    display_text += f"{condition:<12} {roi:<18} {count:<8} {avg:<12.3f} {med:<12.3f}\n"

            display_text += f"\nSaved to: {save_path}"

            # Show in custom resizable table dialog
            self.show_stats_table(stats_df, save_path, len(condition_groups))

            self.lbl_status.setText(f"Summary stats saved to {save_path.name}")

            print(f"\n[OK] Summary statistics saved to: {save_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate summary:\n{str(e)}")
            traceback.print_exc()

    def show_stats_table(self, stats_df, save_path, n_conditions):
        """Display statistics in a resizable table dialog with nice formatting"""
        from PyQt6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QHBoxLayout
        from PyQt6.QtCore import Qt

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Spike Latency Summary Statistics")
        dialog.resize(900, 600)  # Resizable window

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(f"Summary statistics for {n_conditions} conditions")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 10px;")
        layout.addWidget(info_label)

        # Create table
        table = QTableWidget()
        table.setRowCount(len(stats_df))
        table.setColumnCount(len(stats_df.columns))
        table.setHorizontalHeaderLabels(stats_df.columns.tolist())

        # Style table
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1e222d;
                color: white;
                gridline-color: #3a3f4b;
                border: 1px solid #3a3f4b;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3f4b;
            }
            QTableWidget::item:selected {
                background-color: #4a5568;
            }
            QHeaderView::section {
                background-color: #2a2e3a;
                color: white;
                padding: 10px;
                border: 1px solid #3a3f4b;
                font-weight: bold;
            }
        """)

        # Populate table with colored rows
        for row_idx, (_, row_data) in enumerate(stats_df.iterrows()):
            for col_idx, col_name in enumerate(stats_df.columns):
                value = row_data[col_name]

                # Format value
                if col_name in ['Avg_Latency_s', 'Median_Latency_s', 'Std_Latency_s']:
                    display_value = f"{float(value):.3f}"
                elif col_name == 'Spike_Count':
                    display_value = str(int(value))
                else:
                    display_value = str(value)

                item = QTableWidgetItem(display_value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Highlight TOTAL and OVERALL rows
                roi_value = str(row_data['ROI'])
                if 'TOTAL' in roi_value or roi_value == 'OVERALL':
                    item.setBackground(QColor('#2d4356'))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)

                table.setItem(row_idx, col_idx, item)

        # Auto-resize columns
        table.resizeColumnsToContents()
        table.setAlternatingRowColors(True)

        layout.addWidget(table)

        # Path label
        path_label = QLabel(f"Saved to: {save_path}")
        path_label.setStyleSheet("color: #aaa; font-size: 11px; padding: 5px;")
        layout.addWidget(path_label)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        dialog.exec()

    def save_filtered_data(self):
        """Save only the selected spike latencies to a new CSV"""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data to save")
            return

        import pandas as pd

        # Filter data based on checkboxes
        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]

        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        # Ask user where to save (use parent folder since csv_path is now parent folder)
        default_path = Path(self.csv_path) / "spike_latency_detailed_filtered.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Filtered Latency Data",
            str(default_path),
            "CSV Files (*.csv);;All Files (*)"
        )

        if not save_path:
            return

        try:
            df = pd.DataFrame(filtered_data)
            df.to_csv(save_path, index=False)

            n_total = len(self.latency_data)
            n_kept = len(filtered_data)
            n_removed = n_total - n_kept

            QMessageBox.information(
                self,
                "Success",
                f"Saved filtered data to:\n{save_path}\n\n"
                f"Kept: {n_kept} spikes\n"
                f"Removed: {n_removed} spikes"
            )

            self.lbl_status.setText(f"Saved {n_kept}/{n_total} spikes to {Path(save_path).name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
            traceback.print_exc()

    def categorize_by_condition(self):
        """Group spikes by experimental condition and show comparison stats/plot"""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Filter selected spikes
        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]

        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            df['condition_group'] = df['condition'].apply(self.extract_condition_group)

            # Group by condition_group and calculate statistics
            stats_rows = []
            condition_groups = df.groupby('condition_group')

            for cond_group, cond_df in condition_groups:
                n_spikes = len(cond_df)
                avg_latency = cond_df['latency_s'].mean()
                median_latency = cond_df['latency_s'].median()
                std_latency = cond_df['latency_s'].std()
                sem_latency = cond_df['latency_s'].sem()  # Standard error of mean

                stats_rows.append({
                    'Condition_Group': cond_group,
                    'Spike_Count': n_spikes,
                    'Avg_Latency_s': avg_latency,
                    'Median_Latency_s': median_latency,
                    'Std_Latency_s': std_latency,
                    'SEM_Latency_s': sem_latency
                })

            stats_df = pd.DataFrame(stats_rows)
            stats_df = stats_df.sort_values('Condition_Group')

            # Save stats to CSV
            parent_folder = Path(self.csv_path)
            csv_path = parent_folder / "spike_latency_by_condition.csv"
            stats_df.to_csv(csv_path, index=False)

            # Create visualization (academic white style)
            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            })
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
            fig.patch.set_facecolor('white')

            conditions = stats_df['Condition_Group'].values
            avg_latencies = stats_df['Avg_Latency_s'].values
            spike_counts = stats_df['Spike_Count'].values
            sems = stats_df['SEM_Latency_s'].values
            x_pos = np.arange(len(conditions))

            # Plot 1: Average latency by condition with error bars
            ax1.bar(x_pos, avg_latencies, yerr=sems, width=0.55,
                    capsize=4, color='#b0c4de', edgecolor='black', linewidth=1.0,
                    error_kw=dict(lw=1.2, capthick=1.2))
            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(conditions, fontsize=11, fontweight='bold')
            ax1.set_ylabel('Average Latency (s)', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Condition', fontsize=12, fontweight='bold')
            ax1.tick_params(axis='y', labelsize=10)
            ax1.set_facecolor('white')
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_linewidth(1.2)
            ax1.spines['bottom'].set_linewidth(1.2)
            ax1.set_ylim(bottom=0)

            # Plot 2: Spike count by condition (total counts, no dots/error bars)
            ax2.bar(x_pos, spike_counts, width=0.55,
                    color='#a8d8a8', edgecolor='black', linewidth=1.0)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(conditions, fontsize=11, fontweight='bold')
            ax2.set_ylabel('Spike Count', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Condition', fontsize=12, fontweight='bold')
            ax2.tick_params(axis='y', labelsize=10)
            ax2.set_facecolor('white')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['left'].set_linewidth(1.2)
            ax2.spines['bottom'].set_linewidth(1.2)
            ax2.set_ylim(bottom=0)



            plt.tight_layout()

            # Save plot
            plot_path = parent_folder / "spike_latency_by_condition.png"
            fig.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')

            # Show results in dialog
            self.show_categorization_results(stats_df, csv_path, plot_path, "Condition")

            self.lbl_status.setText(f"Condition analysis saved: {csv_path.name}, {plot_path.name}")
            print(f"\n[OK] Condition categorization saved to: {csv_path}")
            print(f"[OK] Plot saved to: {plot_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to categorize by condition:\n{str(e)}")
            traceback.print_exc()

    def categorize_by_roi(self):
        """Group spikes by ROI and show comparison stats/plot"""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Filter selected spikes
        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]

        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            # Group by ROI and calculate statistics
            stats_rows = []
            roi_groups = df.groupby('ROI')

            for roi_name, roi_df in roi_groups:
                n_spikes = len(roi_df)
                avg_latency = roi_df['latency_s'].mean()
                median_latency = roi_df['latency_s'].median()
                std_latency = roi_df['latency_s'].std()
                sem_latency = roi_df['latency_s'].sem()  # Standard error of mean

                stats_rows.append({
                    'ROI': roi_name,
                    'Spike_Count': n_spikes,
                    'Avg_Latency_s': avg_latency,
                    'Median_Latency_s': median_latency,
                    'Std_Latency_s': std_latency,
                    'SEM_Latency_s': sem_latency
                })

            stats_df = pd.DataFrame(stats_rows)
            stats_df = stats_df.sort_values('ROI')

            # Save stats to CSV
            parent_folder = Path(self.csv_path)
            csv_path = parent_folder / "spike_latency_by_roi.csv"
            stats_df.to_csv(csv_path, index=False)

            # Create visualization (academic white style)
            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            })
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), dpi=150)
            fig.patch.set_facecolor('white')

            rois = stats_df['ROI'].values
            avg_latencies = stats_df['Avg_Latency_s'].values
            spike_counts = stats_df['Spike_Count'].values
            sems = stats_df['SEM_Latency_s'].values
            x_pos = np.arange(len(rois))

            # Plot 1: Average latency by ROI with error bars
            ax1.bar(x_pos, avg_latencies, yerr=sems, width=0.55,
                    capsize=4, color='#b0c4de', edgecolor='black', linewidth=1.0,
                    error_kw=dict(lw=1.2, capthick=1.2))
            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(rois, rotation=45, ha='right', fontsize=10)
            ax1.set_ylabel('Average Latency (s)', fontsize=12, fontweight='bold')
            ax1.set_xlabel('ROI', fontsize=12, fontweight='bold')
            ax1.tick_params(axis='y', labelsize=10)
            ax1.set_facecolor('white')
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_linewidth(1.2)
            ax1.spines['bottom'].set_linewidth(1.2)
            ax1.set_ylim(bottom=0)

            # Plot 2: Spike count by ROI (total counts, no dots/error bars)
            ax2.bar(x_pos, spike_counts, width=0.55,
                    color='#a8d8a8', edgecolor='black', linewidth=1.0)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(rois, rotation=45, ha='right', fontsize=10)
            ax2.set_ylabel('Spike Count', fontsize=12, fontweight='bold')
            ax2.set_xlabel('ROI', fontsize=12, fontweight='bold')
            ax2.tick_params(axis='y', labelsize=10)
            ax2.set_facecolor('white')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['left'].set_linewidth(1.2)
            ax2.spines['bottom'].set_linewidth(1.2)
            ax2.set_ylim(bottom=0)



            plt.tight_layout()

            # Save plot
            plot_path = parent_folder / "spike_latency_by_roi.png"
            fig.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')

            # Show results in dialog
            self.show_categorization_results(stats_df, csv_path, plot_path, "ROI")

            self.lbl_status.setText(f"ROI analysis saved: {csv_path.name}, {plot_path.name}")
            print(f"\n[OK] ROI categorization saved to: {csv_path}")
            print(f"[OK] Plot saved to: {plot_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to categorize by ROI:\n{str(e)}")
            traceback.print_exc()

    def generate_bar_plot_with_significance(self):
        """Generate academic bar plot with individual data points and pairwise significance."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        # Filter selected spikes
        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]

        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            # Extract condition group from condition name
            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)
            groups = sorted(df['condition_group'].unique())
            n_groups = len(groups)

            if n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 2 condition groups for significance testing.")
                return

            # Collect per-group latency arrays
            group_data = {}
            for g in groups:
                group_data[g] = df.loc[df['condition_group'] == g, 'latency_s'].values

            # Compute means, SEM
            means = [np.mean(group_data[g]) for g in groups]
            sems = [sp_stats.sem(group_data[g]) if len(group_data[g]) > 1 else 0.0
                    for g in groups]

            # Pairwise Mann-Whitney U tests
            pair_results = []
            for i, j in combinations(range(n_groups), 2):
                g_a, g_b = groups[i], groups[j]
                arr_a, arr_b = group_data[g_a], group_data[g_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    stat, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                pair_results.append((i, j, g_a, g_b, pval))

            def pval_to_stars(p):
                if p < 0.001:
                    return "***"
                elif p < 0.01:
                    return "**"
                elif p < 0.05:
                    return "*"
                else:
                    return "ns"

            # ---- Per-ROI data ----
            roi_groups = df.groupby('ROI')
            roi_names = sorted(roi_groups.groups.keys())
            n_rois = len(roi_names)
            roi_data = {r: roi_groups.get_group(r)['latency_s'].values for r in roi_names}
            roi_means = [np.mean(roi_data[r]) for r in roi_names]
            roi_sems = [sp_stats.sem(roi_data[r]) if len(roi_data[r]) > 1 else 0.0
                        for r in roi_names]

            # ---- Create academic-style 2-panel figure ----
            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })

            fig_w = max(10, 1.6 * n_groups + 1.2 * n_rois)
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_w, 5), dpi=150,
                                           gridspec_kw={'width_ratios': [n_groups, max(n_rois, 1)]})
            fig.patch.set_facecolor('white')

            # ---- Left panel: By condition ----
            ax1.set_facecolor('white')
            x_pos = np.arange(n_groups)
            bar_width = 0.55

            ax1.bar(x_pos, means, width=bar_width, yerr=sems,
                    capsize=4, color='#b0c4de', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2),
                    zorder=2)

            rng = np.random.default_rng(42)
            for gi, g in enumerate(groups):
                vals = group_data[g]
                jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                ax1.scatter(gi + jitter, vals, color='#333333', s=18,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            # Significance brackets
            sig_pairs = [(i, j, p) for i, j, _, _, p in pair_results if p < 0.05]
            sig_pairs.sort(key=lambda x: x[1] - x[0])

            y_max = max(np.max(vals) for vals in group_data.values() if len(vals) > 0)
            bracket_y = y_max * 1.08
            bracket_step = y_max * 0.08

            for rank, (i, j, pval) in enumerate(sig_pairs):
                y_bar = bracket_y + rank * bracket_step
                ax1.plot([i, i, j, j], [y_bar - bracket_step * 0.15, y_bar, y_bar,
                         y_bar - bracket_step * 0.15], lw=1.0, color='black')
                stars = pval_to_stars(pval)
                ax1.text((i + j) / 2, y_bar + bracket_step * 0.05, stars,
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(groups, fontsize=11, fontweight='bold')
            ax1.set_ylabel('Latency (s)', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Condition', fontsize=12, fontweight='bold')
            ax1.tick_params(axis='y', labelsize=10)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_linewidth(1.2)
            ax1.spines['bottom'].set_linewidth(1.2)

            if sig_pairs:
                top_y = bracket_y + len(sig_pairs) * bracket_step + bracket_step * 0.3
                ax1.set_ylim(bottom=0, top=top_y)
            else:
                ax1.set_ylim(bottom=0)

            # ---- Right panel: By ROI ----
            ax2.set_facecolor('white')
            x_roi = np.arange(n_rois)

            ax2.bar(x_roi, roi_means, width=bar_width, yerr=roi_sems,
                    capsize=4, color='#d4a0a0', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2),
                    zorder=2)

            rng2 = np.random.default_rng(99)
            for ri, r in enumerate(roi_names):
                vals = roi_data[r]
                jitter = rng2.uniform(-0.15, 0.15, size=len(vals))
                ax2.scatter(ri + jitter, vals, color='#333333', s=18,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            # Pairwise Mann-Whitney U tests between ROIs
            roi_pair_results = []
            for ri, rj in combinations(range(n_rois), 2):
                r_a, r_b = roi_names[ri], roi_names[rj]
                arr_a, arr_b = roi_data[r_a], roi_data[r_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                roi_pair_results.append((ri, rj, r_a, r_b, pval))

            roi_sig_pairs = [(i, j, p) for i, j, _, _, p in roi_pair_results if p < 0.05]
            roi_sig_pairs.sort(key=lambda x: x[1] - x[0])

            ax2.set_xticks(x_roi)
            ax2.set_xticklabels(roi_names, rotation=45, ha='right', fontsize=10)
            ax2.set_ylabel('Latency (s)', fontsize=12, fontweight='bold')
            ax2.set_xlabel('ROI', fontsize=12, fontweight='bold')
            ax2.tick_params(axis='y', labelsize=10)
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['left'].set_linewidth(1.2)
            ax2.spines['bottom'].set_linewidth(1.2)

            # Significance brackets for ROI panel
            if roi_sig_pairs:
                roi_y_max = max(np.max(roi_data[r]) for r in roi_names if len(roi_data[r]) > 0)
                roi_bracket_y = roi_y_max * 1.08
                roi_bracket_step = roi_y_max * 0.08
                for rank, (i, j, pval) in enumerate(roi_sig_pairs):
                    y_bar = roi_bracket_y + rank * roi_bracket_step
                    ax2.plot([i, i, j, j], [y_bar - roi_bracket_step * 0.15, y_bar, y_bar,
                             y_bar - roi_bracket_step * 0.15], lw=1.0, color='black')
                    stars = pval_to_stars(pval)
                    ax2.text((i + j) / 2, y_bar + roi_bracket_step * 0.05, stars,
                             ha='center', va='bottom', fontsize=10, fontweight='bold')
                top_y = roi_bracket_y + len(roi_sig_pairs) * roi_bracket_step + roi_bracket_step * 0.3
                ax2.set_ylim(bottom=0, top=top_y)
            else:
                ax2.set_ylim(bottom=0)



            plt.tight_layout()

            # Save
            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / "latency_bar_plot.svg"
            png_path = parent_folder / "latency_bar_plot.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight',
                        facecolor='white')
            plt.close(fig)

            # Also save per-ROI stats CSV
            roi_stats_rows = []
            for r in roi_names:
                roi_stats_rows.append({
                    'ROI': r,
                    'Spike_Count': len(roi_data[r]),
                    'Mean_Latency_s': np.mean(roi_data[r]),
                    'Median_Latency_s': np.median(roi_data[r]),
                    'Std_Latency_s': np.std(roi_data[r], ddof=1) if len(roi_data[r]) > 1 else 0.0,
                    'SEM_Latency_s': sp_stats.sem(roi_data[r]) if len(roi_data[r]) > 1 else 0.0,
                })
            roi_stats_df = pd.DataFrame(roi_stats_rows)
            roi_csv_path = parent_folder / "latency_per_roi_stats.csv"
            roi_stats_df.to_csv(roi_csv_path, index=False)

            # Build per-ROI pairwise significance table
            roi_sig_rows = []
            for i, j, r_a, r_b, pval in roi_pair_results:
                roi_sig_rows.append({
                    'ROI_A': r_a,
                    'ROI_B': r_b,
                    'n_A': len(roi_data[r_a]),
                    'n_B': len(roi_data[r_b]),
                    'Mean_A': np.mean(roi_data[r_a]),
                    'Mean_B': np.mean(roi_data[r_b]),
                    'p_value': pval,
                    'Significance': pval_to_stars(pval),
                })
            roi_sig_df = pd.DataFrame(roi_sig_rows)
            roi_sig_csv_path = parent_folder / "latency_roi_significance.csv"
            roi_sig_df.to_csv(roi_sig_csv_path, index=False)

            # Build condition significance table as DataFrame
            sig_rows = []
            for i, j, g_a, g_b, pval in pair_results:
                sig_rows.append({
                    'Group_A': g_a,
                    'Group_B': g_b,
                    'n_A': len(group_data[g_a]),
                    'n_B': len(group_data[g_b]),
                    'Mean_A': np.mean(group_data[g_a]),
                    'Mean_B': np.mean(group_data[g_b]),
                    'p_value': pval,
                    'Significance': pval_to_stars(pval),
                })
            sig_df = pd.DataFrame(sig_rows)
            sig_csv_path = parent_folder / "latency_significance.csv"
            sig_df.to_csv(sig_csv_path, index=False)

            # Show results in dialog
            self._show_bar_plot_dialog(sig_df, png_path, svg_path, sig_csv_path,
                                       roi_stats_df=roi_stats_df, roi_csv_path=roi_csv_path,
                                       roi_sig_df=roi_sig_df, roi_sig_csv_path=roi_sig_csv_path)

            self.lbl_status.setText(f"Bar plot + significance saved")
            print(f"\n[OK] Bar plot SVG: {svg_path}")
            print(f"[OK] Bar plot PNG: {png_path}")
            print(f"[OK] Condition significance: {sig_csv_path}")
            print(f"[OK] Per-ROI stats: {roi_csv_path}")
            print(f"[OK] ROI significance: {roi_sig_csv_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"Failed to generate bar plot:\n{str(e)}")
            traceback.print_exc()

    def _show_bar_plot_dialog(self, sig_df, png_path, svg_path, sig_csv_path,
                              roi_stats_df=None, roi_csv_path=None,
                              roi_sig_df=None, roi_sig_csv_path=None):
        """Show bar plot + significance table + per-ROI table in a dialog."""
        from PyQt6.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem,
                                     QVBoxLayout, QPushButton, QHBoxLayout,
                                     QScrollArea, QWidget)

        table_style = """
            QTableWidget { background-color: #1e222d; color: white;
                           gridline-color: #3a3f4b; border: 1px solid #3a3f4b; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #2a2e3a; color: white;
                                   padding: 8px; border: 1px solid #3a3f4b;
                                   font-weight: bold; }
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("Latency Bar Plot + Significance")
        dialog.resize(950, 850)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Plot image
        plot_label = QLabel()
        plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_pixmap = QPixmap(str(png_path))
        if not plot_pixmap.isNull():
            scaled = plot_pixmap.scaled(
                900, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            plot_label.setPixmap(scaled)
        layout.addWidget(plot_label)

        # --- Significance table ---
        info_label = QLabel("Pairwise Significance (Mann-Whitney U test)")
        info_label.setStyleSheet("font-size: 13px; font-weight: bold; color: white; padding: 6px;")
        layout.addWidget(info_label)

        table = QTableWidget()
        table.setRowCount(len(sig_df))
        table.setColumnCount(len(sig_df.columns))
        table.setHorizontalHeaderLabels(sig_df.columns.tolist())
        table.setStyleSheet(table_style)

        for row_idx, (_, row_data) in enumerate(sig_df.iterrows()):
            for col_idx, col_name in enumerate(sig_df.columns):
                value = row_data[col_name]
                if col_name == 'p_value':
                    display = f"{float(value):.4f}"
                elif col_name in ('Mean_A', 'Mean_B'):
                    display = f"{float(value):.3f}"
                elif col_name in ('n_A', 'n_B'):
                    display = str(int(value))
                else:
                    display = str(value)

                item = QTableWidgetItem(display)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if col_name == 'Significance' and value != 'ns':
                    item.setBackground(QColor('#2d4356'))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col_name == 'p_value' and float(value) < 0.05:
                    item.setBackground(QColor('#2d4356'))

                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        # --- Per-ROI stats table ---
        if roi_stats_df is not None and len(roi_stats_df) > 0:
            roi_label = QLabel("Per-ROI Latency Statistics")
            roi_label.setStyleSheet("font-size: 13px; font-weight: bold; color: white; padding: 6px;")
            layout.addWidget(roi_label)

            roi_table = QTableWidget()
            roi_table.setRowCount(len(roi_stats_df))
            roi_table.setColumnCount(len(roi_stats_df.columns))
            roi_table.setHorizontalHeaderLabels(roi_stats_df.columns.tolist())
            roi_table.setStyleSheet(table_style)

            for row_idx, (_, row_data) in enumerate(roi_stats_df.iterrows()):
                for col_idx, col_name in enumerate(roi_stats_df.columns):
                    value = row_data[col_name]
                    if col_name == 'ROI':
                        display = str(value)
                    elif col_name == 'Spike_Count':
                        display = str(int(value))
                    else:
                        display = f"{float(value):.4f}"
                    item = QTableWidgetItem(display)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    roi_table.setItem(row_idx, col_idx, item)

            roi_table.resizeColumnsToContents()
            roi_table.setAlternatingRowColors(True)
            layout.addWidget(roi_table)

        # --- Per-ROI pairwise significance table ---
        if roi_sig_df is not None and len(roi_sig_df) > 0:
            roi_sig_label = QLabel("Per-ROI Pairwise Significance (Mann-Whitney U test)")
            roi_sig_label.setStyleSheet("font-size: 13px; font-weight: bold; color: white; padding: 6px;")
            layout.addWidget(roi_sig_label)

            roi_sig_table = QTableWidget()
            roi_sig_table.setRowCount(len(roi_sig_df))
            roi_sig_table.setColumnCount(len(roi_sig_df.columns))
            roi_sig_table.setHorizontalHeaderLabels(roi_sig_df.columns.tolist())
            roi_sig_table.setStyleSheet(table_style)

            for row_idx, (_, row_data) in enumerate(roi_sig_df.iterrows()):
                for col_idx, col_name in enumerate(roi_sig_df.columns):
                    value = row_data[col_name]
                    if col_name == 'p_value':
                        display = f"{float(value):.4f}"
                    elif col_name in ('Mean_A', 'Mean_B'):
                        display = f"{float(value):.3f}"
                    elif col_name in ('n_A', 'n_B'):
                        display = str(int(value))
                    else:
                        display = str(value)

                    item = QTableWidgetItem(display)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    if col_name == 'Significance' and value != 'ns':
                        item.setBackground(QColor('#2d4356'))
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    if col_name == 'p_value' and float(value) < 0.05:
                        item.setBackground(QColor('#2d4356'))

                    roi_sig_table.setItem(row_idx, col_idx, item)

            roi_sig_table.resizeColumnsToContents()
            roi_sig_table.setAlternatingRowColors(True)
            layout.addWidget(roi_sig_table)

        # Path labels
        paths = [f"SVG: {svg_path}", f"PNG: {png_path}", f"Condition CSV: {sig_csv_path}"]
        if roi_csv_path:
            paths.append(f"Per-ROI Stats CSV: {roi_csv_path}")
        if roi_sig_csv_path:
            paths.append(f"ROI Significance CSV: {roi_sig_csv_path}")
        for label_text in paths:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
            layout.addWidget(lbl)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)

        dialog.exec()

    def generate_spike_count_bar_plot(self):
        """Generate academic bar plot of spike counts per condition with significance."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)

            # Count spikes per replicate (original condition) then group
            replicate_counts = df.groupby('condition').size().reset_index(name='spike_count')
            replicate_counts['condition_group'] = replicate_counts['condition'].apply(extract_condition_group)

            groups = sorted(replicate_counts['condition_group'].unique())
            n_groups = len(groups)

            if n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 2 condition groups for comparison.")
                return

            # Collect per-group spike count arrays (one value per replicate)
            group_counts = {}
            for g in groups:
                group_counts[g] = replicate_counts.loc[
                    replicate_counts['condition_group'] == g, 'spike_count'].values.astype(float)

            means = [np.mean(group_counts[g]) for g in groups]
            sems = [sp_stats.sem(group_counts[g]) if len(group_counts[g]) > 1 else 0.0
                    for g in groups]

            # Pairwise Mann-Whitney U tests
            pair_results = []
            for i, j in combinations(range(n_groups), 2):
                g_a, g_b = groups[i], groups[j]
                arr_a, arr_b = group_counts[g_a], group_counts[g_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                pair_results.append((i, j, g_a, g_b, pval))

            def pval_to_stars(p):
                if p < 0.001: return "***"
                elif p < 0.01: return "**"
                elif p < 0.05: return "*"
                else: return "ns"

            # ---- Per-ROI spike counts (sum across all conditions) ----
            roi_replicate_counts = df.groupby(['ROI', 'condition']).size().reset_index(name='spike_count')
            roi_replicate_counts['condition_group'] = roi_replicate_counts['condition'].apply(extract_condition_group)
            # Total spikes per ROI per replicate-condition
            rois = sorted(df['ROI'].unique())
            n_rois = len(rois)

            # Per-ROI: collect per-replicate counts for significance testing
            roi_per_rep = {}
            for roi in rois:
                roi_per_rep[roi] = roi_replicate_counts.loc[
                    roi_replicate_counts['ROI'] == roi, 'spike_count'].values.astype(float)

            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })

            parent_folder = Path(self.csv_path)
            bar_width = 0.55

            # ============ FIGURE 1: Per-condition spike count ============
            fig1, ax1 = plt.subplots(figsize=(max(5, 1.6 * n_groups), 5), dpi=150)
            fig1.patch.set_facecolor('white')
            ax1.set_facecolor('white')
            x_pos = np.arange(n_groups)

            ax1.bar(x_pos, means, width=bar_width, yerr=sems,
                    capsize=4, color='#a8d8a8', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2), zorder=2)

            rng = np.random.default_rng(42)
            for gi, g in enumerate(groups):
                vals = group_counts[g]
                jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                ax1.scatter(gi + jitter, vals, color='#333333', s=22,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            sig_pairs = [(i, j, p) for i, j, _, _, p in pair_results if p < 0.05]
            sig_pairs.sort(key=lambda x: x[1] - x[0])

            y_max = max(np.max(v) for v in group_counts.values() if len(v) > 0)
            bracket_y = y_max * 1.12
            bracket_step = y_max * 0.10

            for rank, (i, j, pval) in enumerate(sig_pairs):
                y_bar = bracket_y + rank * bracket_step
                ax1.plot([i, i, j, j], [y_bar - bracket_step * 0.15, y_bar, y_bar,
                         y_bar - bracket_step * 0.15], lw=1.0, color='black')
                ax1.text((i + j) / 2, y_bar + bracket_step * 0.05, pval_to_stars(pval),
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(groups, fontsize=11, fontweight='bold')
            ax1.set_ylabel('Spike Count', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Condition', fontsize=12, fontweight='bold')
            ax1.tick_params(axis='y', labelsize=10)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_linewidth(1.2)
            ax1.spines['bottom'].set_linewidth(1.2)
            if sig_pairs:
                ax1.set_ylim(bottom=0, top=bracket_y + len(sig_pairs) * bracket_step + bracket_step * 0.3)
            else:
                ax1.set_ylim(bottom=0)


            plt.tight_layout()
            svg_path = parent_folder / "spike_count_bar_plot.svg"
            png_path = parent_folder / "spike_count_bar_plot.png"
            fig1.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig1.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig1)

            # ============ FIGURE 2: Per-ROI spike count ============
            fig2, ax2 = plt.subplots(figsize=(max(5, 1.2 * n_rois), 5), dpi=150)
            fig2.patch.set_facecolor('white')
            ax2.set_facecolor('white')

            roi_means = [np.mean(roi_per_rep[r]) for r in rois]
            roi_sems = [sp_stats.sem(roi_per_rep[r]) if len(roi_per_rep[r]) > 1 else 0.0
                        for r in rois]
            x_roi = np.arange(n_rois)

            ax2.bar(x_roi, roi_means, width=bar_width, yerr=roi_sems,
                    capsize=4, color='#d4a0a0', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2), zorder=2)

            rng2 = np.random.default_rng(99)
            for ri, roi in enumerate(rois):
                vals = roi_per_rep[roi]
                jitter = rng2.uniform(-0.15, 0.15, size=len(vals))
                ax2.scatter(ri + jitter, vals, color='#333333', s=22,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            # Pairwise Mann-Whitney U between ROIs
            roi_pair_results = []
            for i, j in combinations(range(n_rois), 2):
                r_a, r_b = rois[i], rois[j]
                arr_a, arr_b = roi_per_rep[r_a], roi_per_rep[r_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                roi_pair_results.append((i, j, r_a, r_b, pval))

            roi_sig_pairs = [(i, j, p) for i, j, _, _, p in roi_pair_results if p < 0.05]
            roi_sig_pairs.sort(key=lambda x: x[1] - x[0])

            if roi_per_rep and any(len(v) > 0 for v in roi_per_rep.values()):
                roi_y_max = max(np.max(v) for v in roi_per_rep.values() if len(v) > 0)
            else:
                roi_y_max = 1.0
            roi_bracket_y = roi_y_max * 1.12
            roi_bracket_step = roi_y_max * 0.10

            for rank, (i, j, pval) in enumerate(roi_sig_pairs):
                y_bar = roi_bracket_y + rank * roi_bracket_step
                ax2.plot([i, i, j, j], [y_bar - roi_bracket_step * 0.15, y_bar, y_bar,
                         y_bar - roi_bracket_step * 0.15], lw=1.0, color='black')
                ax2.text((i + j) / 2, y_bar + roi_bracket_step * 0.05, pval_to_stars(pval),
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax2.set_xticks(x_roi)
            ax2.set_xticklabels(rois, fontsize=10, fontweight='bold', rotation=45, ha='right')
            ax2.set_ylabel('Spike Count', fontsize=12, fontweight='bold')
            ax2.set_xlabel('ROI', fontsize=12, fontweight='bold')
            ax2.tick_params(axis='y', labelsize=10)
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['left'].set_linewidth(1.2)
            ax2.spines['bottom'].set_linewidth(1.2)
            if roi_sig_pairs:
                ax2.set_ylim(bottom=0, top=roi_bracket_y + len(roi_sig_pairs) * roi_bracket_step + roi_bracket_step * 0.3)
            else:
                ax2.set_ylim(bottom=0)


            plt.tight_layout()
            roi_svg_path = parent_folder / "spike_count_per_roi_bar_plot.svg"
            roi_png_path = parent_folder / "spike_count_per_roi_bar_plot.png"
            fig2.savefig(str(roi_svg_path), format='svg', bbox_inches='tight')
            fig2.savefig(str(roi_png_path), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig2)

            # Condition significance CSV
            sig_rows = []
            for i, j, g_a, g_b, pval in pair_results:
                sig_rows.append({
                    'Group_A': g_a, 'Group_B': g_b,
                    'n_A': len(group_counts[g_a]), 'n_B': len(group_counts[g_b]),
                    'Mean_A': np.mean(group_counts[g_a]), 'Mean_B': np.mean(group_counts[g_b]),
                    'p_value': pval, 'Significance': pval_to_stars(pval),
                })
            sig_df = pd.DataFrame(sig_rows)
            sig_csv_path = parent_folder / "spike_count_significance.csv"
            sig_df.to_csv(sig_csv_path, index=False)

            # Per-ROI stats CSV
            roi_stats_rows = []
            for roi in rois:
                vals = roi_per_rep[roi]
                roi_stats_rows.append({
                    'ROI': roi, 'Total_Spikes': int(np.sum(vals)),
                    'Mean_per_replicate': np.mean(vals),
                    'SEM': sp_stats.sem(vals) if len(vals) > 1 else 0.0,
                    'n_replicates': len(vals),
                })
            roi_stats_df = pd.DataFrame(roi_stats_rows)
            roi_csv_path = parent_folder / "spike_count_per_roi_stats.csv"
            roi_stats_df.to_csv(roi_csv_path, index=False)

            # Per-ROI significance CSV
            roi_sig_rows = []
            for i, j, r_a, r_b, pval in roi_pair_results:
                roi_sig_rows.append({
                    'ROI_A': r_a, 'ROI_B': r_b,
                    'n_A': len(roi_per_rep[r_a]), 'n_B': len(roi_per_rep[r_b]),
                    'Mean_A': np.mean(roi_per_rep[r_a]), 'Mean_B': np.mean(roi_per_rep[r_b]),
                    'p_value': pval, 'Significance': pval_to_stars(pval),
                })
            roi_sig_df = pd.DataFrame(roi_sig_rows)
            roi_sig_csv_path = parent_folder / "spike_count_roi_significance.csv"
            roi_sig_df.to_csv(roi_sig_csv_path, index=False)

            self._show_spike_count_dialog(
                png_path, svg_path, sig_df, sig_csv_path,
                roi_png_path, roi_svg_path,
                roi_stats_df, roi_csv_path,
                roi_sig_df, roi_sig_csv_path)
            self.lbl_status.setText("Spike count bar plots saved")
            print(f"\n[OK] Condition spike count plot: {svg_path}")
            print(f"[OK] Per-ROI spike count plot: {roi_svg_path}")
            print(f"[OK] Condition significance: {sig_csv_path}")
            print(f"[OK] Per-ROI stats: {roi_csv_path}")
            print(f"[OK] ROI significance: {roi_sig_csv_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate spike count plot:\n{str(e)}")
            traceback.print_exc()

    def _show_spike_count_dialog(self, cond_png, cond_svg, cond_sig_df, cond_sig_csv,
                                  roi_png, roi_svg,
                                  roi_stats_df, roi_stats_csv,
                                  roi_sig_df, roi_sig_csv):
        """Show both spike count plots (condition + per-ROI) with significance tables."""
        import pandas as pd
        from PyQt6.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem,
                                     QVBoxLayout, QPushButton, QHBoxLayout,
                                     QScrollArea, QWidget)

        table_style = """
            QTableWidget { background-color: #1e222d; color: white;
                           gridline-color: #3a3f4b; border: 1px solid #3a3f4b; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #2a2e3a; color: white;
                                   padding: 8px; border: 1px solid #3a3f4b;
                                   font-weight: bold; }
        """
        section_style = "font-size: 13px; font-weight: bold; color: white; padding: 6px;"

        def add_df_table(parent_layout, title, dataframe):
            lbl = QLabel(title)
            lbl.setStyleSheet(section_style)
            parent_layout.addWidget(lbl)

            tbl = QTableWidget()
            tbl.setRowCount(len(dataframe))
            tbl.setColumnCount(len(dataframe.columns))
            tbl.setHorizontalHeaderLabels(dataframe.columns.tolist())
            tbl.setStyleSheet(table_style)

            for r_idx, (_, r_data) in enumerate(dataframe.iterrows()):
                for c_idx, c_name in enumerate(dataframe.columns):
                    val = r_data[c_name]
                    if pd.isna(val):
                        disp = ""
                    elif c_name == 'p_value':
                        disp = f"{float(val):.4f}"
                    elif c_name in ('Mean_A', 'Mean_B', 'Mean_per_replicate', 'SEM'):
                        disp = f"{float(val):.4f}"
                    elif c_name in ('n_A', 'n_B', 'Total_Spikes', 'n_replicates'):
                        disp = str(int(val))
                    else:
                        disp = str(val)

                    item = QTableWidgetItem(disp)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if c_name == 'Significance' and str(val) not in ('ns', '', 'nan'):
                        item.setBackground(QColor('#2d4356'))
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    if c_name == 'p_value' and not pd.isna(val) and float(val) < 0.05:
                        item.setBackground(QColor('#2d4356'))
                    tbl.setItem(r_idx, c_idx, item)

            tbl.resizeColumnsToContents()
            tbl.setAlternatingRowColors(True)
            row_height = 32
            header_height = 36
            min_h = header_height + len(dataframe) * row_height + 20
            tbl.setMinimumHeight(max(200, min_h))
            parent_layout.addWidget(tbl)

        dialog = QDialog(self)
        dialog.setWindowTitle("Spike Count Bar Plots + Significance")
        dialog.resize(1050, 1100)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # --- Condition plot ---
        cond_lbl_title = QLabel("Spike Count per Condition")
        cond_lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 8px;")
        layout.addWidget(cond_lbl_title)

        cond_img = QLabel()
        cond_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cond_pix = QPixmap(str(cond_png))
        if not cond_pix.isNull():
            scaled = cond_pix.scaled(
                950, 1500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            cond_img.setPixmap(scaled)
        layout.addWidget(cond_img)

        if cond_sig_df is not None and len(cond_sig_df) > 0:
            add_df_table(layout, "Per-Condition Pairwise Significance (Mann-Whitney U)", cond_sig_df)

        # --- ROI plot ---
        roi_lbl_title = QLabel("Spike Count per ROI")
        roi_lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 8px;")
        layout.addWidget(roi_lbl_title)

        roi_img = QLabel()
        roi_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roi_pix = QPixmap(str(roi_png))
        if not roi_pix.isNull():
            scaled = roi_pix.scaled(
                950, 1500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            roi_img.setPixmap(scaled)
        layout.addWidget(roi_img)

        if roi_stats_df is not None and len(roi_stats_df) > 0:
            add_df_table(layout, "Per-ROI Spike Count Summary", roi_stats_df)

        if roi_sig_df is not None and len(roi_sig_df) > 0:
            add_df_table(layout, "Per-ROI Pairwise Significance (Mann-Whitney U)", roi_sig_df)

        # Path labels
        paths = [f"Condition SVG: {cond_svg}", f"Condition PNG: {cond_png}",
                 f"ROI SVG: {roi_svg}", f"ROI PNG: {roi_png}"]
        if cond_sig_csv:
            paths.append(f"Condition significance CSV: {cond_sig_csv}")
        if roi_stats_csv:
            paths.append(f"ROI stats CSV: {roi_stats_csv}")
        if roi_sig_csv:
            paths.append(f"ROI significance CSV: {roi_sig_csv}")
        for label_text in paths:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
            layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)
        dialog.exec()

    def generate_per_roi_spike_count_plot(self):
        """Generate per-ROI subplots comparing spike count across conditions with significance."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)
            rois = sorted(df['ROI'].unique())
            groups = sorted(df['condition_group'].unique())
            n_rois = len(rois)
            n_groups = len(groups)

            if n_rois == 0 or n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 1 ROI and 2 condition groups.")
                return

            def pval_to_stars(p):
                if p < 0.001:
                    return "***"
                elif p < 0.01:
                    return "**"
                elif p < 0.05:
                    return "*"
                return "ns"

            # Count spikes per ROI per replicate (original condition)
            spike_counts_df = df.groupby(['ROI', 'condition']).size().reset_index(name='spike_count')
            spike_counts_df['condition_group'] = spike_counts_df['condition'].apply(extract_condition_group)

            # Figure layout: grid of subplots, one per ROI
            n_cols = min(3, n_rois)
            n_rows = (n_rois + n_cols - 1) // n_cols

            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })

            fig, axes = plt.subplots(n_rows, n_cols,
                                     figsize=(5 * n_cols, 4.5 * n_rows),
                                     dpi=150, squeeze=False)
            fig.patch.set_facecolor('white')

            bar_width = 0.55
            all_stats_rows = []

            for roi_idx, roi_name in enumerate(rois):
                row_i = roi_idx // n_cols
                col_i = roi_idx % n_cols
                ax = axes[row_i][col_i]
                ax.set_facecolor('white')

                roi_sc = spike_counts_df[spike_counts_df['ROI'] == roi_name]

                # Collect spike count arrays per condition group (one value per replicate)
                group_data = {}
                for g in groups:
                    vals = roi_sc.loc[roi_sc['condition_group'] == g, 'spike_count'].values.astype(float)
                    if len(vals) > 0:
                        group_data[g] = vals

                active_groups = [g for g in groups if g in group_data]
                n_active = len(active_groups)

                if n_active == 0:
                    ax.set_title(f"{roi_name}\n(no data)", fontsize=11, fontweight='bold')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    continue

                means = [np.mean(group_data[g]) for g in active_groups]
                sems = [sp_stats.sem(group_data[g]) if len(group_data[g]) > 1 else 0.0
                        for g in active_groups]
                x_pos = np.arange(n_active)

                # Bars (green like condition spike count plot)
                ax.bar(x_pos, means, width=bar_width, yerr=sems,
                       capsize=4, color='#a8d8a8', edgecolor='black',
                       linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2),
                       zorder=2)

                # Individual data points
                rng = np.random.default_rng(roi_idx * 7 + 42)
                for gi, g in enumerate(active_groups):
                    vals = group_data[g]
                    jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                    ax.scatter(gi + jitter, vals, color='#333333', s=14,
                               edgecolors='black', linewidths=0.3, alpha=0.7, zorder=3)

                # Pairwise significance (Mann-Whitney U)
                if n_active >= 2:
                    pair_results = []
                    for i, j in combinations(range(n_active), 2):
                        g_a, g_b = active_groups[i], active_groups[j]
                        arr_a, arr_b = group_data[g_a], group_data[g_b]
                        if len(arr_a) >= 2 and len(arr_b) >= 2:
                            _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                        else:
                            pval = 1.0
                        pair_results.append((i, j, g_a, g_b, pval))
                        all_stats_rows.append({
                            'ROI': roi_name,
                            'Group_A': g_a, 'Group_B': g_b,
                            'n_A': len(arr_a), 'n_B': len(arr_b),
                            'Mean_A': np.mean(arr_a), 'Mean_B': np.mean(arr_b),
                            'p_value': pval, 'Significance': pval_to_stars(pval),
                        })

                    sig_pairs = [(i, j, p) for i, j, _, _, p in pair_results if p < 0.05]
                    sig_pairs.sort(key=lambda x: x[1] - x[0])

                    if sig_pairs:
                        y_max = max(np.max(group_data[g]) for g in active_groups)
                        bracket_y = y_max * 1.08
                        bracket_step = y_max * 0.10
                        for rank, (i, j, pval) in enumerate(sig_pairs):
                            y_bar = bracket_y + rank * bracket_step
                            ax.plot([i, i, j, j],
                                    [y_bar - bracket_step * 0.15, y_bar, y_bar,
                                     y_bar - bracket_step * 0.15],
                                    lw=1.0, color='black')
                            ax.text((i + j) / 2, y_bar + bracket_step * 0.05,
                                    pval_to_stars(pval),
                                    ha='center', va='bottom', fontsize=9, fontweight='bold')
                        top_y = bracket_y + len(sig_pairs) * bracket_step + bracket_step * 0.3
                        ax.set_ylim(bottom=0, top=top_y)
                    else:
                        ax.set_ylim(bottom=0)
                else:
                    ax.set_ylim(bottom=0)

                ax.set_title(roi_name, fontsize=11, fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(active_groups, fontsize=9, fontweight='bold')
                ax.set_ylabel('Spike Count', fontsize=10)
                ax.tick_params(axis='y', labelsize=9)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_linewidth(1.0)
                ax.spines['bottom'].set_linewidth(1.0)


            # Hide unused subplots
            for idx in range(n_rois, n_rows * n_cols):
                row_i = idx // n_cols
                col_i = idx % n_cols
                axes[row_i][col_i].set_visible(False)

            fig.suptitle("Spike Count per Condition for Each ROI", fontsize=14, fontweight='bold', y=1.01)
            plt.tight_layout()

            # Save
            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / "spike_count_per_roi_per_condition.svg"
            png_path = parent_folder / "spike_count_per_roi_per_condition.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight',
                        facecolor='white')
            plt.close(fig)

            # Save Mann-Whitney significance CSV
            if all_stats_rows:
                mw_df = pd.DataFrame(all_stats_rows)
                mw_csv = parent_folder / "spike_count_per_roi_significance.csv"
                mw_df.to_csv(mw_csv, index=False)
            else:
                mw_df = pd.DataFrame()
                mw_csv = None

            # ---- (1) Linear Mixed Effects Model ----
            lmm_df = None
            lmm_csv = None
            try:
                import statsmodels.formula.api as smf

                # Build per-replicate spike count with ROI and condition_group
                lmm_input = spike_counts_df[['spike_count', 'condition_group', 'ROI']].copy()
                lmm_input.rename(columns={'spike_count': 'count'}, inplace=True)
                if len(lmm_input['condition_group'].unique()) >= 2 and len(lmm_input['ROI'].unique()) >= 2:
                    md = smf.mixedlm("count ~ C(condition_group)", lmm_input, groups=lmm_input["ROI"])
                    mdf = md.fit(reml=True)

                    lmm_rows = []
                    for term, coef in mdf.fe_params.items():
                        se = mdf.bse_fe[term]
                        z = mdf.tvalues[term]
                        p = mdf.pvalues[term]
                        lmm_rows.append({
                            'Term': term,
                            'Coefficient': coef,
                            'Std_Error': se,
                            'z_value': z,
                            'p_value': p,
                            'Significance': pval_to_stars(p),
                        })
                    lmm_rows.append({
                        'Term': 'ROI (random effect var)',
                        'Coefficient': float(mdf.cov_re.iloc[0, 0]),
                        'Std_Error': np.nan, 'z_value': np.nan,
                        'p_value': np.nan, 'Significance': '',
                    })
                    lmm_df = pd.DataFrame(lmm_rows)
                    lmm_csv = parent_folder / "spike_count_lmm_results.csv"
                    lmm_df.to_csv(lmm_csv, index=False)
                    print(f"[OK] Spike count LMM results: {lmm_csv}")
                else:
                    print("[SKIP] LMM: need >= 2 condition groups and >= 2 ROIs")
            except ImportError:
                print("[SKIP] LMM: statsmodels not installed (pip install statsmodels)")
            except Exception as e_lmm:
                print(f"[WARN] Spike count LMM failed: {e_lmm}")

            # ---- (2) Paired t-test (per-ROI mean spike count) ----
            paired_rows = []
            roi_cond_means = spike_counts_df.groupby(['ROI', 'condition_group'])['spike_count'].mean().unstack()

            for g_a, g_b in combinations(groups, 2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                n_paired = len(paired)
                if n_paired < 2:
                    continue

                vals_a = paired[g_a].values
                vals_b = paired[g_b].values
                t_stat, p_val = sp_stats.ttest_rel(vals_a, vals_b)

                diff = vals_a - vals_b
                d_cohen = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else 0.0

                paired_rows.append({
                    'Group_A': g_a, 'Group_B': g_b,
                    'n_paired_ROIs': n_paired,
                    'Mean_A': np.mean(vals_a), 'Mean_B': np.mean(vals_b),
                    'Mean_Diff': np.mean(diff),
                    't_statistic': t_stat,
                    'p_value': p_val,
                    'Cohens_d': d_cohen,
                    'Significance': pval_to_stars(p_val),
                })

            paired_df = pd.DataFrame(paired_rows) if paired_rows else None
            paired_csv = None
            if paired_df is not None and len(paired_df) > 0:
                paired_csv = parent_folder / "spike_count_paired_ttest.csv"
                paired_df.to_csv(paired_csv, index=False)
                print(f"[OK] Spike count paired t-test: {paired_csv}")

            # ---- (3) Spearman correlation (per-ROI mean spike count between conditions) ----
            spearman_rows = []
            for g_a, g_b in combinations(groups,    2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                if len(paired) < 3:
                    continue

                rho, p_val = sp_stats.spearmanr(paired[g_a].values, paired[g_b].values)
                spearman_rows.append({
                    'Condition_A': g_a, 'Condition_B': g_b,
                    'n_ROIs': len(paired),
                    'Spearman_rho': rho,
                    'p_value': p_val,
                    'Significance': pval_to_stars(p_val),
                })

            spearman_df = pd.DataFrame(spearman_rows) if spearman_rows else None
            spearman_csv = None
            if spearman_df is not None and len(spearman_df) > 0:
                spearman_csv = parent_folder / "spike_count_spearman_correlation.csv"
                spearman_df.to_csv(spearman_csv, index=False)
                print(f"[OK] Spike count Spearman correlation: {spearman_csv}")

            # Show dialog with all results
            self._show_per_roi_condition_dialog(
                png_path, svg_path, mw_csv,
                sig_df=mw_df if len(mw_df) > 0 else None,
                lmm_df=lmm_df, lmm_csv=lmm_csv,
                paired_df=paired_df, paired_csv=paired_csv,
                spearman_df=spearman_df, spearman_csv=spearman_csv,
            )

            self.lbl_status.setText("Per-ROI spike count plot + analyses saved")
            print(f"[OK] Per-ROI spike count plot SVG: {svg_path}")
            print(f"[OK] Per-ROI spike count plot PNG: {png_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"Failed to generate per-ROI spike count plot:\n{str(e)}")
            traceback.print_exc()

    def _lookup_spike_amplitude(self, condition, roi, spike_time_s):
        """Look up the dF/F amplitude at the given spike time from the dff_table."""
        import numpy as np
        dff_df = self.dff_data_dict.get(condition)
        if dff_df is None:
            return np.nan
        if 'Time (s)' not in dff_df.columns or roi not in dff_df.columns:
            return np.nan
        t = dff_df['Time (s)'].to_numpy(dtype=float)
        y = dff_df[roi].to_numpy(dtype=float)
        idx = np.argmin(np.abs(t - spike_time_s))
        return float(y[idx])

    def generate_spike_amplitude_plot(self):
        """Generate bar plots of averaged spike amplitude per condition and per ROI."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        if not hasattr(self, 'dff_data_dict') or not self.dff_data_dict:
            QMessageBox.warning(self, "Warning",
                                "No dF/F data available. Re-load data from analysis folder.")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            # Look up amplitude for each spike
            amp_rows = []
            for row in filtered_data:
                amp = self._lookup_spike_amplitude(
                    row['condition'], row['ROI'], float(row['spike_time_s']))
                if not np.isnan(amp):
                    amp_rows.append({
                        'condition': row['condition'],
                        'ROI': row['ROI'],
                        'spike_time_s': float(row['spike_time_s']),
                        'amplitude': amp,
                    })

            if not amp_rows:
                QMessageBox.warning(self, "Warning",
                                    "Could not look up any spike amplitudes from dF/F data.")
                return

            df = pd.DataFrame(amp_rows)

            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)
            groups = sorted(df['condition_group'].unique())
            rois = sorted(df['ROI'].unique())
            n_groups = len(groups)
            n_rois = len(rois)

            if n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 2 condition groups for comparison.")
                return

            def pval_to_stars(p):
                if p < 0.001: return "***"
                elif p < 0.01: return "**"
                elif p < 0.05: return "*"
                else: return "ns"

            # --- Per-condition: average amplitude across all ROIs per replicate ---
            rep_amp = df.groupby('condition')['amplitude'].mean().reset_index()
            rep_amp['condition_group'] = rep_amp['condition'].apply(extract_condition_group)

            group_amps = {}
            for g in groups:
                group_amps[g] = rep_amp.loc[
                    rep_amp['condition_group'] == g, 'amplitude'].values.astype(float)

            cond_means = [np.mean(group_amps[g]) for g in groups]
            cond_sems = [sp_stats.sem(group_amps[g]) if len(group_amps[g]) > 1 else 0.0
                         for g in groups]

            # Pairwise Mann-Whitney between conditions
            cond_pair_results = []
            for i, j in combinations(range(n_groups), 2):
                g_a, g_b = groups[i], groups[j]
                arr_a, arr_b = group_amps[g_a], group_amps[g_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                cond_pair_results.append((i, j, g_a, g_b, pval))

            # --- Per-ROI: average amplitude across all conditions per replicate ---
            roi_rep_amp = df.groupby(['ROI', 'condition'])['amplitude'].mean().reset_index()
            roi_amps = {}
            for roi in rois:
                roi_amps[roi] = roi_rep_amp.loc[
                    roi_rep_amp['ROI'] == roi, 'amplitude'].values.astype(float)

            roi_means = [np.mean(roi_amps[r]) for r in rois]
            roi_sems = [sp_stats.sem(roi_amps[r]) if len(roi_amps[r]) > 1 else 0.0
                        for r in rois]

            # Pairwise Mann-Whitney between ROIs
            roi_pair_results = []
            for i, j in combinations(range(n_rois), 2):
                r_a, r_b = rois[i], rois[j]
                arr_a, arr_b = roi_amps[r_a], roi_amps[r_b]
                if len(arr_a) >= 2 and len(arr_b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                else:
                    pval = 1.0
                roi_pair_results.append((i, j, r_a, r_b, pval))

            # ============ PLOTTING ============
            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })
            bar_width = 0.55
            parent_folder = Path(self.csv_path)

            # ---- Figure 1: Per-condition amplitude ----
            fig1, ax1 = plt.subplots(figsize=(max(5, 1.6 * n_groups), 5), dpi=150)
            fig1.patch.set_facecolor('white')
            ax1.set_facecolor('white')
            x_pos = np.arange(n_groups)

            ax1.bar(x_pos, cond_means, width=bar_width, yerr=cond_sems,
                    capsize=4, color='#b0c4de', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2), zorder=2)

            rng = np.random.default_rng(42)
            for gi, g in enumerate(groups):
                vals = group_amps[g]
                jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                ax1.scatter(gi + jitter, vals, color='#333333', s=22,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            cond_sig = [(i, j, p) for i, j, _, _, p in cond_pair_results if p < 0.05]
            cond_sig.sort(key=lambda x: x[1] - x[0])
            if group_amps:
                y_max = max(np.max(v) for v in group_amps.values() if len(v) > 0)
            else:
                y_max = 1.0
            bracket_y = y_max * 1.12
            bracket_step = y_max * 0.10
            for rank, (i, j, pval) in enumerate(cond_sig):
                y_bar = bracket_y + rank * bracket_step
                ax1.plot([i, i, j, j], [y_bar - bracket_step * 0.15, y_bar, y_bar,
                         y_bar - bracket_step * 0.15], lw=1.0, color='black')
                ax1.text((i + j) / 2, y_bar + bracket_step * 0.05, pval_to_stars(pval),
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax1.set_xticks(x_pos)
            ax1.set_xticklabels(groups, fontsize=11, fontweight='bold')
            ax1.set_ylabel('Spike Amplitude (dF/F)', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Condition', fontsize=12, fontweight='bold')
            ax1.tick_params(axis='y', labelsize=10)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_linewidth(1.2)
            ax1.spines['bottom'].set_linewidth(1.2)
            if cond_sig:
                ax1.set_ylim(bottom=0, top=bracket_y + len(cond_sig) * bracket_step + bracket_step * 0.3)
            else:
                ax1.set_ylim(bottom=0)

            plt.tight_layout()

            cond_svg = parent_folder / "spike_amplitude_per_condition.svg"
            cond_png = parent_folder / "spike_amplitude_per_condition.png"
            fig1.savefig(str(cond_svg), format='svg', bbox_inches='tight')
            fig1.savefig(str(cond_png), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig1)

            # ---- Figure 2: Per-ROI amplitude ----
            fig2, ax2 = plt.subplots(figsize=(max(5, 1.2 * n_rois), 5), dpi=150)
            fig2.patch.set_facecolor('white')
            ax2.set_facecolor('white')
            x_roi = np.arange(n_rois)

            ax2.bar(x_roi, roi_means, width=bar_width, yerr=roi_sems,
                    capsize=4, color='#d4a0a0', edgecolor='black',
                    linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2), zorder=2)

            rng2 = np.random.default_rng(99)
            for ri, roi in enumerate(rois):
                vals = roi_amps[roi]
                jitter = rng2.uniform(-0.15, 0.15, size=len(vals))
                ax2.scatter(ri + jitter, vals, color='#333333', s=22,
                            edgecolors='black', linewidths=0.4, alpha=0.7, zorder=3)

            roi_sig = [(i, j, p) for i, j, _, _, p in roi_pair_results if p < 0.05]
            roi_sig.sort(key=lambda x: x[1] - x[0])
            if roi_amps:
                roi_y_max = max(np.max(v) for v in roi_amps.values() if len(v) > 0)
            else:
                roi_y_max = 1.0
            roi_bracket_y = roi_y_max * 1.12
            roi_bracket_step = roi_y_max * 0.10
            for rank, (i, j, pval) in enumerate(roi_sig):
                y_bar = roi_bracket_y + rank * roi_bracket_step
                ax2.plot([i, i, j, j], [y_bar - roi_bracket_step * 0.15, y_bar, y_bar,
                         y_bar - roi_bracket_step * 0.15], lw=1.0, color='black')
                ax2.text((i + j) / 2, y_bar + roi_bracket_step * 0.05, pval_to_stars(pval),
                         ha='center', va='bottom', fontsize=10, fontweight='bold')

            ax2.set_xticks(x_roi)
            ax2.set_xticklabels(rois, fontsize=10, fontweight='bold', rotation=45, ha='right')
            ax2.set_ylabel('Spike Amplitude (dF/F)', fontsize=12, fontweight='bold')
            ax2.set_xlabel('ROI', fontsize=12, fontweight='bold')
            ax2.tick_params(axis='y', labelsize=10)
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['left'].set_linewidth(1.2)
            ax2.spines['bottom'].set_linewidth(1.2)
            if roi_sig:
                ax2.set_ylim(bottom=0, top=roi_bracket_y + len(roi_sig) * roi_bracket_step + roi_bracket_step * 0.3)
            else:
                ax2.set_ylim(bottom=0)

            plt.tight_layout()

            roi_svg = parent_folder / "spike_amplitude_per_roi.svg"
            roi_png = parent_folder / "spike_amplitude_per_roi.png"
            fig2.savefig(str(roi_svg), format='svg', bbox_inches='tight')
            fig2.savefig(str(roi_png), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig2)

            # ============ CSV outputs ============
            # Condition significance
            cond_sig_rows = []
            for i, j, g_a, g_b, pval in cond_pair_results:
                cond_sig_rows.append({
                    'Group_A': g_a, 'Group_B': g_b,
                    'n_A': len(group_amps[g_a]), 'n_B': len(group_amps[g_b]),
                    'Mean_A': np.mean(group_amps[g_a]), 'Mean_B': np.mean(group_amps[g_b]),
                    'p_value': pval, 'Significance': pval_to_stars(pval),
                })
            cond_sig_df = pd.DataFrame(cond_sig_rows)
            cond_sig_csv = parent_folder / "spike_amplitude_condition_significance.csv"
            cond_sig_df.to_csv(cond_sig_csv, index=False)

            # ROI stats
            roi_stats_rows = []
            for roi in rois:
                vals = roi_amps[roi]
                roi_stats_rows.append({
                    'ROI': roi, 'n_spikes': len(vals),
                    'Mean_Amplitude': np.mean(vals),
                    'SEM': sp_stats.sem(vals) if len(vals) > 1 else 0.0,
                })
            roi_stats_df = pd.DataFrame(roi_stats_rows)
            roi_stats_csv = parent_folder / "spike_amplitude_per_roi_stats.csv"
            roi_stats_df.to_csv(roi_stats_csv, index=False)

            # ROI significance
            roi_sig_rows = []
            for i, j, r_a, r_b, pval in roi_pair_results:
                roi_sig_rows.append({
                    'ROI_A': r_a, 'ROI_B': r_b,
                    'n_A': len(roi_amps[r_a]), 'n_B': len(roi_amps[r_b]),
                    'Mean_A': np.mean(roi_amps[r_a]), 'Mean_B': np.mean(roi_amps[r_b]),
                    'p_value': pval, 'Significance': pval_to_stars(pval),
                })
            roi_sig_df = pd.DataFrame(roi_sig_rows)
            roi_sig_csv = parent_folder / "spike_amplitude_roi_significance.csv"
            roi_sig_df.to_csv(roi_sig_csv, index=False)

            # Per-spike amplitude CSV (all data)
            amp_df = df[['condition', 'condition_group', 'ROI', 'spike_time_s', 'amplitude']]
            amp_csv = parent_folder / "spike_amplitude_all.csv"
            amp_df.to_csv(amp_csv, index=False)

            # Show dialog
            self._show_spike_amplitude_dialog(
                cond_png, cond_svg, cond_sig_df, cond_sig_csv,
                roi_png, roi_svg, roi_stats_df, roi_stats_csv,
                roi_sig_df, roi_sig_csv, amp_csv)

            self.lbl_status.setText("Spike amplitude plots saved")
            print(f"\n[OK] Condition amplitude plot: {cond_svg}")
            print(f"[OK] Per-ROI amplitude plot: {roi_svg}")
            print(f"[OK] All amplitudes CSV: {amp_csv}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"Failed to generate spike amplitude plot:\n{str(e)}")
            traceback.print_exc()

    def _show_spike_amplitude_dialog(self, cond_png, cond_svg, cond_sig_df, cond_sig_csv,
                                      roi_png, roi_svg, roi_stats_df, roi_stats_csv,
                                      roi_sig_df, roi_sig_csv, amp_csv):
        """Show spike amplitude plots + significance tables in a dialog."""
        import pandas as pd
        from PyQt6.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem,
                                     QVBoxLayout, QPushButton, QHBoxLayout,
                                     QScrollArea, QWidget)

        table_style = """
            QTableWidget { background-color: #1e222d; color: white;
                           gridline-color: #3a3f4b; border: 1px solid #3a3f4b; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #2a2e3a; color: white;
                                   padding: 8px; border: 1px solid #3a3f4b;
                                   font-weight: bold; }
        """
        section_style = "font-size: 13px; font-weight: bold; color: white; padding: 6px;"

        def add_df_table(parent_layout, title, dataframe):
            lbl = QLabel(title)
            lbl.setStyleSheet(section_style)
            parent_layout.addWidget(lbl)
            tbl = QTableWidget()
            tbl.setRowCount(len(dataframe))
            tbl.setColumnCount(len(dataframe.columns))
            tbl.setHorizontalHeaderLabels(dataframe.columns.tolist())
            tbl.setStyleSheet(table_style)
            for r_idx, (_, r_data) in enumerate(dataframe.iterrows()):
                for c_idx, c_name in enumerate(dataframe.columns):
                    val = r_data[c_name]
                    if pd.isna(val):
                        disp = ""
                    elif c_name in ('p_value', 'Mean_A', 'Mean_B', 'Mean_Amplitude', 'SEM'):
                        disp = f"{float(val):.4f}"
                    elif c_name in ('n_A', 'n_B', 'n_spikes'):
                        disp = str(int(val))
                    else:
                        disp = str(val)
                    item = QTableWidgetItem(disp)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if c_name == 'Significance' and str(val) not in ('ns', '', 'nan'):
                        item.setBackground(QColor('#2d4356'))
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    if c_name == 'p_value' and not pd.isna(val) and float(val) < 0.05:
                        item.setBackground(QColor('#2d4356'))
                    tbl.setItem(r_idx, c_idx, item)
            tbl.resizeColumnsToContents()
            tbl.setAlternatingRowColors(True)
            row_h = 32
            min_h = 36 + len(dataframe) * row_h + 20
            tbl.setMinimumHeight(max(200, min_h))
            parent_layout.addWidget(tbl)

        dialog = QDialog(self)
        dialog.setWindowTitle("Spike Amplitude Analysis")
        dialog.resize(1050, 1100)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Condition plot
        lbl1 = QLabel("Spike Amplitude per Condition (averaged across ROIs)")
        lbl1.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 8px;")
        layout.addWidget(lbl1)
        img1 = QLabel()
        img1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix1 = QPixmap(str(cond_png))
        if not pix1.isNull():
            img1.setPixmap(pix1.scaled(950, 1500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(img1)

        if cond_sig_df is not None and len(cond_sig_df) > 0:
            add_df_table(layout, "Per-Condition Pairwise Significance (Mann-Whitney U)", cond_sig_df)

        # ROI plot
        lbl2 = QLabel("Spike Amplitude per ROI (averaged across conditions)")
        lbl2.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 8px;")
        layout.addWidget(lbl2)
        img2 = QLabel()
        img2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix2 = QPixmap(str(roi_png))
        if not pix2.isNull():
            img2.setPixmap(pix2.scaled(950, 1500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(img2)

        if roi_stats_df is not None and len(roi_stats_df) > 0:
            add_df_table(layout, "Per-ROI Amplitude Summary", roi_stats_df)
        if roi_sig_df is not None and len(roi_sig_df) > 0:
            add_df_table(layout, "Per-ROI Pairwise Significance (Mann-Whitney U)", roi_sig_df)

        # File paths
        paths = [f"Condition SVG: {cond_svg}", f"ROI SVG: {roi_svg}",
                 f"All amplitudes CSV: {amp_csv}",
                 f"Condition significance: {cond_sig_csv}",
                 f"ROI stats: {roi_stats_csv}",
                 f"ROI significance: {roi_sig_csv}"]
        for t in paths:
            lbl = QLabel(t)
            lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
            layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)
        dialog.exec()

    def generate_per_roi_amplitude_plot(self):
        """Generate per-ROI subplots comparing spike amplitude across conditions with significance."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        if not hasattr(self, 'dff_data_dict') or not self.dff_data_dict:
            QMessageBox.warning(self, "Warning",
                                "No dF/F data available. Re-load data from analysis folder.")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            # Look up amplitude for each spike
            amp_rows = []
            for row in filtered_data:
                amp = self._lookup_spike_amplitude(
                    row['condition'], row['ROI'], float(row['spike_time_s']))
                if not np.isnan(amp):
                    amp_rows.append({
                        'condition': row['condition'],
                        'ROI': row['ROI'],
                        'spike_time_s': float(row['spike_time_s']),
                        'amplitude': amp,
                    })

            if not amp_rows:
                QMessageBox.warning(self, "Warning",
                                    "Could not look up any spike amplitudes from dF/F data.")
                return

            df = pd.DataFrame(amp_rows)

            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)
            rois = sorted(df['ROI'].unique())
            groups = sorted(df['condition_group'].unique())
            n_rois = len(rois)
            n_groups = len(groups)

            if n_rois == 0 or n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 1 ROI and 2 condition groups.")
                return

            def pval_to_stars(p):
                if p < 0.001: return "***"
                elif p < 0.01: return "**"
                elif p < 0.05: return "*"
                return "ns"

            # Grid of subplots, one per ROI
            n_cols = min(3, n_rois)
            n_rows_plot = (n_rois + n_cols - 1) // n_cols

            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })

            fig, axes = plt.subplots(n_rows_plot, n_cols,
                                     figsize=(5 * n_cols, 4.5 * n_rows_plot),
                                     dpi=150, squeeze=False)
            fig.patch.set_facecolor('white')

            bar_width = 0.55
            all_stats_rows = []

            for roi_idx, roi_name in enumerate(rois):
                row_i = roi_idx // n_cols
                col_i = roi_idx % n_cols
                ax = axes[row_i][col_i]
                ax.set_facecolor('white')

                roi_df = df[df['ROI'] == roi_name]

                # Collect amplitude data per condition group
                group_data = {}
                for g in groups:
                    vals = roi_df.loc[roi_df['condition_group'] == g, 'amplitude'].values
                    if len(vals) > 0:
                        group_data[g] = vals

                active_groups = [g for g in groups if g in group_data]
                n_active = len(active_groups)

                if n_active == 0:
                    ax.set_title(f"{roi_name}\n(no data)", fontsize=11, fontweight='bold')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    continue

                means = [np.mean(group_data[g]) for g in active_groups]
                sems = [sp_stats.sem(group_data[g]) if len(group_data[g]) > 1 else 0.0
                        for g in active_groups]
                x_pos = np.arange(n_active)

                ax.bar(x_pos, means, width=bar_width, yerr=sems,
                       capsize=4, color='#b0c4de', edgecolor='black',
                       linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2), zorder=2)

                rng = np.random.default_rng(roi_idx * 7 + 42)
                for gi, g in enumerate(active_groups):
                    vals = group_data[g]
                    jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                    ax.scatter(gi + jitter, vals, color='#333333', s=14,
                               edgecolors='black', linewidths=0.3, alpha=0.7, zorder=3)

                # Pairwise significance
                if n_active >= 2:
                    pair_results = []
                    for i, j in combinations(range(n_active), 2):
                        g_a, g_b = active_groups[i], active_groups[j]
                        arr_a, arr_b = group_data[g_a], group_data[g_b]
                        if len(arr_a) >= 2 and len(arr_b) >= 2:
                            _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                        else:
                            pval = 1.0
                        pair_results.append((i, j, g_a, g_b, pval))
                        all_stats_rows.append({
                            'ROI': roi_name,
                            'Group_A': g_a, 'Group_B': g_b,
                            'n_A': len(arr_a), 'n_B': len(arr_b),
                            'Mean_A': np.mean(arr_a), 'Mean_B': np.mean(arr_b),
                            'p_value': pval, 'Significance': pval_to_stars(pval),
                        })

                    sig_pairs = [(i, j, p) for i, j, _, _, p in pair_results if p < 0.05]
                    sig_pairs.sort(key=lambda x: x[1] - x[0])

                    if sig_pairs:
                        y_max = max(np.max(group_data[g]) for g in active_groups)
                        bracket_y = y_max * 1.08
                        bracket_step = y_max * 0.10
                        for rank, (i, j, pval) in enumerate(sig_pairs):
                            y_bar = bracket_y + rank * bracket_step
                            ax.plot([i, i, j, j],
                                    [y_bar - bracket_step * 0.15, y_bar, y_bar,
                                     y_bar - bracket_step * 0.15],
                                    lw=1.0, color='black')
                            ax.text((i + j) / 2, y_bar + bracket_step * 0.05,
                                    pval_to_stars(pval),
                                    ha='center', va='bottom', fontsize=9, fontweight='bold')
                        top_y = bracket_y + len(sig_pairs) * bracket_step + bracket_step * 0.3
                        ax.set_ylim(bottom=0, top=top_y)
                    else:
                        ax.set_ylim(bottom=0)
                else:
                    ax.set_ylim(bottom=0)

                ax.set_title(roi_name, fontsize=11, fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(active_groups, fontsize=9, fontweight='bold')
                ax.set_ylabel('Amplitude (dF/F)', fontsize=10)
                ax.tick_params(axis='y', labelsize=9)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_linewidth(1.0)
                ax.spines['bottom'].set_linewidth(1.0)


            # Hide unused subplots
            for idx in range(n_rois, n_rows_plot * n_cols):
                row_i = idx // n_cols
                col_i = idx % n_cols
                axes[row_i][col_i].set_visible(False)

            fig.suptitle("Spike Amplitude per Condition for Each ROI",
                         fontsize=14, fontweight='bold', y=1.01)
            plt.tight_layout()

            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / "spike_amplitude_per_roi_per_condition.svg"
            png_path = parent_folder / "spike_amplitude_per_roi_per_condition.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight',
                        facecolor='white')
            plt.close(fig)

            # Mann-Whitney significance CSV
            if all_stats_rows:
                mw_df = pd.DataFrame(all_stats_rows)
                mw_csv = parent_folder / "spike_amplitude_per_roi_significance.csv"
                mw_df.to_csv(mw_csv, index=False)
            else:
                mw_df = pd.DataFrame()
                mw_csv = None

            # ---- LMM ----
            lmm_df = None
            lmm_csv = None
            try:
                import statsmodels.formula.api as smf
                lmm_input = df[['amplitude', 'condition_group', 'ROI']].dropna()
                if len(lmm_input['condition_group'].unique()) >= 2 and len(lmm_input['ROI'].unique()) >= 2:
                    md = smf.mixedlm("amplitude ~ C(condition_group)", lmm_input, groups=lmm_input["ROI"])
                    mdf = md.fit(reml=True)
                    lmm_rows = []
                    for term, coef in mdf.fe_params.items():
                        se = mdf.bse_fe[term]
                        z = mdf.tvalues[term]
                        p = mdf.pvalues[term]
                        lmm_rows.append({
                            'Term': term, 'Coefficient': coef,
                            'Std_Error': se, 'z_value': z,
                            'p_value': p, 'Significance': pval_to_stars(p),
                        })
                    lmm_rows.append({
                        'Term': 'ROI (random effect var)',
                        'Coefficient': float(mdf.cov_re.iloc[0, 0]),
                        'Std_Error': np.nan, 'z_value': np.nan,
                        'p_value': np.nan, 'Significance': '',
                    })
                    lmm_df = pd.DataFrame(lmm_rows)
                    lmm_csv = parent_folder / "spike_amplitude_lmm_results.csv"
                    lmm_df.to_csv(lmm_csv, index=False)
                    print(f"[OK] Amplitude LMM results: {lmm_csv}")
            except ImportError:
                print("[SKIP] LMM: statsmodels not installed")
            except Exception as e_lmm:
                print(f"[WARN] Amplitude LMM failed: {e_lmm}")

            # ---- Paired t-test ----
            paired_rows = []
            roi_cond_means = df.groupby(['ROI', 'condition_group'])['amplitude'].mean().unstack()
            for g_a, g_b in combinations(groups, 2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                n_paired = len(paired)
                if n_paired < 2:
                    continue
                vals_a = paired[g_a].values
                vals_b = paired[g_b].values
                t_stat, p_val = sp_stats.ttest_rel(vals_a, vals_b)
                diff = vals_a - vals_b
                d_cohen = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else 0.0
                paired_rows.append({
                    'Group_A': g_a, 'Group_B': g_b,
                    'n_paired_ROIs': n_paired,
                    'Mean_A': np.mean(vals_a), 'Mean_B': np.mean(vals_b),
                    'Mean_Diff': np.mean(diff),
                    't_statistic': t_stat, 'p_value': p_val,
                    'Cohens_d': d_cohen, 'Significance': pval_to_stars(p_val),
                })
            paired_df = pd.DataFrame(paired_rows) if paired_rows else None
            paired_csv = None
            if paired_df is not None and len(paired_df) > 0:
                paired_csv = parent_folder / "spike_amplitude_paired_ttest.csv"
                paired_df.to_csv(paired_csv, index=False)
                print(f"[OK] Amplitude paired t-test: {paired_csv}")

            # ---- Spearman correlation ----
            spearman_rows = []
            for g_a, g_b in combinations(groups, 2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                if len(paired) < 3:
                    continue
                rho, p_val = sp_stats.spearmanr(paired[g_a].values, paired[g_b].values)
                spearman_rows.append({
                    'Condition_A': g_a, 'Condition_B': g_b,
                    'n_ROIs': len(paired),
                    'Spearman_rho': rho, 'p_value': p_val,
                    'Significance': pval_to_stars(p_val),
                })
            spearman_df = pd.DataFrame(spearman_rows) if spearman_rows else None
            spearman_csv = None
            if spearman_df is not None and len(spearman_df) > 0:
                spearman_csv = parent_folder / "spike_amplitude_spearman_correlation.csv"
                spearman_df.to_csv(spearman_csv, index=False)
                print(f"[OK] Amplitude Spearman correlation: {spearman_csv}")

            # Show dialog
            self._show_per_roi_condition_dialog(
                png_path, svg_path, mw_csv,
                sig_df=mw_df if len(mw_df) > 0 else None,
                lmm_df=lmm_df, lmm_csv=lmm_csv,
                paired_df=paired_df, paired_csv=paired_csv,
                spearman_df=spearman_df, spearman_csv=spearman_csv,
            )

            self.lbl_status.setText("Per-ROI amplitude plot + analyses saved")
            print(f"[OK] Per-ROI amplitude plot SVG: {svg_path}")
            print(f"[OK] Per-ROI amplitude plot PNG: {png_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"Failed to generate per-ROI amplitude plot:\n{str(e)}")
            traceback.print_exc()

    # =====================================================================
    #  Publication-quality plots (violin / ROI detail)
    # =====================================================================

    def _build_metric_df(self, metric):
        """Build a DataFrame with columns [condition, condition_group, ROI, ROI_label, value]
        for the requested metric ('latency', 'amplitude', 'event_count')."""
        import numpy as np
        import pandas as pd

        filtered = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered:
            return None

        ecg = self.extract_condition_group

        if metric == "latency":
            rows = []
            for r in filtered:
                rows.append({
                    'condition': r['condition'],
                    'condition_group': ecg(r['condition']),
                    'ROI': r['ROI'],
                    'value': float(r['latency_s']),
                })
            return pd.DataFrame(rows)

        elif metric == "amplitude":
            if not hasattr(self, 'dff_data_dict') or not self.dff_data_dict:
                return None
            rows = []
            for r in filtered:
                amp = self._lookup_spike_amplitude(
                    r['condition'], r['ROI'], float(r['spike_time_s']))
                if not np.isnan(amp):
                    rows.append({
                        'condition': r['condition'],
                        'condition_group': ecg(r['condition']),
                        'ROI': r['ROI'],
                        'value': amp,
                    })
            return pd.DataFrame(rows) if rows else None

        elif metric == "event_count":
            # one data point per (ROI, replicate-condition) = spike count
            tmp = pd.DataFrame(filtered)
            tmp['condition_group'] = tmp['condition'].apply(ecg)
            counts = tmp.groupby(['ROI', 'condition', 'condition_group']).size().reset_index(name='value')
            return counts

        return None

    def _clean_roi_label(self, roi_name):
        import re
        label = re.sub(r'\s*\[.*?\]', '', roi_name)
        label = label.replace('.', ' ')
        return label

    def _generate_violin_plot(self, metric):
        """3-panel publication plot: violin+box by condition, violin+box by ROI, KDE."""
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        from scipy import stats as sp_stats
        from scipy.stats import gaussian_kde
        from itertools import combinations

        df = self._build_metric_df(metric)
        if df is None or len(df) == 0:
            QMessageBox.warning(self, "Warning",
                                f"No data available for {metric}.")
            return

        metric_labels = {
            'latency': ('Latency (s)', 'Spike Latency'),
            'amplitude': ('Amplitude (dF/F)', 'Spike Amplitude'),
            'event_count': ('Spike Count', 'Event Count'),
        }
        y_label, title_base = metric_labels[metric]

        try:
            df['ROI_label'] = df['ROI'].apply(self._clean_roi_label)

            all_conds = sorted(df['condition_group'].unique())
            cond_colors = self._build_cond_colors(all_conds)

            # stats per condition
            cond_stats = df.groupby('condition_group')['value'].agg(['mean', 'std', 'count']).rename(
                columns={'mean': 'avg', 'std': 'sd', 'count': 'n'})
            HAS_CTRL = 'Ctrl' in cond_stats.index
            if HAS_CTRL:
                ctrl_mean = cond_stats.loc['Ctrl', 'avg']
                ctrl_sd = cond_stats.loc['Ctrl', 'sd']
                ctrl_n = cond_stats.loc['Ctrl', 'n']
                def cohens_d(row):
                    pooled = np.sqrt(((row['n']-1)*row['sd']**2 + (ctrl_n-1)*ctrl_sd**2) / (row['n']+ctrl_n-2))
                    return (ctrl_mean - row['avg']) / pooled if pooled > 0 else 0.0
                cond_stats['cohens_d'] = cond_stats.apply(cohens_d, axis=1)
                cond_stats['pct_reduction'] = (ctrl_mean - cond_stats['avg']) / ctrl_mean * 100

            cond_stats = cond_stats.sort_values('avg')
            cond_order = cond_stats.index.tolist()

            roi_stats = df.groupby('ROI_label')['value'].agg(['mean', 'std', 'count']).rename(
                columns={'mean': 'avg', 'std': 'sd', 'count': 'n'}).sort_values('avg')
            roi_order = roi_stats.index.tolist()

            # significance (Mann-Whitney)
            def pval_to_stars(p):
                if p < 0.001: return "***"
                elif p < 0.01: return "**"
                elif p < 0.05: return "*"
                return "ns"

            sig_pairs = []
            cond_pos = {c: i for i, c in enumerate(cond_order)}
            for i, j in combinations(range(len(cond_order)), 2):
                g_a, g_b = cond_order[i], cond_order[j]
                a = df.loc[df['condition_group'] == g_a, 'value'].values
                b = df.loc[df['condition_group'] == g_b, 'value'].values
                if len(a) >= 2 and len(b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(a, b, alternative='two-sided')
                else:
                    pval = 1.0
                if pval < 0.05:
                    sig_pairs.append((i, j, pval, pval_to_stars(pval)))

            # academic style
            mpl.rcParams.update({
                "font.family": "Arial", "font.size": 9,
                "axes.titlesize": 11, "axes.labelsize": 10,
                "axes.linewidth": 0.8, "svg.fonttype": "none",
            })

            fig, (ax1, ax2, ax3) = plt.subplots(
                3, 1, figsize=(9, 14),
                gridspec_kw={"height_ratios": [1.4, 1.2, 0.8], "hspace": 0.45})

            # ── Panel A: by condition ──
            data_by_cond = [df.loc[df['condition_group'] == c, 'value'].values for c in cond_order]
            positions = np.arange(len(cond_order))

            vp = ax1.violinplot(data_by_cond, positions=positions,
                                showextrema=False, showmedians=False, widths=0.7)
            for i, body in enumerate(vp['bodies']):
                body.set_facecolor(cond_colors.get(cond_order[i], '#999999'))
                body.set_edgecolor('black'); body.set_linewidth(0.5); body.set_alpha(0.35)

            bp = ax1.boxplot(data_by_cond, positions=positions,
                             widths=0.25, patch_artist=True, showfliers=False, zorder=4,
                             medianprops=dict(color='black', linewidth=1.2),
                             whiskerprops=dict(linewidth=0.8), capprops=dict(linewidth=0.8),
                             boxprops=dict(linewidth=0.6))
            for i, patch in enumerate(bp['boxes']):
                patch.set_facecolor(cond_colors.get(cond_order[i], '#999999'))
                patch.set_alpha(0.85)

            rng = np.random.default_rng(42)
            for i, (cond, vals) in enumerate(zip(cond_order, data_by_cond)):
                jitter = rng.uniform(-0.12, 0.12, size=len(vals))
                ax1.scatter(positions[i] + jitter, vals, s=14,
                            color=cond_colors.get(cond, '#999999'),
                            edgecolor='black', linewidth=0.3, zorder=5, alpha=0.7)

            y_max = max(v.max() for v in data_by_cond if len(v) > 0) if data_by_cond else 1.0
            for i, cond in enumerate(cond_order):
                row = cond_stats.loc[cond]
                ax1.text(positions[i], max(row['avg'] * 0.15 + y_max * 0.02, 0.5),
                         f"N={int(row['n'])}", ha='center', va='bottom',
                         fontsize=7.5, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.8), zorder=6)
                if HAS_CTRL and cond != 'Ctrl':
                    top = np.max(df.loc[df['condition_group'] == cond, 'value'])
                    ax1.text(positions[i], top + y_max * 0.03,
                             f"d={row['cohens_d']:.2f}", ha='center', va='bottom',
                             fontsize=6.5, color='#333333')
                    sign = '-' if row['pct_reduction'] > 0 else '+'
                    ax1.text(positions[i], top + y_max * 0.09,
                             f"{sign}{abs(row['pct_reduction']):.0f}%",
                             ha='center', va='bottom', fontsize=6.5, fontweight='bold',
                             color='#B22222' if row['pct_reduction'] > 0 else '#228B22')

            # significance brackets
            def draw_bracket(ax, x1, x2, y, label, lw=0.7, color='#333333'):
                tip = (y - ax.get_ylim()[0]) * 0.02
                ax.plot([x1, x1, x2, x2], [y - tip, y, y, y - tip],
                        lw=lw, color=color, clip_on=False, zorder=10)
                ax.text((x1 + x2) / 2, y + tip * 0.3, label,
                        ha='center', va='bottom', fontsize=7, color=color,
                        fontweight='bold', zorder=10)

            sig_pairs.sort(key=lambda x: x[1] - x[0])
            bracket_base = y_max * 1.18
            bracket_step = y_max * 0.07
            for k, (i, j, pval, stars) in enumerate(sig_pairs):
                draw_bracket(ax1, i, j, bracket_base + k * bracket_step, stars)
            top_bracket = bracket_base + len(sig_pairs) * bracket_step
            ax1.set_ylim(0, top_bracket + y_max * 0.06)


            ax1.set_xticks(positions)
            ax1.set_xticklabels(cond_order, fontweight='bold')
            ax1.set_ylabel(y_label)
            ax1.set_title(f"A.  {title_base} by Stimulation Condition", loc='left', fontweight='bold')
            ax1.spines[['top', 'right']].set_visible(False)
            ax1.set_xlim(-0.6, len(cond_order) - 0.4)

            # ── Panel B: by ROI ──
            data_by_roi = [df.loc[df['ROI_label'] == r, 'value'].values for r in roi_order]
            positions_r = np.arange(len(roi_order))

            vp2 = ax2.violinplot(data_by_roi, positions=positions_r,
                                 showextrema=False, showmedians=False, widths=0.7)
            for body in vp2['bodies']:
                body.set_facecolor('#4C72B0'); body.set_edgecolor('black')
                body.set_linewidth(0.4); body.set_alpha(0.30)

            bp2 = ax2.boxplot(data_by_roi, positions=positions_r,
                              widths=0.22, patch_artist=True, showfliers=False, zorder=4,
                              medianprops=dict(color='black', linewidth=1),
                              whiskerprops=dict(linewidth=0.7), capprops=dict(linewidth=0.7),
                              boxprops=dict(linewidth=0.5))
            for patch in bp2['boxes']:
                patch.set_facecolor('#4C72B0'); patch.set_alpha(0.75)

            for i, (roi, vals) in enumerate(zip(roi_order, data_by_roi)):
                jitter = rng.uniform(-0.10, 0.10, size=len(vals))
                ax2.scatter(positions_r[i] + jitter, vals, s=10, color='#4C72B0',
                            edgecolor='black', linewidth=0.25, zorder=5, alpha=0.65)

            for i, roi in enumerate(roi_order):
                row = roi_stats.loc[roi]
                ax2.text(positions_r[i], max(y_max * 0.01, 0.3),
                         f"N={int(row['n'])}", ha='center', va='bottom',
                         fontsize=5.5, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.8), zorder=6)

            ax2.set_xticks(positions_r)
            ax2.set_xticklabels(roi_order, rotation=55, ha='right', fontsize=6.5)
            ax2.set_ylabel(y_label)
            ax2.set_title(f"B.  {title_base} by ROI", loc='left', fontweight='bold')
            ax2.spines[['top', 'right']].set_visible(False)
            ax2.set_xlim(-0.6, len(roi_order) - 0.4)
            y_max_r = max(v.max() for v in data_by_roi if len(v) > 0) if data_by_roi else 1.0
            ax2.set_ylim(0, y_max_r * 1.10)


            # ── Panel C: KDE distribution ──
            vals_all = df['value'].values
            if len(vals_all) > 1:
                t_grid = np.linspace(0, vals_all.max() + vals_all.max() * 0.1, 500)
                for cond in cond_order:
                    vals = df.loc[df['condition_group'] == cond, 'value'].values
                    if len(vals) < 2:
                        continue
                    kde = gaussian_kde(vals, bw_method='silverman')
                    density = kde(t_grid)
                    ax3.plot(t_grid, density, color=cond_colors.get(cond, '#999999'),
                             linewidth=1.5, label=cond)
                    ax3.fill_between(t_grid, density, color=cond_colors.get(cond, '#999999'), alpha=0.15)

            ax3.set_xlabel(y_label)
            ax3.set_ylabel('Density')
            ax3.set_title(f"C.  {title_base} Distribution (KDE) by Condition", loc='left', fontweight='bold')
            ax3.spines[['top', 'right']].set_visible(False)
            ax3.legend(frameon=True, framealpha=0.9, edgecolor='#cccccc', fontsize=7.5, ncol=4, loc='upper right')
            ax3.set_ylim(bottom=0)

            # Ctrl reference line
            if HAS_CTRL:
                for ax in (ax1, ax2):
                    ax.axhline(ctrl_mean, ls='--', lw=0.7, color='#888888', zorder=2)
                    ax.text(ax.get_xlim()[1], ctrl_mean + y_max * 0.01,
                            f"Ctrl mean = {ctrl_mean:.2f}", ha='right', va='bottom',
                            fontsize=7, color='#888888')
                ax3.axvline(ctrl_mean, ls='--', lw=0.7, color='#888888', zorder=2)

            # save
            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / f"{metric}_violin_plot.svg"
            png_path = parent_folder / f"{metric}_violin_plot.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            self._show_pub_plot_dialog(f"{title_base} — Violin Plot", png_path, svg_path)
            self.lbl_status.setText(f"{title_base} violin plot saved")
            print(f"[OK] {title_base} violin plot: {svg_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate violin plot:\n{str(e)}")
            traceback.print_exc()

    def _generate_roi_detail_plot(self, metric):
        """2-panel publication plot: bar per ROI with colour gradient + line trend."""
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        from scipy import stats as sp_stats

        df = self._build_metric_df(metric)
        if df is None or len(df) == 0:
            QMessageBox.warning(self, "Warning",
                                f"No data available for {metric}.")
            return

        metric_labels = {
            'latency': ('Mean Latency (s)', 'Spike Latency per ROI'),
            'amplitude': ('Mean Amplitude (dF/F)', 'Spike Amplitude per ROI'),
            'event_count': ('Mean Spike Count', 'Event Count per ROI'),
        }
        y_label, title_base = metric_labels[metric]

        try:
            df['ROI_label'] = df['ROI'].apply(self._clean_roi_label)

            # stats per ROI
            roi_stats = df.groupby('ROI_label')['value'].agg(['mean', 'std', 'count', 'sem']).rename(
                columns={'mean': 'avg', 'std': 'sd', 'count': 'n', 'sem': 'sem_val'})
            roi_stats['sem_val'] = roi_stats['sem_val'].fillna(0)
            roi_stats = roi_stats.sort_values('avg').reset_index()

            # academic style
            mpl.rcParams.update({
                "font.family": "Arial", "font.size": 9,
                "axes.titlesize": 12, "axes.labelsize": 11,
                "axes.linewidth": 0.8, "svg.fonttype": "none",
            })

            # colour gradient
            cmap = mpl.colormaps['RdYlBu_r']
            norm = mpl.colors.Normalize(vmin=roi_stats['avg'].min(), vmax=roi_stats['avg'].max())
            bar_colors = [cmap(norm(v)) for v in roi_stats['avg']]

            fig, (ax, ax2) = plt.subplots(
                2, 1, figsize=(12, 9.5),
                gridspec_kw={"height_ratios": [1, 0.7], "hspace": 0.40})

            x = np.arange(len(roi_stats))
            sem = roi_stats['sem_val'].values

            # ── Panel A: bar per ROI ──
            ax.bar(x, roi_stats['avg'], yerr=sem, capsize=3,
                   color=bar_colors, edgecolor='black', linewidth=0.5,
                   width=0.65, zorder=3,
                   error_kw={'elinewidth': 0.8, 'capthick': 0.8, 'color': '#333333'})

            # individual data points
            rng = np.random.default_rng(42)
            for i, row in roi_stats.iterrows():
                roi_label = row['ROI_label']
                vals = df.loc[df['ROI_label'] == roi_label, 'value'].values
                if len(vals) == 0:
                    continue
                jitter = rng.uniform(-0.18, 0.18, size=len(vals))
                ax.scatter(x[i] + jitter, vals, s=16, color='white', edgecolor='black',
                           linewidth=0.4, zorder=5, alpha=0.85)

            # labels on bars
            for i, row in roi_stats.iterrows():
                mean_val = row['avg']
                n = int(row['n'])
                bar_top = mean_val + row['sem_val']
                ax.text(x[i], bar_top + roi_stats['avg'].max() * 0.02,
                        f"{mean_val:.2f}", ha='center', va='bottom',
                        fontsize=7, fontweight='bold', color='#222222')
                ax.text(x[i], roi_stats['avg'].max() * 0.02,
                        f"N={n}", ha='center', va='bottom',
                        fontsize=6.5, fontweight='bold', color='#444444',
                        bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85), zorder=6)

            # grand mean
            grand_mean = np.average(roi_stats['avg'], weights=roi_stats['n'])
            ax.axhline(grand_mean, ls='--', lw=0.8, color='#888888', zorder=2)
            ax.text(x[-1] + 0.4, grand_mean + roi_stats['avg'].max() * 0.01,
                    f"weighted mean = {grand_mean:.2f}", ha='right', va='bottom',
                    fontsize=7.5, color='#888888')

            ax.set_xticks(x)
            ax.set_xticklabels(roi_stats['ROI_label'], rotation=45, ha='right', fontweight='bold')
            ax.set_ylabel(y_label)
            ax.set_title(f"A.  {title_base}", loc='left', fontweight='bold')
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_xlim(-0.6, len(roi_stats) - 0.4)
            ax.set_ylim(0, ax.get_ylim()[1] * 1.12)

            # colour bar
            sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=[ax, ax2], pad=0.02, aspect=40, shrink=0.6)
            cbar.set_label(y_label, fontsize=9)
            cbar.outline.set_linewidth(0.5)

            # ── Panel B: line trend ──
            means = roi_stats['avg'].values
            sems = roi_stats['sem_val'].values
            line_colors = [cmap(norm(v)) for v in means]

            ax2.plot(x, means, color='#333333', linewidth=1.2, zorder=3)
            ax2.fill_between(x, means - sems, np.maximum(means + sems, 0),
                             color='#4C72B0', alpha=0.15, zorder=2, label='SEM')

            for i in range(len(x)):
                ax2.plot(x[i], means[i], marker='o', markersize=7,
                         color=line_colors[i], markeredgecolor='black',
                         markeredgewidth=0.6, zorder=5)
                ax2.annotate(f"{means[i]:.2f}", (x[i], means[i]),
                             textcoords='offset points', xytext=(0, 9),
                             ha='center', va='bottom', fontsize=6.5, color='#222222',
                             fontweight='bold')

            ax2.axhline(grand_mean, ls='--', lw=0.8, color='#888888', zorder=1)
            ax2.text(x[-1] + 0.4, grand_mean + roi_stats['avg'].max() * 0.01,
                     f"weighted mean = {grand_mean:.2f}", ha='right', va='bottom',
                     fontsize=7.5, color='#888888')

            ax2.set_xticks(x)
            ax2.set_xticklabels(roi_stats['ROI_label'], rotation=45, ha='right', fontweight='bold')
            ax2.set_ylabel(y_label)
            ax2.set_title(f"B.  Mean {title_base.split(' per')[0]} Trend across ROIs",
                          loc='left', fontweight='bold')
            ax2.spines[['top', 'right']].set_visible(False)
            ax2.set_xlim(-0.6, len(roi_stats) - 0.4)
            ax2.set_ylim(0, max(means + sems) * 1.18 if len(means) > 0 else 1.0)

            ax2.legend(loc='upper left', fontsize=8, framealpha=0.9, edgecolor='#cccccc')

            # save
            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / f"{metric}_roi_detail.svg"
            png_path = parent_folder / f"{metric}_roi_detail.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            self._show_pub_plot_dialog(f"{title_base} — ROI Detail", png_path, svg_path)
            self.lbl_status.setText(f"{title_base} ROI detail plot saved")
            print(f"[OK] {title_base} ROI detail: {svg_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate ROI detail plot:\n{str(e)}")
            traceback.print_exc()

    # ──────────────────────────────────────────────────────────────────────────
    #  Shared colour helper
    # ──────────────────────────────────────────────────────────────────────────

    def _build_cond_colors(self, cond_list):
        """Return a {condition: hex_color} dict for the given list of conditions.

        Priority: user override → grouped default table → sequential fallback.
        """
        colors = {}
        fb_idx = 0
        for c in cond_list:
            if c in self._custom_cond_colors:
                colors[c] = self._custom_cond_colors[c]
            elif c in self._COND_GROUP_COLORS:
                colors[c] = self._COND_GROUP_COLORS[c]
            else:
                colors[c] = self._FALLBACK_COLORS[fb_idx % len(self._FALLBACK_COLORS)]
                fb_idx += 1
        return colors

    def _open_color_editor(self):
        """Open the interactive condition colour editor."""
        # Gather all condition groups currently present in loaded data
        if not self.latency_data:
            QMessageBox.information(self, "No Data", "Load data first to edit colours.")
            return
        import pandas as pd
        df = pd.DataFrame(self.latency_data)
        all_conds = sorted(df['condition'].apply(self.extract_condition_group).unique())
        current_colors = self._build_cond_colors(all_conds)

        dlg = _CondColorEditorDialog(all_conds, current_colors, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._custom_cond_colors.update(dlg.get_colors())
            self.lbl_status.setText("Condition colours updated.")

    # ──────────────────────────────────────────────────────────────────────────
    #  Publication Bar Plots — coloured bars, selective significance brackets
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_pub_bar_plot(self, metric):
        """Colored bar plot (mean ± SEM) with configurable condition order and
        user-selected significance brackets.  Also saves a significance matrix
        figure and CSV for downstream use."""
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        from scipy import stats as sp_stats
        from itertools import combinations

        df = self._build_metric_df(metric)
        if df is None or len(df) == 0:
            QMessageBox.warning(self, "Warning", f"No data available for {metric}.")
            return

        metric_labels = {
            'latency':     ('Latency (s)',       'Event Latency'),
            'amplitude':   ('Amplitude (ΔF/F)',  'Event Amplitude'),
            'event_count': ('Event Count',       'Event Count'),
        }
        y_label, title_base = metric_labels[metric]

        try:
            all_conds = sorted(df['condition_group'].unique())
            cond_colors = self._build_cond_colors(all_conds)

            # ── default condition order ──
            DEFAULT_ORDER = ["5s", "10s", "20s", "2mW", "2Hz", "5Hz", "Ctrl", "Far Light Control"]
            present = set(all_conds)
            ordered = [c for c in DEFAULT_ORDER if c in present]
            ordered += sorted(c for c in present if c not in ordered)

            # ── compute all pairwise Mann-Whitney stats ──
            all_pairs = []
            for i, j in combinations(range(len(ordered)), 2):
                g_a, g_b = ordered[i], ordered[j]
                a = df.loc[df['condition_group'] == g_a, 'value'].values
                b = df.loc[df['condition_group'] == g_b, 'value'].values
                if len(a) >= 2 and len(b) >= 2:
                    _, pval = sp_stats.mannwhitneyu(a, b, alternative='two-sided')
                else:
                    pval = 1.0
                all_pairs.append({
                    'idx_a': i, 'idx_b': j,
                    'group_a': g_a, 'group_b': g_b,
                    'n_a': len(a), 'n_b': len(b),
                    'mean_a': float(np.mean(a)) if len(a) else np.nan,
                    'mean_b': float(np.mean(b)) if len(b) else np.nan,
                    'pval': pval,
                    'stars': self._pval_to_stars(pval),
                    'significant': pval < 0.05,
                })

            # ── configuration dialog ──
            dlg = _PubBarPlotConfigDialog(ordered, all_pairs, cond_colors, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            final_order = dlg.get_condition_order()
            selected_pair_keys = dlg.get_selected_pairs()  # set of (g_a, g_b) tuples

            # Re-index pairs to final_order positions
            cond_pos = {c: i for i, c in enumerate(final_order)}
            sig_pairs_to_draw = []
            for p in all_pairs:
                key = (p['group_a'], p['group_b'])
                if key not in selected_pair_keys:
                    continue
                if p['group_a'] not in cond_pos or p['group_b'] not in cond_pos:
                    continue
                sig_pairs_to_draw.append((
                    cond_pos[p['group_a']], cond_pos[p['group_b']],
                    p['pval'], p['stars']
                ))
            # Sort shortest span first so brackets don't overlap needlessly
            sig_pairs_to_draw.sort(key=lambda x: x[1] - x[0])

            # ── compute per-condition stats in final order ──
            stats_rows = []
            for cond in final_order:
                vals = df.loc[df['condition_group'] == cond, 'value'].values
                if len(vals) == 0:
                    continue
                stats_rows.append({
                    'cond': cond, 'vals': vals,
                    'mean': float(np.mean(vals)),
                    'sem':  float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0,
                    'n':    len(vals),
                })
            if not stats_rows:
                QMessageBox.warning(self, "Warning", "No data after filtering.")
                return

            # ── publication figure style (Nature/Cell style) ──
            mpl.rcParams.update({
                "font.family":      "Arial",
                "font.size":        9,
                "axes.titlesize":   10,
                "axes.labelsize":   9,
                "axes.linewidth":   0.8,
                "xtick.major.width":0.8,
                "ytick.major.width":0.8,
                "xtick.major.size": 3.5,
                "ytick.major.size": 3.5,
                "xtick.direction":  "out",
                "ytick.direction":  "out",
                "svg.fonttype":     "none",
            })

            BAR_W   = 0.52          # bar width
            BAR_ALPHA = 0.82        # bar face transparency
            DOT_SIZE  = 22          # individual data point size
            DOT_ALPHA = 0.65

            n_bars = len(stats_rows)
            fig_w  = max(4.5, n_bars * 1.05 + 1.8)
            fig, ax = plt.subplots(figsize=(fig_w, 5.2))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')

            positions = np.arange(n_bars)
            rng = np.random.default_rng(42)

            # subtle horizontal grid behind bars
            ax.yaxis.grid(True, color='#e0e0e0', linewidth=0.5, linestyle='-', zorder=0)
            ax.set_axisbelow(True)

            for i, row in enumerate(stats_rows):
                hex_col = cond_colors.get(row['cond'], '#7B8794')
                r_int = int(hex_col[1:3], 16)
                g_int = int(hex_col[3:5], 16)
                b_int = int(hex_col[5:7], 16)
                face_rgba = (r_int/255, g_int/255, b_int/255, BAR_ALPHA)
                edge_rgba = (r_int/255 * 0.55, g_int/255 * 0.55, b_int/255 * 0.55, 1.0)

                # bar
                ax.bar(positions[i], row['mean'],
                       width=BAR_W, color=face_rgba,
                       edgecolor=edge_rgba, linewidth=0.9,
                       zorder=3)

                # SEM error bar drawn separately for fine control
                ax.errorbar(positions[i], row['mean'], yerr=row['sem'],
                            fmt='none', ecolor=edge_rgba,
                            elinewidth=1.1, capsize=3.5, capthick=1.1,
                            zorder=5)

                # individual data points: white fill, colour edge → clean look
                jitter = rng.uniform(-0.14, 0.14, size=len(row['vals']))
                ax.scatter(positions[i] + jitter, row['vals'],
                           s=DOT_SIZE, color='white',
                           edgecolor=edge_rgba, linewidth=0.9,
                           zorder=6, alpha=DOT_ALPHA)

                # sample-size annotation just above x-axis baseline
                ax.text(positions[i], ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 0,
                        f"n={row['n']}", ha='center', va='bottom',
                        fontsize=6.5, color='#555555', style='italic')

            # significance brackets
            all_vals = np.concatenate([r['vals'] for r in stats_rows])
            y_data_max = float(np.max(all_vals)) if len(all_vals) else 1.0
            y_bar_top  = max(r['mean'] + r['sem'] for r in stats_rows)
            bracket_base = max(y_data_max, y_bar_top) * 1.08
            bracket_step = max(y_data_max, y_bar_top) * 0.10

            def _draw_bracket(ax, x1, x2, y, label):
                tip = bracket_step * 0.18
                ax.plot([x1, x1, x2, x2],
                        [y - tip, y, y, y - tip],
                        lw=0.8, color='#2c2c2c', clip_on=False, zorder=10)
                ax.text((x1 + x2) / 2, y + tip * 0.25, label,
                        ha='center', va='bottom',
                        fontsize=8, color='#2c2c2c',
                        fontweight='bold', zorder=10)

            for k, (xi, xj, _pv, stars) in enumerate(sig_pairs_to_draw):
                _draw_bracket(ax, xi, xj, bracket_base + k * bracket_step, stars)

            ylim_top = bracket_base + len(sig_pairs_to_draw) * bracket_step + bracket_step * 0.5
            ax.set_ylim(bottom=0, top=max(ylim_top, y_bar_top * 1.30))

            # axes decoration
            ax.set_xticks(positions)
            cond_labels = [r['cond'] for r in stats_rows]
            ax.set_xticklabels(cond_labels,
                               fontsize=8.5, fontweight='bold',
                               rotation=30 if max(len(c) for c in cond_labels) > 5 else 0,
                               ha='right' if max(len(c) for c in cond_labels) > 5 else 'center')
            ax.set_ylabel(y_label, labelpad=6)
            ax.set_title(f"{title_base} by Stimulation Condition",
                         fontweight='bold', pad=10, loc='left')
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines['left'].set_linewidth(0.8)
            ax.spines['bottom'].set_linewidth(0.8)
            ax.set_xlim(-0.65, n_bars - 0.35)
            fig.tight_layout(pad=1.4)

            # ── save bar plot ──
            parent_folder = Path(self.csv_path)
            bar_svg = parent_folder / f"{metric}_pub_bar_plot.svg"
            bar_png = parent_folder / f"{metric}_pub_bar_plot.png"
            fig.savefig(str(bar_svg), format='svg', bbox_inches='tight')
            fig.savefig(str(bar_png), format='png', dpi=300, bbox_inches='tight', facecolor='white')
            plt.close(fig)

            # ── significance matrix figure ──
            sig_png, sig_csv = self._save_significance_matrix(
                metric, all_pairs, final_order, parent_folder)

            self._show_pub_plot_dialog(f"{title_base} — Bar Plot", bar_png, bar_svg,
                                       extra_paths=[("Significance matrix", sig_png),
                                                    ("Significance CSV", sig_csv)])
            self.lbl_status.setText(f"{title_base} bar plot saved")
            print(f"[OK] {title_base} bar plot: {bar_svg}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate bar plot:\n{str(e)}")
            traceback.print_exc()

    def _pval_to_stars(self, p):
        if p < 0.001: return "***"
        if p < 0.01:  return "**"
        if p < 0.05:  return "*"
        return "ns"

    def _save_significance_matrix(self, metric, all_pairs, cond_order, parent_folder):
        """Save significance matrix as PNG figure and CSV."""
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        import pandas as pd

        n = len(cond_order)
        pmat = np.ones((n, n))
        idx_map = {c: i for i, c in enumerate(cond_order)}

        csv_rows = []
        for p in all_pairs:
            if p['group_a'] in idx_map and p['group_b'] in idx_map:
                i, j = idx_map[p['group_a']], idx_map[p['group_b']]
                pmat[i, j] = p['pval']
                pmat[j, i] = p['pval']
                csv_rows.append({
                    'Condition_A': p['group_a'], 'Condition_B': p['group_b'],
                    'n_A': p['n_a'], 'n_B': p['n_b'],
                    'Mean_A': round(p['mean_a'], 4) if not np.isnan(p['mean_a']) else '',
                    'Mean_B': round(p['mean_b'], 4) if not np.isnan(p['mean_b']) else '',
                    'p_value': round(p['pval'], 5),
                    'Significance': p['stars'],
                })

        # CSV
        sig_csv = parent_folder / f"{metric}_significance_table.csv"
        pd.DataFrame(csv_rows).to_csv(str(sig_csv), index=False)

        # ── significance matrix figure — clean academic heatmap ──
        mpl.rcParams.update({
            "font.family": "Arial", "font.size": 9, "svg.fonttype": "none",
        })
        cell_px  = max(0.80, 7.5 / max(n, 1))
        fig_size = max(4.5, n * cell_px + 2.0)
        fig, ax  = plt.subplots(figsize=(fig_size, fig_size * 0.92))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#f8f8f8')

        # Blue-grey → white → deep orange-red (NS is white, significant is warm)
        # Using a perceptually-uniform diverging feel anchored at p=0.05
        cmap = mpl.colors.LinearSegmentedColormap.from_list(
            'pub_sig',
            [
                '#f7f7f7',   # p ~ 0.05  (barely significant / NS) — near white
                '#FDD0A2',   # p ~ 0.02  — light peach
                '#FD8D3C',   # p ~ 0.01  — warm orange
                '#D94801',   # p ~ 0.001 — burnt orange
                '#7F2704',   # p < 0.001 — deep mahogany
            ],
            N=256
        )
        norm = mpl.colors.Normalize(vmin=0, vmax=0.05)

        # Lower triangle only
        mask_upper = np.triu(np.ones((n, n), dtype=bool), k=0)
        display = np.where(mask_upper, np.nan, pmat)
        im = ax.imshow(display, cmap=cmap, norm=norm, aspect='equal', zorder=1)

        # cell annotations
        fs_cell = max(6, min(9, int(72 / max(n, 1))))
        for i in range(n):
            for j in range(n):
                if j >= i:
                    continue
                p_val = pmat[i, j]
                stars = self._pval_to_stars(p_val)
                # white text on dark cells, dark on light cells
                text_color = 'white' if p_val < 0.005 else '#1a1a1a'
                # top line: significance stars; bottom line: numeric p
                ax.text(j, i,
                        f"{stars}\n{'<0.001' if p_val < 0.001 else f'{p_val:.3f}'}",
                        ha='center', va='center',
                        fontsize=fs_cell, color=text_color,
                        fontweight='bold', linespacing=1.3)

        # diagonal and upper triangle: clean light fill
        for i in range(n):
            for j in range(i, n):
                fc = '#e8e8e8' if i == j else '#f2f2f2'
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                             fc=fc, ec='white', lw=1.0, zorder=2))
            # diagonal label
            ax.text(i, i, cond_order[i], ha='center', va='center',
                    fontsize=fs_cell, fontweight='bold', color='#444444', zorder=3)

        # grid lines
        for k in range(n + 1):
            ax.axhline(k - 0.5, color='white', lw=1.0, zorder=4)
            ax.axvline(k - 0.5, color='white', lw=1.0, zorder=4)

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(cond_order, rotation=40, ha='right',
                           fontsize=8, fontweight='bold')
        ax.set_yticklabels(cond_order, fontsize=8, fontweight='bold')
        ax.set_title(
            f"Pairwise Significance — {metric.replace('_', ' ').title()}\n"
            f"Mann–Whitney U test (two-sided)",
            fontweight='bold', pad=10, fontsize=9, loc='left')
        ax.tick_params(length=0)

        cbar = fig.colorbar(im, ax=ax, shrink=0.55, pad=0.03,
                            orientation='vertical')
        cbar.set_label("p-value", fontsize=8)
        cbar.outline.set_linewidth(0.4)
        cbar.ax.tick_params(labelsize=7)
        # mark the 0.05 significance threshold on the colourbar
        cbar.ax.axhline(y=0.05 / 0.05, color='#555555', lw=0.8, ls='--')

        ax.spines[:].set_visible(False)
        fig.tight_layout(pad=1.5)

        sig_png = parent_folder / f"{metric}_significance_matrix.png"
        sig_svg = parent_folder / f"{metric}_significance_matrix.svg"
        fig.savefig(str(sig_svg), format='svg', bbox_inches='tight')
        fig.savefig(str(sig_png), format='png', dpi=300, bbox_inches='tight', facecolor='white')
        plt.close(fig)

        print(f"[OK] Significance matrix: {sig_png}")
        print(f"[OK] Significance CSV:    {sig_csv}")
        return sig_png, sig_csv

    def _show_pub_plot_dialog(self, title, png_path, svg_path, extra_paths=None):
        """Show a publication plot in a scrollable dialog.

        extra_paths: optional list of (label, path) tuples for additional
                     generated files (e.g. significance matrix PNG/CSV).
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(1000, 850)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Main bar/violin plot
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(str(png_path))
        if not pix.isNull():
            img_label.setPixmap(pix.scaled(
                950, 3000,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(img_label)

        # If extra PNGs exist (e.g. significance matrix), show them below
        if extra_paths:
            for label, path in extra_paths:
                if path is None:
                    continue
                path_str = str(path)
                if path_str.endswith('.png'):
                    hdr = QLabel(f"── {label} ──")
                    hdr.setStyleSheet("color: #ccc; font-size: 10px; padding: 4px 0 1px 0;")
                    layout.addWidget(hdr)
                    extra_lbl = QLabel()
                    extra_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    epix = QPixmap(path_str)
                    if not epix.isNull():
                        extra_lbl.setPixmap(epix.scaled(
                            950, 1200,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation))
                    layout.addWidget(extra_lbl)

        # File path labels
        for t in [f"SVG: {svg_path}", f"PNG: {png_path}"]:
            lbl = QLabel(t)
            lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
            layout.addWidget(lbl)
        if extra_paths:
            for label, path in extra_paths:
                if path is not None:
                    lbl = QLabel(f"{label}: {path}")
                    lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
                    layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)
        dialog.exec()

    def export_spike_count_csv(self):
        """Export total spike counts per condition/ROI as a CSV file."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            extract_condition_group = self.extract_condition_group

            # Per-condition (replicate) counts
            per_cond = df.groupby('condition').size().reset_index(name='spike_count')
            per_cond['condition_group'] = per_cond['condition'].apply(extract_condition_group)

            # Per-condition-group summary
            group_summary = per_cond.groupby('condition_group').agg(
                total_spikes=('spike_count', 'sum'),
                n_replicates=('spike_count', 'count'),
                mean_spikes=('spike_count', 'mean'),
                std_spikes=('spike_count', 'std'),
            ).reset_index()

            # Per ROI counts
            per_roi = df.groupby('ROI').size().reset_index(name='spike_count')

            parent_folder = Path(self.csv_path)

            # Save all three tables
            path_per_cond = parent_folder / "spike_count_per_condition.csv"
            per_cond.to_csv(path_per_cond, index=False)

            path_group = parent_folder / "spike_count_by_group.csv"
            group_summary.to_csv(path_group, index=False)

            path_roi = parent_folder / "spike_count_per_roi.csv"
            per_roi.to_csv(path_roi, index=False)

            QMessageBox.information(
                self, "Spike Count Exported",
                f"Saved 3 files to:\n{parent_folder}\n\n"
                f"  - spike_count_per_condition.csv  ({len(per_cond)} rows)\n"
                f"  - spike_count_by_group.csv  ({len(group_summary)} groups)\n"
                f"  - spike_count_per_roi.csv  ({len(per_roi)} ROIs)"
            )
            self.lbl_status.setText("Spike count CSVs exported")
            print(f"[OK] Spike count CSVs saved to {parent_folder}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export spike counts:\n{str(e)}")
            traceback.print_exc()

    def generate_per_roi_condition_plot(self):
        """Generate per-ROI subplots comparing latency across conditions with significance."""
        if not self.latency_data:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy import stats as sp_stats
        from itertools import combinations

        filtered_data = [
            row for idx, row in enumerate(self.latency_data)
            if self.checkboxes[idx].isChecked()
        ]
        if not filtered_data:
            QMessageBox.warning(self, "Warning", "No spikes selected")
            return

        try:
            df = pd.DataFrame(filtered_data)

            # Extract condition group
            extract_condition_group = self.extract_condition_group

            df['condition_group'] = df['condition'].apply(extract_condition_group)
            rois = sorted(df['ROI'].unique())
            groups = sorted(df['condition_group'].unique())
            n_rois = len(rois)
            n_groups = len(groups)

            if n_rois == 0 or n_groups < 2:
                QMessageBox.warning(self, "Warning",
                                    "Need at least 1 ROI and 2 condition groups.")
                return

            def pval_to_stars(p):
                if p < 0.001:
                    return "***"
                elif p < 0.01:
                    return "**"
                elif p < 0.05:
                    return "*"
                return "ns"

            # Figure layout: grid of subplots, one per ROI
            n_cols = min(3, n_rois)
            n_rows = (n_rois + n_cols - 1) // n_cols

            plt.rcParams.update({
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "svg.fonttype": "none",
            })

            fig, axes = plt.subplots(n_rows, n_cols,
                                     figsize=(5 * n_cols, 4.5 * n_rows),
                                     dpi=150, squeeze=False)
            fig.patch.set_facecolor('white')

            bar_width = 0.55
            all_stats_rows = []

            for roi_idx, roi_name in enumerate(rois):
                row_i = roi_idx // n_cols
                col_i = roi_idx % n_cols
                ax = axes[row_i][col_i]
                ax.set_facecolor('white')

                roi_df = df[df['ROI'] == roi_name]

                # Collect data per condition group for this ROI
                group_data = {}
                for g in groups:
                    vals = roi_df.loc[roi_df['condition_group'] == g, 'latency_s'].values
                    if len(vals) > 0:
                        group_data[g] = vals

                active_groups = [g for g in groups if g in group_data]
                n_active = len(active_groups)

                if n_active == 0:
                    ax.set_title(f"{roi_name}\n(no data)", fontsize=11, fontweight='bold')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    continue

                means = [np.mean(group_data[g]) for g in active_groups]
                sems = [sp_stats.sem(group_data[g]) if len(group_data[g]) > 1 else 0.0
                        for g in active_groups]
                x_pos = np.arange(n_active)

                # Bars
                ax.bar(x_pos, means, width=bar_width, yerr=sems,
                       capsize=4, color='#b0c4de', edgecolor='black',
                       linewidth=1.0, error_kw=dict(lw=1.2, capthick=1.2),
                       zorder=2)

                # Individual data points
                rng = np.random.default_rng(roi_idx * 7 + 42)
                for gi, g in enumerate(active_groups):
                    vals = group_data[g]
                    jitter = rng.uniform(-0.15, 0.15, size=len(vals))
                    ax.scatter(gi + jitter, vals, color='#333333', s=14,
                               edgecolors='black', linewidths=0.3, alpha=0.7, zorder=3)

                # Pairwise significance
                if n_active >= 2:
                    pair_results = []
                    for i, j in combinations(range(n_active), 2):
                        g_a, g_b = active_groups[i], active_groups[j]
                        arr_a, arr_b = group_data[g_a], group_data[g_b]
                        if len(arr_a) >= 2 and len(arr_b) >= 2:
                            _, pval = sp_stats.mannwhitneyu(arr_a, arr_b, alternative='two-sided')
                        else:
                            pval = 1.0
                        pair_results.append((i, j, g_a, g_b, pval))
                        all_stats_rows.append({
                            'ROI': roi_name,
                            'Group_A': g_a, 'Group_B': g_b,
                            'n_A': len(arr_a), 'n_B': len(arr_b),
                            'Mean_A': np.mean(arr_a), 'Mean_B': np.mean(arr_b),
                            'p_value': pval, 'Significance': pval_to_stars(pval),
                        })

                    sig_pairs = [(i, j, p) for i, j, _, _, p in pair_results if p < 0.05]
                    sig_pairs.sort(key=lambda x: x[1] - x[0])

                    if sig_pairs:
                        y_max = max(np.max(group_data[g]) for g in active_groups)
                        bracket_y = y_max * 1.08
                        bracket_step = y_max * 0.10
                        for rank, (i, j, pval) in enumerate(sig_pairs):
                            y_bar = bracket_y + rank * bracket_step
                            ax.plot([i, i, j, j],
                                    [y_bar - bracket_step * 0.15, y_bar, y_bar,
                                     y_bar - bracket_step * 0.15],
                                    lw=1.0, color='black')
                            ax.text((i + j) / 2, y_bar + bracket_step * 0.05,
                                    pval_to_stars(pval),
                                    ha='center', va='bottom', fontsize=9, fontweight='bold')
                        top_y = bracket_y + len(sig_pairs) * bracket_step + bracket_step * 0.3
                        ax.set_ylim(bottom=0, top=top_y)
                    else:
                        ax.set_ylim(bottom=0)
                else:
                    ax.set_ylim(bottom=0)

                ax.set_title(roi_name, fontsize=11, fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(active_groups, fontsize=9, fontweight='bold')
                ax.set_ylabel('Latency (s)', fontsize=10)
                ax.tick_params(axis='y', labelsize=9)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_linewidth(1.0)
                ax.spines['bottom'].set_linewidth(1.0)


            # Hide unused subplots
            for idx in range(n_rois, n_rows * n_cols):
                row_i = idx // n_cols
                col_i = idx % n_cols
                axes[row_i][col_i].set_visible(False)

            fig.suptitle("Latency per Condition for Each ROI", fontsize=14, fontweight='bold', y=1.01)
            plt.tight_layout()

            # Save
            parent_folder = Path(self.csv_path)
            svg_path = parent_folder / "latency_per_roi_per_condition.svg"
            png_path = parent_folder / "latency_per_roi_per_condition.png"
            fig.savefig(str(svg_path), format='svg', bbox_inches='tight')
            fig.savefig(str(png_path), format='png', dpi=300, bbox_inches='tight',
                        facecolor='white')
            plt.close(fig)

            # Save Mann-Whitney significance CSV
            if all_stats_rows:
                mw_df = pd.DataFrame(all_stats_rows)
                mw_csv = parent_folder / "latency_per_roi_per_condition_significance.csv"
                mw_df.to_csv(mw_csv, index=False)
            else:
                mw_df = pd.DataFrame()
                mw_csv = None

            # ---- (1) Linear Mixed Effects Model ----
            lmm_df = None
            lmm_csv = None
            try:
                import statsmodels.formula.api as smf

                # Need per-spike data with condition_group and ROI
                lmm_input = df[['latency_s', 'condition_group', 'ROI']].dropna()
                if len(lmm_input['condition_group'].unique()) >= 2 and len(lmm_input['ROI'].unique()) >= 2:
                    md = smf.mixedlm("latency_s ~ C(condition_group)", lmm_input, groups=lmm_input["ROI"])
                    mdf = md.fit(reml=True)

                    # Extract fixed effects table
                    lmm_rows = []
                    for term, coef in mdf.fe_params.items():
                        se = mdf.bse_fe[term]
                        z = mdf.tvalues[term]
                        p = mdf.pvalues[term]
                        lmm_rows.append({
                            'Term': term,
                            'Coefficient': coef,
                            'Std_Error': se,
                            'z_value': z,
                            'p_value': p,
                            'Significance': pval_to_stars(p),
                        })
                    # Add random effect variance
                    lmm_rows.append({
                        'Term': 'ROI (random effect var)',
                        'Coefficient': float(mdf.cov_re.iloc[0, 0]),
                        'Std_Error': np.nan, 'z_value': np.nan,
                        'p_value': np.nan, 'Significance': '',
                    })
                    lmm_df = pd.DataFrame(lmm_rows)
                    lmm_csv = parent_folder / "latency_lmm_results.csv"
                    lmm_df.to_csv(lmm_csv, index=False)
                    print(f"[OK] LMM results: {lmm_csv}")
                else:
                    print("[SKIP] LMM: need >= 2 condition groups and >= 2 ROIs")
            except ImportError:
                print("[SKIP] LMM: statsmodels not installed (pip install statsmodels)")
            except Exception as e_lmm:
                print(f"[WARN] LMM failed: {e_lmm}")

            # ---- (2) Paired t-test (per-ROI mean latency) ----
            paired_rows = []
            # Build per-ROI mean latency matrix
            roi_cond_means = df.groupby(['ROI', 'condition_group'])['latency_s'].mean().unstack()

            for g_a, g_b in combinations(groups, 2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                n_paired = len(paired)
                if n_paired < 2:
                    continue

                vals_a = paired[g_a].values
                vals_b = paired[g_b].values

                t_stat, p_val = sp_stats.ttest_rel(vals_a, vals_b)

                # Cohen's d for paired samples
                diff = vals_a - vals_b
                d_cohen = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else 0.0

                paired_rows.append({
                    'Group_A': g_a, 'Group_B': g_b,
                    'n_paired_ROIs': n_paired,
                    'Mean_A': np.mean(vals_a), 'Mean_B': np.mean(vals_b),
                    'Mean_Diff': np.mean(diff),
                    't_statistic': t_stat,
                    'p_value': p_val,
                    'Cohens_d': d_cohen,
                    'Significance': pval_to_stars(p_val),
                })

            paired_df = pd.DataFrame(paired_rows) if paired_rows else None
            paired_csv = None
            if paired_df is not None and len(paired_df) > 0:
                paired_csv = parent_folder / "latency_paired_ttest.csv"
                paired_df.to_csv(paired_csv, index=False)
                print(f"[OK] Paired t-test: {paired_csv}")

            # ---- (3) Spearman correlation (per-ROI mean latency between conditions) ----
            spearman_rows = []
            for g_a, g_b in combinations(groups, 2):
                if g_a not in roi_cond_means.columns or g_b not in roi_cond_means.columns:
                    continue
                paired = roi_cond_means[[g_a, g_b]].dropna()
                if len(paired) < 3:
                    continue

                rho, p_val = sp_stats.spearmanr(paired[g_a].values, paired[g_b].values)
                spearman_rows.append({
                    'Condition_A': g_a, 'Condition_B': g_b,
                    'n_ROIs': len(paired),
                    'Spearman_rho': rho,
                    'p_value': p_val,
                    'Significance': pval_to_stars(p_val),
                })

            spearman_df = pd.DataFrame(spearman_rows) if spearman_rows else None
            spearman_csv = None
            if spearman_df is not None and len(spearman_df) > 0:
                spearman_csv = parent_folder / "latency_spearman_correlation.csv"
                spearman_df.to_csv(spearman_csv, index=False)
                print(f"[OK] Spearman correlation: {spearman_csv}")

            # Show dialog with all results
            self._show_per_roi_condition_dialog(
                png_path, svg_path, mw_csv,
                sig_df=mw_df if len(mw_df) > 0 else None,
                lmm_df=lmm_df, lmm_csv=lmm_csv,
                paired_df=paired_df, paired_csv=paired_csv,
                spearman_df=spearman_df, spearman_csv=spearman_csv,
            )

            self.lbl_status.setText("Per-ROI condition plot + analyses saved")
            print(f"[OK] Per-ROI condition plot SVG: {svg_path}")
            print(f"[OK] Per-ROI condition plot PNG: {png_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"Failed to generate per-ROI condition plot:\n{str(e)}")
            traceback.print_exc()

    def _show_per_roi_condition_dialog(self, png_path, svg_path, sig_csv_path,
                                       sig_df=None, lmm_df=None, lmm_csv=None,
                                       paired_df=None, paired_csv=None,
                                       spearman_df=None, spearman_csv=None):
        """Show per-ROI condition plot + all analysis tables in a dialog."""
        from PyQt6.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem,
                                     QVBoxLayout, QPushButton, QHBoxLayout,
                                     QScrollArea, QWidget)

        table_style = """
            QTableWidget { background-color: #1e222d; color: white;
                           gridline-color: #3a3f4b; border: 1px solid #3a3f4b; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #2a2e3a; color: white;
                                   padding: 8px; border: 1px solid #3a3f4b;
                                   font-weight: bold; }
        """
        section_style = "font-size: 13px; font-weight: bold; color: white; padding: 6px;"

        def add_df_table(parent_layout, title, dataframe):
            """Helper to add a labelled table for a DataFrame."""
            lbl = QLabel(title)
            lbl.setStyleSheet(section_style)
            parent_layout.addWidget(lbl)

            tbl = QTableWidget()
            tbl.setRowCount(len(dataframe))
            tbl.setColumnCount(len(dataframe.columns))
            tbl.setHorizontalHeaderLabels(dataframe.columns.tolist())
            tbl.setStyleSheet(table_style)

            for r_idx, (_, r_data) in enumerate(dataframe.iterrows()):
                for c_idx, c_name in enumerate(dataframe.columns):
                    val = r_data[c_name]
                    # Format display
                    if pd.isna(val):
                        disp = ""
                    elif c_name == 'p_value':
                        disp = f"{float(val):.4f}"
                    elif c_name in ('Mean_A', 'Mean_B', 'Mean_Diff', 'Coefficient',
                                    'Std_Error', 'z_value', 't_statistic',
                                    'Cohens_d', 'Spearman_rho'):
                        disp = f"{float(val):.4f}"
                    elif c_name in ('n_A', 'n_B', 'n_paired_ROIs', 'n_ROIs'):
                        disp = str(int(val))
                    else:
                        disp = str(val)

                    item = QTableWidgetItem(disp)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    if c_name == 'Significance' and str(val) not in ('ns', '', 'nan'):
                        item.setBackground(QColor('#2d4356'))
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    if c_name == 'p_value' and not pd.isna(val) and float(val) < 0.05:
                        item.setBackground(QColor('#2d4356'))

                    tbl.setItem(r_idx, c_idx, item)

            tbl.resizeColumnsToContents()
            tbl.setAlternatingRowColors(True)
            # Set minimum height so each panel is tall enough to read
            row_height = 32
            header_height = 36
            min_h = header_height + len(dataframe) * row_height + 20
            tbl.setMinimumHeight(max(250, min_h))
            parent_layout.addWidget(tbl)

        # --- Build dialog ---
        import pandas as pd

        dialog = QDialog(self)
        dialog.setWindowTitle("Latency per Condition for Each ROI — Full Analysis")
        dialog.resize(1100, 1200)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Plot image
        plot_label = QLabel()
        plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_pixmap = QPixmap(str(png_path))
        if not plot_pixmap.isNull():
            scaled = plot_pixmap.scaled(
                1050, 2000,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            plot_label.setPixmap(scaled)
        layout.addWidget(plot_label)

        # 1. Mann-Whitney U table
        if sig_df is not None and len(sig_df) > 0:
            add_df_table(layout, "Per-ROI Pairwise Significance (Mann-Whitney U)", sig_df)

        # 2. LMM table
        if lmm_df is not None and len(lmm_df) > 0:
            add_df_table(layout, "Linear Mixed Effects Model (condition ~ fixed, ROI ~ random)", lmm_df)

        # 3. Paired t-test table
        if paired_df is not None and len(paired_df) > 0:
            add_df_table(layout, "Paired t-test (per-ROI mean latency) + Cohen's d", paired_df)

        # 4. Spearman correlation table
        if spearman_df is not None and len(spearman_df) > 0:
            add_df_table(layout, "Spearman Correlation (per-ROI mean latency between conditions)", spearman_df)

        # Path labels
        paths = [f"SVG: {svg_path}", f"PNG: {png_path}"]
        if sig_csv_path:
            paths.append(f"Mann-Whitney CSV: {sig_csv_path}")
        if lmm_csv:
            paths.append(f"LMM CSV: {lmm_csv}")
        if paired_csv:
            paths.append(f"Paired t-test CSV: {paired_csv}")
        if spearman_csv:
            paths.append(f"Spearman CSV: {spearman_csv}")
        for label_text in paths:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaa; font-size: 10px; padding: 1px;")
            layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)

        dialog.exec()

    def show_categorization_results(self, stats_df, csv_path, plot_path, category_type):
        """Show categorization results in a dialog with table and plot"""
        from PyQt6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QPushButton, QHBoxLayout

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Spike Latency by {category_type}")
        dialog.resize(1000, 800)  # Larger default size

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(f"Statistics grouped by {category_type}")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white; padding: 10px;")
        layout.addWidget(info_label)

        # Use splitter for adjustable table/plot sizes
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)

        # Table
        table = QTableWidget()
        table.setRowCount(len(stats_df))
        table.setColumnCount(len(stats_df.columns))
        table.setHorizontalHeaderLabels(stats_df.columns.tolist())

        # Style table
        table.setStyleSheet("""
            QTableWidget {
                background-color: #1e222d;
                color: white;
                gridline-color: #3a3f4b;
                border: 1px solid #3a3f4b;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3f4b;
            }
            QHeaderView::section {
                background-color: #2a2e3a;
                color: white;
                padding: 10px;
                border: 1px solid #3a3f4b;
                font-weight: bold;
            }
        """)

        # Populate table
        for row_idx, (_, row_data) in enumerate(stats_df.iterrows()):
            for col_idx, col_name in enumerate(stats_df.columns):
                value = row_data[col_name]

                # Format value
                if col_name in ['Avg_Latency_s', 'Median_Latency_s', 'Std_Latency_s', 'SEM_Latency_s']:
                    display_value = f"{float(value):.3f}"
                elif col_name == 'Spike_Count':
                    display_value = str(int(value))
                else:
                    display_value = str(value)

                item = QTableWidgetItem(display_value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()
        table.setAlternatingRowColors(True)
        splitter.addWidget(table)

        # Plot image
        plot_label = QLabel()
        plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_pixmap = QPixmap(str(plot_path))
        if not plot_pixmap.isNull():
            scaled_pixmap = plot_pixmap.scaled(
                950, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            plot_label.setPixmap(scaled_pixmap)
        splitter.addWidget(plot_label)

        # Set initial splitter sizes (table gets 40%, plot gets 60%)
        splitter.setSizes([300, 450])
        layout.addWidget(splitter)

        # Path labels
        csv_label = QLabel(f"CSV: {csv_path}")
        csv_label.setStyleSheet("color: #aaa; font-size: 10px; padding: 2px;")
        plot_label_path = QLabel(f"Plot: {plot_path}")
        plot_label_path.setStyleSheet("color: #aaa; font-size: 10px; padding: 2px;")
        layout.addWidget(csv_label)
        layout.addWidget(plot_label_path)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(35)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        dialog.exec()


# ==========================================
# 5. PUB BAR PLOT CONFIG DIALOG
# ==========================================
class _PubBarPlotConfigDialog(QDialog):
    """Dialog for configuring publication bar plots.

    Lets the user:
      1. Reorder conditions using Up / Down buttons.
      2. Choose which pairwise significance comparisons to annotate.
    """

    def __init__(self, cond_order, all_pairs, cond_colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Bar Plot")
        self.resize(680, 520)

        self._cond_colors = cond_colors
        self._all_pairs = all_pairs

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # ── Section 1: Condition ordering ──────────────────────────────────
        grp_order = QGroupBox("Condition Order  (select and use Up / Down to reorder)")
        order_layout = QHBoxLayout(grp_order)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for c in cond_order:
            item = QListWidgetItem(c)
            hex_col = cond_colors.get(c, '#999999')
            from PyQt6.QtGui import QColor
            item.setBackground(QColor(hex_col))
            # choose black or white text based on luminance
            r, g, b = int(hex_col[1:3], 16), int(hex_col[3:5], 16), int(hex_col[5:7], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            item.setForeground(QColor('#000000' if lum > 140 else '#ffffff'))
            self._list.addItem(item)
        order_layout.addWidget(self._list, 1)

        btn_col = QVBoxLayout()
        btn_up = QPushButton("▲ Up")
        btn_up.setFixedHeight(28)
        btn_up.clicked.connect(self._move_up)
        btn_dn = QPushButton("▼ Down")
        btn_dn.setFixedHeight(28)
        btn_dn.clicked.connect(self._move_down)
        btn_col.addWidget(btn_up)
        btn_col.addWidget(btn_dn)
        btn_col.addStretch()
        order_layout.addLayout(btn_col)
        main_layout.addWidget(grp_order)

        # ── Section 2: Significance pairs ──────────────────────────────────
        grp_sig = QGroupBox("Significance Brackets to Annotate")
        sig_v = QVBoxLayout(grp_sig)

        # quick-select buttons
        qs_row = QHBoxLayout()
        btn_all_sig = QPushButton("Check Significant (*,**,***)")
        btn_all_sig.setFixedHeight(24)
        btn_all_sig.clicked.connect(lambda: self._check_by(lambda p: p['significant']))
        btn_none = QPushButton("Uncheck All")
        btn_none.setFixedHeight(24)
        btn_none.clicked.connect(lambda: self._check_by(lambda p: False))
        btn_all = QPushButton("Check All")
        btn_all.setFixedHeight(24)
        btn_all.clicked.connect(lambda: self._check_by(lambda p: True))
        qs_row.addWidget(btn_all_sig)
        qs_row.addWidget(btn_all)
        qs_row.addWidget(btn_none)
        qs_row.addStretch()
        sig_v.addLayout(qs_row)

        self._sig_table = QTableWidget(0, 5)
        self._sig_table.setHorizontalHeaderLabels(
            ["Show", "Condition A", "Condition B", "p-value", "Stars"])
        self._sig_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._sig_table.horizontalHeader().setStretchLastSection(True)
        self._sig_table.verticalHeader().setVisible(False)
        self._sig_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._sig_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)

        self._chk_map = {}  # (g_a, g_b) -> QCheckBox
        for p in all_pairs:
            row = self._sig_table.rowCount()
            self._sig_table.insertRow(row)

            chk = QCheckBox()
            chk.setChecked(p['significant'])
            chk_cell = QWidget()
            chk_layout = QHBoxLayout(chk_cell)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self._sig_table.setCellWidget(row, 0, chk_cell)
            self._chk_map[(p['group_a'], p['group_b'])] = chk

            self._sig_table.setItem(row, 1, QTableWidgetItem(p['group_a']))
            self._sig_table.setItem(row, 2, QTableWidgetItem(p['group_b']))
            pval_item = QTableWidgetItem(f"{p['pval']:.4f}")
            pval_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._sig_table.setItem(row, 3, pval_item)
            stars_item = QTableWidgetItem(p['stars'])
            stars_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p['significant']:
                from PyQt6.QtGui import QColor
                stars_item.setForeground(QColor('#006400'))
            self._sig_table.setItem(row, 4, stars_item)

        sig_v.addWidget(self._sig_table)
        main_layout.addWidget(grp_sig, 1)

        # ── OK / Cancel ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("Generate Plot")
        btn_ok.setFixedHeight(32)
        btn_ok.setFixedWidth(130)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setFixedWidth(90)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        main_layout.addLayout(btn_row)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _move_up(self):
        row = self._list.currentRow()
        if row > 0:
            item = self._list.takeItem(row)
            self._list.insertItem(row - 1, item)
            self._list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._list.currentRow()
        if row < self._list.count() - 1:
            item = self._list.takeItem(row)
            self._list.insertItem(row + 1, item)
            self._list.setCurrentRow(row + 1)

    def _check_by(self, predicate):
        for pair_key, chk in self._chk_map.items():
            p = next((x for x in self._all_pairs
                      if (x['group_a'], x['group_b']) == pair_key), None)
            if p is not None:
                chk.setChecked(predicate(p))

    # ── results ─────────────────────────────────────────────────────────────
    def get_condition_order(self):
        return [self._list.item(i).text() for i in range(self._list.count())]

    def get_selected_pairs(self):
        """Return set of (group_a, group_b) tuples whose checkbox is checked."""
        return {k for k, chk in self._chk_map.items() if chk.isChecked()}


# ==========================================
# 6. CONDITION COLOUR EDITOR DIALOG
# ==========================================
class _CondColorEditorDialog(QDialog):
    """Interactive colour editor for condition groups.

    Displays each condition with a coloured swatch button.
    Clicking a swatch opens QColorDialog so the user can pick any colour.
    Group membership is labelled so users know which conditions are related.
    """

    # Which display group each condition belongs to (for labelling)
    _GROUP_LABELS = {
        "5s":               "Duration",
        "10s":              "Duration",
        "20s":              "Duration",
        "1mW":              "Power",
        "2mW":              "Power",
        "2Hz":              "Frequency",
        "5Hz":              "Frequency",
        "Ctrl":             "Control",
        "Far Light Control":"Control",
    }

    def __init__(self, cond_list, current_colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Condition Colours")
        self.resize(480, min(80 + len(cond_list) * 46, 640))

        self._colors = dict(current_colors)   # working copy

        main = QVBoxLayout(self)
        main.setSpacing(6)

        info = QLabel("Click a colour swatch to change it.  "
                      "Changes apply to all publication plots.")
        info.setStyleSheet("color:#aaa; font-size:10px;")
        main.addWidget(info)

        # Scroll area for condition rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        headers = ["Condition", "Group", "Colour", "Hex code"]
        for col, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            lbl.setStyleSheet("color:#ccc; font-size:10px;")
            grid.addWidget(lbl, 0, col)

        self._swatch_btns = {}   # cond → QPushButton
        self._hex_labels  = {}   # cond → QLabel

        for row_i, cond in enumerate(cond_list, start=1):
            hex_col = self._colors.get(cond, "#999999")
            group   = self._GROUP_LABELS.get(cond, "—")

            # condition name
            lbl_name = QLabel(cond)
            lbl_name.setStyleSheet("font-weight:bold;")
            grid.addWidget(lbl_name, row_i, 0)

            # group label with a subtle background tint
            group_tints = {
                "Duration":  "#1a2a3a",
                "Power":     "#2a1a0a",
                "Frequency": "#0a2a1a",
                "Control":   "#202020",
            }
            lbl_grp = QLabel(group)
            lbl_grp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_grp.setStyleSheet(
                f"background:{group_tints.get(group,'#1a1a1a')};"
                f"color:#ccc; border-radius:3px; padding:1px 6px; font-size:9px;")
            grid.addWidget(lbl_grp, row_i, 1)

            # colour swatch button
            btn = QPushButton()
            btn.setFixedSize(52, 26)
            self._apply_swatch_style(btn, hex_col)
            btn.clicked.connect(lambda _checked, c=cond: self._pick_color(c))
            self._swatch_btns[cond] = btn
            grid.addWidget(btn, row_i, 2)

            # hex label
            lbl_hex = QLabel(hex_col.upper())
            lbl_hex.setStyleSheet("font-family:monospace; font-size:9px; color:#aaa;")
            self._hex_labels[cond] = lbl_hex
            grid.addWidget(lbl_hex, row_i, 3)

        scroll.setWidget(inner)
        main.addWidget(scroll, 1)

        # Reset + OK/Cancel row
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.setFixedHeight(28)
        btn_reset.clicked.connect(lambda: self._reset(cond_list, parent))
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_ok = QPushButton("Apply")
        btn_ok.setFixedHeight(32)
        btn_ok.setFixedWidth(90)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        main.addLayout(btn_row)

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_swatch_style(btn, hex_col):
        """Paint the button with a solid colour fill and a darker border."""
        try:
            from PyQt6.QtGui import QColor
            qc  = QColor(hex_col)
            r, g, b = qc.red(), qc.green(), qc.blue()
            dark = f"#{int(r*0.55):02x}{int(g*0.55):02x}{int(b*0.55):02x}"
            lum  = 0.299*r + 0.587*g + 0.114*b
            fg   = "#000000" if lum > 140 else "#ffffff"
            btn.setStyleSheet(
                f"QPushButton{{background:{hex_col}; color:{fg};"
                f"border:1.5px solid {dark}; border-radius:4px;}}"
                f"QPushButton:hover{{border:2px solid white;}}")
        except Exception:
            pass

    def _pick_color(self, cond):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        current = QColor(self._colors.get(cond, "#999999"))
        picked  = QColorDialog.getColor(current, self, f"Choose colour — {cond}",
                                        QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if picked.isValid():
            hex_col = picked.name()          # always returns #rrggbb
            self._colors[cond] = hex_col
            self._apply_swatch_style(self._swatch_btns[cond], hex_col)
            self._hex_labels[cond].setText(hex_col.upper())

    def _reset(self, cond_list, parent_page):
        """Restore all colours to the class-level grouped defaults."""
        defaults = getattr(parent_page, '_COND_GROUP_COLORS', {})
        fb = getattr(parent_page, '_FALLBACK_COLORS', [])
        fb_i = 0
        for cond in cond_list:
            if cond in defaults:
                hex_col = defaults[cond]
            else:
                hex_col = fb[fb_i % len(fb)] if fb else "#999999"
                fb_i += 1
            self._colors[cond] = hex_col
            self._apply_swatch_style(self._swatch_btns[cond], hex_col)
            self._hex_labels[cond].setText(hex_col.upper())

    def get_colors(self):
        return dict(self._colors)


# ==========================================
# 7. ZOOMABLE PREVIEW WIDGET
# ==========================================
class ZoomableImageWidget(QWidget):
    """
    A widget that displays an image (from a file path) inside a QScrollArea.
    Supports:
      - Fit-to-window on load
      - Ctrl+Wheel zoom
      - Toolbar buttons for Zoom In / Out / Fit
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None          # full-resolution source
        self._zoom_factor = 1.0
        self._min_zoom = 0.05
        self._max_zoom = 10.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Zoom toolbar
        tb = QHBoxLayout()
        tb.setSpacing(6)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(32, 28)
        self.btn_zoom_in.clicked.connect(lambda: self._zoom_relative(1.25))

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedSize(32, 28)
        self.btn_zoom_out.clicked.connect(lambda: self._zoom_relative(0.8))

        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.setFixedSize(48, 28)
        self.btn_zoom_fit.clicked.connect(self.fit_to_window)

        self.btn_zoom_100 = QPushButton("1:1")
        self.btn_zoom_100.setFixedSize(40, 28)
        self.btn_zoom_100.clicked.connect(self._zoom_to_100)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(55)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setStyleSheet("color: #aaa; font-size: 11px;")

        tb.addWidget(self.btn_zoom_out)
        tb.addWidget(self.lbl_zoom)
        tb.addWidget(self.btn_zoom_in)
        tb.addWidget(self.btn_zoom_fit)
        tb.addWidget(self.btn_zoom_100)
        tb.addStretch()
        layout.addLayout(tb)

        # Scroll area with image label
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: #ffffff;")

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background-color: #ffffff;")
        self.scroll.setWidget(self.img_label)

        layout.addWidget(self.scroll, stretch=1)

        # Install event filter for wheel-zoom
        self.scroll.viewport().installEventFilter(self)

    # ---- public API ----
    def load_image(self, path: str):
        """Load an image file and fit it to the viewport."""
        self._pixmap = QPixmap(path)
        if self._pixmap.isNull():
            self.img_label.setText("Failed to load image")
            return
        self.fit_to_window()

    def fit_to_window(self):
        """Scale image so it fits entirely inside the visible viewport."""
        if self._pixmap is None or self._pixmap.isNull():
            return
        vp = self.scroll.viewport().size()
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        if pw == 0 or ph == 0:
            return
        sx = (vp.width() - 4) / pw
        sy = (vp.height() - 4) / ph
        self._zoom_factor = min(sx, sy)
        self._apply_zoom()

    # ---- internals ----
    def _zoom_to_100(self):
        self._zoom_factor = 1.0
        self._apply_zoom()

    def _zoom_relative(self, factor: float):
        self._zoom_factor = max(self._min_zoom,
                                min(self._max_zoom,
                                    self._zoom_factor * factor))
        self._apply_zoom()

    def _apply_zoom(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        new_w = int(self._pixmap.width() * self._zoom_factor)
        new_h = int(self._pixmap.height() * self._zoom_factor)
        scaled = self._pixmap.scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.img_label.setPixmap(scaled)
        self.img_label.resize(scaled.size())
        self.lbl_zoom.setText(f"{self._zoom_factor * 100:.0f}%")

    def eventFilter(self, obj, event):
        """Ctrl + Wheel  =>  zoom."""
        if obj is self.scroll.viewport():
            from PyQt6.QtCore import QEvent
            if event.type() == QEvent.Type.Wheel:
                mods = event.modifiers()
                if mods & Qt.KeyboardModifier.ControlModifier:
                    delta = event.angleDelta().y()
                    factor = 1.15 if delta > 0 else 1 / 1.15
                    self._zoom_relative(factor)
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """When the widget itself is resized, refit if currently fitted."""
        super().resizeEvent(event)
        # Only auto-refit when the zoom is already at "fit" level
        if self._pixmap and not self._pixmap.isNull():
            vp = self.scroll.viewport().size()
            pw = self._pixmap.width()
            ph = self._pixmap.height()
            if pw and ph:
                fit_zoom = min((vp.width() - 4) / pw, (vp.height() - 4) / ph)
                # If the user hasn't manually zoomed away from fit, keep fitting
                if abs(self._zoom_factor - fit_zoom) / max(fit_zoom, 0.01) < 0.15:
                    self.fit_to_window()


# ==========================================
# 5b. INTERACTIVE ROI SCENE (for ROI Map)
# ==========================================
class InteractiveROIScene(QGraphicsScene):
    """
    QGraphicsScene that displays a reference image and supports
    clickable/draggable ROI markers with labels.
    """
    marker_selected = pyqtSignal(int)   # index of selected marker
    marker_added = pyqtSignal(int)      # index of newly added marker
    markers_changed = pyqtSignal()      # any marker change (add/remove/move)

    MARKER_RADIUS = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_item = None          # QGraphicsPixmapItem
        self._markers = []               # list of dicts
        self._mode = "select"            # "select" or "add"
        self._dragging_idx = -1
        self._selected_idx = -1
        self._next_roi_number = 1
        self._label_format = "roi_count" # "roi_count", "count_only", "roi_only"
        self._drag_offset = QPointF(0, 0)

    # ---- image ----
    def load_image(self, path: str) -> bool:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            # Fallback: try loading via PIL for 16-bit TIFFs
            if HAS_OCR:
                try:
                    pil_img = PILImage.open(path).convert("RGBA")
                    from PyQt6.QtGui import QImage
                    data = pil_img.tobytes("raw", "RGBA")
                    qimg = QImage(data, pil_img.width, pil_img.height,
                                  QImage.Format.Format_RGBA8888)
                    pixmap = QPixmap.fromImage(qimg)
                except Exception:
                    pass
            if pixmap.isNull():
                return False

        if self._image_item:
            self.removeItem(self._image_item)
        self._image_item = QGraphicsPixmapItem(pixmap)
        self._image_item.setZValue(-10)
        self.addItem(self._image_item)
        self.setSceneRect(QRectF(pixmap.rect()))
        return True

    def image_loaded(self) -> bool:
        return self._image_item is not None

    # ---- markers ----
    def add_marker(self, x: float, y: float, roi_number: int,
                   spike_count: int = 0) -> int:
        r = self.MARKER_RADIUS
        pen = QPen(QColor(0, 0, 0), 2)
        brush = QBrush(QColor(174, 170, 191, 180))
        ellipse = QGraphicsEllipseItem(x - r, y - r, 2 * r, 2 * r)
        ellipse.setPen(pen)
        ellipse.setBrush(brush)
        ellipse.setZValue(5)
        self.addItem(ellipse)

        text = QGraphicsSimpleTextItem("")
        text.setZValue(6)
        font = QFont("Arial", 10, QFont.Weight.Bold)
        text.setFont(font)
        text.setBrush(QBrush(QColor(255, 255, 255)))
        self.addItem(text)

        marker = {
            "x": x, "y": y,
            "roi_number": roi_number,
            "spike_count": spike_count,
            "ellipse": ellipse,
            "text": text,
        }
        self._markers.append(marker)
        idx = len(self._markers) - 1
        self._update_single_label(idx)

        if roi_number >= self._next_roi_number:
            self._next_roi_number = roi_number + 1

        self.marker_added.emit(idx)
        self.markers_changed.emit()
        return idx

    def remove_marker(self, idx: int):
        if 0 <= idx < len(self._markers):
            m = self._markers.pop(idx)
            self.removeItem(m["ellipse"])
            self.removeItem(m["text"])
            if self._selected_idx == idx:
                self._selected_idx = -1
            elif self._selected_idx > idx:
                self._selected_idx -= 1
            self.markers_changed.emit()

    def clear_markers(self):
        for m in self._markers:
            self.removeItem(m["ellipse"])
            self.removeItem(m["text"])
        self._markers.clear()
        self._selected_idx = -1
        self._next_roi_number = 1
        self.markers_changed.emit()

    def marker_count(self) -> int:
        return len(self._markers)

    def get_marker(self, idx: int) -> dict:
        return self._markers[idx]

    def get_markers(self) -> list:
        return list(self._markers)

    def set_roi_number(self, idx: int, num: int):
        if 0 <= idx < len(self._markers):
            self._markers[idx]["roi_number"] = num
            self._update_single_label(idx)
            self.markers_changed.emit()

    def set_spike_count(self, idx: int, count: int):
        if 0 <= idx < len(self._markers):
            self._markers[idx]["spike_count"] = count
            self._update_single_label(idx)

    def set_label_format(self, fmt: str):
        self._label_format = fmt
        self.update_labels()

    def update_labels(self):
        for i in range(len(self._markers)):
            self._update_single_label(i)

    def _update_single_label(self, idx: int):
        m = self._markers[idx]
        fmt = self._label_format
        if fmt == "count_only":
            label = f"{m['spike_count']}"
        elif fmt == "roi_only":
            label = f"ROI {m['roi_number']}"
        else:
            label = f"ROI {m['roi_number']}\n{m['spike_count']} spk"
        m["text"].setText(label)
        # Position text above the marker
        br = m["text"].boundingRect()
        m["text"].setPos(m["x"] - br.width() / 2, m["y"] - self.MARKER_RADIUS - br.height() - 2)

    def _select_marker(self, idx: int):
        # Deselect previous
        if 0 <= self._selected_idx < len(self._markers):
            self._markers[self._selected_idx]["ellipse"].setPen(QPen(QColor(0, 0, 0), 2))
        self._selected_idx = idx
        if 0 <= idx < len(self._markers):
            self._markers[idx]["ellipse"].setPen(QPen(QColor(255, 215, 0), 3))
            self.marker_selected.emit(idx)

    def _find_marker_at(self, pos: QPointF) -> int:
        r = self.MARKER_RADIUS + 8  # generous hit area
        for i, m in enumerate(self._markers):
            dx = pos.x() - m["x"]
            dy = pos.y() - m["y"]
            if dx * dx + dy * dy <= r * r:
                return i
        return -1

    # ---- mode ----
    def set_mode(self, mode: str):
        self._mode = mode

    # ---- mouse events ----
    def mousePressEvent(self, event):
        pos = event.scenePos()
        if self._mode == "add" and event.button() == Qt.MouseButton.LeftButton:
            num = self._next_roi_number
            self.add_marker(pos.x(), pos.y(), num)
            return

        if self._mode == "select" and event.button() == Qt.MouseButton.LeftButton:
            hit = self._find_marker_at(pos)
            if hit >= 0:
                self._select_marker(hit)
                self._dragging_idx = hit
                m = self._markers[hit]
                self._drag_offset = QPointF(m["x"] - pos.x(), m["y"] - pos.y())
                return
            else:
                self._select_marker(-1)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_idx >= 0:
            pos = event.scenePos()
            nx = pos.x() + self._drag_offset.x()
            ny = pos.y() + self._drag_offset.y()
            m = self._markers[self._dragging_idx]
            m["x"] = nx
            m["y"] = ny
            r = self.MARKER_RADIUS
            m["ellipse"].setRect(nx - r, ny - r, 2 * r, 2 * r)
            self._update_single_label(self._dragging_idx)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_idx >= 0:
            self._dragging_idx = -1
            self.markers_changed.emit()
            return
        super().mouseReleaseEvent(event)


# ==========================================
# 5c. TRACE VISUALIZATION PAGE
# ==========================================
class TraceVisualizationPage(QWidget):
    """
    Page for visualizing and exporting ΔF/F traces to SVG with
    condition offsets, end-of-trace labels, and zoomable preview.
    """
    def __init__(self):
        super().__init__()
        self.analysis_folder = None
        self.available_conditions = []
        self.available_rois = []
        self.svg_path = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 20, 20)
        layout.setSpacing(10)

        # Header: title + quick generate action
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        lbl_title = QLabel("Trace Visualization & Export")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-bottom: 8px;")
        lbl_title.setWordWrap(True)
        lbl_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(lbl_title, 1)

        self.btn_generate = QPushButton("Generate SVG")
        self.btn_generate.setFixedHeight(36)
        self.btn_generate.setMinimumWidth(170)
        self.btn_generate.setObjectName("actionBtn")
        self.btn_generate.clicked.connect(self.generate_svg)
        self.btn_generate.setEnabled(False)

        self.btn_generate_html = QPushButton("Generate HTML")
        self.btn_generate_html.setFixedHeight(36)
        self.btn_generate_html.setMinimumWidth(170)
        self.btn_generate_html.setObjectName("actionBtn")
        self.btn_generate_html.clicked.connect(self.generate_html)
        self.btn_generate_html.setEnabled(False)

        header_layout.addWidget(self.btn_generate_html, 0, Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.btn_generate, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_layout)

        # Main horizontal split: left controls | right preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # ===================== LEFT PANEL (scrollable) =====================
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMaximumWidth(420)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        # --- 1. Load Data ---
        grp_load = QGroupBox("1. Load Analysis Data")
        load_layout = QVBoxLayout()
        self.btn_load_folder = QPushButton("Select Analysis Output Folder")
        self.btn_load_folder.setFixedHeight(36)
        self.btn_load_folder.clicked.connect(self.load_analysis_folder)
        self.lbl_folder_status = QLabel("No folder selected")
        self.lbl_folder_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_folder_status.setWordWrap(True)
        load_layout.addWidget(self.btn_load_folder)
        load_layout.addWidget(self.lbl_folder_status)
        grp_load.setLayout(load_layout)

        # --- 2. Select Conditions ---
        grp_conditions = QGroupBox("2. Select Conditions")
        cond_layout = QVBoxLayout()
        cond_btn_layout = QHBoxLayout()
        self.btn_select_all_cond = QPushButton("Select All")
        self.btn_select_all_cond.clicked.connect(lambda: self.list_conditions.selectAll())
        self.btn_deselect_all_cond = QPushButton("Deselect All")
        self.btn_deselect_all_cond.clicked.connect(lambda: self.list_conditions.clearSelection())
        cond_btn_layout.addWidget(self.btn_select_all_cond)
        cond_btn_layout.addWidget(self.btn_deselect_all_cond)

        # Quick-select buttons for common conditions
        quick_select_layout = QHBoxLayout()
        quick_select_layout.setSpacing(4)
        self._quick_select_patterns = ["10s", "20s", "5s", "2Hz", "5Hz", "1mW", "Ctrl"]
        for pat in self._quick_select_patterns:
            btn = QPushButton(pat)
            btn.setFixedHeight(26)
            btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
            btn.clicked.connect(lambda checked, p=pat: self._quick_select_conditions(p))
            quick_select_layout.addWidget(btn)

        self.list_conditions = QListWidget()
        self.list_conditions.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_conditions.setMinimumHeight(120)
        cond_layout.addLayout(cond_btn_layout)
        cond_layout.addLayout(quick_select_layout)
        cond_layout.addWidget(self.list_conditions)
        grp_conditions.setLayout(cond_layout)

        # --- 3. Select ROIs ---
        grp_rois = QGroupBox("3. Select ROIs")
        roi_layout = QVBoxLayout()
        roi_btn_layout = QHBoxLayout()
        self.btn_select_all_roi = QPushButton("Select All")
        self.btn_select_all_roi.clicked.connect(lambda: self.list_rois.selectAll())
        self.btn_deselect_all_roi = QPushButton("Deselect All")
        self.btn_deselect_all_roi.clicked.connect(lambda: self.list_rois.clearSelection())
        roi_btn_layout.addWidget(self.btn_select_all_roi)
        roi_btn_layout.addWidget(self.btn_deselect_all_roi)
        self.list_rois = QListWidget()
        self.list_rois.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_rois.setMinimumHeight(120)
        roi_layout.addLayout(roi_btn_layout)
        roi_layout.addWidget(self.list_rois)
        grp_rois.setLayout(roi_layout)

        # --- 4. Visualization Options ---
        grp_options = QGroupBox("4. Visualization Options")
        options_layout = QFormLayout()

        self.combo_layout = QComboBox()
        self.combo_layout.addItems([
            "Stacked (one subplot per ROI)",
            "Grid",
            "Overlay (all on same axes)",
        ])
        self.combo_layout.setCurrentIndex(0)

        self.check_show_stim = QCheckBox("Show stimulation windows")
        self.check_show_stim.setChecked(True)
        self.check_show_spikes = QCheckBox("Show spike markers")
        self.check_show_spikes.setChecked(True)

        self.combo_stim_mode = QComboBox()
        self.combo_stim_mode.addItem("Auto (from filename)", "auto")
        self.combo_stim_mode.addItem("20s", "20s")
        self.combo_stim_mode.addItem("10s", "10s")
        self.combo_stim_mode.addItem("5s", "5s")
        self.combo_stim_mode.addItem("None", "none")
        self.combo_stim_mode.setCurrentIndex(0)

        # -- Offset controls --
        self.combo_offset = QComboBox()
        self.combo_offset.addItems([
            "None (overlaid)",
            "Auto (separate traces)",
            "Manual offset",
        ])
        self.combo_offset.setCurrentIndex(1)  # default auto
        self.combo_offset.currentIndexChanged.connect(self._on_offset_mode_changed)

        self.spin_manual_offset = QDoubleSpinBox()
        self.spin_manual_offset.setRange(0.01, 50.0)
        self.spin_manual_offset.setValue(0.5)
        self.spin_manual_offset.setSingleStep(0.1)
        self.spin_manual_offset.setSuffix("  (ΔF/F)")
        self.spin_manual_offset.setEnabled(False)

        options_layout.addRow("Layout:", self.combo_layout)
        options_layout.addRow("Stim Window:", self.combo_stim_mode)
        options_layout.addRow("Condition Offset:", self.combo_offset)
        options_layout.addRow("Manual Offset:", self.spin_manual_offset)
        options_layout.addRow("", self.check_show_stim)
        options_layout.addRow("", self.check_show_spikes)
        grp_options.setLayout(options_layout)

        # --- 5. Save & Open ---
        grp_actions = QGroupBox("5. Save & Open")
        actions_layout = QVBoxLayout()

        self.btn_save = QPushButton("Save SVG As ...")
        self.btn_save.setFixedHeight(36)
        self.btn_save.clicked.connect(self.save_svg_as)
        self.btn_save.setEnabled(False)

        self.btn_open_external = QPushButton("Open in Browser")
        self.btn_open_external.setFixedHeight(32)
        self.btn_open_external.clicked.connect(self.open_svg_external)
        self.btn_open_external.setEnabled(False)

        self.lbl_svg_status = QLabel("")
        self.lbl_svg_status.setStyleSheet("color: #5fd75f; font-size: 11px;")
        self.lbl_svg_status.setWordWrap(True)

        actions_layout.addWidget(self.btn_save)
        actions_layout.addWidget(self.btn_open_external)
        actions_layout.addWidget(self.lbl_svg_status)
        grp_actions.setLayout(actions_layout)

        left_layout.addWidget(grp_load)
        left_layout.addWidget(grp_conditions)
        left_layout.addWidget(grp_rois)
        left_layout.addWidget(grp_options)
        left_layout.addWidget(grp_actions)
        left_layout.addStretch()

        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)

        # ===================== RIGHT PANEL (preview) =====================
        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)

        lbl_preview_title = QLabel("Preview  (Ctrl+Wheel to zoom)")
        lbl_preview_title.setObjectName("cardTitle")
        right_layout.addWidget(lbl_preview_title)

        self.preview_widget = ZoomableImageWidget()
        right_layout.addWidget(self.preview_widget, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([420, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

    # ---- slot helpers ----
    def _on_offset_mode_changed(self, idx):
        self.spin_manual_offset.setEnabled(idx == 2)

    def _quick_select_conditions(self, pattern: str):
        """Select conditions whose name contains *pattern* (case-insensitive)."""
        self.list_conditions.clearSelection()
        pat_lower = pattern.lower()
        for i in range(self.list_conditions.count()):
            item = self.list_conditions.item(i)
            if pat_lower in item.text().lower():
                item.setSelected(True)

    # ---- data loading ----
    def load_analysis_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Analysis Output Folder", "")
        if not folder_path:
            return
        try:
            import pandas as pd
            parent_folder = Path(folder_path)
            subfolders = [f for f in parent_folder.iterdir() if f.is_dir()]
            if not subfolders:
                QMessageBox.warning(self, "No Conditions",
                                    f"No subfolders in:\n{parent_folder}")
                return

            conditions = []
            all_rois = set()
            for sf in subfolders:
                dff_file = sf / "dff_table.csv"
                if dff_file.exists():
                    conditions.append(sf.name)
                    try:
                        dff_df = pd.read_csv(dff_file)
                        roi_cols = [c for c in dff_df.columns if c != "Time (s)"]
                        all_rois.update(roi_cols)
                    except Exception:
                        continue

            if not conditions:
                QMessageBox.warning(self, "No Data",
                                    "No valid dff_table.csv found in subfolders.")
                return

            self.analysis_folder = str(parent_folder)
            self.available_conditions = sorted(conditions)
            self.available_rois = sorted(all_rois)

            self.list_conditions.clear()
            for c in self.available_conditions:
                self.list_conditions.addItem(c)

            self.list_rois.clear()
            for r in self.available_rois:
                self.list_rois.addItem(r)

            self.list_conditions.selectAll()
            self.list_rois.selectAll()

            self.lbl_folder_status.setText(
                f"Loaded: {len(conditions)} conditions, {len(all_rois)} ROIs\n"
                f"From: {parent_folder.name}")
            self.lbl_folder_status.setStyleSheet("color: #5fd75f; font-size: 11px;")
            self.btn_generate.setEnabled(True)
            self.btn_generate_html.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load folder:\n{e}")
            traceback.print_exc()

    # ---- generation ----
    def generate_svg(self):
        if not self.analysis_folder:
            QMessageBox.warning(self, "Warning", "Load a folder first")
            return

        selected_conditions = [it.text() for it in self.list_conditions.selectedItems()]
        if not selected_conditions:
            QMessageBox.warning(self, "Warning", "Select at least one condition")
            return

        selected_rois = [it.text() for it in self.list_rois.selectedItems()]
        if not selected_rois:
            QMessageBox.warning(self, "Warning", "Select at least one ROI")
            return

        layout_modes = ["stacked", "grid", "overlay"]
        layout_mode = layout_modes[self.combo_layout.currentIndex()]

        offset_modes = ["none", "auto", "manual"]
        offset_mode = offset_modes[self.combo_offset.currentIndex()]
        manual_val = self.spin_manual_offset.value()

        show_stim = self.check_show_stim.isChecked()
        show_spikes = self.check_show_spikes.isChecked()
        stim_preset_mode = self.combo_stim_mode.currentData()

        try:
            svg_path = bp.plot_multi_roi_traces_svg(
                analysis_output_folder=self.analysis_folder,
                selected_conditions=selected_conditions,
                selected_rois=selected_rois,
                output_path=None,
                layout_mode=layout_mode,
                figsize=(16, max(3 * len(selected_rois), 6)),
                show_stim_windows=show_stim,
                show_spike_markers=show_spikes,
                condition_offset=offset_mode,
                manual_offset_value=manual_val,
                stim_preset_mode=stim_preset_mode,
            )

            self.svg_path = svg_path

            # Load the companion PNG for fast preview
            png_path = svg_path.replace(".svg", "_preview.png")
            if os.path.isfile(png_path):
                self.preview_widget.load_image(png_path)
            else:
                self.preview_widget.load_image(svg_path)

            self.btn_save.setEnabled(True)
            self.btn_open_external.setEnabled(True)
            self.lbl_svg_status.setText(f"Generated: {Path(svg_path).name}")
            self.lbl_svg_status.setStyleSheet("color: #5fd75f; font-size: 11px;")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate SVG:\n{e}")
            traceback.print_exc()

    def generate_html(self):
        """Generate an interactive HTML report using Plotly."""
        if not self.analysis_folder:
            QMessageBox.warning(self, "Warning", "Load a folder first")
            return

        selected_conditions = [it.text() for it in self.list_conditions.selectedItems()]
        if not selected_conditions:
            QMessageBox.warning(self, "Warning", "Select at least one condition")
            return

        selected_rois = [it.text() for it in self.list_rois.selectedItems()]
        if not selected_rois:
            QMessageBox.warning(self, "Warning", "Select at least one ROI")
            return

        show_stim = self.check_show_stim.isChecked()
        show_spikes = self.check_show_spikes.isChecked()
        stim_preset_mode = self.combo_stim_mode.currentData()

        offset_modes = ["none", "auto", "manual"]
        offset_mode = offset_modes[self.combo_offset.currentIndex()]
        manual_val = self.spin_manual_offset.value()

        # Ask where to save
        default_path = str(Path(self.analysis_folder) / "trace_report.html")
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save HTML Report", default_path,
            "HTML Files (*.html);;All Files (*)")
        if not save_path:
            return

        try:
            html_path = bp.generate_interactive_html(
                analysis_output_folder=self.analysis_folder,
                selected_conditions=selected_conditions,
                selected_rois=selected_rois,
                output_path=save_path,
                show_stim_windows=show_stim,
                show_spike_markers=show_spikes,
                stim_preset_mode=stim_preset_mode,
                condition_offset=offset_mode,
                manual_offset_value=manual_val,
            )

            reply = QMessageBox.question(
                self, "HTML Report Saved",
                f"Report saved to:\n{html_path}\n\nOpen in browser?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(html_path)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate HTML:\n{e}")
            traceback.print_exc()

    # ---- save / open ----
    def save_svg_as(self):
        if not self.svg_path:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG", str(Path(self.svg_path).name),
            "SVG Files (*.svg);;All Files (*)")
        if not save_path:
            return
        try:
            import shutil
            shutil.copy(self.svg_path, save_path)
            QMessageBox.information(self, "Saved", f"SVG saved to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def open_svg_external(self):
        if not self.svg_path:
            return
        try:
            import webbrowser
            webbrowser.open(f"file://{Path(self.svg_path).absolute()}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open:\n{e}")


# ==========================================
# 5d. ROI MAP PAGE
# ==========================================
class ROIMapPage(QWidget):
    """
    Page for overlaying spike counts on a reference microscopy image.
    Supports OCR auto-detection of ROI labels and manual marker placement.
    """
    def __init__(self):
        super().__init__()
        self.analysis_folder = None
        self.spike_data = {}        # roi_number -> {condition -> n_spikes}
        self.all_conditions = []
        self._selected_idx = -1
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)

        # Title
        lbl_title = QLabel("ROI Map")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; margin-bottom: 2px;")
        lbl_title.setFixedHeight(28)
        layout.addWidget(lbl_title)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- LEFT PANEL (controls in scroll area) ----
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMaximumWidth(420)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)

        # Group 1: Reference Image
        grp_image = QGroupBox("1. Reference Image")
        grp_image_l = QVBoxLayout(grp_image)
        self.btn_load_image = QPushButton("Select Image...")
        self.btn_load_image.setFixedHeight(35)
        self.btn_load_image.clicked.connect(self.load_image)
        grp_image_l.addWidget(self.btn_load_image)
        self.lbl_image_info = QLabel("No image loaded")
        self.lbl_image_info.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_image_info.setWordWrap(True)
        grp_image_l.addWidget(self.lbl_image_info)
        left_layout.addWidget(grp_image)

        # Group 2: ROI Detection
        grp_ocr = QGroupBox("2. Detect ROI Labels")
        grp_ocr_l = QVBoxLayout(grp_ocr)
        self.btn_run_ocr = QPushButton("Run OCR Detection")
        self.btn_run_ocr.setFixedHeight(35)
        self.btn_run_ocr.setEnabled(False)
        self.btn_run_ocr.clicked.connect(self.run_ocr)
        grp_ocr_l.addWidget(self.btn_run_ocr)
        self.lbl_ocr_status = QLabel("Requires pytesseract + Tesseract OCR" if not HAS_OCR else "Ready")
        self.lbl_ocr_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_ocr_status.setWordWrap(True)
        grp_ocr_l.addWidget(self.lbl_ocr_status)
        left_layout.addWidget(grp_ocr)

        # Group 3: Spike Data
        grp_spike = QGroupBox("3. Spike Data")
        grp_spike_l = QVBoxLayout(grp_spike)
        self.btn_load_data = QPushButton("Load Analysis Folder")
        self.btn_load_data.setFixedHeight(35)
        self.btn_load_data.clicked.connect(self.load_analysis_folder)
        grp_spike_l.addWidget(self.btn_load_data)

        self.list_conditions = QListWidget()
        self.list_conditions.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_conditions.setMaximumHeight(150)
        grp_spike_l.addWidget(QLabel("Conditions:"))
        grp_spike_l.addWidget(self.list_conditions)

        cond_btn_row = QHBoxLayout()
        btn_sel_all = QPushButton("Select All")
        btn_sel_all.clicked.connect(self.list_conditions.selectAll)
        btn_desel = QPushButton("Deselect All")
        btn_desel.clicked.connect(self.list_conditions.clearSelection)
        cond_btn_row.addWidget(btn_sel_all)
        cond_btn_row.addWidget(btn_desel)
        grp_spike_l.addLayout(cond_btn_row)

        self.btn_match = QPushButton("Match Spike Counts to Markers")
        self.btn_match.setFixedHeight(35)
        self.btn_match.setEnabled(False)
        self.btn_match.clicked.connect(self.match_spike_data)
        grp_spike_l.addWidget(self.btn_match)

        self.lbl_spike_status = QLabel("No data loaded")
        self.lbl_spike_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self.lbl_spike_status.setWordWrap(True)
        grp_spike_l.addWidget(self.lbl_spike_status)
        left_layout.addWidget(grp_spike)

        # Group 4: Marker Tools
        grp_marker = QGroupBox("4. Marker Tools")
        grp_marker_l = QVBoxLayout(grp_marker)

        self.btn_add_mode = QPushButton("Add Marker (click image)")
        self.btn_add_mode.setFixedHeight(35)
        self.btn_add_mode.setCheckable(True)
        self.btn_add_mode.setEnabled(False)
        self.btn_add_mode.clicked.connect(self.toggle_add_mode)
        grp_marker_l.addWidget(self.btn_add_mode)

        marker_btn_row = QHBoxLayout()
        self.btn_delete_sel = QPushButton("Delete Selected")
        self.btn_delete_sel.setEnabled(False)
        self.btn_delete_sel.clicked.connect(self.delete_selected_marker)
        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.clicked.connect(self.clear_all_markers)
        marker_btn_row.addWidget(self.btn_delete_sel)
        marker_btn_row.addWidget(self.btn_clear_all)
        grp_marker_l.addLayout(marker_btn_row)

        roi_num_row = QHBoxLayout()
        roi_num_row.addWidget(QLabel("Selected ROI #:"))
        self.spin_roi_num = QSpinBox()
        self.spin_roi_num.setRange(1, 999)
        self.spin_roi_num.setEnabled(False)
        self.spin_roi_num.valueChanged.connect(self.on_roi_number_changed)
        roi_num_row.addWidget(self.spin_roi_num)
        grp_marker_l.addLayout(roi_num_row)

        self.lbl_marker_count = QLabel("Markers: 0")
        self.lbl_marker_count.setStyleSheet("color: #aaa; font-size: 11px;")
        grp_marker_l.addWidget(self.lbl_marker_count)
        left_layout.addWidget(grp_marker)

        # Group 5: Display Options
        grp_display = QGroupBox("5. Display Options")
        grp_display_l = QFormLayout(grp_display)

        self.combo_label_fmt = QComboBox()
        self.combo_label_fmt.addItem("ROI + Count", "roi_count")
        self.combo_label_fmt.addItem("Count Only", "count_only")
        self.combo_label_fmt.addItem("ROI Only", "roi_only")
        self.combo_label_fmt.currentIndexChanged.connect(self.on_label_format_changed)
        grp_display_l.addRow("Label format:", self.combo_label_fmt)

        self.spin_marker_size = QSpinBox()
        self.spin_marker_size.setRange(6, 50)
        self.spin_marker_size.setValue(12)
        self.spin_marker_size.valueChanged.connect(self.on_marker_size_changed)
        grp_display_l.addRow("Marker radius:", self.spin_marker_size)

        left_layout.addWidget(grp_display)

        # Save button
        self.btn_save = QPushButton("Save Annotated Image")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_annotated_image)
        left_layout.addWidget(self.btn_save)

        left_layout.addStretch()
        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)

        # ---- RIGHT PANEL (interactive canvas) ----
        right_frame = QFrame()
        right_frame.setObjectName("card")
        right_layout = QVBoxLayout(right_frame)

        # Zoom toolbar
        zoom_bar = QHBoxLayout()
        btn_fit = QPushButton("Fit")
        btn_fit.setFixedWidth(50)
        btn_fit.clicked.connect(self.zoom_fit)
        btn_100 = QPushButton("1:1")
        btn_100.setFixedWidth(50)
        btn_100.clicked.connect(self.zoom_100)
        btn_zin = QPushButton("+")
        btn_zin.setFixedWidth(35)
        btn_zin.clicked.connect(lambda: self.zoom_relative(1.25))
        btn_zout = QPushButton("-")
        btn_zout.setFixedWidth(35)
        btn_zout.clicked.connect(lambda: self.zoom_relative(0.8))
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setStyleSheet("color: #aaa; font-size: 11px;")
        zoom_bar.addWidget(btn_fit)
        zoom_bar.addWidget(btn_100)
        zoom_bar.addWidget(btn_zin)
        zoom_bar.addWidget(btn_zout)
        zoom_bar.addWidget(self.lbl_zoom)
        zoom_bar.addStretch()
        right_layout.addLayout(zoom_bar)

        # Graphics view
        self.scene = InteractiveROIScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.view.viewport().installEventFilter(self)
        right_layout.addWidget(self.view)

        splitter.addWidget(right_frame)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Connect scene signals
        self.scene.marker_selected.connect(self.on_marker_selected)
        self.scene.markers_changed.connect(self.on_markers_changed)

    # ---- event filter for Ctrl+Wheel zoom + marker interaction ----
    def eventFilter(self, obj, event):
        if obj is not self.view.viewport():
            return super().eventFilter(obj, event)

        # Ctrl+Wheel zoom
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                factor = 1.15 if delta > 0 else 1 / 1.15
                self.zoom_relative(factor)
                return True

        from PyQt6.QtCore import QEvent as _QE

        # Mouse press: check for marker hit before ScrollHandDrag takes over
        if event.type() == _QE.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            if self.scene._mode == "add":
                self.scene.add_marker(scene_pos.x(), scene_pos.y(),
                                      self.scene._next_roi_number)
                return True
            # select mode: check marker hit
            hit = self.scene._find_marker_at(scene_pos)
            if hit >= 0:
                self.scene._select_marker(hit)
                self.on_marker_selected(hit)  # directly update UI controls
                self.scene._dragging_idx = hit
                m = self.scene._markers[hit]
                self.scene._drag_offset = QPointF(
                    m["x"] - scene_pos.x(), m["y"] - scene_pos.y())
                return True  # consume event so ScrollHandDrag doesn't pan

        # Mouse move: drag selected marker
        if event.type() == _QE.Type.MouseMove and self.scene._dragging_idx >= 0:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            nx = scene_pos.x() + self.scene._drag_offset.x()
            ny = scene_pos.y() + self.scene._drag_offset.y()
            m = self.scene._markers[self.scene._dragging_idx]
            m["x"] = nx
            m["y"] = ny
            r = self.scene.MARKER_RADIUS
            m["ellipse"].setRect(nx - r, ny - r, 2 * r, 2 * r)
            self.scene._update_single_label(self.scene._dragging_idx)
            return True

        # Mouse release: stop drag
        if event.type() == _QE.Type.MouseButtonRelease and self.scene._dragging_idx >= 0:
            self.scene._dragging_idx = -1
            self.scene.markers_changed.emit()
            return True

        return super().eventFilter(obj, event)

    # ---- zoom helpers ----
    def zoom_fit(self):
        if self.scene.image_loaded():
            self.view.fitInView(self.scene.sceneRect(),
                                Qt.AspectRatioMode.KeepAspectRatio)
            self._update_zoom_label()

    def zoom_100(self):
        self.view.resetTransform()
        self._update_zoom_label()

    def zoom_relative(self, factor: float):
        self.view.scale(factor, factor)
        self._update_zoom_label()

    def _update_zoom_label(self):
        t = self.view.transform()
        pct = int(t.m11() * 100)
        self.lbl_zoom.setText(f"{pct}%")

    # ---- image loading ----
    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Reference Image", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All Files (*)")
        if not path:
            return

        ok = self.scene.load_image(path)
        if not ok:
            QMessageBox.critical(self, "Error",
                                 f"Failed to load image:\n{path}")
            return

        self.zoom_fit()
        fname = Path(path).name
        rect = self.scene.sceneRect()
        self.lbl_image_info.setText(
            f"{fname}\n{int(rect.width())} x {int(rect.height())} px")
        self.lbl_image_info.setStyleSheet("color: #5fd75f; font-size: 11px;")
        self.btn_run_ocr.setEnabled(True)
        self.btn_add_mode.setEnabled(True)
        self.btn_save.setEnabled(True)

    # ---- OCR ----
    def run_ocr(self):
        if not HAS_OCR:
            QMessageBox.information(
                self, "OCR Not Available",
                "pytesseract and/or Pillow are not installed.\n\n"
                "To enable automatic ROI detection:\n"
                "  pip install pytesseract Pillow\n\n"
                "You also need Tesseract OCR installed:\n"
                "  https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "You can manually place markers using the\n"
                "'Add Marker' button instead.")
            return

        if not self.scene.image_loaded():
            return

        try:
            # Get image path from the pixmap item
            pixmap = self.scene._image_item.pixmap()
            # Convert QPixmap to PIL Image for pytesseract
            qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            width, height = qimg.width(), qimg.height()
            ptr = qimg.bits()
            ptr.setsize(width * height * 4)
            pil_img = PILImage.frombytes("RGBA", (width, height), bytes(ptr))

            # Run OCR with digit whitelist
            custom_config = r'--psm 6 -c tessedit_char_whitelist=0123456789'
            data = pytesseract.image_to_data(
                pil_img, config=custom_config,
                output_type=pytesseract.Output.DICT)

            found = 0
            seen_numbers = set()
            n_items = len(data['text'])
            for i in range(n_items):
                text = data['text'][i].strip()
                conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
                if not text or conf < 30:
                    continue
                try:
                    num = int(text)
                except ValueError:
                    continue
                if num < 1 or num > 99 or num in seen_numbers:
                    continue
                seen_numbers.add(num)

                # Center of bounding box
                cx = data['left'][i] + data['width'][i] / 2
                cy = data['top'][i] + data['height'][i] / 2
                self.scene.add_marker(cx, cy, num)
                found += 1

            if found == 0:
                self.lbl_ocr_status.setText(
                    "No numeric labels detected. Use manual placement.")
                self.lbl_ocr_status.setStyleSheet("color: #ff9955; font-size: 11px;")
            else:
                self.lbl_ocr_status.setText(f"Detected {found} ROI labels via OCR")
                self.lbl_ocr_status.setStyleSheet("color: #5fd75f; font-size: 11px;")

        except Exception as e:
            err = str(e)
            if "TesseractNotFoundError" in type(e).__name__ or "tesseract" in err.lower():
                self.lbl_ocr_status.setText(
                    "Tesseract binary not found. Install from:\n"
                    "https://github.com/UB-Mannheim/tesseract/wiki")
            else:
                self.lbl_ocr_status.setText(f"OCR error: {err}")
            self.lbl_ocr_status.setStyleSheet("color: #ff5555; font-size: 11px;")
            traceback.print_exc()

    # ---- analysis data loading ----
    def load_analysis_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Analysis Output Folder", "")
        if not folder:
            return

        import pandas as pd
        parent = Path(folder)
        subfolders = [f for f in parent.iterdir() if f.is_dir()]
        if not subfolders:
            QMessageBox.warning(self, "No Subfolders",
                                "No condition subfolders found.")
            return

        self.spike_data.clear()
        self.all_conditions.clear()
        loaded = 0

        for sf in subfolders:
            spike_file = sf / "spike_summary.csv"
            if not spike_file.exists():
                continue
            try:
                df = pd.read_csv(spike_file)
                if "ROI" not in df.columns or "n_spikes" not in df.columns:
                    continue
                cond = sf.name
                self.all_conditions.append(cond)
                for _, row in df.iterrows():
                    roi_num = bp.extract_roi_number(str(row["ROI"]))
                    if roi_num is None:
                        continue
                    if roi_num not in self.spike_data:
                        self.spike_data[roi_num] = {}
                    self.spike_data[roi_num][cond] = int(row["n_spikes"])
                loaded += 1
            except Exception:
                continue

        self.analysis_folder = str(parent)
        self.list_conditions.clear()
        for c in sorted(self.all_conditions):
            self.list_conditions.addItem(c)
        self.list_conditions.selectAll()

        if loaded > 0:
            self.btn_match.setEnabled(True)
            self.lbl_spike_status.setText(
                f"Loaded {loaded} conditions, {len(self.spike_data)} ROIs")
            self.lbl_spike_status.setStyleSheet("color: #5fd75f; font-size: 11px;")
        else:
            self.lbl_spike_status.setText("No spike_summary.csv found in subfolders")
            self.lbl_spike_status.setStyleSheet("color: #ff9955; font-size: 11px;")

    def match_spike_data(self):
        selected = [it.text() for it in self.list_conditions.selectedItems()]
        if not selected:
            QMessageBox.warning(self, "Warning", "No conditions selected")
            return

        matched = 0
        for i, m in enumerate(self.scene.get_markers()):
            rnum = m["roi_number"]
            if rnum in self.spike_data:
                total = sum(self.spike_data[rnum].get(c, 0) for c in selected)
                self.scene.set_spike_count(i, total)
                matched += 1
            else:
                self.scene.set_spike_count(i, 0)

        n_markers = self.scene.marker_count()
        self.lbl_spike_status.setText(
            f"Matched {matched}/{n_markers} markers "
            f"({len(selected)} conditions selected)")
        self.lbl_spike_status.setStyleSheet("color: #5fd75f; font-size: 11px;")

    # ---- marker tools ----
    def toggle_add_mode(self):
        if self.btn_add_mode.isChecked():
            self.scene.set_mode("add")
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.scene.set_mode("select")
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.view.unsetCursor()

    def on_marker_selected(self, idx: int):
        self._selected_idx = idx
        m = self.scene.get_marker(idx)
        self.spin_roi_num.blockSignals(True)
        self.spin_roi_num.setValue(m["roi_number"])
        self.spin_roi_num.blockSignals(False)
        self.spin_roi_num.setEnabled(True)
        self.btn_delete_sel.setEnabled(True)

    def on_markers_changed(self):
        n = self.scene.marker_count()
        self.lbl_marker_count.setText(f"Markers: {n}")

    def on_roi_number_changed(self, val: int):
        if self._selected_idx >= 0:
            self.scene.set_roi_number(self._selected_idx, val)

    def delete_selected_marker(self):
        if self._selected_idx >= 0:
            self.scene.remove_marker(self._selected_idx)
            self._selected_idx = -1
            self.spin_roi_num.setEnabled(False)
            self.btn_delete_sel.setEnabled(False)

    def clear_all_markers(self):
        if self.scene.marker_count() == 0:
            return
        reply = QMessageBox.question(
            self, "Confirm",
            f"Remove all {self.scene.marker_count()} markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.scene.clear_markers()
            self._selected_idx = -1
            self.spin_roi_num.setEnabled(False)
            self.btn_delete_sel.setEnabled(False)

    # ---- display options ----
    def on_label_format_changed(self):
        fmt = self.combo_label_fmt.currentData()
        self.scene.set_label_format(fmt)

    def on_marker_size_changed(self, val: int):
        self.scene.MARKER_RADIUS = val
        # Rebuild marker visuals
        for i, m in enumerate(self.scene.get_markers()):
            r = val
            m["ellipse"].setRect(m["x"] - r, m["y"] - r, 2 * r, 2 * r)
            self.scene._update_single_label(i)

    # ---- save annotated image ----
    def save_annotated_image(self):
        if not self.scene.image_loaded():
            QMessageBox.warning(self, "Warning", "Load an image first")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotated Image", "",
            "PNG Files (*.png);;JPEG Files (*.jpg);;TIFF Files (*.tif);;All Files (*)")
        if not save_path:
            return

        rect = self.scene.sceneRect()
        image = QImage(int(rect.width()), int(rect.height()),
                       QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()

        image.save(save_path)
        QMessageBox.information(
            self, "Saved",
            f"Annotated image saved to:\n{save_path}")


# ==========================================
# 6. MAIN WINDOW
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NMJ Analysis Pro")
        self.resize(1300, 950)

        container = QWidget()
        self.setCentralWidget(container)
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(15, 30, 15, 30)
        side_layout.setSpacing(10)

        lbl_app = QLabel("NMJ\nANALYTICS")
        lbl_app.setObjectName("sidebarTitle")
        lbl_app.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(lbl_app)
        side_layout.addSpacing(30)

        self.btn_page1 = self.create_nav_btn("Batch Process")
        self.btn_page2 = self.create_nav_btn("Settings")
        self.btn_page3 = self.create_nav_btn("Spike Review")
        self.btn_page4 = self.create_nav_btn("Trace Visualizer")
        self.btn_page5 = self.create_nav_btn("ROI Map")

        side_layout.addWidget(self.btn_page1)
        side_layout.addWidget(self.btn_page2)
        side_layout.addWidget(self.btn_page3)
        side_layout.addWidget(self.btn_page4)
        side_layout.addWidget(self.btn_page5)
        side_layout.addStretch()

        lbl_ver = QLabel("v2.9")
        lbl_ver.setStyleSheet("color: #4a506a; font-size: 10px; background-color: transparent;")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(lbl_ver)

        main_layout.addWidget(self.sidebar)

        # --- CONTENT STACK ---
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentArea")

        self.page_settings = SettingsPage()
        self.page_batch = BatchAnalysisPage(self.page_settings)
        self.page_settings.batch_ref = self.page_batch  # cross-reference for config save/load
        self.page_spike_review = SpikeLatencyReviewPage()
        self.page_trace_viz = TraceVisualizationPage()
        self.page_roi_map = ROIMapPage()

        self.stack.addWidget(self.page_batch)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_spike_review)
        self.stack.addWidget(self.page_trace_viz)
        self.stack.addWidget(self.page_roi_map)

        main_layout.addWidget(self.stack)

        self.btn_page1.clicked.connect(lambda: self.switch_page(0, self.btn_page1))
        self.btn_page2.clicked.connect(lambda: self.switch_page(1, self.btn_page2))
        self.btn_page3.clicked.connect(lambda: self.switch_page(2, self.btn_page3))
        self.btn_page4.clicked.connect(lambda: self.switch_page(3, self.btn_page4))
        self.btn_page5.clicked.connect(lambda: self.switch_page(4, self.btn_page5))

        self.btn_page1.click()
        self.apply_styles()

    def create_nav_btn(self, text):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setObjectName("navBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def switch_page(self, index, btn_sender):
        self.stack.setCurrentIndex(index)
        for btn in [self.btn_page1, self.btn_page2, self.btn_page3,
                     self.btn_page4, self.btn_page5]:
            btn.setChecked(False)
        btn_sender.setChecked(True)

    def apply_styles(self):
        self.setStyleSheet("""
            /* GLOBAL RESET */
            QWidget {
                background-color: #1b1e2b;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QLabel { background-color: transparent; }

            /* --- SIDEBAR --- */
            QFrame#sidebar { background-color: #151722; border-right: 1px solid #252836; }
            QLabel#sidebarTitle { font-size: 20px; font-weight: 900; color: #ffffff; letter-spacing: 2px; }
            QPushButton#navBtn {
                background-color: transparent;
                text-align: left; padding: 12px 15px; border-radius: 10px;
                color: #8b9bb4; font-weight: 600;
            }
            QPushButton#navBtn:hover { background-color: #252836; color: white; }
            QPushButton#navBtn:checked { background-color: #aeaabf; color: #1b1e2b; }

            /* --- CARDS & GROUPS --- */
            QFrame#card { background-color: #272a3f; border-radius: 15px; }
            QGroupBox {
                border: 1px solid #363b52;
                border-radius: 8px;
                margin-top: 20px;
                font-weight: bold;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #aeaabf;
            }
            QLabel#cardTitle { font-size: 16px; font-weight: bold; color: #ffffff; padding: 5px 0 10px 0; }

            /* --- INPUTS --- */
            QLineEdit, QDoubleSpinBox, QSpinBox {
                background-color: #1b1e2b;
                border: 1px solid #363b52;
                border-radius: 6px;
                padding: 5px;
                color: white;
            }
            QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #aeaabf; }

            /* --- SPINBOX UP/DOWN BUTTONS --- */
            QDoubleSpinBox::up-button, QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #363b52;
                border-bottom: 1px solid #363b52;
                border-top-right-radius: 5px;
                background-color: #2a2e3d;
            }
            QDoubleSpinBox::down-button, QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                border-left: 1px solid #363b52;
                border-top: 1px solid #363b52;
                border-bottom-right-radius: 5px;
                background-color: #2a2e3d;
            }
            QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
                background-color: #3a3f52;
            }
            QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed,
            QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed {
                background-color: #4a4f62;
            }
            QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 6px solid #aeaabf;
            }
            QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #aeaabf;
            }
            QDoubleSpinBox::up-arrow:hover, QSpinBox::up-arrow:hover {
                border-bottom-color: #ffffff;
            }
            QDoubleSpinBox::down-arrow:hover, QSpinBox::down-arrow:hover {
                border-top-color: #ffffff;
            }

            /* --- CHECKBOX STYLING (FIXED) --- */
            QCheckBox {
                spacing: 8px;
                background-color: transparent; /* Ensures no black block */
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #565f89;
                border-radius: 4px;
                background: #1b1e2b;
            }
            QCheckBox::indicator:checked {
                background: #aeaabf;
                border: 1px solid #aeaabf;
                /* Optional: You can add an image here for a checkmark, 
                   but solid color works well for this flat theme */
            }
            QCheckBox::indicator:hover {
                border: 1px solid #aeaabf;
            }

            QListWidget {
                background-color: #1b1e2b;
                border: 1px solid #363b52;
                border-radius: 8px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item:selected { background-color: #3e445e; color: white; border-radius: 4px; }
            QSplitter::handle { background-color: transparent; }

            /* --- BUTTONS --- */
            QPushButton {
                background-color: #363b52;
                border: none; padding: 8px; border-radius: 6px;
                color: white; font-weight: bold;
            }
            QPushButton:hover { background-color: #454b66; }
            QPushButton#actionBtn { background-color: #aeaabf; color: #1b1e2b; font-size: 15px; }
            QPushButton#actionBtn:hover { background-color: #c4c1d4; }
            QPushButton#actionBtn:disabled { background-color: #363555b52; color: #666; }
            QPushButton#dangerBtn { background-color: #363b52; color: #ff5555; }
            QPushButton#dangerBtn:hover { background-color: #ff5555; color: white; }

            /* --- SCROLLBAR --- */
            QScrollBar:vertical { border: none; background: #272a3f; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background: #363b52; min-height: 20px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # Set explicit application font to prevent QFont::setPointSize warnings
    app_font = QFont("Segoe UI", 10)
    app.setFont(app_font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
