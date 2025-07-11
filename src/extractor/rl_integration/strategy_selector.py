"""RL-based processing strategy selection for marker"""
Module: strategy_selector.py

import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from dataclasses import dataclass
import time
import logging
from enum import Enum

# Import from graham_rl_commons
try:
    from graham_rl_commons import DQNAgent, RLState, RLAction, RLReward, RLTracker
except ImportError:
    raise ImportError(
        "graham_rl_commons not found. Install with: "
        "pip install git+file:///home/graham/workspace/experiments/rl_commons"
    )

from .feature_extractor import DocumentFeatureExtractor, DocumentMetadata

logger = logging.getLogger(__name__)


class ProcessingStrategy(Enum):
    """Available document processing strategies"""
    FAST_PARSE = 0      # PyPDF basic extraction
    STANDARD_OCR = 1    # Tesseract standard settings
    ADVANCED_OCR = 2    # Tesseract with preprocessing
    HYBRID_SMART = 3    # Marker ML-enhanced processing


@dataclass
class StrategyConfig:
    """Configuration for each processing strategy"""
    name: str
    method: str
    expected_time_per_page: float  # seconds
    expected_accuracy: float       # 0-1
    resource_usage: float         # 0-1 (1 = high)
    
    # Method-specific parameters
    parameters: Dict[str, Any] = None


# Define available strategies
STRATEGY_CONFIGS = {
    ProcessingStrategy.FAST_PARSE: StrategyConfig(
        name="fast_parse",
        method="pypdf_basic",
        expected_time_per_page=0.5,
        expected_accuracy=0.7,
        resource_usage=0.1,
        parameters={"encoding": "utf-8", "layout_analysis": False}
    ),
    ProcessingStrategy.STANDARD_OCR: StrategyConfig(
        name="standard_ocr",
        method="tesseract_standard",
        expected_time_per_page=2.0,
        expected_accuracy=0.85,
        resource_usage=0.5,
        parameters={"lang": "eng", "oem": 3, "psm": 3}
    ),
    ProcessingStrategy.ADVANCED_OCR: StrategyConfig(
        name="advanced_ocr",
        method="tesseract_advanced",
        expected_time_per_page=4.0,
        expected_accuracy=0.95,
        resource_usage=0.8,
        parameters={
            "lang": "eng",
            "oem": 3,
            "psm": 3,
            "preprocessing": ["deskew", "denoise", "contrast"],
            "multi_column": True
        }
    ),
    ProcessingStrategy.HYBRID_SMART: StrategyConfig(
        name="hybrid_smart",
        method="marker_ml_enhanced",
        expected_time_per_page=3.0,
        expected_accuracy=0.92,
        resource_usage=0.6,
        parameters={
            "use_layout_model": True,
            "use_ocr_fallback": True,
            "batch_size": 4
        }
    )
}


