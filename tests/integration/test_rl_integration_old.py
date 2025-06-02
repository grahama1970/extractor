"""Test RL integration for marker document processing"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import json
from unittest.mock import Mock, patch

# Import the RL components
from marker.rl_integration import (
    ProcessingStrategySelector,
    ProcessingStrategy,
    DocumentFeatureExtractor
)
from marker.rl_integration.feature_extractor import DocumentMetadata


class TestDocumentFeatureExtractor:
    """Test document feature extraction"""
    
    def test_extract_from_metadata(self):
        """Test feature extraction from document metadata"""
        metadata = DocumentMetadata(
            page_count=10,
            file_size_mb=2.5,
            has_images=True,
            has_tables=True,
            estimated_text_density=0.7,
            detected_languages=["en"],
            is_scanned=False,
            has_forms=False,
            complexity_score=0.6
        )
        
        extractor = DocumentFeatureExtractor()
        features = extractor.extract_from_metadata(metadata)
        
        # Check feature dimensions
        assert features.shape == (extractor.feature_dim,)
        
        # Check normalized values
        assert 0 <= features[0] <= 1  # normalized page count
        assert 0 <= features[1] <= 1  # normalized file size
        
    def test_extract_from_file(self, tmp_path):
        """Test feature extraction from actual file"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        extractor = DocumentFeatureExtractor()
        
        # Mock the PDF analysis
        with patch.object(extractor, '_analyze_pdf') as mock_analyze:
            mock_analyze.return_value = DocumentMetadata(
                page_count=5,
                file_size_mb=1.0,
                has_images=False,
                has_tables=False,
                estimated_text_density=0.8,
                detected_languages=["en"],
                is_scanned=False,
                has_forms=False,
                complexity_score=0.3
            )
            
            features = extractor.extract_from_file(pdf_path)
            assert features.shape == (extractor.feature_dim,)


class TestProcessingStrategySelector:
    """Test RL-based strategy selection"""
    
    @pytest.fixture
    def selector(self, tmp_path):
        """Create a strategy selector with temporary model path"""
        model_path = tmp_path / "test_model"
        return ProcessingStrategySelector(
            model_path=model_path,
            learning_rate=0.001,
            exploration_rate=0.1
        )
    
    def test_initialization(self, selector):
        """Test selector initialization"""
        assert selector.agent is not None
        assert selector.feature_extractor is not None
        assert len(selector.strategies) == 4
        
    def test_select_strategy_exploration(self, selector):
        """Test strategy selection in exploration mode"""
        # Create mock features
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Force exploration
        selector.set_mode("train")
        strategies_selected = set()
        
        # Run multiple times to ensure exploration
        for _ in range(100):
            strategy, confidence = selector.select_strategy(features)
            strategies_selected.add(strategy)
            
        # Should explore multiple strategies
        assert len(strategies_selected) > 1
        
    def test_select_strategy_exploitation(self, selector):
        """Test strategy selection in exploitation mode"""
        # Create mock features
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Train the model with a clear preference
        selector.set_mode("train")
        
        # Simulate training: HYBRID_SMART is best for these features
        for _ in range(50):
            strategy = ProcessingStrategy.HYBRID_SMART
            reward = 1.0  # High reward
            selector.update(features, strategy, reward, features)
            
        # Switch to evaluation mode
        selector.set_mode("eval")
        
        # Should consistently select HYBRID_SMART
        strategies = []
        for _ in range(10):
            strategy, confidence = selector.select_strategy(features)
            strategies.append(strategy)
            
        # Most selections should be HYBRID_SMART
        hybrid_count = sum(1 for s in strategies if s == ProcessingStrategy.HYBRID_SMART)
        assert hybrid_count >= 8
        
    def test_update_learning(self, selector):
        """Test that the agent learns from feedback"""
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Get initial Q-values
        initial_q_values = selector.agent.get_q_values(features)
        
        # Provide positive feedback for ADVANCED_OCR
        strategy = ProcessingStrategy.ADVANCED_OCR
        reward = 1.0
        next_features = features + np.random.randn(*features.shape) * 0.1
        
        selector.update(features, strategy, reward, next_features)
        
        # Q-values should change after update
        updated_q_values = selector.agent.get_q_values(features)
        assert not np.allclose(initial_q_values, updated_q_values)
        
    def test_calculate_reward(self, selector):
        """Test reward calculation"""
        # Test successful processing
        reward = selector.calculate_reward(
            processing_time=2.0,
            accuracy_score=0.9,
            resource_usage=0.5,
            expected_time=3.0,
            expected_accuracy=0.85
        )
        assert reward > 0  # Should be positive
        
        # Test poor performance
        reward = selector.calculate_reward(
            processing_time=10.0,  # Much slower than expected
            accuracy_score=0.5,    # Poor accuracy
            resource_usage=0.9,    # High resource usage
            expected_time=3.0,
            expected_accuracy=0.85
        )
        assert reward < 0  # Should be negative
        
    def test_save_and_load_model(self, selector, tmp_path):
        """Test model persistence"""
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Train the model
        selector.set_mode("train")
        for i in range(20):
            strategy = ProcessingStrategy(i % 4)
            reward = np.random.rand()
            selector.update(features, strategy, reward, features)
            
        # Save model
        save_path = tmp_path / "saved_model"
        selector.save_model(save_path)
        
        # Create new selector and load model
        new_selector = ProcessingStrategySelector(model_path=save_path)
        new_selector.load_model(save_path)
        
        # Compare Q-values
        original_q = selector.agent.get_q_values(features)
        loaded_q = new_selector.agent.get_q_values(features)
        
        assert np.allclose(original_q, loaded_q)
        
    def test_get_metrics(self, selector):
        """Test metrics collection"""
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Perform some selections and updates
        for _ in range(10):
            strategy, _ = selector.select_strategy(features)
            reward = np.random.rand()
            selector.update(features, strategy, reward, features)
            
        metrics = selector.get_metrics()
        
        assert "total_selections" in metrics
        assert "average_reward" in metrics
        assert "exploration_rate" in metrics
        assert metrics["total_selections"] == 10


