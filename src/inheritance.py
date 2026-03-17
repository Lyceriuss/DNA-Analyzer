import pandas as pd

def analyze_inheritance(child_df, parent1_df, parent2_df=None, parent1_name="Parent 1", parent2_name="Parent 2"):
    """
    Compares a primary subject's DNA DataFrame against 1 or 2 relatives to determine trait origins.
    """
    if child_df.empty:
        return pd.DataFrame()

    # 1. Prepare Child Data
    # We only need specific columns for the PDF table
    cols_to_keep = ['RSID', 'Gene', 'Domain', 'Trait', 'Result', 'Score', 'Interpretation']
    
    # Filter columns that actually exist in the dataframe to prevent KeyError
    existing_cols = [col for col in cols_to_keep if col in child_df.columns]
    child_base = child_df[existing_cols].copy()
    
    # Rename child columns for clarity during the merge
    child_base = child_base.rename(columns={'Result': 'Child_Result', 'Score': 'Child_Score'})

    # 2. Merge Relative 1
    if not parent1_df.empty:
        p1_base = parent1_df[['RSID', 'Result', 'Score']].copy()
        p1_base = p1_base.rename(columns={'Result': f'{parent1_name}_Result', 'Score': f'{parent1_name}_Score'})
        # Left merge: We only care about traits the child has
        merged_df = pd.merge(child_base, p1_base, on='RSID', how='left')
    else:
        merged_df = child_base.copy()
        merged_df[f'{parent1_name}_Result'] = 'N/A'

    # 3. Merge Relative 2 (if provided)
    has_p2 = parent2_df is not None and not parent2_df.empty
    if has_p2:
        p2_base = parent2_df[['RSID', 'Result', 'Score']].copy()
        p2_base = p2_base.rename(columns={'Result': f'{parent2_name}_Result', 'Score': f'{parent2_name}_Score'})
        merged_df = pd.merge(merged_df, p2_base, on='RSID', how='left')

    # 4. Logic Engine: Determine Source
    def determine_source(row):
        # Convert to string to handle missing/NaN values safely
        c_res = str(row.get('Child_Result', 'nan'))
        p1_res = str(row.get(f'{parent1_name}_Result', 'nan'))
        p2_res = str(row.get(f'{parent2_name}_Result', 'nan')) if has_p2 else 'nan'

        # If the child's result is missing, we can't compare
        if c_res == 'nan': return "Unknown"

        if has_p2:
            # Case 1: Neither parent was tested for this specific SNP
            if p1_res == 'nan' and p2_res == 'nan': 
                return "Relatives Not Tested"
            
            # Case 2: Exact match with BOTH
            elif c_res == p1_res and c_res == p2_res:
                return "Both Sides"
                
            # Case 3: Exact match with Relative 1
            elif c_res == p1_res:
                return f"Match: {parent1_name}"
                
            # Case 4: Exact match with Relative 2
            elif c_res == p2_res:
                return f"Match: {parent2_name}"
                
            # Case 5: Recombination (e.g., Child is A/G, Mom is A/A, Dad is G/G)
            else:
                return "Mixed / Recombined"
        else:
            # Only 1 relative to compare against
            if p1_res == 'nan': 
                return "Relative Not Tested"
            elif c_res == p1_res:
                return f"Match: {parent1_name}"
            else:
                return "Different"

    # Apply the logic row by row
    merged_df['Inheritance_Source'] = merged_df.apply(determine_source, axis=1)

    # 5. Clean up the DataFrame for the UI (Replace NaN with 'N/A')
    fill_dict = {f'{parent1_name}_Result': 'N/A'}
    if has_p2:
        fill_dict[f'{parent2_name}_Result'] = 'N/A'
    merged_df = merged_df.fillna(fill_dict)

    # 6. Sorting: Bring the most impactful traits to the top
    # We want traits furthest from the baseline (Score = 5) to show up first
    if 'Child_Score' in merged_df.columns:
        merged_df['Abs_Impact'] = abs(merged_df['Child_Score'] - 5)
        merged_df = merged_df.sort_values(by=['Abs_Impact', 'Domain'], ascending=[False, True])
        merged_df = merged_df.drop(columns=['Abs_Impact'])

    return merged_df