class ProcessingStrategySelector:
    """
    RL-based selection of document processing strategies
    Uses DQN to learn optimal strategy based on document features
    """
    
    def __init__(self,
                 model_path: Optional[Path] = None,
                 exploration_rate: float = 0.2,
                 enable_tracking: bool = True):
        """
        Initialize strategy selector
        
        Args:
            model_path: Path to saved RL model
            exploration_rate: Initial epsilon for exploration
            enable_tracking: Whether to track performance metrics
        """
        self.feature_extractor = DocumentFeatureExtractor()
        self.metadata_manager = DocumentMetadata()
        
        # Add quality requirement to state (10 features + 1)
        state_dim = 11
        action_dim = len(ProcessingStrategy)
        
        # Initialize DQN agent
        self.agent = DQNAgent(
            name="marker_strategy_selector",
            state_dim=state_dim,
            action_dim=action_dim,
            learning_rate=1e-3,
            discount_factor=0.95,
            epsilon_start=exploration_rate,
            epsilon_end=0.05,
            epsilon_decay=0.995,
            batch_size=32,
            buffer_size=5000,
            target_update_freq=100,
            hidden_dims=[128, 64],
            device="cpu"  # Use GPU if available in production
        )
        
        # Performance tracking
        self.enable_tracking = enable_tracking
        if enable_tracking:
            self.tracker = RLTracker("marker_rl")
        
        # Processing history for analysis
        self.processing_history = []
        
        # Load existing model if provided
        if model_path and model_path.exists():
            try:
                self.agent.load(model_path)
                logger.info(f"Loaded RL model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
    
    def select_strategy(self,
                       document_path: Path,
                       quality_requirement: float = 0.85,
                       time_constraint: Optional[float] = None,
                       resource_constraint: Optional[float] = None) -> Dict[str, Any]:
        """
        Select optimal processing strategy for document
        
        Args:
            document_path: Path to document
            quality_requirement: Minimum acceptable quality (0-1)
            time_constraint: Maximum time allowed (seconds)
            resource_constraint: Maximum resource usage (0-1)
            
        Returns:
            Dictionary with selected strategy and metadata
        """
        # Extract document features
        doc_features = self.feature_extractor.extract(document_path)
        
        # Add quality requirement to state
        state_features = np.append(doc_features, quality_requirement)
        state = RLState(
            features=state_features,
            context={
                "document": str(document_path),
                "quality_req": quality_requirement,
                "time_constraint": time_constraint,
                "resource_constraint": resource_constraint
            }
        )
        
        # Get RL decision
        action = self.agent.select_action(state, explore=self.agent.training)
        strategy = ProcessingStrategy(action.action_id)
        config = STRATEGY_CONFIGS[strategy]
        
        # Check constraints
        if time_constraint or resource_constraint:
            valid_strategy = self._check_constraints(
                strategy, doc_features, time_constraint, resource_constraint
            )
            if valid_strategy != strategy:
                logger.info(f"Overriding {strategy.name} with {valid_strategy.name} due to constraints")
                strategy = valid_strategy
                config = STRATEGY_CONFIGS[strategy]
        
        # Track decision
        if self.enable_tracking:
            self.tracker.log_step(0, {
                "strategy": strategy.value,
                "expected_accuracy": config.expected_accuracy,
                "expected_time": config.expected_time_per_page
            })
        
        # Prepare result
        result = {
            "strategy": strategy,
            "strategy_name": config.name,
            "config": config,
            "action_id": action.action_id,
            "expected_accuracy": config.expected_accuracy,
            "expected_time_per_page": config.expected_time_per_page,
            "resource_usage": config.resource_usage,
            "parameters": config.parameters,
            "exploration_used": action.parameters.get("exploration", False),
            "q_values": action.parameters.get("q_values"),
            "features": doc_features.tolist()
        }
        
        return result
    
    def update_from_result(self,
                          document_path: Path,
                          strategy: ProcessingStrategy,
                          processing_time: float,
                          accuracy_score: float,
                          quality_requirement: float = 0.85,
                          extraction_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Update RL model based on processing results
        
        Args:
            document_path: Path to processed document
            strategy: Strategy that was used
            processing_time: Actual processing time
            accuracy_score: Achieved accuracy (0-1)
            quality_requirement: Quality requirement used
            extraction_metrics: Additional metrics from extraction
            
        Returns:
            Update metrics
        """
        # Extract features again (or could cache from selection)
        doc_features = self.feature_extractor.extract(document_path)
        state_features = np.append(doc_features, quality_requirement)
        
        # Create RL state and action
        state = RLState(features=state_features)
        action = RLAction(
            action_type="select_strategy",
            action_id=strategy.value
        )
        
        # Calculate multi-objective reward
        reward_value, reward_components = self._calculate_reward(
            strategy=strategy,
            processing_time=processing_time,
            accuracy_score=accuracy_score,
            quality_requirement=quality_requirement,
            extraction_metrics=extraction_metrics
        )
        
        reward = RLReward(value=reward_value, components=reward_components)
        
        # Update agent (using same state as next_state for terminal step)
        update_metrics = self.agent.update(state, action, reward, state, done=True)
        
        # Track performance
        if self.enable_tracking:
            self.tracker.log_training_metrics(update_metrics)
            self.tracker.log_step(reward_value, {
                "accuracy": accuracy_score,
                "processing_time": processing_time,
                "strategy": strategy.value
            })
        
        # Record in metadata for future similarity matching
        self.metadata_manager.record_processing_result(
            document_path=document_path,
            features=doc_features,
            strategy=strategy.name,
            success=accuracy_score >= quality_requirement,
            metrics={
                "accuracy": accuracy_score,
                "time": processing_time,
                "reward": reward_value
            }
        )
        
        # Add to history
        self.processing_history.append({
            "document": str(document_path),
            "strategy": strategy.name,
            "accuracy": accuracy_score,
            "time": processing_time,
            "reward": reward_value,
            "quality_met": accuracy_score >= quality_requirement
        })
        
        # Save model periodically
        if self.agent.training_steps % 100 == 0:
            self._save_model()
        
        return update_metrics
    
    def _calculate_reward(self,
                         strategy: ProcessingStrategy,
                         processing_time: float,
                         accuracy_score: float,
                         quality_requirement: float,
                         extraction_metrics: Optional[Dict[str, Any]] = None) -> Tuple[float, Dict[str, float]]:
        """Calculate multi-objective reward"""
        config = STRATEGY_CONFIGS[strategy]
        
        # Normalize time (assume max 10s per page is very bad)
        time_score = 1.0 - min(1.0, processing_time / 10.0)
        
        # Quality score
        quality_score = accuracy_score
        
        # Requirement satisfaction (binary but important)
        requirement_met = float(accuracy_score >= quality_requirement)
        
        # Resource efficiency
        resource_score = 1.0 - config.resource_usage
        
        # Additional metrics if available
        completeness_score = 0.8  # Default
        if extraction_metrics:
            # Text extraction completeness
            if "text_coverage" in extraction_metrics:
                completeness_score = extraction_metrics["text_coverage"]
            
            # Table/figure extraction success
            if "tables_extracted" in extraction_metrics:
                completeness_score *= 0.8 + 0.2 * extraction_metrics["tables_extracted"]
        
        # Weighted combination
        weights = {
            "quality": 0.35,
            "speed": 0.25,
            "requirement": 0.25,
            "resource": 0.10,
            "completeness": 0.05
        }
        
        components = {
            "quality": quality_score,
            "speed": time_score,
            "requirement": requirement_met,
            "resource": resource_score,
            "completeness": completeness_score
        }
        
        # Calculate weighted reward
        reward = sum(weights[k] * v for k, v in components.items())
        
        # Penalty for not meeting requirement
        if not requirement_met:
            reward *= 0.5
        
        return reward, components
    
    def _check_constraints(self,
                          selected_strategy: ProcessingStrategy,
                          doc_features: np.ndarray,
                          time_constraint: Optional[float],
                          resource_constraint: Optional[float]) -> ProcessingStrategy:
        """Check if selected strategy meets constraints"""
        config = STRATEGY_CONFIGS[selected_strategy]
        
        # Estimate pages from features
        estimated_pages = int(np.exp(doc_features[1] * 5))  # Reverse normalization
        
        if time_constraint:
            expected_time = config.expected_time_per_page * estimated_pages
            if expected_time > time_constraint:
                # Find faster strategy
                for strategy in ProcessingStrategy:
                    alt_config = STRATEGY_CONFIGS[strategy]
                    if alt_config.expected_time_per_page * estimated_pages <= time_constraint:
                        return strategy
        
        if resource_constraint:
            if config.resource_usage > resource_constraint:
                # Find less resource-intensive strategy
                for strategy in ProcessingStrategy:
                    alt_config = STRATEGY_CONFIGS[strategy]
                    if alt_config.resource_usage <= resource_constraint:
                        return strategy
        
        return selected_strategy
    
    def _save_model(self):
        """Save the RL model"""
        model_dir = Path.home() / ".marker" / "rl_models"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        model_path = model_dir / "strategy_selector.pt"
        try:
            self.agent.save(model_path)
            logger.info(f"Saved RL model to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def get_performance_report(self) -> str:
        """Generate performance report"""
        if not self.processing_history:
            return "No processing history available"
        
        report = ["=== Marker RL Strategy Selection Report ===\n"]
        
        # Overall statistics
        total_docs = len(self.processing_history)
        avg_accuracy = np.mean([h["accuracy"] for h in self.processing_history])
        avg_time = np.mean([h["time"] for h in self.processing_history])
        quality_met_rate = np.mean([h["quality_met"] for h in self.processing_history])
        
        report.append(f"Total Documents Processed: {total_docs}")
        report.append(f"Average Accuracy: {avg_accuracy:.3f}")
        report.append(f"Average Processing Time: {avg_time:.2f}s")
        report.append(f"Quality Requirement Met: {quality_met_rate*100:.1f}%")
        report.append(f"Current Exploration Rate: {self.agent.epsilon:.3f}\n")
        
        # Strategy usage
        strategy_counts = {}
        strategy_performance = {}
        
        for history in self.processing_history:
            strategy = history["strategy"]
            if strategy not in strategy_counts:
                strategy_counts[strategy] = 0
                strategy_performance[strategy] = {"accuracy": [], "time": [], "reward": []}
            
            strategy_counts[strategy] += 1
            strategy_performance[strategy]["accuracy"].append(history["accuracy"])
            strategy_performance[strategy]["time"].append(history["time"])
            strategy_performance[strategy]["reward"].append(history["reward"])
        
        report.append("Strategy Usage and Performance:")
        for strategy, count in strategy_counts.items():
            perf = strategy_performance[strategy]
            report.append(f"\n{strategy}:")
            report.append(f"  Usage: {count} ({count/total_docs*100:.1f}%)")
            report.append(f"  Avg Accuracy: {np.mean(perf['accuracy']):.3f}")
            report.append(f"  Avg Time: {np.mean(perf['time']):.2f}s")
            report.append(f"  Avg Reward: {np.mean(perf['reward']):.3f}")
        
        # Learning progress
        if self.enable_tracking:
            tracker_stats = self.tracker.get_current_stats()
            report.append(f"\n=== Learning Progress ===")
            report.append(f"Training Steps: {tracker_stats.get('total_steps', 0)}")
            report.append(f"Episodes: {tracker_stats.get('total_episodes', 0)}")
            
            if "avg_reward_100" in tracker_stats:
                report.append(f"Recent Avg Reward (100): {tracker_stats['avg_reward_100']:.3f}")
        
        return "\n".join(report)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        # Calculate total selections
        total_selections = len(self.processing_history)
        
        # Calculate strategy counts
        strategy_counts = {}
        for strategy in ProcessingStrategy:
            strategy_counts[strategy] = sum(1 for h in self.processing_history if h["strategy"] == strategy.name)
        
        # Calculate average reward
        average_reward = 0.0
        if self.processing_history:
            average_reward = np.mean([h["reward"] for h in self.processing_history])
        
        metrics = {
            "total_selections": total_selections,
            "strategy_counts": strategy_counts,
            "average_reward": average_reward,
            "exploration_rate": self.agent.epsilon if hasattr(self.agent, "epsilon") else 0.0
        }
        
        return metrics

