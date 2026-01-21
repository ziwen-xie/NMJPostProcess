import sys
import os
from pathlib import Path
import traceback

# GUI Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QListWidget, QFileDialog,
    QGroupBox, QFormLayout, QLineEdit, QDoubleSpinBox, QCheckBox,
    QProgressBar, QScrollArea, QMessageBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool
from PyQt6.QtGui import QPixmap, QFont
import matplotlib.pyplot as plt

# --- IMPORT YOUR SOURCE FILE ---
try:
    import BatchProcess as bp
except ImportError:
    print("Error: Could not import 'BatchProcess.py'. Make sure it is in the same directory.")
    sys.exit(1)


# ==========================================
# 1. ANALYSIS WORKER (The "Glue" Logic)
# ==========================================
class WorkerSignals(QObject):
    finished = pyqtSignal(str, str)  # file_path, image_path
    error = pyqtSignal(str, str)  # file_path, error_message


class AnalysisWorker(QRunnable):
    def __init__(self, file_path, config):
        super().__init__()
        self.file_path = Path(file_path)
        self.config = config
        self.signals = WorkerSignals()

    def run(self):
        try:
            import copy
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
                exclude_spikes_in_windows=local_cfg.exclude_spikes_in_stim
            )

            bg_was_roi = (local_cfg.bg_source == "roi_column")

            plt.switch_backend('Agg')
            local_cfg.fig_size = (8, 5)
            fig = bp.plot_dff(dff_df, roi_cols, local_cfg, bg_was_roi, spike_times)

            output_filename = f"Delta_F_plot_all_{self.file_path.stem}.png"
            output_path = self.file_path.parent / output_filename

            fig.savefig(output_path, dpi=90, bbox_inches='tight')
            plt.close(fig)

            self.signals.finished.emit(str(self.file_path), str(output_path))

        except Exception as e:
            err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
            self.signals.error.emit(str(self.file_path), err_msg)


