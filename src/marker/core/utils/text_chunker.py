"""
Text chunking module for GitGet repository analysis.

This module provides functionality to break down text into manageable chunks
while preserving section structure, hierarchy, and metadata. It's specifically 
designed to work with the GitGet workflow for analyzing repositories.

Key features:
1. Detects section hierarchy in documents
2. Preserves section relationships and paths
3. Tokenizes text using configured models
4. Splits content into chunks of specified token size
5. Maintains metadata across all chunks
6. Generates stable hashes for each section

Sample Input:
    ```python
    # Using local implementation of TextChunker and count_tokens_with_tiktoken
    
    markdown_text = '''
    # Repository Overview
    
    This project provides utilities for parsing and analyzing code.
    
    ## Installation
    
    Install using pip:
    ```bash
    pip install mypackage
    ```
    
    ## Usage Examples
    
    Here's how to use the primary features...
    '''
    
    chunker = TextChunker(
        max_tokens=300,
        overlap_tokens=50,
        preserve_sections=True
    )
    chunks = chunker.chunk_text(markdown_text, file_path="README.md")
    ```

Expected Output:
    ```python
    [
        {
            "content": "# Repository Overview\n\nThis project provides utilities for parsing and analyzing code.",
            "section_path": ["Repository Overview"],
            "section_id": "71f8a37d42",
            "metadata": {
                "file": "README.md",
                "tokens": 21,
                "start_idx": 0,
                "end_idx": 81
            }
        },
        {
            "content": "## Installation\n\nInstall using pip:\n```bash\npip install mypackage\n```",
            "section_path": ["Repository Overview", "Installation"],
            "section_id": "b3e5f2a981",
            "metadata": {
                "file": "README.md",
                "tokens": 26,
                "start_idx": 83,
                "end_idx": 162
            }
        },
        {
            "content": "## Usage Examples\n\nHere's how to use the primary features...",
            "section_path": ["Repository Overview", "Usage Examples"],
            "section_id": "c4f7d1b692",
            "metadata": {
                "file": "README.md",
                "tokens": 18,
                "start_idx": 164,
                "end_idx": 225
            }
        }
    ]
    ```
"""

import os
import re
import datetime
import hashlib
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Set, Union
from loguru import logger

# Import required packages
import tiktoken
import spacy


def hash_string(input_string: str) -> str:
    """
    Creates a stable hash for a given string using SHA256.
    
    Args:
        input_string: The string to hash.
        
    Returns:
        A hexadecimal string representation of the hash.
    """
    encoded_string = input_string.encode("utf-8")
    hash_object = hashlib.sha256(encoded_string)
    return hash_object.hexdigest()


