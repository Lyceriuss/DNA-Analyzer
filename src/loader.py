# src/loader.py
import pandas as pd
import os
import sys

def load_dna_file(filepath):
    """
    Loads a DNA raw data file (CSV/TXT) and returns a dictionary mapping RSID -> Genotype.
    Handles MyHeritage/23andMe formats by skipping comment lines.
    """
    if not os.path.exists(filepath):
        print(f"❌ Error: File not found at {filepath}")
        return {}

    try:
        # read_csv with comment='#' automatically skips lines starting with #
        # sep=None allows python to sniff if it's comma or tab separated
        df = pd.read_csv(filepath, comment='#', sep=None, engine='python', dtype=str)
        
        # Standardize columns: UPPERCASE and strip whitespace
        df.columns = [c.upper().strip() for c in df.columns]

        # Validation: Check for essential columns
        if 'RSID' not in df.columns or 'RESULT' not in df.columns:
            print(f"❌ Error: Input file missing required columns (RSID, RESULT). Found: {list(df.columns)}")
            return {}

        # Drop rows where result is missing or empty
        df = df.dropna(subset=['RSID', 'RESULT'])
        
        # Convert to dictionary: {'rs123': 'AG', 'rs456': 'TT'}
        # We strip quotes just in case the CSV has them like "AG"
        dna_dict = pd.Series(
            df.RESULT.str.replace('"', '').str.strip().values,
            index=df.RSID.str.replace('"', '').str.strip()
        ).to_dict()

        print(f"✅ Successfully loaded {len(dna_dict)} SNPs from {os.path.basename(filepath)}")
        return dna_dict

    except Exception as e:
        print(f"❌ Critical Error loading file: {e}")
        return {}