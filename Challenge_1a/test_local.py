#!/usr/bin/env python3
import os
import json
import fitz  # PyMuPDF
import re
from pathlib import Path
from collections import Counter

def extract_title_and_outline(pdf_path):
    """Extract title and hierarchical outline from PDF."""
    doc = fitz.open(pdf_path)
    
    # Try to get title from metadata first
    title = doc.metadata.get('title', '').strip()
    
    outline = []
    all_text_spans = []
    
    # Collect all text spans from all pages
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")
        
        for block in blocks["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text and len(text) > 1:
                            all_text_spans.append({
                                "text": text,
                                "size": span["size"],
                                "flags": span["flags"],
                                "font": span["font"],
                                "page": page_num + 1
                            })
    
    if not all_text_spans:
        doc.close()
        return {"title": title or "Untitled Document", "outline": []}
    
    # Find body text size (most common size)
    sizes = [span["size"] for span in all_text_spans]
    size_counter = Counter(sizes)
    body_size = size_counter.most_common(1)[0][0]
    
    # If no title in metadata, try to extract from first page
    if not title:
        first_page_spans = [span for span in all_text_spans if span["page"] == 1]
        if first_page_spans:
            # Find the largest text on first page as potential title
            max_size = max(span["size"] for span in first_page_spans)
            for span in first_page_spans:
                if span["size"] == max_size and is_likely_title(span["text"]):
                    title = span["text"]
                    break
        
        if not title:
            title = "Untitled Document"
    
    # Extract headings
    potential_headings = []
    
    for span in all_text_spans:
        text = span["text"]
        size = span["size"]
        flags = span["flags"]
        
        # Skip very short or very long text
        if len(text) < 2 or len(text) > 200:
            continue
            
        # Check if it's likely a heading
        is_bold = flags & 16
        size_ratio = size / body_size
        
        if is_likely_heading(text, size_ratio, is_bold):
            level = determine_heading_level(size_ratio, is_bold, size)
            potential_headings.append({
                "level": level,
                "text": text,
                "page": span["page"],
                "size": size,
                "size_ratio": size_ratio
            })
    
    # Remove duplicates (same text on same page)
    seen = set()
    for heading in potential_headings:
        key = (heading["text"], heading["page"])
        if key not in seen:
            seen.add(key)
            outline.append({
                "level": heading["level"],
                "text": heading["text"],
                "page": heading["page"]
            })
    
    # Sort by page then by size (larger headings first within same page)
    outline.sort(key=lambda x: (x["page"], -next(h["size"] for h in potential_headings 
                                                 if h["text"] == x["text"] and h["page"] == x["page"])))
    
    doc.close()
    
    return {
        "title": title,
        "outline": outline
    }

def is_likely_title(text):
    """Check if text is likely a document title."""
    text = text.strip()
    
    # Skip common non-title patterns
    if re.match(r'^(Page|Figure|Table|\d+|Date:|From:|To:)', text, re.IGNORECASE):
        return False
    
    # Title characteristics
    if len(text) > 10 and len(text) < 150:
        return True
    
    return False

def is_likely_heading(text, size_ratio, is_bold):
    """Check if text is likely a heading based on multiple criteria."""
    text = text.strip()
    
    # Skip very short fragmented text
    if len(text) < 3:
        return False
    
    # Skip common non-heading patterns
    skip_patterns = [
        r'^(Figure|Table|Equation|Page|Date|From|To|Email|Phone|www\.|http|March|April|May|June|July|August|September|October|November|December)',
        r'^\d+$',  # Just numbers
        r'^[.,:;!?()]+$',  # Just punctuation
        r'^(the|this|that|and|or|but|if|when|where|how|what|why|for|with|as|at|in|on|by)\s',  # Common start words for body text
        r'^\$\d+',  # Money amounts
        r'^\d{4}$',  # Years
        r'^p\.m\.|^a\.m\.',  # Time indicators
        r'^\d+:\d+',  # Time format
        r'^\d+\.\d+%',  # Percentages
        r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',  # Days
    ]
    
    for pattern in skip_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return False
    
    # Skip fragmented words (less than 4 chars and not complete words)
    if len(text) < 4 and not text.isupper():
        return False
    
    # Skip text that looks like fragments or incomplete
    if re.match(r'^[a-z]', text) and len(text) < 10:  # lowercase start, short
        return False
    
    # Skip text that ends mid-word
    if text.endswith(('f', 'r', 'n', 'st', 'nd', 'rd', 'th')) and len(text) < 8:
        return False
    
    # Heading indicators
    heading_score = 0
    
    # Size-based scoring (more stringent)
    if size_ratio > 1.8:
        heading_score += 4
    elif size_ratio > 1.4:
        heading_score += 3
    elif size_ratio > 1.2:
        heading_score += 2
    elif size_ratio > 1.1:
        heading_score += 1
    
    # Bold text
    if is_bold:
        heading_score += 2
    
    # Text pattern scoring
    # Numbered sections (e.g., "1. Introduction", "2.1 Overview")
    if re.match(r'^\d+\.?\d*\.?\s*[A-Z]', text):
        heading_score += 4
    
    # All caps (but not too long)
    if text.isupper() and 3 <= len(text) <= 50:
        heading_score += 3
    
    # Starts with capital, no period at end, reasonable length
    if re.match(r'^[A-Z].*[^.]$', text) and 5 <= len(text) <= 100:
        heading_score += 1
    
    # Contains colon (often in headings like "Background:")
    if text.endswith(':') and len(text) > 5:
        heading_score += 3
    
    # Appendix patterns
    if re.match(r'^Appendix\s+[A-Z]', text, re.IGNORECASE):
        heading_score += 4
    
    # Common heading words
    heading_words = ['summary', 'introduction', 'background', 'conclusion', 'references', 
                     'methodology', 'results', 'discussion', 'abstract', 'overview',
                     'timeline', 'approach', 'requirements', 'evaluation', 'appendix',
                     'milestones', 'preamble', 'membership', 'funding', 'phase']
    
    if any(word in text.lower() for word in heading_words):
        heading_score += 2
    
    # Length considerations (prefer reasonable length headings)
    if 5 <= len(text) <= 80:
        heading_score += 1
    elif len(text) > 100:
        heading_score -= 2  # Penalize very long text
    
    # Complete words bonus
    words = text.split()
    if len(words) >= 2 and all(len(word) >= 3 for word in words):
        heading_score += 1
    
    return heading_score >= 4

def determine_heading_level(size_ratio, is_bold, absolute_size):
    """Determine heading level based on multiple factors."""
    # Primary factor: size ratio
    if size_ratio > 2.0:
        return "H1"
    elif size_ratio > 1.6:
        return "H1" if is_bold else "H2"
    elif size_ratio > 1.3:
        return "H2"
    elif size_ratio > 1.1:
        return "H2" if is_bold else "H3"
    else:
        return "H3"

def process_pdfs():
    """Process all PDFs in input directory and output JSON files."""
    input_dir = Path("./input")
    output_dir = Path("./output")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    # Process each PDF file
    for pdf_file in input_dir.glob("*.pdf"):
        try:
            print(f"Processing {pdf_file.name}...")
            
            result = extract_title_and_outline(pdf_file)
            
            # Save to JSON
            output_file = output_dir / f"{pdf_file.stem}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"Saved outline to {output_file.name}")
            
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")

if __name__ == "__main__":
    print("Starting local PDF processing...")
    process_pdfs()
    print("Local processing completed!")