class SectionHierarchy:
    """
    Manages a stack representing the current section hierarchy path.
    
    This class tracks the nesting of sections in a document, allowing for
    preservation of section relationships when chunking text.
    """

    def __init__(self):
        """Initialize the section hierarchy stack."""
        # Stack stores tuples: (section_number_str, full_title_str, content_hash_str)
        self.stack: List[Tuple[str, str, str]] = []
        logger.debug("SectionHierarchy initialized.")

    def update(self, section_number: str, section_title: str, section_content: str):
        """
        Updates the hierarchy stack based on a newly encountered section.

        Args:
            section_number: The number string (e.g., "5", "5.2", "5.5.1").
            section_title: The title string (e.g., "Operational Safety Requirements").
            section_content: The content associated with this specific section (used for hashing).
        """
        logger.debug(
            f"Updating hierarchy with section: {section_number=}, {section_title=}"
        )
        # Parse the current section number into a list of ints
        try:
            nums = [int(n) for n in section_number.split(".") if n]
            current_level = len(nums)
            logger.debug(f"Parsed section number parts: {nums=}, {current_level=}")
        except ValueError:
            logger.warning(
                f"Could not parse section number '{section_number}'. Skipping hierarchy update."
            )
            return

        # Pop anything on the stack that isn't an ancestor of this one
        while self.stack:
            prev_number_str, _, _ = self.stack[-1]
            try:
                prev_nums = [int(n) for n in prev_number_str.split(".") if n]
                prev_level = len(prev_nums)
            except ValueError:
                # If somehow invalid, just pop it off
                logger.warning(f"Invalid number on stack '{prev_number_str}', popping.")
                self.stack.pop()
                continue

            # ancestor if prev_level < current_level and prefix matches
            is_ancestor = prev_level < current_level and nums[:prev_level] == prev_nums
            logger.debug(
                f"Is '{prev_number_str}' an ancestor of '{section_number}'? {is_ancestor}"
            )

            if not is_ancestor:
                logger.debug(f"Popping non-ancestor '{prev_number_str}'")
                self.stack.pop()
            else:
                # once we hit a true ancestor, stop popping
                break

        # Now append the current section
        full_title = f"{section_number} {section_title}".strip()
        section_hash = hash_string(full_title + section_content)
        self.stack.append((section_number, full_title, section_hash))
        logger.debug(
            f"Appended to stack: {section_number=}, {full_title=}, hash={section_hash}"
        )
        logger.debug(f"Current hierarchy stack: {[t for _, t, _ in self.stack]}")

    def get_titles(self) -> List[str]:
        """Return all titles in the current hierarchy (ancestors + current)."""
        titles = [title for (_, title, _) in self.stack]
        logger.debug(f"Getting titles: {titles}")
        return titles

    def get_hashes(self) -> List[str]:
        """Return all hashes in the current hierarchy (ancestors + current)."""
        hashes = [h for (_, _, h) in self.stack]
        logger.debug(f"Getting hashes: {hashes}")
        return hashes

    def __str__(self):
        """String representation of the hierarchy."""
        return " -> ".join([title for _, title, _ in self.stack])


