import streamlit as st
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time, random, os

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


def process_data(df):
    compound_names = df.iloc[:, 0].dropna().unique()
    results = []

    progress = st.progress(0)
    status = st.empty()

    status.text("Fetching PubChem data...")
    pubchem_results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_compound = {executor.submit(get_pubchem_info, c): c for c in compound_names}
        for i, future in enumerate(as_completed(future_to_compound)):
            data = future.result()
            if data:
                pubchem_results.append(data)
            progress.progress(int(((i + 1) / len(compound_names)) * 50))

    status.text("Annotating with ClassyFire...")
    final_results = []
    for i, item in enumerate(pubchem_results):
        classy = get_classyfire_info(item['InChIKey'])
        combined = {**item, **classy}
        final_results.append(combined)
        progress.progress(50 + int(((i + 1) / len(pubchem_results)) * 50))

    status.text("✅ Done! Data processed successfully.")
    return pd.DataFrame(final_results)

# ------------------ Streamlit UI ------------------

st.set_page_config(page_title="Chemical Data Extractor", page_icon="🧪")

st.title("🧬 ChemExtractor")
st.markdown("Upload an Excel file containing **compound names** (first column). The app will fetch details from **PubChem** and **ClassyFire** automatically.")

uploaded_file = st.file_uploader("📂 Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.write("### Preview of Uploaded File:")
    st.dataframe(df.head())

    if st.button("🚀 Start Extraction"):
        with st.spinner("Processing compounds..."):
            output_df = process_data(df)

        st.success("Extraction completed successfully!")
        st.write("### Extracted Data:")
        st.dataframe(output_df)

        # Download option
        output_path = "chem_data_output.xlsx"
        output_df.to_excel(output_path, index=False)
        with open(output_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Processed Excel File",
                data=f,
                file_name="ChemExtractor_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("👆 Please upload an Excel file to get started.")
