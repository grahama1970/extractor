"""
Module: quick_start_rl.py

External Dependencies:
- numpy: https://numpy.org/doc/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Quick start script for testing RL integration in marker
"""

import sys
import logging
from pathlib import Path
import numpy as np

# Add marker to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from marker.rl_integration import (
    ProcessingStrategySelector,
    ProcessingStrategy,
    DocumentFeatureExtractor
)
from marker.rl_integration.deployment import SafeStrategyDeployment, DeploymentMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def simulate_document_processing():
    """Simulate document processing with RL strategy selection"""
    
    logger.info("Initializing RL-based strategy selector...")
    
    # Create selector
    model_path = Path("./models/rl_strategy")
    model_path.mkdir(parents=True, exist_ok=True)
    
    selector = ProcessingStrategySelector(
        model_path=model_path,
        learning_rate=0.001,
        exploration_rate=0.3  # Higher exploration for demo
    )
    
    # Create safe deployment wrapper
    safe_deployer = SafeStrategyDeployment(
        rl_selector=selector,
        fallback_strategy=ProcessingStrategy.STANDARD_OCR,
        rollout_percentage=0.5,  # 50% for demo
        mode=DeploymentMode.CANARY
    )
    
    logger.info("Starting document processing simulation...")
    
    # Simulate processing 20 documents
    for i in range(20):
        logger.info(f"\n--- Processing Document {i+1} ---")
        
        # Generate random document features
        features = np.random.rand(selector.feature_extractor.feature_dim)
        features[0] = np.random.randint(1, 100) / 100  # Page count
        features[1] = np.random.rand() * 10 / 50       # File size
        features[2] = np.random.choice([0, 1])          # Has images
        features[3] = np.random.choice([0, 1])          # Has tables
        
        # Select strategy
        strategy = safe_deployer.select_strategy(features)
        logger.info(f"Selected strategy: {strategy.name}")
        
        # Simulate processing results
        if strategy == ProcessingStrategy.FAST_PARSE:
            processing_time = np.random.normal(0.5, 0.1)
            accuracy = np.random.normal(0.7, 0.05)
            resource_usage = 0.1
        elif strategy == ProcessingStrategy.STANDARD_OCR:
            processing_time = np.random.normal(2.0, 0.3)
            accuracy = np.random.normal(0.85, 0.03)
            resource_usage = 0.5
        elif strategy == ProcessingStrategy.ADVANCED_OCR:
            processing_time = np.random.normal(4.0, 0.5)
            accuracy = np.random.normal(0.95, 0.02)
            resource_usage = 0.8
        else:  # HYBRID_SMART
            processing_time = np.random.normal(3.0, 0.4)
            accuracy = np.random.normal(0.92, 0.03)
            resource_usage = 0.6
            
        # Clip values to valid ranges
        processing_time = max(0.1, processing_time)
        accuracy = np.clip(accuracy, 0, 1)
        
        logger.info(f"Processing time: {processing_time:.2f}s")
        logger.info(f"Accuracy: {accuracy:.2%}")
        logger.info(f"Resource usage: {resource_usage:.1%}")
        
        # Update performance
        safe_deployer.update_performance(
            strategy=strategy,
            performance_score=accuracy,
            processing_time=processing_time,
            features=features
        )
        
        # Calculate reward for learning
        reward = selector.calculate_reward(
            processing_time=processing_time,
            accuracy_score=accuracy,
            resource_usage=resource_usage,
            expected_time=3.0,
            expected_accuracy=0.85
        )
        
        # Update RL agent
        selector.update(features, strategy, reward, features)
        
        logger.info(f"Reward: {reward:.3f}")
        
    # Print final statistics
    logger.info("\n=== Final Statistics ===")
    
    # Selector metrics
    metrics = selector.get_metrics()
    logger.info(f"Total selections: {metrics['total_selections']}")
    logger.info(f"Average reward: {metrics['average_reward']:.3f}")
    
    # Deployment status
    status = safe_deployer.get_deployment_status()
    logger.info(f"\nDeployment mode: {status['mode']}")
    logger.info(f"RL selections: {status['rl_selections']}")
    logger.info(f"Fallback selections: {status['fallback_selections']}")
    logger.info(f"Error rate: {status['error_rate']:.3%}")
    
    if status['rl_performance']['average_score'] > 0:
        logger.info(f"\nRL Performance:")
        logger.info(f"  Average score: {status['rl_performance']['average_score']:.3f}")
        logger.info(f"  Average time: {status['rl_performance']['average_time']:.2f}s")
        
    if status['fallback_performance']['average_score'] > 0:
        logger.info(f"\nFallback Performance:")
        logger.info(f"  Average score: {status['fallback_performance']['average_score']:.3f}")
        logger.info(f"  Average time: {status['fallback_performance']['average_time']:.2f}s")
        
    # Save model
    selector.save_model(model_path / "trained_model")
    logger.info(f"\nModel saved to {model_path / 'trained_model'}")
    
    # Save deployment metrics
    safe_deployer.save_metrics(model_path / "deployment_metrics.json")
    logger.info(f"Deployment metrics saved to {model_path / 'deployment_metrics.json'}")


def test_feature_extraction():
    """Test feature extraction on mock documents"""
    logger.info("Testing feature extraction...")
    
    extractor = DocumentFeatureExtractor()
    
    # Create mock metadata
    from marker.rl_integration.feature_extractor import DocumentMetadata
    
    # Simple document
    simple_doc = DocumentMetadata(
        page_count=5,
        file_size_mb=0.5,
        has_images=False,
        has_tables=False,
        estimated_text_density=0.9,
        detected_languages=["en"],
        is_scanned=False,
        has_forms=False,
        complexity_score=0.2
    )
    
    # Complex document
    complex_doc = DocumentMetadata(
        page_count=100,
        file_size_mb=25.0,
        has_images=True,
        has_tables=True,
        estimated_text_density=0.5,
        detected_languages=["en", "es", "fr"],
        is_scanned=True,
        has_forms=True,
        complexity_score=0.9
    )
    
    simple_features = extractor.extract_from_metadata(simple_doc)
    complex_features = extractor.extract_from_metadata(complex_doc)
    
    logger.info(f"Simple document features: {simple_features}")
    logger.info(f"Complex document features: {complex_features}")
    
    return extractor


def main():
    """Main entry point"""
    logger.info("=== Marker RL Integration Quick Start ===\n")
    
    # Check if rl_commons is installed
    try:
        import graham_rl_commons
        logger.info(" graham_rl_commons is installed")
    except ImportError:
        logger.error(" graham_rl_commons not found!")
        logger.error("Please install with: pip install -e /home/graham/workspace/experiments/rl_commons")
        sys.exit(1)
        
    # Test feature extraction
    test_feature_extraction()
    
    # Run simulation
    simulate_document_processing()
    
    logger.info("\n=== Quick Start Complete! ===")
    logger.info("\nNext steps:")
    logger.info("1. Run the full test suite: pytest test/test_rl_integration.py")
    logger.info("2. Integrate with actual document processors")
    logger.info("3. Train on real document data")
    logger.info("4. Deploy in shadow mode for production testing")


if __name__ == "__main__":
    main()