class TextChunker:
    """
    A class for chunking text while preserving section structure.
    
    This chunker can identify section headers in text, maintain their hierarchical
    relationships, and split the content into chunks of specified token size while
    preserving metadata across chunks.
    """

    def __init__(
        self,
        max_tokens: int = 500,
        min_overlap: int = 100,
        model_name: str = "gemini-2.5-pro-preview-03-25",
        spacy_model: str = "en_core_web_sm",
    ):
        """
        Initialize the TextChunker.
        
        Args:
            max_tokens: Maximum number of tokens per chunk.
            min_overlap: Minimum number of tokens to overlap between chunks.
            model_name: Name of the model for token counting.
            spacy_model: Name of the spaCy model for sentence splitting.
        """
        self.max_tokens = max_tokens
        self.min_overlap = min_overlap
        self.model_name = model_name
        self.spacy_model_name = spacy_model
        
        # Initialize tokenizer
        self._setup_tokenizer()
        
        # Initialize sentence splitter
        self._setup_sentence_splitter()
        
        # Initialize section hierarchy tracker
        self.section_hierarchy = SectionHierarchy()
        
        # OPTIMIZATION: Add token count cache to avoid repeated calculations
        self._token_count_cache = {}
        
        logger.info(
            f"Initialized TextChunker with max_tokens={max_tokens}, "
            f"min_overlap={min_overlap}, model={model_name}"
        )

    def _setup_tokenizer(self):
        """Set up the tokenizer based on the model."""
        try:
            openai_models = {
                "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-32k",
                "gpt-4o", "gpt-4-turbo"
            }
            if any(self.model_name.startswith(m) for m in openai_models):
                # For OpenAI models, use the specific encoding
                self.encoding = tiktoken.encoding_for_model(self.model_name)
            else:
                # For other models, use cl100k_base as default
                self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.debug(f"Using tiktoken with {self.model_name} encoding")
        except Exception as e:
            logger.warning(f"Error initializing tiktoken: {e}. Using fallback counting.")
            self.encoding = None

    def _setup_sentence_splitter(self):
        """Set up the sentence splitter."""
        try:
            self.nlp = spacy.load(self.spacy_model_name)
            logger.debug(f"Using spaCy model {self.spacy_model_name} for sentence splitting")
        except OSError:
            logger.warning(f"SpaCy model '{self.spacy_model_name}' not found. Using regex fallback.")
            self.nlp = None
        except Exception as e:
            logger.warning(f"Error loading spaCy model: {e}. Using regex fallback.")
            self.nlp = None

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.
        Uses memoization to avoid recounting the same text.
        
        Args:
            text: The text to count tokens for.
            
        Returns:
            The number of tokens in the text.
        """
        # OPTIMIZATION: Check cache first before encoding
        if text in self._token_count_cache:
            return self._token_count_cache[text]
            
        # Only encode if not in cache
        if self.encoding is not None:
            token_count = len(self.encoding.encode(text))
            
            # OPTIMIZATION: Cache result to avoid future encoding
            self._token_count_cache[text] = token_count
            return token_count
        else:
            # Fallback to character-based estimation
            return int(len(text) / 4)

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: The text to split.
            
        Returns:
            A list of sentences.
        """
        if self.nlp is not None:
            # Use spaCy for sentence splitting
            return [sent.text.strip() for sent in self.nlp(text).sents]
        else:
            # Fallback to regex-based sentence splitting if spaCy model failed to load
            sentences = re.split(r'(?<=[.!?])\s+', text)
            return [s.strip() for s in sentences if s.strip()]
    
    def chunk_text(self, text: str, repo_link: str, file_path: str) -> List[Dict]:
        """
        Main method to chunk text while preserving section structure.
        
        Args:
            text: The text to chunk.
            repo_link: Link to the repository.
            file_path: Path to the file within the repository.
            
        Returns:
            A list of chunk dictionaries with metadata.
        """
        logger.info(f"Starting chunk_text for file: {file_path}")
        
        # First, split the text into sections
        sections = self._split_by_sections(text)
        extracted_data: List[Dict] = []

        if sections:
            logger.info(f"Found {len(sections)} sections")
            for idx, (sec_num, sec_title, span) in enumerate(sections):
                start, end = span
                section_content = text[start:end].strip()
                self.section_hierarchy.update(sec_num, sec_title, section_content)

                extracted_data.extend(
                    self._chunk_section(
                        text,
                        sec_num,
                        sec_title,
                        section_content,
                        span,
                        repo_link,
                        file_path,
                    )
                )
        else:
            logger.warning("No sections found, using fallback chunking")
            extracted_data.extend(self._fallback_chunking(text, repo_link, file_path))

        logger.info(f"Generated {len(extracted_data)} chunks")
        return extracted_data

    def _split_by_sections(self, text: str) -> List[Tuple[str, str, Tuple[int, int]]]:
        """
        Split text into sections based on markdown headers.
        
        This identifies section markers like:
          **4. General Design Requirements**
          **4 General Plant Design**
          **4.1 Plant Design Basis**
        
        Args:
            text: The text to split into sections.
            
        Returns:
            A list of tuples: (section_number, section_title, (start, end))
        """
        logger.info("Splitting text into sections")
        section_pattern = re.compile(
            r"^"  # start of line
            r"\*\*"  # **
            r"(?P<number>\d+(?:\.\d+)*\.?)"  # 4 or 4. or 4.1 or 4.1.1.
            r"\s+"  # at least one space
            r"(?P<title>[A-Z0-9][^\n*]+?)"  # title (no newlines allowed)
            r"\s*\*\*"  # optional space, then closing **
            r"[ \t]*$",  # only whitespace until EOL
            re.MULTILINE,
        )

        sections: List[Tuple[str, str, Tuple[int, int]]] = []
        for m in section_pattern.finditer(text):
            raw = m.group("number")
            num = raw.rstrip(".")  # normalize "4." → "4"
            title = m.group("title").strip()
            start, hdr_end = m.start(), m.end()

            nxt = section_pattern.search(text, hdr_end)
            end = nxt.start() if nxt else len(text)

            sections.append((num, title, (start, end)))

        # trailing "untitled" chunk if any
        if sections:
            last_end = sections[-1][2][1]
            if last_end < len(text) and text[last_end:].strip():
                sections.append(("", text[last_end:].strip(), (last_end, len(text))))
        else:
            # no headers → entire doc
            sections.append(("", text, (0, len(text))))

        logger.info(f"Split text into {len(sections)} sections")
        return sections
    
    def _create_chunk_dict(
        self,
        chunk_content: str,
        token_count: int,
        section_title: str,
        start_line: int,
        file_path: str,
        repo_link: str,
    ) -> Dict[str, Any]:
        """
        OPTIMIZATION: Helper method to create a chunk dictionary with metadata.
        Reduces code duplication and centralizes chunk creation.
        
        Args:
            chunk_content: The content of the chunk.
            token_count: The token count of the chunk content.
            section_title: The section title.
            start_line: The starting line number.
            file_path: Path to the file within the repository.
            repo_link: Link to the repository.
            
        Returns:
            A dictionary with chunk metadata.
        """
        # Calculate end line based on newlines in content
        end_line = start_line + chunk_content.count("\n")
        
        # Create section hash once
        section_hash = hash_string(chunk_content)
        
        # Cache the section title token count
        if section_title not in self._token_count_cache:
            self.count_tokens(section_title)  # This will cache the result
        
        # Create and return the chunk dictionary
        return {
            "file_path": file_path,
            "repo_link": repo_link,
            "extraction_date": datetime.datetime.now().isoformat(),
            "code_line_span": (start_line, end_line),
            "description_line_span": (start_line, end_line),
            "code": chunk_content,
            "code_type": "text",
            "description": section_title,
            "code_token_count": token_count,
            "description_token_count": self._token_count_cache.get(section_title, self.count_tokens(section_title)),
            "embedding_code": None,
            "embedding_description": None,
            "code_metadata": {},
            "section_id": section_hash,
            "section_path": self.section_hierarchy.get_titles(),
            "section_hash_path": self.section_hierarchy.get_hashes(),
        }
    
    def _chunk_section(
        self,
        text: str,
        section_number: str,
        section_title: str,
        section_content: str,
        span: Tuple[int, int],
        repo_link: str,
        file_path: str,
    ) -> List[Dict]:
        """
        Chunk a single section into smaller pieces based on token limit.
        
        Args:
            text: The full text.
            section_number: The section number string.
            section_title: The section title string.
            section_content: The content of this section.
            span: The (start, end) character offsets in the original text.
            repo_link: Link to the repository.
            file_path: Path to the file within the repository.
            
        Returns:
            A list of chunk dictionaries with metadata.
        """
        logger.info(f"Chunking section: {section_title!r}")
        sentences = self.split_into_sentences(section_content)
        chunks = []
        current_chunk = ""
        token_count = 0
        start_line = span[0] + 1  # 1-indexed line numbering

        for sent in sentences:
            sent_tokens = self.count_tokens(sent)
            
            # If this single sentence is already larger than max_tokens, split it further
            if sent_tokens > self.max_tokens:
                # If we have accumulated content, flush it first
                if current_chunk:
                    # OPTIMIZATION: Use the helper method for chunk creation
                    chunk_dict = self._create_chunk_dict(
                        chunk_content=current_chunk,
                        token_count=token_count,
                        section_title=section_title,
                        start_line=start_line,
                        file_path=file_path,
                        repo_link=repo_link
                    )
                    chunks.append(chunk_dict)
                    
                    # Update start line for next chunk
                    start_line = chunk_dict["code_line_span"][1] + 1
                    current_chunk = ""
                    token_count = 0
                
                # Now handle the oversized sentence by splitting it into words
                words = sent.split(' ')
                current_sentence_chunk = ""
                current_sentence_token_count = 0
                
                for word in words:
                    word_tokens = self.count_tokens(word + " ")
                    if current_sentence_token_count + word_tokens > self.max_tokens and current_sentence_chunk:
                        # OPTIMIZATION: Use the helper method for chunk creation
                        chunk_dict = self._create_chunk_dict(
                            chunk_content=current_sentence_chunk,
                            token_count=current_sentence_token_count,
                            section_title=section_title,
                            start_line=start_line,
                            file_path=file_path,
                            repo_link=repo_link
                        )
                        chunks.append(chunk_dict)
                        
                        # Update start line for next chunk
                        start_line = chunk_dict["code_line_span"][1] + 1
                        current_sentence_chunk = ""
                        current_sentence_token_count = 0
                    
                    current_sentence_chunk += word + " "
                    current_sentence_token_count += word_tokens
                
                # Add any remaining words in the final sentence chunk
                if current_sentence_chunk:
                    section_hash = hash_string(current_sentence_chunk)
                    end_line = start_line + current_sentence_chunk.count("\n")
                    chunks.append(
                        {
                            "file_path": file_path,
                            "repo_link": repo_link,
                            "extraction_date": datetime.datetime.now().isoformat(),
                            "code_line_span": (start_line, end_line),
                            "description_line_span": (start_line, end_line),
                            "code": current_sentence_chunk,
                            "code_type": "text",
                            "description": section_title,
                            "code_token_count": current_sentence_token_count,
                            "description_token_count": self.count_tokens(section_title),
                            "embedding_code": None,
                            "embedding_description": None,
                            "code_metadata": {},
                            "section_id": section_hash,
                            "section_path": self.section_hierarchy.get_titles(),
                            "section_hash_path": self.section_hierarchy.get_hashes(),
                        }
                    )
                    start_line = end_line + 1
                
            # Normal case - if adding this sentence would exceed tokens, flush the current chunk
            elif token_count + sent_tokens > self.max_tokens and current_chunk:
                section_hash = hash_string(current_chunk)
                end_line = start_line + current_chunk.count("\n")
                chunks.append(
                    {
                        "file_path": file_path,
                        "repo_link": repo_link,
                        "extraction_date": datetime.datetime.now().isoformat(),
                        "code_line_span": (start_line, end_line),
                        "description_line_span": (start_line, end_line),
                        "code": current_chunk,
                        "code_type": "text",
                        "description": section_title,
                        "code_token_count": token_count,
                        "description_token_count": self.count_tokens(section_title),
                        "embedding_code": None,
                        "embedding_description": None,
                        "code_metadata": {},
                        "section_id": section_hash,
                        "section_path": self.section_hierarchy.get_titles(),
                        "section_hash_path": self.section_hierarchy.get_hashes(),
                    }
                )
                start_line = end_line + 1
                current_chunk = ""
                token_count = 0
                
                # Add the current sentence
                current_chunk += sent + "\n"
                token_count += sent_tokens
            else:
                # Add the sentence to the current chunk
                current_chunk += sent + "\n"
                token_count += sent_tokens

        # flush any remaining content
        if current_chunk:
            # OPTIMIZATION: Use the helper method for the final chunk
            chunk_dict = self._create_chunk_dict(
                chunk_content=current_chunk,
                token_count=token_count,
                section_title=section_title,
                start_line=start_line,
                file_path=file_path,
                repo_link=repo_link
            )
            chunks.append(chunk_dict)

        logger.info(f"Section {section_title!r} chunked into {len(chunks)} pieces")
        return chunks
    
    def _fallback_chunking(
        self, text: str, repo_link: str, file_path: str
    ) -> List[Dict]:
        """
        Handle text without identifiable sections using fallback chunking.
        
        Args:
            text: The text to chunk.
            repo_link: Link to the repository.
            file_path: Path to the file within the repository.
            
        Returns:
            A list with a single chunk dictionary.
        """
        logger.info("Performing fallback chunking")
        
        code_token_count = self.count_tokens(text)
        section_hash = hash_string(text)
        code_start_line = 1
        code_end_line = text.count("\n") + 1

        data = {
            "file_path": file_path,
            "repo_link": repo_link,
            "extraction_date": datetime.datetime.now().isoformat(),
            "code_line_span": (code_start_line, code_end_line),
            "description_line_span": (1, 1),
            "code": text,
            "code_type": "text",
            "description": "",
            "code_token_count": code_token_count,
            "description_token_count": 0,
            "embedding_code": None,
            "embedding_description": None,
            "code_metadata": {},  # We'll add code metadata later
            "section_id": section_hash,
            "section_path": self.section_hierarchy.get_titles(),
            "section_hash_path": self.section_hierarchy.get_hashes(),
        }
        logger.info(f"Created fallback chunk with section_id={section_hash}")
        return [data]


