#!/usr/bin/env python3
"""
Create a simple PDF with adjacent text blocks for testing.
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def create_test_pdf(filename="test_adjacent_blocks.pdf"):
    """Create a PDF with text that should be in adjacent blocks."""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(inch, height - inch, "Test Document")
    
    # Paragraphs with text that might be split into adjacent blocks
    c.setFont("Helvetica", 12)
    y_position = height - 2*inch
    
    # First paragraph - should create adjacent text blocks
    text_lines = [
        "This is the first line of text. ",
        "This is the second line of text. ",
        "This is the third line of text.",
    ]
    
    for line in text_lines:
        c.drawString(inch, y_position, line)
        y_position -= 15
    
    y_position -= 20
    
    # Second paragraph with inline formatting that might create separate blocks
    c.drawString(inch, y_position, "This paragraph has ")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(inch + 120, y_position, "bold text")
    c.setFont("Helvetica", 12)
    c.drawString(inch + 180, y_position, " and normal text.")
    
    y_position -= 40
    
    # List items that should be adjacent
    list_items = [
        "• First item in the list",
        "• Second item in the list",
        "• Third item in the list",
    ]
    
    for item in list_items:
        c.drawString(inch, y_position, item)
        y_position -= 15
    
    c.save()
    print(f"Created {filename}")

if __name__ == "__main__":
    create_test_pdf()