class TestIntegrationWithMarker:
    """Test integration with actual marker components"""
    
    @pytest.fixture
    def mock_processor(self):
        """Create mock document processor"""
        processor = Mock()
        processor.process.return_value = {
            "text": "Extracted text",
            "accuracy": 0.9,
            "processing_time": 2.0,
            "resource_usage": 0.5
        }
        return processor
    
    def test_end_to_end_processing(self, tmp_path, mock_processor):
        """Test complete document processing with RL"""
        # Create selector
        selector = ProcessingStrategySelector(model_path=tmp_path / "model")
        
        # Create mock document
        doc_path = tmp_path / "document.pdf"
        doc_path.write_bytes(b"Mock PDF")
        
        # Extract features
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Select strategy
        strategy, confidence = selector.select_strategy(features)
        
        # Process document with selected strategy
        result = mock_processor.process(doc_path, strategy=strategy)
        
        # Calculate reward
        reward = selector.calculate_reward(
            processing_time=result["processing_time"],
            accuracy_score=result["accuracy"],
            resource_usage=result["resource_usage"],
            expected_time=3.0,
            expected_accuracy=0.85
        )
        
        # Update selector
        selector.update(features, strategy, reward, features)
        
        # Verify the process completed
        assert result["text"] is not None
        assert selector.get_metrics()["total_selections"] == 1


class TestSafeDeployment:
    """Test safe deployment features"""
    
    def test_fallback_mechanism(self, tmp_path):
        """Test fallback to rule-based selection"""
        from marker.rl_integration.deployment import SafeStrategyDeployment
        
        # Create selector that will fail
        selector = ProcessingStrategySelector(model_path=tmp_path / "model")
        
        # Create safe deployment wrapper
        safe_deployer = SafeStrategyDeployment(
            rl_selector=selector,
            fallback_strategy=ProcessingStrategy.STANDARD_OCR,
            rollout_percentage=0.5
        )
        
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Test that it works even if RL fails
        with patch.object(selector, 'select_strategy', side_effect=Exception("RL failed")):
            strategy = safe_deployer.select_strategy(features)
            assert strategy == ProcessingStrategy.STANDARD_OCR
            
    def test_gradual_rollout(self, tmp_path):
        """Test gradual rollout of RL selection"""
        from marker.rl_integration.deployment import SafeStrategyDeployment
        
        selector = ProcessingStrategySelector(model_path=tmp_path / "model")
        
        # Create safe deployment with 30% rollout
        safe_deployer = SafeStrategyDeployment(
            rl_selector=selector,
            fallback_strategy=ProcessingStrategy.STANDARD_OCR,
            rollout_percentage=0.3
        )
        
        features = np.random.rand(selector.feature_extractor.feature_dim)
        
        # Run many selections
        rl_count = 0
        fallback_count = 0
        
        for _ in range(1000):
            with patch.object(selector, 'select_strategy', return_value=(ProcessingStrategy.HYBRID_SMART, 0.9)):
                strategy = safe_deployer.select_strategy(features)
                if strategy == ProcessingStrategy.HYBRID_SMART:
                    rl_count += 1
                else:
                    fallback_count += 1
                    
        # Should be roughly 30% RL, 70% fallback
        rl_percentage = rl_count / (rl_count + fallback_count)
        assert 0.25 <= rl_percentage <= 0.35


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
