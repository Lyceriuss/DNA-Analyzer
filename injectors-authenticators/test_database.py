import requests
import json

def get_uniprot_biochem_data(gene_symbol, amino_acid_position=None):
    """
    Fetches protein function and specific variant mechanics from UniProt.
    """
    print(f"Querying UniProt for {gene_symbol}...")
    
    # Query for the human (organism_id:9606) version of the exact gene
   # Added +AND+reviewed:true to strictly pull the Swiss-Prot curated data
    url = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene_symbol}+AND+organism_id:9606+AND+reviewed:true&format=json&size=1"
    
    response = requests.get(url)
    if not response.ok:
        return {"error": f"HTTP {response.status_code}"}
        
    data = response.json()
    if not data.get("results"):
        return {"error": "Protein not found in UniProt"}
        
    protein = data["results"][0]
    
    # Initialize our clean dictionary
    clean_data = {
        "source": "UniProt",
        "accession_id": protein.get("primaryAccession"),
        "protein_name": protein.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value"),
        "general_function": [],
        "catalytic_activity": [],
        "variant_mechanics": "No specific variant data requested or found."
    }
    
    # 1. Extract the General Function and Chemical Reactions
    for comment in protein.get("comments", []):
        if comment["commentType"] == "FUNCTION":
            clean_data["general_function"].append(comment["texts"][0]["value"])
        elif comment["commentType"] == "CATALYTIC ACTIVITY":
            if "reaction" in comment:
                clean_data["catalytic_activity"].append(comment["reaction"]["name"])
                
    # 2. Extract the specific wet-lab data for the mutation (if requested)
    if amino_acid_position:
        for feature in protein.get("features", []):
            # UniProt logs mutations under "Natural variant" or "Mutagenesis"
            if feature["type"] == "Natural variant":
                location = feature.get("location", {}).get("start", {}).get("value")
                
                # If we find the exact position (e.g., 429), grab the biochemical notes
                if location == amino_acid_position:
                    original = feature.get("originalSequence", "")
                    mutated = feature.get("alternativeSequence", "")
                    description = feature.get("description", "No description provided.")
                    
                    clean_data["variant_mechanics"] = f"{original} -> {mutated} at pos {location}: {description}"
                    break # We found it, stop looping
                    
    return clean_data

if __name__ == "__main__":
    # Testing MTHFR and specifically looking at position 429 (from Glu429Ala / rs1801131)
    uniprot_result = get_uniprot_biochem_data("MTHFR", 429)
    print(json.dumps(uniprot_result, indent=4))