# ==========================================
# 2. MAIN GUI WINDOW
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Calcium Imaging Analysis Tool")
        self.resize(1250, 950)

        self.threadpool = QThreadPool()
        font = QFont()
        font.setPointSize(11)
        QApplication.setFont(font)

        self.file_paths = []
        self.processed_count = 0

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- TOP SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)
        main_layout.addWidget(splitter, stretch=2)

        # 1. LEFT PANEL
        left_panel = QGroupBox("1. Data Selection")
        left_layout = QVBoxLayout(left_panel)

        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add CSV Files")
        self.btn_add.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogStart))
        self.btn_add.clicked.connect(self.add_files)

        self.btn_clear = QPushButton("Clear List")
        self.btn_clear.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogDiscardButton))
        self.btn_clear.clicked.connect(self.clear_files)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_clear)

        left_layout.addLayout(btn_layout)
        left_layout.addWidget(self.file_list)
        splitter.addWidget(left_panel)

        # 2. RIGHT PANEL
        right_panel = QGroupBox("2. Analysis Configuration")
        right_layout = QVBoxLayout(right_panel)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setVerticalSpacing(15)

        self.inputs = {}
        self.inputs['preset'] = QLineEdit("20s")
        self.inputs['preset'].setPlaceholderText("e.g., 20s, 10s")
        self.inputs['infer_name'] = QCheckBox("Infer Preset from Filename")
        self.inputs['infer_name'].setChecked(True)
        self.inputs['sigma'] = QDoubleSpinBox()
        self.inputs['sigma'].setValue(5.0)
        self.inputs['sigma'].setRange(1.0, 50.0)
        self.inputs['baseline_win'] = QDoubleSpinBox()
        self.inputs['baseline_win'].setValue(15.0)
        self.inputs['roi_key'] = QLineEdit("ROI")
        self.inputs['bg_col'] = QLineEdit("ROI.01 []")

        lbl_preset = QLabel("Stim Preset:")
        lbl_preset.setToolTip("Enter '20s', '10s', '5s' or 'none'.")
        form_layout.addRow(lbl_preset, self.inputs['preset'])
        form_layout.addRow("", self.inputs['infer_name'])
        form_layout.addRow("Spike Sigma (z):", self.inputs['sigma'])
        form_layout.addRow("Baseline Window (s):", self.inputs['baseline_win'])
        form_layout.addRow("ROI Key Search:", self.inputs['roi_key'])
        form_layout.addRow("Exact BG Column:", self.inputs['bg_col'])

        right_layout.addLayout(form_layout)
        right_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Waiting to start (%p%)")

        self.btn_run = QPushButton("RUN ANALYSIS")
        self.btn_run.setMinimumHeight(60)
        self.btn_run.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaPlay))
        self.btn_run.clicked.connect(self.run_analysis)

        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(self.btn_run)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 550])

        # --- BOTTOM SECTION ---
        bottom_group = QGroupBox("3. Result Previews")
        bottom_layout = QVBoxLayout(bottom_group)
        main_layout.addWidget(bottom_group, stretch=3)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        bottom_layout.addWidget(scroll_area)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        scroll_area.setWidget(self.grid_container)

        self.image_labels = []
        for r in range(5):
            for c in range(5):
                lbl = QLabel()
                lbl.setFixedSize(220, 165)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setText(f"Slot {r * 5 + c + 1}")
                self.grid_layout.addWidget(lbl, r, c)
                self.image_labels.append(lbl)

        # Apply initial empty style
        self.reset_grid()

    def apply_styles(self):
        # THEME COLOR: #aeaabf
        # We will use this for accents, borders, and button backgrounds.
        # Text on top of #aeaabf should generally be black/dark grey for readability.

        self.setStyleSheet("""
            /* Main Window */
            QMainWindow { background-color: #fbfbfb; color: #333333; }
            QWidget { color: #333333; }

            /* Group Box */
            QGroupBox {
                background-color: #ffffff;
                border: 2px solid #aeaabf; /* Theme Border */
                border-radius: 8px;
                margin-top: 14px;
                font-weight: bold;
                font-size: 12pt;
                color: #555555;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #555555;
            }

            /* Splitter Handle */
            QSplitter::handle { background-color: #e0e0e0; }

            /* Input Fields */
            QLineEdit, QDoubleSpinBox {
                background-color: #ffffff;
                border: 2px solid #dadada;
                border-radius: 6px;
                padding: 6px;
                font-size: 11pt;
                color: #333333;
            }
            QLineEdit:focus, QDoubleSpinBox:focus {
                border: 2px solid #aeaabf; /* Theme Focus */
            }

            /* List Widget */
            QListWidget {
                background-color: #ffffff;
                border: 2px solid #dadada;
                border-radius: 6px;
                outline: none;
            }
            /* FIX FOR WHITE TEXT ON SELECTION */
            QListWidget::item:selected {
                background-color: #aeaabf; 
                color: #000000; /* Force Black Text */
                border: none;
            }
            QListWidget::item:hover {
                background-color: #f0f0f5;
            }
            QListWidget::item:alternate { background-color: #fafafa; }

            /* Standard Buttons */
            QPushButton {
                background-color: #aeaabf; /* Theme Color */
                color: #2b2b2b; /* Dark text for contrast */
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 11pt;
                border: none;
            }
            QPushButton:hover { 
                background-color: #bwb8cd; /* Slightly darker */
            }
            QPushButton:pressed { 
                background-color: #9c98ad; 
                padding-top: 10px; /* Pressed effect */
            }
            QPushButton:disabled { 
                background-color: #e0e0e0; 
                color: #a0a0a0; 
            }

            /* Progress Bar */
            QProgressBar {
                border: 2px solid #dadada;
                border-radius: 6px;
                text-align: center;
                background-color: #ffffff;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #aeaabf; /* Theme Color */
            }
        """)

        # Override Run Button for slightly more emphasis but same palette family
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #aeaabf;
                border: 2px solid #9c98ad;
                font-size: 12pt;
                color: #000000;
            }
            QPushButton:hover { background-color: #bab6ca; }
            QPushButton:pressed { background-color: #9c98ad; }
        """)

    # --- ACTIONS ---

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select CSV Files", "", "CSV Files (*.csv)")
        if files:
            for f in files:
                if f not in self.file_paths:
                    self.file_paths.append(f)
                    self.file_list.addItem(os.path.basename(f))

    def clear_files(self):
        self.file_paths = []
        self.file_list.clear()
        self.reset_grid()

    def reset_grid(self):
        for i, lbl in enumerate(self.image_labels):
            lbl.clear()
            lbl.setText(f"Slot {i + 1}")
            # Empty slot style: dashed border, light grey
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #f7f7f7;
                    border: 2px dashed #d0d0d0;
                    border-radius: 8px;
                    color: #a0a0a0;
                    font-weight: bold;
                }
            """)

    def get_config(self):
        try:
            cfg = bp.Config()
            cfg.stim_preset = self.inputs['preset'].text()
            cfg.stim_preset_infer_from_name = self.inputs['infer_name'].isChecked()
            cfg.spike_z_sigma = self.inputs['sigma'].value()
            cfg.baseline_window_half_s = self.inputs['baseline_win'].value()
            cfg.roi_key = self.inputs['roi_key'].text()
            cfg.bg_column_name = self.inputs['bg_col'].text()

            presets = {
                "20s": [(30, 50), (80, 100), (130, 150)],
                "10s": [(30, 40), (70, 80), (110, 120)],
                "5s": [(30, 35), (65, 70), (100, 105)],
                "none": [],
            }
            if cfg.stim_preset in presets:
                cfg.stim_windows = presets[cfg.stim_preset]

            return cfg
        except Exception as e:
            QMessageBox.critical(self, "Config Error", str(e))
            return None

    def run_analysis(self):
        if not self.file_paths:
            QMessageBox.warning(self, "No Files", "Please add CSV files first.")
            return

        cfg = self.get_config()
        if not cfg:
            return

        self.btn_run.setEnabled(False)
        self.btn_run.setText("Running Processing...")
        self.reset_grid()
        self.processed_count = 0
        self.progress_bar.setMaximum(len(self.file_paths))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Processing... (%v/%m)")

        for f_path in self.file_paths:
            worker = AnalysisWorker(f_path, cfg)
            worker.signals.finished.connect(self.on_worker_finished)
            worker.signals.error.connect(self.on_worker_error)
            self.threadpool.start(worker)

    def on_worker_finished(self, file_path, image_path):
        self.processed_count += 1
        self.progress_bar.setValue(self.processed_count)

        slot_index = (self.processed_count - 1)
        if slot_index < 25:
            lbl = self.image_labels[slot_index]
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pix = pixmap.scaled(
                    lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                lbl.setPixmap(scaled_pix)
                # Success Style: Solid theme border
                lbl.setStyleSheet("""
                    QLabel {
                        background-color: white;
                        border: 3px solid #aeaabf;
                        border-radius: 8px;
                    }
                """)
                lbl.setToolTip(f"{os.path.basename(file_path)}\n{image_path}")

        if self.processed_count == len(self.file_paths):
            self.on_all_finished()

    def on_worker_error(self, file_path, err_msg):
        self.processed_count += 1
        self.progress_bar.setValue(self.processed_count)
        print(f"Error in {file_path}:\n{err_msg}")

        slot_index = (self.processed_count - 1)
        if slot_index < 25:
            lbl = self.image_labels[slot_index]
            lbl.setText("ERROR\nSee Console")
            # Error Style: Keep red for errors as it's critical info
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #fff0f0;
                    border: 2px solid #e57373;
                    border-radius: 8px;
                    color: #d32f2f;
                    font-weight: bold;
                }
            """)
            lbl.setToolTip(f"Error processing {os.path.basename(file_path)}")

        if self.processed_count == len(self.file_paths):
            self.on_all_finished()

    def on_all_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("RUN ANALYSIS")
        self.progress_bar.setFormat("Finished (%m files)")
        QMessageBox.information(self, "Complete", f"Batch processing finished for {len(self.file_paths)} files.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())