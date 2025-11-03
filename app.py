import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time, random, threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import os

# ------------------ Core Functions ------------------

def get_pubchem_info(compound_name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/property/SMILES,InChIKey,MolecularFormula,XLogP/JSON"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        props = response.json()['PropertyTable']['Properties'][0]
        return {
            'Compound Name': compound_name,
            'SMILES': props.get('SMILES'),
            'InChIKey': props.get('InChIKey'),
            'Molecular Formula': props.get('MolecularFormula'),
            'Lipophilicity (XLogP)': props.get('XLogP')
        }
    except Exception:
        return None


def get_classyfire_info(inchikey, retries=3, base_delay=1.5):
    if not inchikey:
        return {'Class': None, 'Subclass': None, 'Superclass': None}
    for attempt in range(retries):
        try:
            url = f"http://classyfire.wishartlab.com/entities/{inchikey}.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            d = response.json()
            return {
                'Class': d.get('class', {}).get('name'),
                'Subclass': d.get('subclass', {}).get('name'),
                'Superclass': d.get('superclass', {}).get('name')
            }
        except Exception:
            time.sleep(base_delay + random.uniform(0, 1.5))
    return {'Class': None, 'Subclass': None, 'Superclass': None}


def process_file(input_file, status_text, progress_bar):
    try:
        status_text.set("Reading Excel file...")
        df = pd.read_excel(input_file)
        compound_names = df.iloc[:, 0].dropna().unique()

        status_text.set("Fetching PubChem data...")
        pubchem_results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_compound = {executor.submit(get_pubchem_info, c): c for c in compound_names}
            for i, future in enumerate(as_completed(future_to_compound)):
                data = future.result()
                if data:
                    pubchem_results.append(data)
                progress_bar["value"] = (i + 1) / len(compound_names) * 50
                progress_bar.update()

        status_text.set("Annotating with ClassyFire...")
        final_results = []
        for i, item in enumerate(pubchem_results):
            classy = get_classyfire_info(item['InChIKey'])
            combined = {**item, **classy}
            final_results.append(combined)
            progress_bar["value"] = 50 + (i + 1) / len(pubchem_results) * 50
            progress_bar.update()

        output_file = os.path.splitext(input_file)[0] + "_output.xlsx"
        pd.DataFrame(final_results).to_excel(output_file, index=False)
        status_text.set(f"✅ Done! Saved as {os.path.basename(output_file)}")
        messagebox.showinfo("Success", f"Data saved as:\n{output_file}")

    except Exception as e:
        messagebox.showerror("Error", str(e))
        status_text.set("❌ Error occurred. See details above.")


# ------------------ GUI Setup ------------------

def start_process():
    input_file = file_path.get()
    if not input_file or not os.path.exists(input_file):
        messagebox.showwarning("Warning", "Please select a valid Excel file.")
        return
    threading.Thread(target=process_file, args=(input_file, status_text, progress_bar), daemon=True).start()


def browse_file():
    filename = filedialog.askopenfilename(
        title="Select Excel File", filetypes=[("Excel files", "*.xlsx *.xls")]
    )
    if filename:
        file_path.set(filename)


# GUI Window
root = tk.Tk()
root.title("Chemical Data Extractor")
root.geometry("520x300")
root.resizable(False, False)

file_path = tk.StringVar()
status_text = tk.StringVar(value="Select an Excel file and click Start.")

ttk.Label(root, text="PubChem + ClassyFire Data Extractor", font=("Segoe UI", 13, "bold")).pack(pady=10)

frame = ttk.Frame(root)
frame.pack(pady=5)
ttk.Entry(frame, textvariable=file_path, width=50).grid(row=0, column=0, padx=5)
ttk.Button(frame, text="Browse", command=browse_file).grid(row=0, column=1)

ttk.Button(root, text="Start Extraction", command=start_process).pack(pady=10)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(pady=10)

ttk.Label(root, textvariable=status_text, wraplength=400).pack(pady=10)

root.mainloop()
