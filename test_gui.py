"""
Simple test to launch the GUI and check for errors.
"""
import sys
from GUI_3 import QApplication, MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    print("GUI launched successfully!")
    print("Close the window to exit.")

    sys.exit(app.exec())
