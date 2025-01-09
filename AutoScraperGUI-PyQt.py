import sys
import os
import threading
import webbrowser
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,  # type: ignore
                             QLabel, QLineEdit, QPushButton, QComboBox, QTabWidget, 
                             QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,QStatusBar)
from PyQt5.QtGui import QPalette, QColor # type: ignore
from PyQt5.QtCore import Qt, QThread, pyqtSignal # type: ignore

from AutoScraper import fetch_autotrader_data, save_results_to_csv
from GetUserSelection import get_models_for_make
from AutoScraperUtil import get_all_makes, read_json_file, save_json_to_file, format_time_ymd_hms

class FetchDataThread(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            results = fetch_autotrader_data(self.payload)
            print(f"Type of results: {type(results)}")
            print(f"Content of results: {results[:500] if isinstance(results, str) else results}")
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class AutoScraperGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoScraper GUI")
        self.setGeometry(100, 100, 1200, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        self.basic_search_tab = QWidget()
        self.advanced_search_tab = QWidget()
        self.results_tab = QWidget()

        self.tab_widget.addTab(self.basic_search_tab, "Basic Search")
        self.tab_widget.addTab(self.advanced_search_tab, "Advanced Search")
        self.tab_widget.addTab(self.results_tab, "Results Viewer")

        self.setup_basic_search_tab()
        self.setup_advanced_search_tab()
        self.setup_results_tab()

        #self.set_dark_mode()
        self.statusBar().showMessage("Ready")

    def setup_basic_search_tab(self):
        layout = QVBoxLayout(self.basic_search_tab)

        self.make_combo = QComboBox()
        self.make_combo.addItems(get_all_makes())
        self.make_combo.currentTextChanged.connect(self.update_model_dropdown)

        self.model_combo = QComboBox()

        self.address_input = QLineEdit("Kanata, ON")
        self.proximity_input = QLineEdit("-1")
        self.year_min_combo = QComboBox()
        self.year_max_combo = QComboBox()
        self.year_min_combo.addItems([str(year) for year in range(2025, 1899, -1)])
        self.year_max_combo.addItems([str(year) for year in range(2025, 1899, -1)])
        #self.year_min_combo.setCurrentIndex()
        self.price_min_input = QLineEdit()
        self.price_max_input = QLineEdit()
        self.exclusions_input = QLineEdit()
        self.inclusion_input = QLineEdit()

        layout.addWidget(QLabel("Make:"))
        layout.addWidget(self.make_combo)
        layout.addWidget(QLabel("Model:"))
        layout.addWidget(self.model_combo)
        layout.addWidget(QLabel("Address:"))
        layout.addWidget(self.address_input)
        layout.addWidget(QLabel("Proximity (km):"))
        layout.addWidget(self.proximity_input)
        layout.addWidget(QLabel("Year Min:"))
        layout.addWidget(self.year_min_combo)
        layout.addWidget(QLabel("Year Max:"))
        layout.addWidget(self.year_max_combo)
        layout.addWidget(QLabel("Price Min:"))
        layout.addWidget(self.price_min_input)
        layout.addWidget(QLabel("Price Max:"))
        layout.addWidget(self.price_max_input)
        layout.addWidget(QLabel("Exclusions (comma-separated):"))
        layout.addWidget(self.exclusions_input)
        layout.addWidget(QLabel("Inclusion:"))
        layout.addWidget(self.inclusion_input)

        button_layout = QHBoxLayout()
        fetch_button = QPushButton("Fetch Data")
        fetch_button.clicked.connect(self.fetch_data)
        save_payload_button = QPushButton("Save Payload")
        save_payload_button.clicked.connect(self.save_payload)
        load_payload_button = QPushButton("Load Payload")
        load_payload_button.clicked.connect(self.load_payload)

        button_layout.addWidget(fetch_button)
        button_layout.addWidget(save_payload_button)
        button_layout.addWidget(load_payload_button)

        layout.addLayout(button_layout)

    def setup_advanced_search_tab(self):
        layout = QVBoxLayout(self.advanced_search_tab)

        self.adv_make_input = QLineEdit()
        self.adv_model_input = QLineEdit()
        self.adv_address_input = QLineEdit("Kanata, ON")
        self.adv_proximity_input = QLineEdit("-1")
        self.adv_year_min_input = QLineEdit()
        self.adv_year_max_input = QLineEdit()
        self.adv_price_min_input = QLineEdit()
        self.adv_price_max_input = QLineEdit()
        self.adv_exclusions_input = QLineEdit()
        self.adv_inclusion_input = QLineEdit()

        layout.addWidget(QLabel("Make:"))
        layout.addWidget(self.adv_make_input)
        layout.addWidget(QLabel("Model:"))
        layout.addWidget(self.adv_model_input)
        layout.addWidget(QLabel("Address:"))
        layout.addWidget(self.adv_address_input)
        layout.addWidget(QLabel("Proximity (km):"))
        layout.addWidget(self.adv_proximity_input)
        layout.addWidget(QLabel("Year Min:"))
        layout.addWidget(self.adv_year_min_input)
        layout.addWidget(QLabel("Year Max:"))
        layout.addWidget(self.adv_year_max_input)
        layout.addWidget(QLabel("Price Min:"))
        layout.addWidget(self.adv_price_min_input)
        layout.addWidget(QLabel("Price Max:"))
        layout.addWidget(self.adv_price_max_input)
        layout.addWidget(QLabel("Exclusions (comma-separated):"))
        layout.addWidget(self.adv_exclusions_input)
        layout.addWidget(QLabel("Inclusion:"))
        layout.addWidget(self.adv_inclusion_input)

        button_layout = QHBoxLayout()
        fetch_button = QPushButton("Fetch Data")
        fetch_button.clicked.connect(self.fetch_data_advanced)
        save_payload_button = QPushButton("Save Payload")
        save_payload_button.clicked.connect(self.save_payload_advanced)
        load_payload_button = QPushButton("Load Payload")
        load_payload_button.clicked.connect(self.load_payload)

        button_layout.addWidget(fetch_button)
        button_layout.addWidget(save_payload_button)
        button_layout.addWidget(load_payload_button)

        layout.addLayout(button_layout)

    def setup_results_tab(self):
        allColNames = [
            "Link",
            "Make",
            "Model",
            "Year",
            "Trim",
            "Price",
            "Drivetrain",
            "Kilometres",
            "Status",
            "Body Type",
            "Engine",
            "Cylinder",
            "Transmission",
            "Exterior Colour",
            "Doors",
            "Fuel Type",
            "City Fuel Economy",
            "Hwy Fuel Economy"
        ]
        layout = QVBoxLayout(self.results_tab)
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(allColNames)
        self.results_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.results_tree)

    def set_dark_mode(self):
        app = QApplication.instance()
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

    def update_model_dropdown(self):
        make = self.make_combo.currentText()
        self.model_combo.clear()
        if make:
            models = get_models_for_make(make)
            self.model_combo.addItems(list(models.keys()))

    def get_payload(self, advanced=False):
        if advanced:
            return {
                "Make": self.adv_make_input.text(),
                "Model": self.adv_model_input.text(),
                "Address": self.adv_address_input.text(),
                "Proximity": int(self.adv_proximity_input.text()),
                "YearMin": self.adv_year_min_input.text() or None,
                "YearMax": self.adv_year_max_input.text() or None,
                "PriceMin": int(self.adv_price_min_input.text()) if self.adv_price_min_input.text() else None,
                "PriceMax": int(self.adv_price_max_input.text()) if self.adv_price_max_input.text() else None,
                "Exclusions": [x.strip() for x in self.adv_exclusions_input.text().split(",") if x.strip()],
                "Inclusion": self.adv_inclusion_input.text(),
            }
        else:
            return {
                "Make": self.make_combo.currentText(),
                "Model": self.model_combo.currentText(),
                "Address": self.address_input.text(),
                "Proximity": int(self.proximity_input.text()),
                "YearMin": self.year_min_combo.currentText() or None,
                "YearMax": self.year_max_combo.currentText() or None,
                "PriceMin": int(self.price_min_input.text()) if self.price_min_input.text() else "",
                "PriceMax": int(self.price_max_input.text()) if self.price_max_input.text() else "",
                "Exclusions": [x.strip() for x in self.exclusions_input.text().split(",") if x.strip()],
                "Inclusion": self.inclusion_input.text(),
            }

    def fetch_data(self):
        self.fetch_data_common(advanced=False)

    def fetch_data_advanced(self):
        self.fetch_data_common(advanced=True)

    def fetch_data_common(self, advanced):
        payload = self.get_payload(advanced)
        self.statusBar().showMessage("Fetching data...")
        self.fetch_thread = FetchDataThread(payload)
        self.fetch_thread.finished.connect(self.on_data_fetched)
        self.fetch_thread.error.connect(self.on_fetch_error)
        self.fetch_thread.start()

    def on_data_fetched(self, results):
        if isinstance(results, str):
            QMessageBox.warning(self, "Warning", f"Received unexpected string result: {results[:500]}...")
            print("GOT STRING INSTEAD OF dict")
            return
        
        if not results or not isinstance(results, list):
            QMessageBox.warning(self, "Warning", f"No results found or invalid data received. Type: {type(results)}")
            return

        self.results_tree.clear()
        for result in results:
            if isinstance(result, dict):
                result["link"] = "https://www.autotrader.ca" + result["link"]
                item = QTreeWidgetItem(self.results_tree)
                item.setText(0, str(result.get("link", "")))
                item.setText(1, str(result.get("Make", "")))
                item.setText(2, str(result.get("Model", "")))
                item.setText(3, str(result.get("Year", "")))
                item.setText(4, str(result.get("Trim", "")))
                item.setText(5, str(result.get("Price", "")))
                item.setText(6, str(result.get("Drivetrain", "")))
                item.setText(7, str(result.get("Odometer", "")))
                item.setText(8, str(result.get("Status", "")))
            else:
                print(f"Unexpected result type: {type(result)}, content: {result}")

        self.tab_widget.setCurrentWidget(self.results_tab)

        # Get the current payload
        payload = self.get_payload(self.tab_widget.currentIndex() == 1)  # Check if we're on the advanced tab

        # Create folder and filename for results
        foldernamestr = f"Results/{payload['Make']}_{payload['Model']}"
        if not os.path.exists(foldernamestr):
            os.makedirs(foldernamestr)
        filenamestr = (
            f"{foldernamestr}/{payload['YearMin']}-{payload['YearMax']}_"
            f"{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.csv"
        )

        # Save results to CSV
        try:
            if isinstance(results, list) and all(isinstance(item, dict) for item in results):
                save_results_to_csv(results, payload, filename=filenamestr)
                self.load_csv_to_tree(filenamestr)
                QMessageBox.information(self, "Success", f"Results saved to {filenamestr}")
                
            else:
                raise ValueError("Results are not in the expected format (list of dictionaries)")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to save results: {str(e)}")

        # Update the GUI to show we're done fetching
        self.statusBar().showMessage("Data fetching completed")

    def load_csv_to_tree(self, csv_filename):
        self.results_tree.clear()
        
        # Define column names
        allColNames = [
            "Link", "Make", "Model", "Year", "Trim", "Price", "Drivetrain", "Kilometres", "Status",
            "Body Type", "Engine", "Cylinder", "Transmission", "Exterior Colour", "Doors",
            "Fuel Type", "City Fuel Economy", "Hwy Fuel Economy"
        ]
        
        # Set the column headers
        self.results_tree.setColumnCount(len(allColNames))
        self.results_tree.setHeaderLabels(allColNames)
        
        try:
            with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
                csv_reader = csv.DictReader(csvfile)
                for row in csv_reader:
                    item = QTreeWidgetItem(self.results_tree)
                    for i, col_name in enumerate(allColNames):
                        item.setText(i, str(row.get(col_name, "")))
            
            # Resize columns to content
            for i in range(len(allColNames)):
                self.results_tree.resizeColumnToContents(i)
            
            self.tab_widget.setCurrentWidget(self.results_tab)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load CSV: {str(e)}")
            
            
    def on_fetch_error(self, error_message):
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")

    def save_payload(self):
        self.save_payload_common(advanced=False)

    def save_payload_advanced(self):
        self.save_payload_common(advanced=True)

    def save_payload_common(self, advanced):
        payload = self.get_payload(advanced)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Payload", "", "JSON Files (*.json)")
        if file_path:
            save_json_to_file(payload, file_path)
            QMessageBox.information(self, "Success", f"Payload saved to {file_path}")

    def load_payload(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Payload", "", "JSON Files (*.json)")
        if file_path:
            payload = read_json_file(file_path)
            if payload:
                self.set_payload_values(payload)
                QMessageBox.information(self, "Success", f"Payload loaded from {file_path}")

    def set_payload_values(self, payload):
        # Set values for basic search tab
        self.make_combo.setCurrentText(payload.get("Make", ""))
        self.update_model_dropdown()
        self.model_combo.setCurrentText(payload.get("Model", ""))
        self.address_input.setText(payload.get("Address", ""))
        self.proximity_input.setText(str(payload.get("Proximity", "")))
        self.year_min_combo.setCurrentText(str(payload.get("YearMin", "")))
        self.year_max_combo.setCurrentText(str(payload.get("YearMax", "")))
        self.price_min_input.setText(str(payload.get("PriceMin", "")))
        self.price_max_input.setText(str(payload.get("PriceMax", "")))
        self.exclusions_input.setText(",".join(payload.get("Exclusions", [])))
        self.inclusion_input.setText(payload.get("Inclusion", ""))

        # Set values for advanced search tab
        self.adv_make_input.setText(payload.get("Make", ""))
        self.adv_model_input.setText(payload.get("Model", ""))
        self.adv_address_input.setText(payload.get("Address", ""))
        self.adv_proximity_input.setText(str(payload.get("Proximity", "")))
        self.adv_year_min_input.setText(str(payload.get("YearMin", "")))
        self.adv_year_max_input.setText(str(payload.get("YearMax", "")))
        self.adv_price_min_input.setText(str(payload.get("PriceMin", "")))
        self.adv_price_max_input.setText(str(payload.get("PriceMax", "")))
        self.adv_exclusions_input.setText(",".join(payload.get("Exclusions", [])))
        self.adv_inclusion_input.setText(payload.get("Inclusion", ""))

    def on_item_double_clicked(self, item):
        link = item.text(0)
        if link:
            webbrowser.open(link)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoScraperGUI()
    window.show()
    sys.exit(app.exec_())