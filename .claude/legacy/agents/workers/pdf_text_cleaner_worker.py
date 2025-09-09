#!/usr/bin/env python3
"""
PDF Text Cleaner Worker

Cleans and normalizes extracted text, fixing common PDF extraction issues.
Handles ligatures, encoding problems, hyphenation, and spacing issues.
"""

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import json
import asyncio

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from ftfy import fix_text

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Clean and normalize PDF extracted text")
console = Console()


class PDFTextCleaner:
    """Cleans common PDF text extraction issues."""
    
    def __init__(self):
        # Common ligature mappings
        self.ligature_map = {
            'ﬁ': 'fi',
            'ﬂ': 'fl',
            'ﬀ': 'ff',
            'ﬃ': 'ffi',
            'ﬄ': 'ffl',
            'ﬅ': 'ft',
            'ﬆ': 'st',
            'æ': 'ae',
            'œ': 'oe',
            'Æ': 'AE',
            'Œ': 'OE'
        }
        
        # Quote normalization
        self.quote_map = {
            '"': '"',  # Left double quote
            '"': '"',  # Right double quote
            ''': "'",  # Left single quote
            ''': "'",  # Right single quote
            '„': '"',  # German quote
            '‚': "'",  # German single quote
            '«': '"',  # French quote
            '»': '"',  # French quote
            '‹': "'",  # Single French quote
            '›': "'",  # Single French quote
        }
        
        # Dash normalization
        self.dash_map = {
            '–': '-',  # En dash to hyphen (for ranges, keep as is)
            '—': '—',  # Em dash (keep for emphasis)
            '−': '-',  # Minus sign to hyphen
            '‐': '-',  # Hyphen
            '‑': '-',  # Non-breaking hyphen
        }
        
        # Invisible characters to remove
        self.invisible_chars = {
            '\u200b',  # Zero-width space
            '\u200c',  # Zero-width non-joiner
            '\u200d',  # Zero-width joiner
            '\ufeff',  # Zero-width no-break space
            '\u00ad',  # Soft hyphen
        }
    
    async def clean_text(self,
                        text: str,
                        fix_ligatures: bool = True,
                        fix_quotes: bool = True,
                        fix_encoding: bool = True,
                        fix_hyphenation: bool = True,
                        fix_spacing: bool = True,
                        remove_invisible: bool = True) -> str:
        """Clean text with configurable options."""
        
        if not text:
            return text
        
        # Fix encoding issues first
        if fix_encoding:
            text = fix_text(text)
        
        # Remove invisible characters
        if remove_invisible:
            for char in self.invisible_chars:
                text = text.replace(char, '')
        
        # Fix ligatures
        if fix_ligatures:
            for ligature, replacement in self.ligature_map.items():
                text = text.replace(ligature, replacement)
        
        # Normalize quotes
        if fix_quotes:
            for smart, straight in self.quote_map.items():
                text = text.replace(smart, straight)
        
        # Fix hyphenation
        if fix_hyphenation:
            text = self._fix_hyphenation(text)
        
        # Fix spacing
        if fix_spacing:
            text = self._fix_spacing(text)
        
        # Normalize unicode
        text = unicodedata.normalize('NFC', text)
        
        return text
    
    def _fix_hyphenation(self, text: str) -> str:
        """Fix words split across lines."""
        # Pattern: word-\n followed by lowercase letter
        hyphen_pattern = r'(\w+)-\n([a-z])'
        
        def hyphen_replacer(match):
            part1 = match.group(1)
            part2 = match.group(2)
            
            # Check if it's likely a compound word or split word
            # If part1 ends with common prefixes, keep hyphen
            keep_hyphen_prefixes = ('anti', 'co', 'de', 'dis', 'ex', 'inter', 
                                   'mid', 'non', 'over', 'pre', 'pro', 're', 
                                   'semi', 'sub', 'super', 'trans', 'ultra', 'un')
            
            if part1.lower().endswith(keep_hyphen_prefixes):
                return f"{part1}-{part2}"
            else:
                return f"{part1}{part2}"
        
        text = re.sub(hyphen_pattern, hyphen_replacer, text)
        return text
    
    def _fix_spacing(self, text: str) -> str:
        """Fix various spacing issues."""
        # Fix expanded spacing (T h i s)
        expanded_pattern = r'\b(\w)\s+(\w)\s+(\w)\s+(\w)'
        
        def check_expanded(match):
            chars = [match.group(i) for i in range(1, 5)]
            # If all single characters, likely expanded
            if all(len(c) == 1 for c in chars):
                return ''.join(chars)
            return match.group(0)
        
        text = re.sub(expanded_pattern, check_expanded, text)
        
        # Fix multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Fix space before punctuation
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        
        # Fix missing space after punctuation
        text = re.sub(r'([,.!?;:])([A-Za-z])', r'\1 \2', text)
        
        return text
    
    async def clean_blocks(self, blocks: List[Dict], options: Optional[Dict] = None) -> List[Dict]:
        """Clean text in multiple blocks."""
        if options is None:
            options = {}
        
        cleaned_blocks = []
        for block in blocks:
            cleaned_block = block.copy()
            
            # Clean main text
            if 'text' in block and block['text']:
                cleaned_block['text'] = await self.clean_text(
                    block['text'],
                    **options
                )
            
            # Clean spans if present
            if 'spans' in block:
                cleaned_spans = []
                for span in block['spans']:
                    cleaned_span = span.copy()
                    if 'text' in span:
                        cleaned_span['text'] = await self.clean_text(
                            span['text'],
                            **options
                        )
                    cleaned_spans.append(cleaned_span)
                cleaned_block['spans'] = cleaned_spans
            
            cleaned_blocks.append(cleaned_block)
        
        return cleaned_blocks
    
    def analyze_text_issues(self, text: str) -> Dict:
        """Analyze text for common issues."""
        issues = {
            'ligatures': 0,
            'smart_quotes': 0,
            'encoding_issues': 0,
            'hyphenation': 0,
            'expanded_spacing': 0,
            'invisible_chars': 0,
            'total_chars': len(text)
        }
        
        # Count ligatures
        for ligature in self.ligature_map:
            issues['ligatures'] += text.count(ligature)
        
        # Count smart quotes
        for quote in self.quote_map:
            issues['smart_quotes'] += text.count(quote)
        
        # Check encoding issues
        if text != fix_text(text):
            issues['encoding_issues'] = 1
        
        # Count hyphenation
        issues['hyphenation'] = len(re.findall(r'\w+-\n\w', text))
        
        # Check expanded spacing
        issues['expanded_spacing'] = len(re.findall(r'\b\w\s+\w\s+\w\s+\w', text))
        
        # Count invisible characters
        for char in self.invisible_chars:
            issues['invisible_chars'] += text.count(char)
        
        return issues


