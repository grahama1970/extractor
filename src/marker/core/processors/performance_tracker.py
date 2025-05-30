"""Performance tracking for Claude post-processing.

This module tracks performance metrics for Claude features.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class PerformanceMetrics:
    """Track performance metrics for Claude processing."""
    
    total_processing_time: float = 0.0
    claude_processing_time: float = 0.0
    features_used: List[str] = field(default_factory=list)
    improvements_made: List[str] = field(default_factory=list)
    feature_timings: Dict[str, float] = field(default_factory=dict)
    total_analyses: int = 0
    successful_analyses: int = 0
    fallbacks_triggered: int = 0
    
    def add_feature_time(self, feature: str, duration: float):
        """Add timing for a specific feature."""
        if feature not in self.feature_timings:
            self.feature_timings[feature] = 0.0
        self.feature_timings[feature] += duration
        
        if feature not in self.features_used:
            self.features_used.append(feature)
    
    def add_improvement(self, improvement: str):
        """Record an improvement made."""
        if improvement not in self.improvements_made:
            self.improvements_made.append(improvement)
    
    def get_average_analysis_time(self) -> float:
        """Get average time per analysis."""
        if self.total_analyses == 0:
            return 0.0
        return self.claude_processing_time / self.total_analyses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata."""
        return {
            "features_used": self.features_used,
            "total_claude_time": round(self.claude_processing_time, 1),
            "improvements_made": self.improvements_made,
            "performance_stats": {
                "total_analyses": self.total_analyses,
                "successful_analyses": self.successful_analyses,
                "average_analysis_time": round(self.get_average_analysis_time(), 1),
                "fallbacks_triggered": self.fallbacks_triggered,
                "feature_timings": {k: round(v, 1) for k, v in self.feature_timings.items()}
            }
        }


class PerformanceTracker:
    """Track performance across Claude post-processing."""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self._start_times = {}
    
    def start_feature(self, feature: str):
        """Start timing a feature."""
        self._start_times[feature] = time.time()
    
    def end_feature(self, feature: str, improvement: Optional[str] = None):
        """End timing a feature and optionally record improvement."""
        if feature in self._start_times:
            duration = time.time() - self._start_times[feature]
            self.metrics.add_feature_time(feature, duration)
            self.metrics.claude_processing_time += duration
            del self._start_times[feature]
            
            if improvement:
                self.metrics.add_improvement(improvement)
    
    def record_analysis(self, successful: bool = True):
        """Record an analysis attempt."""
        self.metrics.total_analyses += 1
        if successful:
            self.metrics.successful_analyses += 1
    
    def record_fallback(self):
        """Record a fallback to heuristics."""
        self.metrics.fallbacks_triggered += 1
    
    def start_total_processing(self):
        """Start timing total processing."""
        self._start_times['_total'] = time.time()
    
    def end_total_processing(self):
        """End timing total processing."""
        if '_total' in self._start_times:
            self.metrics.total_processing_time = time.time() - self._start_times['_total']
            del self._start_times['_total']
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata for inclusion in results."""
        return self.metrics.to_dict()