#!/usr/bin/env python3
"""
Multi-Collection PDF Analysis Tool
Processes PDF collections and extracts relevant content based on personas and use cases.
"""

import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse

try:
    import PyPDF2
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    import re
except ImportError as e:
    print(f"Missing required dependencies: {e}")
    print("Install with: pip install PyPDF2 nltk")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFAnalyzer:
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.setup_nltk()
    
    def setup_nltk(self):
        """Download required NLTK data if not present"""
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
            nltk.data.find('corpora/wordnet')
        except LookupError:
            logger.info("Downloading required NLTK data...")
            import ssl
            try:
                _create_unverified_https_context = ssl._create_unverified_context
            except AttributeError:
                pass
            else:
                ssl._create_default_https_context = _create_unverified_https_context
            
            nltk.download('punkt')
            nltk.download('stopwords')
            nltk.download('wordnet')
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[int, str]:
        """Extract text from PDF file, organized by page number"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                pages_text = {}
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        pages_text[page_num] = text.strip()
                
                return pages_text
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return {}
    
    def identify_sections(self, text: str) -> List[Tuple[str, int]]:
        """Identify sections in text based on headings and structure"""
        lines = text.split('\n')
        sections = []
        current_section = ""
        section_start_line = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Detect potential section headers (common patterns)
            if (line.isupper() or 
                re.match(r'^[A-Z][^.]*[A-Z]', line) or
                len(line.split()) < 8 and line.endswith(':') or
                re.match(r'^\d+\.', line)):
                
                if current_section:
                    sections.append((current_section, section_start_line))
                current_section = line.rstrip(':')
                section_start_line = i
        
        if current_section:
            sections.append((current_section, section_start_line))
        
        return sections
    
    def calculate_relevance_score(self, text: str, persona: str, task: str) -> float:
        """Calculate relevance score based on persona and task keywords"""
        # Define persona-specific keywords
        persona_keywords = {
            "Travel Planner": ["travel", "trip", "destination", "hotel", "restaurant", "activity", "tour", "beach", "city", "culture", "food", "nightlife", "transportation"],
            "HR professional": ["form", "signature", "document", "employee", "onboarding", "compliance", "fillable", "workflow", "digital", "electronic", "process"],
            "Food Contractor": ["recipe", "vegetarian", "gluten-free", "buffet", "corporate", "catering", "ingredient", "cooking", "meal", "dish", "menu", "dietary"]
        }
        
        # Extract keywords from task
        task_words = set(word.lower() for word in word_tokenize(task) if len(word) > 3)
        
        # Get persona keywords
        persona_words = set(persona_keywords.get(persona, []))
        
        # Tokenize and clean text
        text_words = set(word.lower() for word in word_tokenize(text.lower()) if len(word) > 3)
        
        # Calculate relevance score
        persona_matches = len(text_words.intersection(persona_words))
        task_matches = len(text_words.intersection(task_words))
        
        # Normalize by text length
        text_length = len(text_words)
        if text_length == 0:
            return 0.0
        
        score = (persona_matches * 2 + task_matches * 3) / text_length
        return min(score * 100, 100.0)  # Cap at 100
    
    def extract_relevant_content(self, pages_text: Dict[int, str], persona: str, task: str, max_sections: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """Extract most relevant sections and subsections"""
        all_sections = []
        seen_content = set()  # Track unique content
        
        for page_num, text in pages_text.items():
            sections = self.identify_sections(text)
            
            if not sections:
                # If no clear sections found, treat entire page as one section
                sections = [("Main Content", 0)]
            
            for section_title, _ in sections:
                relevance_score = self.calculate_relevance_score(text, persona, task)
                
                if relevance_score > 0:
                    # Create unique content hash to avoid duplicates
                    content_hash = hash(section_title.strip().lower())
                    
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        all_sections.append({
                            'title': section_title,
                            'page': page_num,
                            'score': relevance_score,
                            'text': text
                        })
        
        # Sort by relevance score and take top sections
        all_sections.sort(key=lambda x: x['score'], reverse=True)
        top_sections = all_sections[:max_sections]
        
        # Create subsection analysis with unique, refined content
        all_subsections = []
        seen_refined = set()
        
        for section in top_sections:
            # Clean and refine text
            refined_text = self.refine_text(section['text'], persona, task)
            
            # Only add if refined text is meaningful and unique
            if refined_text and len(refined_text.strip()) > 10:
                refined_hash = hash(refined_text.strip().lower())
                if refined_hash not in seen_refined:
                    seen_refined.add(refined_hash)
                    all_subsections.append({
                        'page': section['page'],
                        'text': refined_text,
                        'relevance_score': section['score']
                    })
        
        return top_sections, all_subsections
    
    def refine_text(self, text: str, persona: str, task: str) -> str:
        """Refine and clean extracted text for better readability"""
        # Remove excessive whitespace and clean text
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'[^\w\s\.\,\!\?\:\;\-\(\)\'\"]+', ' ', text)  # Remove special chars
        
        if len(text) < 20:  # Skip very short text
            return ""
        
        # Split into sentences
        try:
            sentences = sent_tokenize(text)
        except:
            sentences = text.split('.')
        
        # Filter and score relevant sentences
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence.split()) > 5:  # Avoid very short sentences
                relevance = self.calculate_relevance_score(sentence, persona, task)
                if relevance > 0.05:  # Lower threshold for individual sentences
                    scored_sentences.append((sentence, relevance))
        
        # Sort by relevance and take diverse content
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # Select diverse sentences (avoid repetition)
        selected_sentences = []
        seen_words = set()
        
        for sentence, score in scored_sentences:
            sentence_words = set(sentence.lower().split())
            # Check if sentence adds new information (at least 30% new words)
            new_words = sentence_words - seen_words
            if len(new_words) >= len(sentence_words) * 0.3:
                selected_sentences.append(sentence)
                seen_words.update(sentence_words)
                
                if len(selected_sentences) >= 3:  # Limit to 3 diverse sentences
                    break
        
        result = ' '.join(selected_sentences)
        return result if len(result) > 20 else ""
    
    def process_collection(self, collection_path: str) -> Dict[str, Any]:
        """Process a single collection"""
        input_file = os.path.join(collection_path, 'challenge1b_input.json')
        pdf_dir = os.path.join(collection_path, 'PDFs')
        
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return {}
        
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        
        persona = input_data['persona']['role']
        task = input_data['job_to_be_done']['task']
        documents = input_data['documents']
        
        logger.info(f"Processing collection: {collection_path}")
        logger.info(f"Persona: {persona}")
        logger.info(f"Task: {task}")
        logger.info(f"Documents: {len(documents)}")
        
        extracted_sections = []
        subsection_analysis = []
        
        for doc in documents:
            pdf_path = os.path.join(pdf_dir, doc['filename'])
            
            if not os.path.exists(pdf_path):
                logger.warning(f"PDF not found: {pdf_path}")
                continue
            
            logger.info(f"Processing: {doc['filename']}")
            
            # Extract text from PDF
            pages_text = self.extract_text_from_pdf(pdf_path)
            
            if not pages_text:
                logger.warning(f"No text extracted from: {doc['filename']}")
                continue
            
            # Extract relevant content
            sections, subsections = self.extract_relevant_content(pages_text, persona, task)
            
            # Add document info to sections
            for i, section in enumerate(sections):
                extracted_sections.append({
                    "document": doc['filename'],
                    "section_title": section['title'],
                    "importance_rank": len(extracted_sections) + 1,
                    "page_number": section['page']
                })
            
            # Add document info to subsections
            for subsection in subsections:
                subsection_analysis.append({
                    "document": doc['filename'],
                    "refined_text": subsection['text'],
                    "page_number": subsection['page']
                })
        
        # Sort extracted sections by importance (already sorted by relevance score)
        for i, section in enumerate(extracted_sections):
            section['importance_rank'] = i + 1
        
        # Create output structure
        output_data = {
            "metadata": {
                "input_documents": [doc['filename'] for doc in documents],
                "persona": persona,
                "job_to_be_done": task,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": extracted_sections[:10],  # Limit to top 10
            "subsection_analysis": subsection_analysis[:10]  # Limit to top 10
        }
        
        return output_data
    
    def save_output(self, output_data: Dict[str, Any], output_path: str):
        """Save output data to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=4)
        logger.info(f"Output saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Multi-Collection PDF Analysis Tool')
    parser.add_argument('--collection', type=str, help='Path to specific collection to process')
    parser.add_argument('--all', action='store_true', help='Process all collections')
    parser.add_argument('--base-dir', type=str, default='.', help='Base directory containing collections')
    
    args = parser.parse_args()
    
    analyzer = PDFAnalyzer()
    
    if args.collection:
        # Process specific collection
        output_data = analyzer.process_collection(args.collection)
        if output_data:
            output_path = os.path.join(args.collection, 'challenge1b_output.json')
            analyzer.save_output(output_data, output_path)
    
    elif args.all:
        # Process all collections
        base_dir = args.base_dir
        collections = ['Collection 1', 'Collection 2', 'Collection 3']
        
        for collection in collections:
            collection_path = os.path.join(base_dir, collection)
            if os.path.exists(collection_path):
                output_data = analyzer.process_collection(collection_path)
                if output_data:
                    output_path = os.path.join(collection_path, 'challenge1b_output.json')
                    analyzer.save_output(output_data, output_path)
            else:
                logger.warning(f"Collection not found: {collection_path}")
    
    else:
        print("Please specify --collection <path> or --all")
        sys.exit(1)

if __name__ == "__main__":
    main()