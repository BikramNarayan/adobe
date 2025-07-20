#!/usr/bin/env python3
import os
import json
import fitz  # PyMuPDF
import re
from pathlib import Path

def extract_title_and_outline(pdf_path):
    """Extract title and hierarchical outline from PDF."""
    doc = fitz.open(pdf_path)

    # Try to get title from metadata first
    title = doc.metadata.get('title', '').strip()

    # (fallback and span-scanning logic to be added)
    outline = []

    doc.close()
    return {"title": title or "Untitled Document", "outline": outline}

def process_pdfs():
    """Process all PDFs in input directory and output JSON files."""
    input_dir = Path("/sample_dataset/pdf")
    output_dir = Path("/sample_dataset/outputs")

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    for pdf_file in input_dir.glob("*.pdf"):
        try:
            print(f"Processing {pdf_file.name}...")
            # TODO: call extract_title_and_outline and dump JSON
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")

if __name__ == "__main__":
    print("Starting processing pdfs")
    process_pdfs()
    print("Completed (stub)")
