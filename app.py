import pandas as pd
import requests
import time, random, io
import streamlit as st


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


def process_file(uploaded_file):
    df = pd.read_excel(uploaded_file)
    compound_names = df.iloc[:, 0].dropna().unique()

    st.info("Fetching PubChem data sequentially with rate limiting...")
    pubchem_results = []
    progress_text = st.empty()
    progress_bar = st.progress(0)

    for i, compound in enumerate(compound_names):
        data = None
        retries = 3
        delay = 1
        while retries > 0:
            data = get_pubchem_info(compound)
            if data is not None:
                break
            else:
                time.sleep(delay)
                delay *= 2  # exponential backoff
                retries -= 1

        if data:
            pubchem_results.append(data)
        else:
            pubchem_results.append({
                'Compound Name': compound,
                'SMILES': None,
                'InChIKey': None,
                'Molecular Formula': None,
                'Lipophilicity (XLogP)': None
            })

        progress_bar.progress((i + 1) / len(compound_names) * 0.5)
        progress_text.text(f"Fetched PubChem data for {i + 1}/{len(compound_names)} compounds")
        time.sleep(0.25)  # 0.25s delay to stay within ~4 requests/sec

    st.info("Annotating with ClassyFire sequentially with rate limiting...")
    final_results = []
    for i, item in enumerate(pubchem_results):
        inchikey = item['InChIKey']
        retries = 3
        delay = 1
        classy = None
        while retries > 0:
            classy = get_classyfire_info(inchikey)
            if classy['Class'] is not None:
                break
            else:
                time.sleep(delay)
                delay *= 2
                retries -= 1

        if classy:
            combined = {**item, **classy}
        else:
            combined = {**item, 'Class': None, 'Subclass': None, 'Superclass': None}

        final_results.append(combined)
        progress_bar.progress(0.5 + (i + 1) / len(pubchem_results) * 0.5)
        progress_text.text(f"Classified {i + 1}/{len(pubchem_results)} compounds")
        time.sleep(0.25)  # delay to avoid API overload

    st.success("✅ Done! All compounds processed successfully.")
    result_df = pd.DataFrame(final_results)
    return result_df


# ------------------ Streamlit UI ------------------

st.title("🧪 Chemical Data Extractor (PubChem + ClassyFire)")
st.write("Upload an Excel file with compound names in the first column.")

uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type=["xlsx", "xls"])

if uploaded_file:
    if st.button("Start Extraction"):
        with st.spinner("Processing... Please wait."):
            result_df = process_file(uploaded_file)
            st.dataframe(result_df)

            # Prepare Excel download
            buffer = io.BytesIO()
            result_df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.download_button(
                label="📥 Download Processed Data (Excel)",
                data=buffer,
                file_name="ChemicalData_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
