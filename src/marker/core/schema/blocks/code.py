import html
from typing import Optional

from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Block


class Code(Block):
    block_type: BlockTypes = BlockTypes.Code
    code: str | None = None
    language: Optional[str] = None
    block_description: str = "A programming code block."

    def assemble_html(self, document, child_blocks, parent_structure):
        code = self.code or ""
        lang_attr = f" class=\"language-{self.language}\"" if self.language else ""
        return (f"<pre>"
                f"<code{lang_attr}>{html.escape(code)}</code>"
                f"</pre>")
