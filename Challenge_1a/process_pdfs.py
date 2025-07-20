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
    
    # Remove duplicates and clean up headings
    seen = set()
    clean_outline = []
    
    # Sort potential headings by page and size first
    potential_headings.sort(key=lambda x: (x["page"], -x["size"]))
    
    for heading in potential_headings:
        text = heading["text"]
        page = heading["page"]
        
        # Skip if we've seen this exact text on this page
        key = (text, page)
        if key in seen:
            continue
        
        # Skip if this looks like a substring of an existing heading on same page
        is_substring = False
        for existing in clean_outline:
            if existing["page"] == page:
                if text in existing["text"] or existing["text"] in text:
                    # Keep the longer, more complete version
                    if len(text) > len(existing["text"]):
                        clean_outline.remove(existing)
                        break
                    else:
                        is_substring = True
                        break
        
        if not is_substring:
            seen.add(key)
            clean_outline.append({
                "level": heading["level"],
                "text": text,
                "page": page
            })
    
    # Final sort by page and hierarchical order
    outline = sorted(clean_outline, key=lambda x: x["page"])
    
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
    if len(text) < 4:
        return False
    
    # Skip common non-heading patterns and OCR errors
    skip_patterns = [
        r'^(Figure|Table|Equation|Page|Date|From|To|Email|Phone|www\.|http)',
        r'^(March|April|May|June|July|August|September|October|November|December)',
        r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
        r'^\d+$',  # Just numbers
        r'^[.,:;!?()]+$',  # Just punctuation
        r'^(the|this|that|and|or|but|if|when|where|how|what|why|for|with|as|at|in|on|by)\s',
        r'^\$\d+',  # Money amounts
        r'^\d{4}$',  # Years
        r'^p\.m\.|^a\.m\.',  # Time indicators
        r'^\d+:\d+',  # Time format
        r'^\d+\.\d+%',  # Percentages
        r'^(RFP:|Request|Proposal|Business|Plan)$',  # Common repeating elements
        r'^\d+\s*-\s*\d+$',  # Page ranges
        r'^[A-Z]\s*$',  # Single letters
    ]
    
    for pattern in skip_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return False
    
    # Skip fragmented or OCR-corrupted text
    # Check for repeated characters (OCR errors like "eeee", "oooo")
    if re.search(r'(.)\1{3,}', text):
        return False
    
    # Skip text with too many single characters or fragments
    if len([c for c in text if c.isalpha()]) < len(text) * 0.7:
        return False
    
    # Skip fragments that don't form complete words
    words = text.split()
    if len(words) == 1 and len(text) < 6 and not text.isupper():
        return False
    
    # Skip text that looks like fragments (ends abruptly)
    if len(text) < 10 and text.endswith(('f', 'r', 'n', 'st', 'nd', 'rd', 'th', 'er', 'ed', 'ing')):
        return False
    
    # Skip lowercase starts unless it's a proper heading pattern
    if re.match(r'^[a-z]', text) and len(text) < 15:
        return False
    
    # Skip text with irregular spacing or formatting
    if '  ' in text or text.count(' ') > len(words):
        return False
    
    # Only allow text that looks like proper headings
    heading_score = 0
    
    # Size-based scoring (much more stringent)
    if size_ratio > 2.0:
        heading_score += 5
    elif size_ratio > 1.6:
        heading_score += 4
    elif size_ratio > 1.3:
        heading_score += 3
    elif size_ratio > 1.15:
        heading_score += 2
    else:
        return False  # Don't consider anything without significant size difference
    
    # Bold text bonus
    if is_bold:
        heading_score += 3
    
    # Strong heading patterns
    # Numbered sections (e.g., "1. Introduction", "2.1 Overview")
    if re.match(r'^\d+\.?\d*\.?\s*[A-Z][a-zA-Z\s]+$', text):
        heading_score += 5
    
    # All caps headings (reasonable length)
    if text.isupper() and 4 <= len(text) <= 40 and ' ' in text:
        heading_score += 4
    
    # Proper case headings ending with colon
    if text.endswith(':') and re.match(r'^[A-Z][a-zA-Z\s]+:$', text) and 6 <= len(text) <= 50:
        heading_score += 4
    
    # Appendix patterns
    if re.match(r'^Appendix\s+[A-Z][\w\s:]*$', text, re.IGNORECASE):
        heading_score += 5
    
    # Common heading words (must be in proper context)
    heading_words = ['summary', 'introduction', 'background', 'conclusion', 'references', 
                     'methodology', 'results', 'discussion', 'abstract', 'overview',
                     'timeline', 'approach', 'requirements', 'evaluation', 'appendix',
                     'milestones', 'preamble', 'membership', 'funding', 'phase']
    
    if any(word in text.lower() for word in heading_words) and len(text) <= 50:
        heading_score += 2
    
    # Title case bonus (First Letter Of Each Word Capitalized)
    words = text.split()
    if len(words) >= 2 and all(word[0].isupper() for word in words if len(word) > 2):
        heading_score += 2
    
    # Length considerations - prefer concise headings
    if 8 <= len(text) <= 60:
        heading_score += 2
    elif len(text) > 80:
        heading_score -= 3  # Strong penalty for very long text
    
    # Must have complete, meaningful words
    if len(words) >= 2 and all(len(word) >= 3 or word.isupper() for word in words):
        heading_score += 1
    
    # Higher threshold for better precision
    return heading_score >= 6

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
    input_dir = Path("/sample_dataset/pdf")
    output_dir = Path("/sample_dataset/outputs")
    
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
    print("Starting processing pdfs")
    process_pdfs()
    print("completed processing pdfs")