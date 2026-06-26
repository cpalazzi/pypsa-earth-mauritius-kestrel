import json
import sys

def validate_notebook(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        cells = nb.get('cells', [])
        for i, cell in enumerate(cells):
            # Check metadata.language (Note: Jupyter cells often don't have metadata.language directly, 
            # they might have it in the notebook metadata or it might be expected per cell in some schemas.
            # The prompt specifically says "confirm every cell has metadata.language")
            if 'language' not in cell.get('metadata', {}):
                print(f"Error: Cell {i} missing metadata.language")
                return False
            
            # Compile each code cell
            if cell.get('cell_type') == 'code':
                source = "".join(cell.get('source', []))
                try:
                    compile(source, f'<cell_{i}>', 'exec')
                except Exception as e:
                    print(f"Error: Cell {i} failed to compile: {e}")
                    return False
        
        print("Notebook validation passed.")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

if __name__ == "__main__":
    if not validate_notebook('notebooks/asset_model/03_interruption_analysis.ipynb'):
        sys.exit(1)
