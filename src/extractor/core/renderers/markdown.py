"""
Module: markdown.py

External Dependencies:
- regex: [Documentation URL]
- bs4: [Documentation URL]
- markdownify: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import re
import json
import hashlib
from collections import defaultdict
from typing import Annotated, Dict, List, Tuple, Optional

import regex
import uuid
from bs4 import NavigableString, BeautifulSoup
from markdownify import MarkdownConverter
from pydantic import BaseModel

from extractor.core.renderers.html import HTMLRenderer
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import BlockId
from extractor.core.schema.document import Document


def escape_dollars(text):
    return text.replace("$", r"\$")

def cleanup_text(full_text):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    return full_text.strip()

def get_formatted_table_text(element):

    text = []
    for content in element.contents:
        if content is None:
            continue

        if isinstance(content, NavigableString):
            stripped = content.strip()
            if stripped:
                text.append(escape_dollars(stripped))
        elif content.name == 'br':
            text.append('<br>')
        elif content.name == "math":
            text.append("$" + content.text + "$")
        else:
            content_str = escape_dollars(str(content))
            text.append(content_str)

    full_text = ""
    for i, t in enumerate(text):
        if t == '<br>':
            full_text += t
        elif i > 0 and text[i - 1] != '<br>':
            full_text += " " + t
        else:
            full_text += t
    return full_text


class SectionBreadcrumb:
    """Class to track section hierarchy for breadcrumb generation"""
    def __init__(self):
        self.hierarchy = {}  # level -> (title, hash)

    def update_hierarchy(self, level: int, title: str, section_hash: str):
        # Remove all higher or equal level sections
        keys_to_remove = [k for k in self.hierarchy.keys() if k >= level]
        for k in keys_to_remove:
            del self.hierarchy[k]

        # Add this section to the hierarchy
        self.hierarchy[level] = (title, section_hash)

    def get_breadcrumb_path(self) -> List[Dict[str, str]]:
        """Generate a breadcrumb path from the current hierarchy"""
        path = []
        for level in sorted(self.hierarchy.keys()):
            title, section_hash = self.hierarchy[level]
            path.append({
                "level": level,
                "title": title,
                "hash": section_hash
            })
        return path

    def generate_breadcrumb_json(self) -> str:
        """Generate a JSON representation of the breadcrumb path"""
        return json.dumps(self.get_breadcrumb_path(), ensure_ascii=False)


class Markdownify(MarkdownConverter):
    def __init__(self, paginate_output, page_separator, inline_math_delimiters, block_math_delimiters, **kwargs):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator
        self.inline_math_delimiters = inline_math_delimiters
        self.block_math_delimiters = block_math_delimiters
        self.section_breadcrumb = SectionBreadcrumb()
        self.include_breadcrumbs = True

    def convert_div(self, el, text, convert_as_inline):
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            return pagination_item + text
        else:
            return text

    def convert_p(self, el, text, convert_as_inline):
        hyphens = r'-—¬'
        has_continuation = el.has_attr('class') and 'has-continuation' in el['class']
        if has_continuation:
            block_type = BlockTypes[el['block-type']]
            if block_type in [BlockTypes.TextInlineMath, BlockTypes.Text]:
                if regex.compile(rf'.*[\p{{Ll}}|\d][{hyphens}]\s?$', regex.DOTALL).match(text):  # handle hypenation across pages
                    return regex.split(rf"[{hyphens}]\s?$", text)[0]
                return f"{text} "
            if block_type == BlockTypes.ListGroup:
                return f"{text}"
        return f"{text}\n\n" if text else ""  # default convert_p behavior

    def convert_math(self, el, text, convert_as_inline):
        block = (el.has_attr('display') and el['display'] == 'block')
        if block:
            return "\n" + self.block_math_delimiters[0] + text + self.block_math_delimiters[1] + "\n"
        else:
            return " " + self.inline_math_delimiters[0] + text + self.inline_math_delimiters[1] + " "

    def convert_h1(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 1)

    def convert_h2(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 2)

    def convert_h3(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 3)

    def convert_h4(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 4)

    def convert_h5(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 5)

    def convert_h6(self, el, text, convert_as_inline):
        return self._convert_heading(el, text, 6)

    def _convert_heading(self, el, text, level):
        """Convert a heading and add breadcrumb data"""
        # Get section hash from element
        section_hash = el.get('data-section-hash', hashlib.sha256(text.encode('utf-8')).hexdigest()[:16])

        # Update breadcrumb hierarchy
        self.section_breadcrumb.update_hierarchy(level, text, section_hash)

        # Create heading markdown
        heading = '#' * level + ' ' + text + '\n'

        # Add breadcrumb data if enabled
        if self.include_breadcrumbs:
            breadcrumb_json = self.section_breadcrumb.generate_breadcrumb_json()
            # Format as HTML comment for easy extraction but invisible in rendered markdown
            breadcrumb_data = f"<!-- SECTION_BREADCRUMB: {breadcrumb_json} -->\n\n"
            return heading + breadcrumb_data
        else:
            return heading


    def convert_table(self, el, text, convert_as_inline):
        # Check for CSV and JSON data
        csv_div = el.find('div', class_='table-csv')
        json_div = el.find('div', class_='table-json')

        csv_content = csv_div.text if csv_div else None
        json_content = json_div.text if json_div else None

        # Remove CSV and JSON divs from the table element before normal processing
        if csv_div:
            csv_div.extract()
        if json_div:
            json_div.extract()

        # Process the table normally
        total_rows = len(el.find_all('tr'))
        colspans = []
        rowspan_cols = defaultdict(int)
        for i, row in enumerate(el.find_all('tr')):
            row_cols = rowspan_cols[i]
            for cell in row.find_all(['td', 'th']):
                colspan = int(cell.get('colspan', 1))
                row_cols += colspan
                for r in range(int(cell.get('rowspan', 1)) - 1):
                    rowspan_cols[i + r] += colspan # Add the colspan to the next rows, so they get the correct number of columns
            colspans.append(row_cols)
        total_cols = max(colspans) if colspans else 0

        grid = [[None for _ in range(total_cols)] for _ in range(total_rows)]

        for row_idx, tr in enumerate(el.find_all('tr')):
            col_idx = 0
            for cell in tr.find_all(['td', 'th']):
                # Skip filled positions
                while col_idx < total_cols and grid[row_idx][col_idx] is not None:
                    col_idx += 1

                # Fill in grid
                value = get_formatted_table_text(cell).replace("\n", " ").replace("|", " ").strip()
                rowspan = int(cell.get('rowspan', 1))
                colspan = int(cell.get('colspan', 1))

                if col_idx >= total_cols:
                    # Skip this cell if we're out of bounds
                    continue

                for r in range(rowspan):
                    for c in range(colspan):
                        try:
                            if r == 0 and c == 0:
                                grid[row_idx][col_idx] = value
                            else:
                                grid[row_idx + r][col_idx + c] = '' # Empty cell due to rowspan/colspan
                        except IndexError:
                            # Sometimes the colspan/rowspan predictions can overflow
                            print(f"Overflow in columns: {col_idx + c} >= {total_cols} or rows: {row_idx + r} >= {total_rows}")
                            continue

                col_idx += colspan

        markdown_lines = []
        col_widths = [0] * total_cols
        for row in grid:
            for col_idx, cell in enumerate(row):
                if cell is not None:
                    col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))

        add_header_line = lambda: markdown_lines.append('|' + '|'.join('-' * (width + 2) for width in col_widths) + '|')

        # Generate markdown rows
        added_header = False
        for i, row in enumerate(grid):
            is_empty_line = all(not cell for cell in row)
            if is_empty_line and not added_header:
                # Skip leading blank lines
                continue

            line = []
            for col_idx, cell in enumerate(row):
                if cell is None:
                    cell = ''
                padding = col_widths[col_idx] - len(str(cell))
                line.append(f" {cell}{' ' * padding} ")
            markdown_lines.append('|' + '|'.join(line) + '|')

            if not added_header:
                # Skip empty lines when adding the header row
                add_header_line()
                added_header = True

        # Handle one row tables
        if total_rows == 1:
            add_header_line()

        table_md = '\n'.join(markdown_lines)
        result = "\n\n" + table_md + "\n\n"

        # Add CSV and JSON data as HTML comments
        if csv_content:
            result += f"<!-- TABLE_CSV:\n{csv_content}\n-->\n\n"

        if json_content:
            result += f"<!-- TABLE_JSON:\n{json_content}\n-->\n\n"

        return result

    def convert_a(self, el, text, convert_as_inline):
        text = self.escape(text)
        # Escape brackets and parentheses in text
        text = re.sub(r"([\[\]()])", r"\\\1", text)
        return super().convert_a(el, text, convert_as_inline)

    def convert_span(self, el, text, convert_as_inline):
        if el.get("id"):
            return f'<span id="{el["id"]}">{text}</span>'
        else:
            return text

    def convert_code(self, el, text, convert_as_inline):
        """Convert code blocks with language attribute."""
        language = ""
        if el.has_attr('class'):
            for cls in el['class']:
                if cls.startswith('language-'):
                    language = cls[9:]  # Extract language from class
                    break

        if language:
            return f"`{text}`" if convert_as_inline else f"```{language}\n{text}\n```"
        else:
            return super().convert_code(el, text, convert_as_inline)

    def escape(self, text):
        text = super().escape(text)
        if self.options['escape_dollars']:
            text = text.replace('$', r'\$')
        return text

class MarkdownOutput(BaseModel):
    markdown: str
    images: dict
    metadata: dict


class MarkdownRenderer(HTMLRenderer):
    page_separator: Annotated[str, "The separator to use between pages.", "Default is '-' * 48."] = "-" * 48
    inline_math_delimiters: Annotated[Tuple[str], "The delimiters to use for inline math."] = ("$", "$")
    block_math_delimiters: Annotated[Tuple[str], "The delimiters to use for block math."] = ("$$", "$$")
    include_breadcrumbs: Annotated[bool, "Whether to include section breadcrumbs in the output."] = True

    @property
    def md_cls(self):
        md = Markdownify(
            self.paginate_output,
            self.page_separator,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=True,
            escape_asterisks=True,
            escape_dollars=True,
            sub_symbol="<sub>",
            sup_symbol="<sup>",
            inline_math_delimiters=self.inline_math_delimiters,
            block_math_delimiters=self.block_math_delimiters
        )
        md.include_breadcrumbs = self.include_breadcrumbs
        return md


    def __call__(self, document: Document) -> MarkdownOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        markdown = self.md_cls.convert(full_html)
        markdown = cleanup_text(markdown)
        return MarkdownOutput(
            markdown=markdown,
            images=images,
            metadata=self.generate_document_metadata(document, document_output)
        )
