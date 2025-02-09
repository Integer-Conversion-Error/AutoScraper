import sys
import os
import webbrowser
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,  # type: ignore
                             QLabel, QLineEdit, QPushButton, QComboBox, QTabWidget, 
                             QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox)

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox, QWidget)
from PyQt5.QtCore import QThread, pyqtSignal # type: ignore

from AutoScraper import fetch_autotrader_data, save_results_to_csv#, save_results_to_csv
from GetUserSelection import get_models_for_make
from AutoScraperUtil import format_time_ymd_hms, get_all_makes, get_trims_for_model, read_json_file, save_json_to_file

class FetchDataThread(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            print(self.payload)
            results = fetch_autotrader_data(self.payload)
            #print(f"Type of results: {type(results)}")
            #print(f"Content of results: {results[:500] if isinstance(results, str) else results}")
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
        layout = QGridLayout(self.basic_search_tab)

        # Create widgets
        self.make_combo = QComboBox()
        self.make_combo.addItems(get_all_makes())
        self.make_combo.currentTextChanged.connect(self.update_model_dropdown)
        
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.update_trim_dropdown)
        
        self.trim_combo = QComboBox()  # New Trim dropdown
        
        self.address_input = QLineEdit("Kanata, ON")
        self.proximity_input = QLineEdit("-1")
        self.year_min_combo = QComboBox()
        self.year_max_combo = QComboBox()
        self.year_min_combo.addItems([str(year) for year in range(2025, 1899, -1)])
        self.year_max_combo.addItems([str(year) for year in range(2025, 1899, -1)])
        self.price_min_input = QLineEdit()
        self.price_max_input = QLineEdit()
        self.km_min_input = QLineEdit()
        self.km_max_input = QLineEdit()
        self.exclusions_input = QLineEdit()
        self.inclusion_input = QLineEdit()

        # Add widgets to layout
        current_row = 0

        # Full-width widgets
        full_width_widgets = [
            ("Make:", self.make_combo),
            ("Model:", self.model_combo),
            ("Trim:", self.trim_combo),  # New Trim dropdown
            ("Address:", self.address_input),
            ("Proximity (km):", self.proximity_input),
            ("Exclusions (comma-separated):", self.exclusions_input),
            ("Inclusion:", self.inclusion_input)
        ]

        for label_text, widget in full_width_widgets:
            layout.addWidget(QLabel(label_text), current_row, 0, 1, 1)
            layout.addWidget(widget, current_row, 1, 1, 2)
            current_row += 1

        # Min/Max widgets
        min_max_widgets = [
            ("Year (min to max):", self.year_min_combo, self.year_max_combo),
            ("Price (min to max):", self.price_min_input, self.price_max_input),
            ("KMs (min to max):", self.km_min_input, self.km_max_input)
        ]

        for label_text, min_widget, max_widget in min_max_widgets:
            layout.addWidget(QLabel(label_text), current_row, 0, 1, 1)
            layout.addWidget(min_widget, current_row, 1, 1, 1)
            layout.addWidget(max_widget, current_row, 2, 1, 1)
            current_row += 1

        # Buttons
        fetch_button = QPushButton("Fetch Data")
        fetch_button.clicked.connect(self.fetch_data)
        save_payload_button = QPushButton("Save Payload")
        save_payload_button.clicked.connect(self.save_payload)
        load_payload_button = QPushButton("Load Payload")
        load_payload_button.clicked.connect(self.load_payload)

        layout.addWidget(fetch_button, current_row, 0, 1, 1)
        layout.addWidget(save_payload_button, current_row, 1, 1, 1)
        layout.addWidget(load_payload_button, current_row, 2, 1, 1)

        # Set column stretch to make all columns equal width
        for i in range(3):
            layout.setColumnStretch(i, 1)

        self.basic_search_tab.setLayout(layout)

    def update_model_dropdown(self):
        make = self.make_combo.currentText()
        self.model_combo.clear()
        if make:
            models = get_models_for_make(make)
            self.model_combo.addItems(list(models.keys()))
        self.update_trim_dropdown()  # Update trims when model is updated

    def update_trim_dropdown(self):
        make = self.make_combo.currentText()
        model = self.model_combo.currentText()
        self.trim_combo.clear()
        if make and model:
            trims = get_trims_for_model(make, model)
            trims.update({"All":1})
            #TODO: Make trims work for actual payload, multithread the loading process, and add an "All" option.
            #print(make,model,trims)
            self.trim_combo.addItems(list(trims.keys()))

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


        self.adv_km_min_input = QLineEdit()  # New Min KM widget
        self.adv_km_max_input = QLineEdit()  # New Max KM widget
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

        layout.addWidget(QLabel("KM Min:"))  # New Min KM label
        layout.addWidget(self.adv_km_min_input)  # New Min KM widget
        layout.addWidget(QLabel("KM Max:"))  # New Max KM label
        layout.addWidget(self.adv_km_max_input)  # New Max KM widget

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

        # Add buttons for loading and saving CSV
        button_layout = QHBoxLayout()
        load_csv_button = QPushButton("Load CSV")
        load_csv_button.clicked.connect(self.load_csv_file)
        save_csv_button = QPushButton("Save CSV")
        save_csv_button.clicked.connect(self.save_csv_file)
        button_layout.addWidget(load_csv_button)
        button_layout.addWidget(save_csv_button)
        layout.addLayout(button_layout)

        self.current_csv_file = None  # To keep track of the currently loaded CSV file

    def load_csv_file(self):
        # Set the base directory to ~/Documents/AutoScraper/Results
        base_directory = os.path.expanduser("~/Documents/AutoScraper/Results")
        
        # Open the file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load CSV File",
            base_directory,
            "CSV Files (*.csv)"
        )
        
        if file_path:
            # The load_csv_to_tree method now handles setting self.current_csv_file
            self.load_csv_to_tree(file_path)

    def load_csv_to_tree(self, csv_filename=None):
        if csv_filename is None:
            # If no filename is provided, open a file dialog
            base_directory = os.path.expanduser("~/Documents/AutoScraper/Results")
            csv_filename, _ = QFileDialog.getOpenFileName(
                self, "Load CSV File", base_directory, "CSV Files (*.csv)"
            )
            if not csv_filename:  # User cancelled the dialog
                return

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
            QMessageBox.information(self, "Success", f"CSV file loaded: {csv_filename}")

            # Store the current CSV file path
            self.current_csv_file = csv_filename

        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load CSV: {str(e)}")

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
                

                "PriceMin": self.adv_price_min_input.text() or "",
                "PriceMax": self.adv_price_max_input.text() or "",
                "OdometerMin": self.adv_km_min_input.text() or "",
                "OdometerMax": self.adv_km_max_input.text() or "",

                "Exclusions": [x.strip() for x in self.adv_exclusions_input.text().split(",") if x.strip()],
                "Inclusion": self.adv_inclusion_input.text(),
            }
        else:
            returnpayload = {
                "Make": self.make_combo.currentText(),
                "Model": self.model_combo.currentText(),
                "Trim": self.trim_combo.currentText(),
                "Address": self.address_input.text(),
                "Proximity": int(self.proximity_input.text()),
                "YearMin": self.year_min_combo.currentText() or None,
                "YearMax": self.year_max_combo.currentText() or None,


                "PriceMin": self.price_min_input.text() or "",
                "PriceMax": self.price_max_input.text() or "",
                "OdometerMin": self.km_min_input.text() or "",
                "OdometerMax": self.km_max_input.text() or "",
                "Exclusions": [x.strip() for x in self.exclusions_input.text().split(",") if x.strip()],
                "Inclusion": self.inclusion_input.text(),
            }
            #print(returnpayload)
            return returnpayload

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
                #result["link"] = "https://www.autotrader.ca" + result["link"]
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
        base_directory = os.path.expanduser("~/Documents/AutoScraper")
        results_directory = os.path.join(base_directory, "Results", payload['Make'], payload['Model'])
        os.makedirs(results_directory, exist_ok=True)

        filename = (
            f"{payload['YearMin']}-{payload['YearMax']}_"
            f"{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.csv"
        )
        full_path = os.path.join(results_directory, filename)

        # Save results to CSV
        try:
            if isinstance(results, list) and all(isinstance(item, dict) for item in results):
                save_results_to_csv(results, payload, filename=full_path)
                self.load_csv_to_tree(full_path)
                QMessageBox.information(self, "Success", f"Results saved to {full_path}")
                
            else:
                raise ValueError("Results are not in the expected format (list of dictionaries)")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to save results: {str(e)}")

        # Update the GUI to show we're done fetching
        self.statusBar().showMessage("Data fetching completed")

    
            
            
    def on_fetch_error(self, error_message):
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")

    def save_payload(self):
        self.save_payload_common(advanced=False)

    def save_payload_advanced(self):
        self.save_payload_common(advanced=True)

    def save_payload_common(self, advanced):
        payload = self.get_payload(advanced)
        base_directory = os.path.expanduser("~/Documents/AutoScraper")
        specific_directory = os.path.join(base_directory, "Queries")
        
        # Create the directory if it doesn't exist
        os.makedirs(specific_directory, exist_ok=True)

        # Create a QFileDialog instance
        dialog = QFileDialog(self)
        dialog.setDirectory(specific_directory)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter("JSON Files (*.json)")
        dialog.setDefaultSuffix("json")
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Payload", "", "JSON Files (*.json)")
        if file_path:
            save_json_to_file(payload, file_path)
            QMessageBox.information(self, "Success", f"Payload saved to {file_path}")

    def load_payload(self):
        # Expand the user's home directory and create the full path
        default_dir = os.path.expanduser("~/Documents/AutoScraper/Queries")
        
        # Ensure the directory exists
        os.makedirs(default_dir, exist_ok=True)

        # Open the file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Payload",
            default_dir,
            "JSON Files (*.json)"
        )

        if file_path:
            payload = read_json_file(file_path)
            if payload:
                self.set_payload_values(payload)
                QMessageBox.information(self, "Success", f"Payload loaded from {file_path}")
            else:
                QMessageBox.warning(self, "Error", "Failed to load payload. The file might be empty")

    def set_payload_values(self, payload):
        # Set values for basic search tab
        self.make_combo.setCurrentText(payload.get("Make", ""))
        self.update_model_dropdown()
        self.model_combo.setCurrentText(payload.get("Model", ""))
        self.update_trim_dropdown()
        self.trim_combo.setCurrentText(payload.get("Trim","All"))
        self.address_input.setText(payload.get("Address", ""))
        self.proximity_input.setText(str(payload.get("Proximity", "")))
        self.year_min_combo.setCurrentText(str(payload.get("YearMin", "")))
        self.year_max_combo.setCurrentText(str(payload.get("YearMax", "")))
        self.price_min_input.setText(str(payload.get("PriceMin", "")))
        self.price_max_input.setText(str(payload.get("PriceMax", "")))
        self.exclusions_input.setText(",".join(payload.get("Exclusions", [])))
        self.inclusion_input.setText(payload.get("Inclusion", ""))

        self.km_min_input.setText(str(payload.get("OdometerMin", "")))
        self.km_max_input.setText(str(payload.get("OdometerMax", "")))
        
        

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
        self.adv_km_min_input.setText(str(payload.get("OdometerMin", "")))
        self.adv_km_max_input.setText(str(payload.get("OdometerMax", "")))

    def save_csv_file(self):
        if self.results_tree.topLevelItemCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to save.")
            return

        # Extract car make and model from the results
        car_make = ""
        car_model = ""
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            print(self.results_tree.headerItem().text(1),self.results_tree.headerItem().text(2))
            make = item.text(1)
            model = item.text(2)
            print(make,model)
            if make and model:
                car_make = make
                car_model = model
                break

        if not car_make or not car_model:
            QMessageBox.warning(self, "Warning", "Unable to determine car make and model from results.")
            return

        # Define the specific directory structure
        base_directory = os.path.expanduser("~/Documents/AutoScraper")
        specific_directory = os.path.join(base_directory, "Results", car_make, car_model)

        # Create the directory if it doesn't exist
        os.makedirs(specific_directory, exist_ok=True)

        # Create a QFileDialog instance
        dialog = QFileDialog(self)
        dialog.setDirectory(specific_directory)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter("CSV Files (*.csv)")
        dialog.setDefaultSuffix("csv")

        if dialog.exec_() == QFileDialog.Accepted:
            file_path = dialog.selectedFiles()[0]
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write header
                    header = [self.results_tree.headerItem().text(i) for i in range(self.results_tree.columnCount())]
                    writer.writerow(header)
                    # Write data
                    for i in range(self.results_tree.topLevelItemCount()):
                        row = [self.results_tree.topLevelItem(i).text(j) for j in range(self.results_tree.columnCount())]
                        writer.writerow(row)

                QMessageBox.information(self, "Success", f"Results saved to {file_path}")

                # Ask if the user wants to delete the original file
                if self.current_csv_file and self.current_csv_file != file_path:
                    try:
                        os.remove(self.current_csv_file)
                        QMessageBox.information(self, "Success", f"Placeholder file deleted: {self.current_csv_file}")
                        self.current_csv_file = file_path
                    except Exception as e:
                        QMessageBox.warning(self, "Warning", f"Failed to delete placeholder file: {str(e)}")

            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to save CSV: {str(e)}")

    def on_item_double_clicked(self, item):
        link = item.text(0)
        if link:
            webbrowser.open(link)

def GUI_main():
    app = QApplication(sys.argv)
    window = AutoScraperGUI()
    window.show()
    sys.exit(app.exec_())
    
if __name__ == "__main__":
    GUI_main()