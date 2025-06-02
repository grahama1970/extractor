"""Document feature extraction for RL state representation"""

import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
import magic
import PyPDF2
import logging
import time

logger = logging.getLogger(__name__)


class DocumentFeatureExtractor:
    """Extract features from documents for RL decision making"""
    
    def __init__(self):
        self.file_type_mapping = {
            "pdf": 1.0,
            "docx": 2.0,
            "doc": 3.0,
            "txt": 4.0,
            "html": 5.0,
            "other": 6.0
        }
    
    def extract(self, document_path: Path) -> np.ndarray:
        """
        Extract feature vector from document
        
        Features:
        1. File size (MB, log-normalized)
        2. Estimated page count
        3. Text density estimate
        4. Has images (binary)
        5. Has tables (binary)
        6. Has code blocks (binary)
        7. Language complexity (0-1)
        8. File type encoding
        9. Estimated scan quality (0-1)
        10. Previous success rate with similar docs
        
        Returns:
            Feature vector of shape (10,)
        """
        features = []
        
        try:
            # 1. File size
            file_size_mb = document_path.stat().st_size / (1024 * 1024)
            features.append(np.log1p(file_size_mb) / 10)  # Normalize
            
            # Determine file type
            file_type = self._detect_file_type(document_path)
            
            if file_type == "pdf":
                pdf_features = self._extract_pdf_features(document_path)
                features.extend(pdf_features)
            else:
                # Default features for non-PDF
                features.extend([
                    0.5,   # page count estimate
                    0.5,   # text density
                    0.0,   # has images
                    0.0,   # has tables
                    0.0,   # has code
                    0.5,   # language complexity
                    self.file_type_mapping.get(file_type, 6.0) / 6.0,  # normalized type
                    0.5,   # scan quality
                    0.5    # previous success rate
                ])
            
        except Exception as e:
            logger.warning(f"Error extracting features from {document_path}: {e}")
            # Return default features
            features = [0.5] * 10
        
        return np.array(features[:10])  # Ensure exactly 10 features
    
    def _detect_file_type(self, path: Path) -> str:
        """Detect file type"""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        elif suffix in [".docx", ".doc"]:
            return "docx" if suffix == ".docx" else "doc"
        elif suffix in [".txt", ".text"]:
            return "txt"
        elif suffix in [".html", ".htm"]:
            return "html"
        else:
            # Try magic for better detection
            try:
                mime = magic.from_file(str(path), mime=True)
                if "pdf" in mime:
                    return "pdf"
                elif "word" in mime or "document" in mime:
                    return "docx"
                elif "text" in mime:
                    return "txt"
            except:
                pass
            return "other"
    
    def _extract_pdf_features(self, pdf_path: Path) -> list:
        """Extract PDF-specific features"""
        features = []
        
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                
                # 2. Page count (normalized)
                page_count = len(reader.pages)
                features.append(np.log1p(page_count) / 5)  # Normalize assuming max ~150 pages
                
                # Sample first few pages for analysis
                sample_text = ""
                for i in range(min(3, page_count)):
                    try:
                        sample_text += reader.pages[i].extract_text()
                    except:
                        pass
                
                # 3. Text density (characters per page)
                text_density = len(sample_text) / max(1, min(3, page_count))
                features.append(min(1.0, text_density / 2000))  # Normalize
                
                # 4. Has images (check for image objects)
                has_images = 0.0
                try:
                    for page in reader.pages[:3]:
                        if "/XObject" in page.get("/Resources", {}):
                            has_images = 1.0
                            break
                except:
                    pass
                features.append(has_images)
                
                # 5. Has tables (heuristic: look for table-like patterns)
                has_tables = 1.0 if "\\t" in sample_text or "|" in sample_text else 0.0
                features.append(has_tables)
                
                # 6. Has code blocks (heuristic)
                code_indicators = ["def ", "class ", "function", "{", "}", "import ", "from "]
                has_code = 1.0 if any(ind in sample_text for ind in code_indicators) else 0.0
                features.append(has_code)
                
                # 7. Language complexity (simple metric based on word length)
                words = sample_text.split()
                if words:
                    avg_word_length = sum(len(w) for w in words) / len(words)
                    complexity = min(1.0, avg_word_length / 10)  # Normalize
                else:
                    complexity = 0.5
                features.append(complexity)
                
                # 8. File type (PDF = 1.0)
                features.append(1.0 / 6.0)
                
                # 9. Scan quality estimate (based on extractable text)
                if sample_text.strip():
                    # If we got text, estimate quality based on readability
                    scan_quality = min(1.0, len(sample_text) / (1000 * min(3, page_count)))
                else:
                    # No text extracted, likely scanned
                    scan_quality = 0.2
                features.append(scan_quality)
                
                # 10. Previous success rate (placeholder - would track historically)
                features.append(0.7)  # Default to 70% success rate
                
        except Exception as e:
            logger.warning(f"Error extracting PDF features: {e}")
            # Return default PDF features
            features = [0.5] * 9
        
        return features


class DocumentMetadata:
    """Store and manage document metadata for better feature extraction"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".marker" / "document_history.json"
        self.history = self._load_history()
    
    def _load_history(self) -> Dict[str, Any]:
        """Load processing history"""
        if self.db_path.exists():
            import json
            return json.loads(self.db_path.read_text())
        return {"documents": {}, "success_rates": {}}
    
    def get_similar_success_rate(self, features: np.ndarray) -> float:
        """Get success rate for similar documents"""
        # Simple implementation - in production, use nearest neighbors
        if not self.history["documents"]:
            return 0.7  # Default
        
        # Find similar documents based on features
        similarities = []
        for doc_id, doc_data in self.history["documents"].items():
            if "features" in doc_data:
                doc_features = np.array(doc_data["features"])
                similarity = 1 - np.linalg.norm(features - doc_features)
                similarities.append((similarity, doc_data.get("success", 0.5)))
        
        if similarities:
            # Weighted average of success rates
            similarities.sort(reverse=True)
            top_k = similarities[:5]
            weights = [s[0] for s in top_k]
            successes = [s[1] for s in top_k]
            
            if sum(weights) > 0:
                return sum(w * s for w, s in zip(weights, successes)) / sum(weights)
        
        return 0.7
    
    def record_processing_result(self, document_path: Path, features: np.ndarray,
                               strategy: str, success: bool, metrics: Dict[str, float]):
        """Record processing result for future learning"""
        doc_id = str(document_path)
        
        self.history["documents"][doc_id] = {
            "features": features.tolist(),
            "strategy": strategy,
            "success": float(success),
            "metrics": metrics,
            "timestamp": time.time()
        }
        
        # Update strategy success rates
        if strategy not in self.history["success_rates"]:
            self.history["success_rates"][strategy] = []
        
        self.history["success_rates"][strategy].append(float(success))
        
        # Keep only recent history
        if len(self.history["success_rates"][strategy]) > 1000:
            self.history["success_rates"][strategy] = \
                self.history["success_rates"][strategy][-1000:]
        
        self._save_history()
    
    def _save_history(self):
        """Save processing history"""
        import json
        self.db_path.parent.mkdir(exist_ok=True)
        self.db_path.write_text(json.dumps(self.history, indent=2))