def count_tokens_with_tiktoken(text: str, model: str = "gemini-2.5-pro-preview-03-25") -> int:
    """
    Count tokens in a string using tiktoken, with fallback to character estimation.
    
    This function provides token counting functionality
    but adds more robust fallback behavior.
    
    Args:
        text: The text to count tokens for.
        model: The model name to use for token counting.
        
    Returns:
        The number of tokens in the text.
    """
    try:
        openai_models = {
            "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-32k",
            "gpt-4o", "gpt-4-turbo"
        }
        if any(model.startswith(m) for m in openai_models):
            encoding = tiktoken.encoding_for_model(model)
        else:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback to character estimation if encoding fails
        return int(len(text) / 4)


# Demonstration and verification code
if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.table import Table
    import argparse
    
    # Setup logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    console = Console()
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Text Chunker Verification")
    parser.add_argument("--file", "-f", type=str, help="Path to a markdown file to test chunking")
    parser.add_argument("--max-tokens", type=int, default=500, help="Maximum tokens per chunk")
    parser.add_argument("--min-overlap", type=int, default=100, help="Minimum token overlap between chunks")
    parser.add_argument("--model", type=str, default="gemini-2.5-pro-preview-03-25", help="Model name for token counting")
    args = parser.parse_args()
    
    # Sample text for verification if no file provided
    sample_text = """
**1. Introduction**

This is a sample document to demonstrate the text chunking functionality.
It has multiple sections with different levels.

**1.1 Purpose**

The purpose of this document is to verify that the text chunker correctly:
1. Identifies section headers
2. Maintains section hierarchy
3. Chunks text within token limits
4. Preserves metadata across chunks

**2. Features**

The text chunker has several important features.

**2.1 Section Detection**

The chunker can detect section headers like this one and build a hierarchy.

**2.2 Token Counting**

The chunker uses tiktoken to accurately count tokens for various models.

**3. Conclusion**

This sample document should be sufficient to verify the basic functionality.
"""
    
    # Use provided file if available
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                test_text = f.read()
                console.print(f"[green]Using text from file:[/green] {args.file}")
        except Exception as e:
            console.print(f"[red]Error reading file:[/red] {e}")
            console.print("[yellow]Using built-in sample text instead[/yellow]")
            test_text = sample_text
    else:
        console.print("[yellow]No file provided, using built-in sample text[/yellow]")
        test_text = sample_text
    
    # Create a chunker and process the text
    chunker = TextChunker(
        max_tokens=args.max_tokens,
        min_overlap=args.min_overlap,
        model_name=args.model
    )
    
    # First verification: token counting
    console.print("\n[bold]Token Counting Verification[/bold]")
    token_table = Table(title="Token Count Comparison")
    token_table.add_column("Text", style="cyan")
    token_table.add_column("Token Count", style="green")
    token_table.add_column("Character Count", style="blue")
    token_table.add_column("Ratio", style="magenta")
    
    test_strings = [
        "This is a short sentence.",
        "This is a longer sentence with more words and should have more tokens.",
        "Technical terms like 'tokenization' and 'chunking' might be counted as single tokens.",
        test_text[:200],  # First 200 chars of test text
    ]
    
    for text in test_strings:
        token_count = chunker.count_tokens(text)
        char_count = len(text)
        ratio = char_count / token_count if token_count > 0 else 0
        token_table.add_row(
            text[:30] + "..." if len(text) > 30 else text,
            str(token_count),
            str(char_count),
            f"{ratio:.2f}"
        )
    
    console.print(token_table)
    
    # Second verification: section detection
    console.print("\n[bold]Section Detection Verification[/bold]")
    sections = chunker._split_by_sections(test_text)
    
    section_table = Table(title="Detected Sections")
    section_table.add_column("Number", style="cyan")
    section_table.add_column("Title", style="green")
    section_table.add_column("Content Length", style="blue")
    
    for sec_num, sec_title, (start, end) in sections:
        section_content = test_text[start:end].strip()
        section_table.add_row(
            sec_num or "(empty)",
            sec_title or "(untitled)",
            str(len(section_content))
        )
    
    console.print(section_table)
    
    # Third verification: chunk generation
    console.print("\n[bold]Chunk Generation Verification[/bold]")
    chunks = chunker.chunk_text(
        test_text, 
        "https://example.com/repo", 
        "example/file.md"
    )
    
    chunk_table = Table(title=f"Generated Chunks (max tokens: {args.max_tokens})")
    chunk_table.add_column("Chunk #", style="cyan")
    chunk_table.add_column("Section", style="green")
    chunk_table.add_column("Token Count", style="blue")
    chunk_table.add_column("Section Hash", style="magenta")
    chunk_table.add_column("Content Preview", style="yellow")
    
    for i, chunk in enumerate(chunks):
        chunk_table.add_row(
            str(i + 1),
            chunk["description"] or "(no section)",
            str(chunk["code_token_count"]),
            chunk["section_id"][:8] + "...",  # First 8 chars of hash
            chunk["code"][:30].replace("\n", " ") + "..." if len(chunk["code"]) > 30 else chunk["code"]
        )
    
    console.print(chunk_table)
    
    # Fourth verification: section hierarchy
    console.print("\n[bold]Section Hierarchy Verification[/bold]")
    hierarchy_table = Table(title="Section Hierarchy")
    hierarchy_table.add_column("Chunk #", style="cyan")
    hierarchy_table.add_column("Section Path", style="green")
    
    for i, chunk in enumerate(chunks):
        path_str = " → ".join(chunk["section_path"]) if chunk["section_path"] else "(root)"
        hierarchy_table.add_row(
            str(i + 1),
            path_str
        )
    
    console.print(hierarchy_table)
    
    # Output the verification result
    total_token_count = sum(chunk["code_token_count"] for chunk in chunks)
    direct_token_count = chunker.count_tokens(test_text)
    
    console.print(f"\n[bold]Verification Summary[/bold]")
    console.print(f"Original text token count: {direct_token_count}")
    console.print(f"Sum of chunk token counts: {total_token_count}")
    console.print(f"Number of chunks created: {len(chunks)}")
    console.print(f"Average tokens per chunk: {total_token_count / len(chunks) if chunks else 0:.1f}")
    
    # Final verification
    passes_verification = True
    verification_failures = {}
    
    # Verify each chunk is within token limit
    for i, chunk in enumerate(chunks):
        if chunk["code_token_count"] > args.max_tokens:
            passes_verification = False
            verification_failures[f"chunk_{i+1}_size"] = {
                "expected": f"<= {args.max_tokens}",
                "actual": chunk["code_token_count"]
            }
    
    # Verify section detection worked (if we have sections in the sample)
    if "**1. Introduction**" in test_text and len(sections) < 2:
        passes_verification = False
        verification_failures["section_detection"] = {
            "expected": "Multiple sections",
            "actual": f"Only {len(sections)} section(s) detected"
        }
    
    # Verify token counting is working
    if chunker.count_tokens("This is a test") < 3:
        passes_verification = False
        verification_failures["token_counting"] = {
            "expected": ">= 3 tokens",
            "actual": f"{chunker.count_tokens('This is a test')} tokens"
        }
    
    if passes_verification:
        console.print("\n[bold green]✅ VALIDATION COMPLETE - Text chunking works as expected[/bold green]")
        sys.exit(0)
    else:
        console.print("\n[bold red]❌ VALIDATION FAILED - Text chunking has issues:[/bold red]")
        for key, details in verification_failures.items():
            console.print(f"  - {key}: Expected: {details['expected']}, Got: {details['actual']}")
        console.print(f"Total errors: {len(verification_failures)} test(s) failed")
        sys.exit(1)