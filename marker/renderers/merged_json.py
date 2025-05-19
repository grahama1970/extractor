"""
Merged JSON Renderer for Marker

This renderer combines adjacent text blocks to create a more compact
and semantically meaningful JSON output.
"""

from typing import Annotated, Dict, List, Tuple
from pydantic import BaseModel

from marker.renderers.json import JSONBlockOutput, JSONOutput, JSONRenderer
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.blocks.base import BlockOutput


class MergedJSONRenderer(JSONRenderer):
    """
    A renderer that merges adjacent text blocks for cleaner JSON output.
    """
    
    merge_block_types: Annotated[
        Tuple[str, ...],
        "Block types that should be merged when adjacent"
    ] = ("Span", "Line", "Text")
    
    merge_within_parents: Annotated[
        Tuple[str, ...],
        "Parent block types within which to merge children"
    ] = ("Page", "Section", "Column", "TextRegion")
    
    def extract_json(self, document: Document, block_output: BlockOutput) -> Dict:
        """Override to handle merging of adjacent blocks."""
        # Get the base JSON representation first
        result = super().extract_json(document, block_output)
        
        # Check if this block has children and if we should merge them
        if (isinstance(result, dict) and
            "children" in result and 
            result.get("block_type") in self.merge_within_parents):
            
            # Merge adjacent children in the JSON structure
            merged_children = self._merge_adjacent_json_blocks(result["children"])
            result["children"] = merged_children
            
            # Add merge information if children were merged
            original_count = len(result["children"])
            merged_count = len(merged_children) 
            if merged_count < original_count:
                result["children_merged"] = original_count - merged_count
        
        return result
    
    def _merge_adjacent_json_blocks(self, children: List[Dict]) -> List[Dict]:
        """Merge adjacent blocks in JSON format."""
        if not children:
            return children
        
        merged = []
        current_merge = None
        
        for child in children:
            block_type = child.get("block_type", "")
            
            # Check if this block can be merged with the previous one
            if (current_merge and 
                block_type in self.merge_block_types and
                block_type == current_merge["block_type"] and
                self._are_json_blocks_adjacent(current_merge, child)):
                
                # Merge with current block
                current_merge = self._merge_two_json_blocks(current_merge, child)
            else:
                # Save the previous merge if it exists
                if current_merge:
                    merged.append(current_merge)
                
                # Start a new block
                current_merge = child.copy() if block_type in self.merge_block_types else None
                if not current_merge:
                    merged.append(child)
        
        # Don't forget the last merge
        if current_merge:
            merged.append(current_merge)
        
        return merged
    
    def _are_json_blocks_adjacent(self, block1: Dict, block2: Dict) -> bool:
        """Check if two JSON blocks are adjacent."""
        bbox1 = block1.get("bbox", [0, 0, 0, 0])
        bbox2 = block2.get("bbox", [0, 0, 0, 0])
        
        # Check if blocks are on roughly the same line
        vertical_overlap = min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1])
        height1 = bbox1[3] - bbox1[1]
        height2 = bbox2[3] - bbox2[1]
        min_height = min(height1, height2)
        
        if min_height <= 0:
            return False
        
        # They're on the same line if they have significant vertical overlap
        same_line = vertical_overlap > (0.6 * min_height)
        
        if same_line:
            # Check horizontal proximity
            horizontal_gap = max(0, bbox2[0] - bbox1[2])  # Gap between right of block1 and left of block2
            return horizontal_gap < (2 * min_height)  # Allow gap up to 2x the height
        else:
            # Check if they're vertically adjacent (one below the other)
            vertical_gap = max(0, bbox2[1] - bbox1[3])  # Gap between bottom of block1 and top of block2
            return vertical_gap < (0.5 * min_height)  # Allow small gap
    
    def _merge_two_json_blocks(self, block1: Dict, block2: Dict) -> Dict:
        """Merge two JSON blocks into one."""
        merged = block1.copy()
        
        # Merge HTML content
        if "html" in block1 and "html" in block2:
            merged["html"] = (block1.get("html", "") + " " + block2.get("html", "")).strip()
        
        # Update bounding box to encompass both blocks
        bbox1 = block1.get("bbox", [0, 0, 0, 0])
        bbox2 = block2.get("bbox", [0, 0, 0, 0])
        
        merged["bbox"] = [
            min(bbox1[0], bbox2[0]),  # min x
            min(bbox1[1], bbox2[1]),  # min y
            max(bbox1[2], bbox2[2]),  # max x
            max(bbox1[3], bbox2[3])   # max y
        ]
        
        # Track merge count
        count1 = block1.get("merged_count", 1)
        count2 = block2.get("merged_count", 1)
        merged["merged_count"] = count1 + count2
        
        # Track merged IDs
        ids1 = block1.get("merged_ids", [block1.get("id", "")])
        ids2 = block2.get("merged_ids", [block2.get("id", "")])
        merged["merged_ids"] = ids1 + ids2
        
        return merged