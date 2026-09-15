import os
import re
import unicodedata
import pandas as pd
from database.connection import SessionLocal
from database.models import Organisation

def normalize_key(text: str) -> str:
    """Strips accents, whitespace, and lowercases text."""
    if not isinstance(text, str):
        return ""
    # Normalize unicode to decompose accents (e.g., é -> e + ')
    nfkd = unicodedata.normalize("NFKD", text)
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return clean.strip().lower()

def clean_val(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    return val_str if val_str else None

def clean_website_url(url: str) -> str:
    """Normalizes website strings to ensure secure https:// protocol and clean formatting."""
    if not url:
        return None
    url = url.strip().rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[7:]
    elif not url.startswith("https://"):
        url = "https://" + url
    return url

def import_excel_organisations(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Reading Excel file: {file_path}")
    df = pd.read_excel(file_path)
    print(f"Found {len(df)} total rows.")

    # Create mapping from normalized column names to original column names
    col_map = {normalize_key(col): col for col in df.columns}
    print("Detected columns:", list(col_map.keys()))

    # Find the matching column names regardless of accents
    societe_col = col_map.get("societe") or col_map.get("nom") or col_map.get("company")
    site_col = col_map.get("site internet") or col_map.get("site") or col_map.get("website")
    linkedin_col = col_map.get("linkedin") or col_map.get("linkedin url")
    ville_col = col_map.get("ville") or col_map.get("city")
    pays_col = col_map.get("pays") or col_map.get("country")

    if not societe_col:
        print(f"Error: Could not locate 'societe' / 'company' column. Available: {list(df.columns)}")
        return

    db = SessionLocal()
    inserted_count = 0
    skipped_count = 0

    try:
        for idx, row in df.iterrows():
            name = clean_val(row.get(societe_col))
            if not name:
                continue

            website = clean_val(row.get(site_col)) if site_col else None
            linkedin = clean_val(row.get(linkedin_col)) if linkedin_col else None
            city = clean_val(row.get(ville_col)) if ville_col else None
            country = clean_val(row.get(pays_col)) if pays_col else None

            # Deduplication check against DB
            existing = db.query(Organisation).filter(
                Organisation.name.ilike(name.strip())
            ).first()

            if existing:
                skipped_count += 1
                continue

            clean_alias = re.sub(r"[^\w\s]", "", name).strip()
            aliases = [clean_alias] if clean_alias.lower() != name.lower() else []

            org = Organisation(
                name=name,
                alternative_names=aliases,
                website=website,
                linkedin_url=linkedin,
                city=city,
                country=country,
                organisation_type="Monitored Company"
            )
            db.add(org)
            inserted_count += 1

        db.commit()
        print("\nImport Complete:")
        print(f"  - Successfully added: {inserted_count}")
        print(f"  - Skipped (already in DB): {skipped_count}")

    except Exception as e:
        db.rollback()
        print(f"Import error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    import_excel_organisations("organisations.xlsx")