# Initialize cleaner
cleaner = PDFTextCleaner()


@app.command("clean")
def clean(
    input_file: Path = typer.Argument(..., help="Text file or JSON with blocks to clean"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    analyze_only: bool = typer.Option(False, "--analyze", "-a", help="Only analyze, don't clean"),
    fix_ligatures: bool = typer.Option(True, "--fix-ligatures/--no-fix-ligatures"),
    fix_quotes: bool = typer.Option(True, "--fix-quotes/--no-fix-quotes"),
    fix_encoding: bool = typer.Option(True, "--fix-encoding/--no-fix-encoding"),
    fix_hyphenation: bool = typer.Option(True, "--fix-hyphenation/--no-fix-hyphenation"),
    fix_spacing: bool = typer.Option(True, "--fix-spacing/--no-fix-spacing")
):
    """Clean PDF extracted text."""
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load input
        if input_file.suffix == '.json':
            with open(input_file) as f:
                data = json.load(f)
                if isinstance(data, list):
                    blocks = data
                else:
                    blocks = data.get('blocks', [])
                    text = None
        else:
            with open(input_file, 'r', encoding='utf-8') as f:
                text = f.read()
                blocks = None
        
        if analyze_only:
            # Analyze issues
            if text:
                issues = cleaner.analyze_text_issues(text)
            else:
                # Analyze all blocks
                all_text = ' '.join(b.get('text', '') for b in blocks)
                issues = cleaner.analyze_text_issues(all_text)
            
            # Display analysis
            table = Table(title="Text Issues Analysis")
            table.add_column("Issue Type", style="cyan")
            table.add_column("Count", style="yellow")
            table.add_column("Percentage", style="green")
            
            total = issues['total_chars']
            for issue_type, count in issues.items():
                if issue_type != 'total_chars' and count > 0:
                    pct = (count / total * 100) if total > 0 else 0
                    table.add_row(issue_type.replace('_', ' ').title(), str(count), f"{pct:.2f}%")
            
            console.print(table)
            return
        
        # Clean text
        options = {
            'fix_ligatures': fix_ligatures,
            'fix_quotes': fix_quotes,
            'fix_encoding': fix_encoding,
            'fix_hyphenation': fix_hyphenation,
            'fix_spacing': fix_spacing
        }
        
        with console.status("Cleaning text..."):
            if text:
                cleaned = await cleaner.clean_text(text, **options)
            else:
                cleaned_blocks = await cleaner.clean_blocks(blocks, options)
                cleaned = cleaned_blocks
        
        # Save output
        if output:
            if isinstance(cleaned, str):
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(cleaned)
            else:
                with open(output, 'w') as f:
                    json.dump(cleaned, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓ Cleaned text saved to {output}[/green]")
        else:
            # Display sample
            if isinstance(cleaned, str):
                console.print("\n[bold]Cleaned text (first 500 chars):[/bold]")
                console.print(cleaned[:500] + "..." if len(cleaned) > 500 else cleaned)
            else:
                console.print(f"\n[bold]Cleaned {len(cleaned)} blocks[/bold]")
    
    asyncio.run(run())


@app.command("compare")
def compare(
    original: Path = typer.Argument(..., help="Original text file"),
    cleaned: Path = typer.Argument(..., help="Cleaned text file")
):
    """Compare original and cleaned text."""
    with open(original, 'r', encoding='utf-8') as f:
        orig_text = f.read()
    
    with open(cleaned, 'r', encoding='utf-8') as f:
        clean_text = f.read()
    
    # Show differences
    import difflib
    differ = difflib.unified_diff(
        orig_text.splitlines(keepends=True),
        clean_text.splitlines(keepends=True),
        fromfile='original',
        tofile='cleaned',
        n=3
    )
    
    console.print("\n[bold]Text differences:[/bold]")
    for line in differ:
        if line.startswith('+'):
            console.print(line, style="green", end='')
        elif line.startswith('-'):
            console.print(line, style="red", end='')
        else:
            console.print(line, end='')


# Worker functions
async def working_usage():
    """Demonstrate text cleaning capabilities."""
    logger.info("Testing PDF text cleaning...")
    
    # Sample text with common issues
    test_text = """
    The ﬁrst algorithm shows efﬁcient perfor-
    mance. "Smart quotes" and 'apostrophes' need fixing.
    
    T h i s  t e x t  i s  s p a c e d  o u t.
    
    Some words are hyphen-
    ated across lines.
    
    Encoding issues: café becomes cafÃ©
    
    Invisible chars: ​zero-width​ spaces
    """
    
    # Analyze issues
    issues = cleaner.analyze_text_issues(test_text)
    logger.info(f"\nIssues found: {issues}")
    
    # Clean text
    cleaned = await cleaner.clean_text(test_text)
    
    logger.info("\nOriginal:")
    logger.info(test_text[:200])
    
    logger.info("\nCleaned:")
    logger.info(cleaned[:200])
    
    # Test block cleaning
    test_blocks = [
        {"type": "Text", "text": "The ﬁrst test"},
        {"type": "Text", "text": "hyphen-\nated word"},
        {"type": "Header", "text": '"Smart Quotes"'}
    ]
    
    cleaned_blocks = await cleaner.clean_blocks(test_blocks)
    logger.info(f"\nCleaned {len(cleaned_blocks)} blocks")


async def debug_function():
    """Test edge cases in text cleaning."""
    logger.info("Testing text cleaning edge cases...")
    
    # Test 1: Preserve intentional hyphens
    compound_words = "The co-author used a pre-compiled sub-module"
    cleaned = await cleaner.clean_text(compound_words)
    logger.info(f"\nCompound words preserved: {compound_words == cleaned}")
    
    # Test 2: Multiple issues in one text
    complex_text = 'The ﬁrst "algorithm" is efﬁ-\ncient'
    cleaned = await cleaner.clean_text(complex_text)
    logger.info(f"Complex: '{complex_text}' → '{cleaned}'")
    
    # Test 3: Unicode normalization
    unicode_text = "café"  # Decomposed
    normalized = await cleaner.clean_text(unicode_text)
    logger.info(f"Unicode normalized: {len(unicode_text)} chars → {len(normalized)} chars")
    
    # Test 4: Don't break URLs
    url_text = "Visit https://example.com/path-with-hyphens"
    cleaned = await cleaner.clean_text(url_text)
    logger.info(f"URL preserved: {url_text == cleaned}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()