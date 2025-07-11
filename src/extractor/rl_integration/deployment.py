"""Safe deployment wrapper for RL-based strategy selection"""
Module: deployment.py

import random
import logging
from typing import Optional, Dict, Any, Callable
from enum import Enum
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import threading

from .strategy_selector import ProcessingStrategySelector, ProcessingStrategy

logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """Deployment modes for RL strategy selection"""
    DISABLED = "disabled"          # Use fallback only
    SHADOW = "shadow"              # Run RL but use fallback
    CANARY = "canary"              # Gradual rollout
    FULL = "full"                  # Full RL deployment


class SafeStrategyDeployment:
    """
    Safe deployment wrapper for RL-based strategy selection
    
    Features:
    - Gradual rollout with configurable percentage
    - Automatic fallback on errors
    - Performance monitoring and rollback
    - A/B testing capabilities
    """
    
    def __init__(self,
                 rl_selector: ProcessingStrategySelector,
                 fallback_strategy: ProcessingStrategy = ProcessingStrategy.STANDARD_OCR,
                 rollout_percentage: float = 0.1,
                 mode: DeploymentMode = DeploymentMode.CANARY,
                 min_performance_threshold: float = 0.8,
                 metrics_window_size: int = 100,
                 auto_rollback: bool = True):
        """
        Initialize safe deployment wrapper
        
        Args:
            rl_selector: The RL strategy selector
            fallback_strategy: Default strategy when not using RL
            rollout_percentage: Percentage of requests to use RL (0-1)
            mode: Deployment mode
            min_performance_threshold: Minimum performance to maintain
            metrics_window_size: Window size for performance metrics
            auto_rollback: Whether to automatically rollback on poor performance
        """
        self.rl_selector = rl_selector
        self.fallback_strategy = fallback_strategy
        self.rollout_percentage = rollout_percentage
        self.mode = mode
        self.min_performance_threshold = min_performance_threshold
        self.metrics_window_size = metrics_window_size
        self.auto_rollback = auto_rollback
        
        # Metrics tracking
        self.metrics_lock = threading.Lock()
        self.rl_metrics = []
        self.fallback_metrics = []
        self.error_count = 0
        self.total_requests = 0
        
        # Performance monitoring
        self.performance_history = []
        self.last_rollback_time = None
        
    def select_strategy(self, 
                       features: np.ndarray,
                       force_mode: Optional[str] = None) -> ProcessingStrategy:
        """
        Select processing strategy with safe deployment
        
        Args:
            features: Document features
            force_mode: Override deployment mode ("rl" or "fallback")
            
        Returns:
            Selected processing strategy
        """
        self.total_requests += 1
        
        # Check deployment mode
        if force_mode == "fallback" or self.mode == DeploymentMode.DISABLED:
            return self._use_fallback("forced_or_disabled")
            
        if force_mode == "rl":
            return self._use_rl(features)
            
        # Shadow mode: run RL but use fallback
        if self.mode == DeploymentMode.SHADOW:
            try:
                # Run RL selection for learning
                rl_strategy, _ = self.rl_selector.select_strategy(features)
                logger.debug(f"Shadow mode: RL selected {rl_strategy}")
            except Exception as e:
                logger.warning(f"Shadow mode RL error: {e}")
            return self._use_fallback("shadow_mode")
            
        # Canary deployment: gradual rollout
        if self.mode == DeploymentMode.CANARY:
            if random.random() < self.rollout_percentage:
                return self._use_rl(features)
            else:
                return self._use_fallback("canary_rollout")
                
        # Full deployment
        if self.mode == DeploymentMode.FULL:
            try:
                return self._use_rl(features)
            except Exception as e:
                logger.error(f"RL selection failed, using fallback: {e}")
                return self._use_fallback("rl_error")
                
    def _use_rl(self, features: np.ndarray) -> ProcessingStrategy:
        """Use RL for strategy selection with error handling"""
        try:
            result = self.rl_selector.select_strategy(features)
            strategy = result["strategy"]
            confidence = result.get("confidence", 0.0)
            
            # Log selection
            with self.metrics_lock:
                self.rl_metrics.append({
                    "timestamp": datetime.now(),
                    "strategy": strategy,
                    "confidence": confidence
                })
                
            logger.info(f"RL selected {strategy.name} with confidence {confidence:.3f}")
            return strategy
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"RL selection error: {e}")
            
            # Check if we need to rollback
            if self.auto_rollback and self._should_rollback():
                self._perform_rollback()
                
            return self._use_fallback("rl_error")
            
    def _use_fallback(self, reason: str) -> ProcessingStrategy:
        """Use fallback strategy"""
        with self.metrics_lock:
            self.fallback_metrics.append({
                "timestamp": datetime.now(),
                "reason": reason
            })
            
        logger.debug(f"Using fallback strategy: {self.fallback_strategy} (reason: {reason})")
        return self.fallback_strategy
        
    def update_performance(self,
                          strategy: ProcessingStrategy,
                          performance_score: float,
                          processing_time: float,
                          features: Optional[np.ndarray] = None):
        """
        Update performance metrics
        
        Args:
            strategy: Strategy that was used
            performance_score: Performance score (0-1)
            processing_time: Time taken to process
            features: Document features (for RL update)
        """
        with self.metrics_lock:
            self.performance_history.append({
                "timestamp": datetime.now(),
                "strategy": strategy,
                "performance": performance_score,
                "processing_time": processing_time,
                "was_rl": strategy != self.fallback_strategy
            })
            
            # Keep window size
            if len(self.performance_history) > self.metrics_window_size:
                self.performance_history.pop(0)
                
        # Update RL if features provided
        if features is not None and strategy != self.fallback_strategy:
            # Calculate reward based on performance
            reward = self._calculate_reward(performance_score, processing_time)
            self.rl_selector.update(features, strategy, reward, features)
            
        # Check performance thresholds
        if self.auto_rollback and self._should_rollback():
            self._perform_rollback()
            
    def _calculate_reward(self, performance_score: float, processing_time: float) -> float:
        """Calculate reward for RL update"""
        # Combine performance and speed
        time_factor = np.exp(-processing_time / 10.0)  # Exponential decay
        return performance_score * 0.7 + time_factor * 0.3
        
    def _should_rollback(self) -> bool:
        """Check if we should rollback based on performance"""
        if len(self.performance_history) < 10:
            return False
            
        # Calculate recent RL performance
        recent_rl = [m for m in self.performance_history[-20:] if m["was_rl"]]
        if len(recent_rl) < 5:
            return False
            
        avg_performance = np.mean([m["performance"] for m in recent_rl])
        
        # Check error rate
        error_rate = self.error_count / max(self.total_requests, 1)
        
        return (avg_performance < self.min_performance_threshold or 
                error_rate > 0.1)
                
    def _perform_rollback(self):
        """Perform rollback to safer deployment mode"""
        logger.warning("Performing automatic rollback due to poor performance")
        
        if self.mode == DeploymentMode.FULL:
            self.mode = DeploymentMode.CANARY
            self.rollout_percentage = 0.1
        elif self.mode == DeploymentMode.CANARY:
            self.rollout_percentage = max(0.01, self.rollout_percentage * 0.5)
            
        self.last_rollback_time = datetime.now()
        
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status and metrics"""
        with self.metrics_lock:
            rl_count = len(self.rl_metrics)
            fallback_count = len(self.fallback_metrics)
            
            # Calculate performance metrics
            if self.performance_history:
                recent_perf = self.performance_history[-20:]
                rl_perf = [m for m in recent_perf if m["was_rl"]]
                fallback_perf = [m for m in recent_perf if not m["was_rl"]]
                
                rl_avg_perf = np.mean([m["performance"] for m in rl_perf]) if rl_perf else 0
                fallback_avg_perf = np.mean([m["performance"] for m in fallback_perf]) if fallback_perf else 0
                
                rl_avg_time = np.mean([m["processing_time"] for m in rl_perf]) if rl_perf else 0
                fallback_avg_time = np.mean([m["processing_time"] for m in fallback_perf]) if fallback_perf else 0
            else:
                rl_avg_perf = fallback_avg_perf = 0
                rl_avg_time = fallback_avg_time = 0
                
        return {
            "mode": self.mode.value,
            "rollout_percentage": self.rollout_percentage,
            "total_requests": self.total_requests,
            "rl_selections": rl_count,
            "fallback_selections": fallback_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.total_requests, 1),
            "rl_performance": {
                "average_score": rl_avg_perf,
                "average_time": rl_avg_time
            },
            "fallback_performance": {
                "average_score": fallback_avg_perf,
                "average_time": fallback_avg_time
            },
            "last_rollback": self.last_rollback_time.isoformat() if self.last_rollback_time else None
        }
        
    def update_rollout_percentage(self, new_percentage: float):
        """Manually update rollout percentage"""
        self.rollout_percentage = max(0.0, min(1.0, new_percentage))
        logger.info(f"Updated rollout percentage to {self.rollout_percentage:.1%}")
        
    def set_mode(self, mode: DeploymentMode):
        """Change deployment mode"""
        self.mode = mode
        logger.info(f"Changed deployment mode to {mode.value}")
        
    def save_metrics(self, filepath: Path):
        """Save deployment metrics to file"""
        metrics = self.get_deployment_status()
        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)
            
    def reset_metrics(self):
        """Reset performance metrics"""
        with self.metrics_lock:
            self.rl_metrics = []
            self.fallback_metrics = []
            self.performance_history = []
            self.error_count = 0
            self.total_requests = 0
            
        logger.info("Reset deployment metrics")


def create_safe_deployment(config_path: Optional[Path] = None) -> SafeStrategyDeployment:
    """
    Create safe deployment from configuration file
    
    Args:
        config_path: Path to deployment configuration
        
    Returns:
        Configured safe deployment wrapper
    """
    # Default configuration
    config = {
        "model_path": "/home/graham/workspace/experiments/marker/models/rl_strategy",
        "fallback_strategy": "STANDARD_OCR",
        "rollout_percentage": 0.1,
        "mode": "canary",
        "min_performance_threshold": 0.8,
        "auto_rollback": True
    }
    
    # Load custom configuration
    if config_path and config_path.exists():
        with open(config_path) as f:
            custom_config = json.load(f)
            config.update(custom_config)
            
    # Create components
    rl_selector = ProcessingStrategySelector(
        model_path=Path(config["model_path"])
    )
    
    fallback_strategy = ProcessingStrategy[config["fallback_strategy"]]
    mode = DeploymentMode(config["mode"])
    
    # Create deployment wrapper
    return SafeStrategyDeployment(
        rl_selector=rl_selector,
        fallback_strategy=fallback_strategy,
        rollout_percentage=config["rollout_percentage"],
        mode=mode,
        min_performance_threshold=config["min_performance_threshold"],
        auto_rollback=config["auto_rollback"]
    )
