import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import webbrowser
import threading
import os
from AutoScraper_ALL import *

# Main GUI Application
def main_gui():
    root = tk.Tk()
    root.title("AutoScraper GUI")
    root.geometry("1200x600")

    # Run get_all_makes at startup
    makes_list = get_all_makes()

    # Tabs Setup
    notebook = ttk.Notebook(root)
    tab_basic_search = ttk.Frame(notebook)
    tab_advanced_search = ttk.Frame(notebook)
    tab_results = ttk.Frame(notebook)

    notebook.add(tab_basic_search, text="Basic Search")
    notebook.add(tab_advanced_search, text="Advanced Search")
    notebook.add(tab_results, text="Results Viewer")
    notebook.pack(expand=True, fill="both")

    # Variables for User Input
    make_var = tk.StringVar()
    model_var = tk.StringVar()
    address_var = tk.StringVar(value="Kanata, ON")
    proximity_var = tk.IntVar(value=-1)
    year_min_var = tk.StringVar()
    year_max_var = tk.StringVar()
    price_min_var = tk.IntVar()
    price_max_var = tk.IntVar()
    exclusions_var = tk.StringVar()
    inclusion_var = tk.StringVar()

    # Year Range Options
    years = [str(year) for year in reversed(range(1950, 2026))]

    # Functions to dynamically update models
    def update_model_dropdown(*args):
        selected_make = make_var.get()
        if selected_make:
            def fetch_models():
                models_dict = get_models_for_make(selected_make)
                model_dropdown["values"] = list(models_dict.keys())

            thread = threading.Thread(target=fetch_models)
            thread.start()

    # Basic Search Form
    tk.Label(tab_basic_search, text="Make:").grid(row=0, column=0, padx=10, pady=5)
    make_dropdown = ttk.Combobox(tab_basic_search, textvariable=make_var, values=makes_list, state="readonly")
    make_dropdown.grid(row=0, column=1, padx=10, pady=5)
    make_var.trace("w", update_model_dropdown)

    tk.Label(tab_basic_search, text="Model:").grid(row=1, column=0, padx=10, pady=5)
    model_dropdown = ttk.Combobox(tab_basic_search, textvariable=model_var, state="readonly")
    model_dropdown.grid(row=1, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Address:").grid(row=2, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=address_var).grid(row=2, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Proximity (km):").grid(row=3, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=proximity_var).grid(row=3, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Year Min:").grid(row=4, column=0, padx=10, pady=5)
    year_min_dropdown = ttk.Combobox(tab_basic_search, textvariable=year_min_var, values=years, state="readonly")
    year_min_dropdown.grid(row=4, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Year Max:").grid(row=5, column=0, padx=10, pady=5)
    year_max_dropdown = ttk.Combobox(tab_basic_search, textvariable=year_max_var, values=years, state="readonly")
    year_max_dropdown.grid(row=5, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Price Min:").grid(row=6, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=price_min_var).grid(row=6, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Price Max:").grid(row=7, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=price_max_var).grid(row=7, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Exclusions (comma-separated):").grid(row=8, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=exclusions_var).grid(row=8, column=1, padx=10, pady=5)

    tk.Label(tab_basic_search, text="Inclusion:").grid(row=9, column=0, padx=10, pady=5)
    tk.Entry(tab_basic_search, textvariable=inclusion_var).grid(row=9, column=1, padx=10, pady=5)

    # Advanced Search Form
    tk.Label(tab_advanced_search, text="Make:").grid(row=0, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=make_var).grid(row=0, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Model:").grid(row=1, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=model_var).grid(row=1, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Address:").grid(row=2, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=address_var).grid(row=2, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Proximity (km):").grid(row=3, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=proximity_var).grid(row=3, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Year Min:").grid(row=4, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=year_min_var).grid(row=4, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Year Max:").grid(row=5, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=year_max_var).grid(row=5, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Price Min:").grid(row=6, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=price_min_var).grid(row=6, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Price Max:").grid(row=7, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=price_max_var).grid(row=7, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Exclusions (comma-separated):").grid(row=8, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=exclusions_var).grid(row=8, column=1, padx=10, pady=5)

    tk.Label(tab_advanced_search, text="Inclusion:").grid(row=9, column=0, padx=10, pady=5)
    tk.Entry(tab_advanced_search, textvariable=inclusion_var).grid(row=9, column=1, padx=10, pady=5)

    # Results Viewer
    tree = ttk.Treeview(tab_results, show="headings")
    tree.pack(expand=True, fill="both")

    # Functions for Buttons
    def fetch_data():
        payload = {
            "Make": make_var.get(),
            "Model": model_var.get(),
            "Address": address_var.get(),
            "Proximity": proximity_var.get(),
            "YearMin": year_min_var.get() if year_min_var.get() else None,
            "YearMax": year_max_var.get() if year_max_var.get() else None,
            "PriceMin": price_min_var.get() if price_min_var.get() else None,
            "PriceMax": price_max_var.get() if price_max_var.get() else None,
            "Exclusions": exclusions_var.get().split(",") if exclusions_var.get() else [],
            "Inclusion": inclusion_var.get(),
        }

        def save_and_load_results():
            try:
                print("Payload being sent to fetch_autotrader_data:", payload)
                results = fetch_autotrader_data(payload)
                print("Results fetched:", results)
                if not isinstance(results, list):
                    raise ValueError("Fetched data is not a list. Please check the data source.")

                # Ensure each result is a dictionary
                for i, result in enumerate(results):
                    print(f"Result at index {i}: {result}")
                    result["link"] = "https://www.autotrader.ca" + result["link"]
                    if not isinstance(result, dict):
                        raise ValueError(f"Result at index {i} is not a dictionary: {result}")

                # Create folder and filename based on payload
                foldernamestr = f"Results/{payload['Make']}_{payload['Model']}"
                if not os.path.exists(foldernamestr):
                    os.makedirs(foldernamestr)

                filenamestr = (
                    f"{foldernamestr}/{payload['YearMin']}-{payload['YearMax']}_"
                    f"{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.csv"
                )

                save_results_to_csv(results, payload, filename=filenamestr)
                print(f"Results saved to {filenamestr}")

                # Reload results from the CSV file into the treeview
                with open(filenamestr, mode="r", newline="", encoding="utf-8") as file:
                    import csv
                    reader = csv.DictReader(file)
                    tree.delete(*tree.get_children())  # Clear existing entries

                    # Update columns dynamically based on the CSV headers
                    tree["columns"] = reader.fieldnames
                    for col in reader.fieldnames:
                        tree.heading(col, text=col)

                    for row in reader:
                        print("Row being processed for treeview:", row)
                        tree.insert("", "end", values=[row.get(col, "") for col in reader.fieldnames])

            except Exception as e:
                print("Error occurred:", e)
                messagebox.showerror("Error", str(e))

        # Run the save and load operation in a separate thread
        thread = threading.Thread(target=save_and_load_results)
        thread.start()

    def on_row_click(event):
        selected_item = tree.focus()
        if not selected_item:
            return
        row_data = tree.item(selected_item, "values")
        if "Link" in tree["columns"]:
            link_index = tree["columns"].index("Link")
            link = row_data[link_index]
            print("Opening link:", link)
            webbrowser.open(link)

    tree.bind("<Double-1>", on_row_click)

    def save_payload():
        payload = {
            "Make": make_var.get(),
            "Model": model_var.get(),
            "Address": address_var.get(),
            "Proximity": proximity_var.get(),
            "YearMin": year_min_var.get() if year_min_var.get() else None,
            "YearMax": year_max_var.get() if year_max_var.get() else None,
            "PriceMin": price_min_var.get() if price_min_var.get() else None,
            "PriceMax": price_max_var.get() if price_max_var.get() else None,
            "Exclusions": exclusions_var.get().split(",") if exclusions_var.get() else [],
            "Inclusion": inclusion_var.get(),
        }
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            save_json_to_file(payload, file_path)
            messagebox.showinfo("Success", f"Payload saved to {file_path}")

    def load_payload():
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            payload = read_json_file(file_path)
            if payload:
                make_var.set(payload.get("Make", ""))
                model_var.set(payload.get("Model", ""))
                address_var.set(payload.get("Address", ""))
                proximity_var.set(payload.get("Proximity", -1))
                year_min_var.set(payload.get("YearMin", ""))
                year_max_var.set(payload.get("YearMax", ""))
                price_min_var.set(payload.get("PriceMin", 0))
                price_max_var.set(payload.get("PriceMax", 0))
                exclusions_var.set(",".join(payload.get("Exclusions", [])))
                inclusion_var.set(payload.get("Inclusion", ""))

    # Buttons
    tk.Button(tab_basic_search, text="Fetch Data", command=fetch_data).grid(row=10, column=0, columnspan=2, pady=10)
    tk.Button(tab_basic_search, text="Save Payload", command=save_payload).grid(row=11, column=0, pady=10)
    tk.Button(tab_basic_search, text="Load Payload", command=load_payload).grid(row=11, column=1, pady=10)

    tk.Button(tab_advanced_search, text="Fetch Data", command=fetch_data).grid(row=10, column=0, columnspan=2, pady=10)
    tk.Button(tab_advanced_search, text="Save Payload", command=save_payload).grid(row=11, column=0, pady=10)
    tk.Button(tab_advanced_search, text="Load Payload", command=load_payload).grid(row=11, column=1, pady=10)

    root.mainloop()

if __name__ == "__main__":
    main_gui()
