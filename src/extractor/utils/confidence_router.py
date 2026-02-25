from typing import Dict, Any, Tuple, Optional
from loguru import logger

class ConfidenceRouter:
    """
    Routes document classification between ML model and heuristics based on confidence score.
    
    Usage:
        router = ConfidenceRouter(threshold=0.9)
        final_label, source = router.route(
            ml_result="arxiv", 
            ml_confidence=0.95, 
            heuristic_result="unknown"
        )
    """
    
    def __init__(self, threshold: float = 0.90):
        self.threshold = threshold

    def route(self, 
              ml_result: Optional[str], 
              ml_confidence: float, 
              heuristic_result: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Determine the final label based on confidence threshold.
        
        Returns:
            Tuple of (selected_label, source, metadata)
            source is either 'classifier' or 'heuristic'
        """
        
        # Guard against None results from classifier
        if ml_result is None:
            return heuristic_result, "heuristic", {
                "reason": "classifier_returned_none",
                "ml_confidence": 0.0,
                "threshold": self.threshold
            }

        # Check confidence threshold
        if ml_confidence >= self.threshold:
            return ml_result, "classifier", {
                "reason": "above_threshold",
                "ml_confidence": ml_confidence,
                "threshold": self.threshold
            }
        else:
            return heuristic_result, "heuristic", {
                "reason": "below_threshold",
                "ml_confidence": ml_confidence,
                "threshold": self.threshold,
                "classifier_proposal": ml_result
            }
