import sys
import os
from pathlib import Path
import traceback
import copy

# GUI Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QListWidget, QFileDialog,
    QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox, QCheckBox,
    QProgressBar, QScrollArea, QMessageBox, QSplitter, QFrame,
    QStackedWidget, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool
from PyQt6.QtGui import QPixmap

# Scientific Imports
import matplotlib.pyplot as plt

# --- IMPORT YOUR SOURCE FILE ---
try:
    import BatchProcess as bp
except ImportError:
    print("Error: Could not import 'BatchProcess.py'. Make sure it is in the same directory.")
    sys.exit(1)


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
    """A separate window to view the full-size image."""

    def __init__(self, image_path):
        super().__init__()
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

        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.lbl_image.setPixmap(pixmap)

        scroll_area.setWidget(self.lbl_image)


# ==========================================
# 1. ANALYSIS WORKER
# ==========================================
class WorkerSignals(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str, str)


class AnalysisWorker(QRunnable):
    def __init__(self, file_path, config):
        super().__init__()
        self.file_path = Path(file_path)
        self.config = config
        self.signals = WorkerSignals()

    def run(self):
        try:
            local_cfg = copy.copy(self.config)
            local_cfg.csv_path = str(self.file_path)

            if local_cfg.stim_preset_infer_from_name:
                bp.apply_inferred_stim_preset(local_cfg, name_hint=self.file_path.name)

            df = bp.load_fluo_csv(local_cfg.csv_path, local_cfg.encoding, local_cfg.skip_first_row)

            roi_cols = bp.find_roi_columns(df, local_cfg.roi_key)
            if not roi_cols:
                raise ValueError(f"No ROI columns found with key '{local_cfg.roi_key}'")

            bg_vec = bp.select_background(df, local_cfg)
            t = df[local_cfg.time_col].to_numpy(dtype=float)
            dff_df = bp.compute_all_dff(df, roi_cols, bg_vec, t, local_cfg)

            _, _, spike_times = bp.detect_spikes_across_rois(
                dff_table=dff_df,
                roi_cols=roi_cols,
                time_col="Time (s)",
                spike_z_sigma=local_cfg.spike_z_sigma,
                width_mode=local_cfg.width_mode,
                width_threshold_s=local_cfg.width_threshold_s,
                stim_windows=local_cfg.stim_windows,
                exclude_spikes_in_windows=local_cfg.exclude_spikes_in_stim,
                baseline_range=(local_cfg.baseline_index_start, local_cfg.baseline_index_end)
            )

            bg_was_roi = (local_cfg.bg_source == "roi_column")

            plt.switch_backend('Agg')
            local_cfg.fig_size = (10, 6)

            fig = bp.plot_dff(dff_df, roi_cols, local_cfg, bg_was_roi, spike_times)

            output_filename = f"Delta_F_plot_all_{self.file_path.stem}.png"
            output_path = self.file_path.parent / output_filename
            fig.savefig(output_path, dpi=100, bbox_inches='tight')
            plt.close(fig)

            self.signals.finished.emit(str(self.file_path), str(output_path))

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
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        lbl_title = QLabel("Advanced Configuration")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; margin-bottom: 20px;")
        layout.addWidget(lbl_title)

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

        # --- Group 3: Advanced Spike Detection ---
        grp_spike = QGroupBox("Advanced Spike Detection")
        form_spike = QFormLayout()

        self.inputs['min_dist'] = QDoubleSpinBox()
        self.inputs['min_dist'].setValue(0.0)
        self.inputs['min_dist'].setSpecialValueText("None")

        self.inputs['width_thr'] = QDoubleSpinBox()
        self.inputs['width_thr'].setRange(0.01, 10.0)
        self.inputs['width_thr'].setValue(0.50)
        self.inputs['width_thr'].setSingleStep(0.1)

        self.inputs['exclude_stim'] = QCheckBox("Exclude spikes during stim")

        form_spike.addRow("Min Spike Distance (s):", self.inputs['min_dist'])
        form_spike.addRow("Min Width (s):", self.inputs['width_thr'])
        form_spike.addRow("", self.inputs['exclude_stim'])

        grp_spike.setLayout(form_spike)
        content_layout.addWidget(grp_spike)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)


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
        self.inputs['auto_ylim'].setChecked(False)
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
            cfg.exclude_spikes_in_stim = s_in['exclude_stim'].isChecked()

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

        self.btn_run.setEnabled(False)
        self.btn_run.setText("PROCESSING...")
        self.reset_grid()
        self.processed_count = 0
        self.progress.setMaximum(len(self.file_paths))
        self.progress.setValue(0)

        for f_path in self.file_paths:
            worker = AnalysisWorker(f_path, cfg)
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
# 4. MAIN WINDOW
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

        side_layout.addWidget(self.btn_page1)
        side_layout.addWidget(self.btn_page2)
        side_layout.addStretch()

        lbl_ver = QLabel("v2.6")
        lbl_ver.setStyleSheet("color: #4a506a; font-size: 10px; background-color: transparent;")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(lbl_ver)

        main_layout.addWidget(self.sidebar)

        # --- CONTENT STACK ---
        self.stack = QStackedWidget()
        self.stack.setObjectName("contentArea")

        self.page_settings = SettingsPage()
        self.page_batch = BatchAnalysisPage(self.page_settings)

        self.stack.addWidget(self.page_batch)
        self.stack.addWidget(self.page_settings)

        main_layout.addWidget(self.stack)

        self.btn_page1.clicked.connect(lambda: self.switch_page(0, self.btn_page1))
        self.btn_page2.clicked.connect(lambda: self.switch_page(1, self.btn_page2))

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
        self.btn_page1.setChecked(False)
        self.btn_page2.setChecked(False)
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

    window = MainWindow()
    window.show()
    sys.exit(app.exec())