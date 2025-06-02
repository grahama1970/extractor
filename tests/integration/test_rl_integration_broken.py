"""Test RL integration for marker document processing - Fixed to match actual API"""

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
            exploration_rate=0.1,
            enable_tracking=True
        )
    
    def test_initialization(self, selector):
        """Test selector initialization"""
        assert selector.agent is not None
        assert selector.feature_extractor is not None
        assert len(ProcessingStrategy) == 4  # Check enum size
        
    def test_select_strategy_exploration(self, selector, tmp_path):
        """Test strategy selection in exploration mode"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)  # 10 features
            
            # Force exploration
            selector.set_mode("train")
            strategies_selected = set()
            
            # Run multiple times to ensure exploration
            for _ in range(100):
                result = selector.select_strategy(
                    document_path=pdf_path,
                    quality_requirement=0.85,
                    time_constraint=None,
                    resource_constraint=None
                )
                strategies_selected.add(result['strategy'])
                
            # Should explore multiple strategies
            assert len(strategies_selected) > 1
        
    def test_select_strategy_exploitation(self, selector, tmp_path):
        """Test strategy selection in exploitation mode"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction - consistent features
        mock_features = np.random.rand(10)
        
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = mock_features
            
            # Train the model with a clear preference
            selector.set_mode("train")
            
            # Simulate training: HYBRID_SMART is best for these features
            for _ in range(50):
                # Select strategy
                result = selector.select_strategy(pdf_path, quality_requirement=0.85)
                
                # Force update with high reward for HYBRID_SMART
                selector.update_from_result(
                    document_path=pdf_path,
                    strategy=ProcessingStrategy.HYBRID_SMART,
                    processing_time=2.0,
                    accuracy_score=0.95,
                    quality_requirement=0.85
                )
                
            # Switch to evaluation mode
            selector.set_mode("eval")
            
            # Should consistently select HYBRID_SMART
            strategies = []
            for _ in range(10):
                result = selector.select_strategy(pdf_path, quality_requirement=0.85)
                strategies.append(result['strategy'])
                
            # Most selections should be HYBRID_SMART
            hybrid_count = sum(1 for s in strategies if s == ProcessingStrategy.HYBRID_SMART)
            assert hybrid_count >= 8
        
    def test_update_from_result(self, selector, tmp_path):
        """Test that the agent learns from feedback"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)
            
            # Provide positive feedback for ADVANCED_OCR
            metrics = selector.update_from_result(
                document_path=pdf_path,
                strategy=ProcessingStrategy.ADVANCED_OCR,
                processing_time=2.0,
                accuracy_score=0.9,
                quality_requirement=0.85,
                extraction_metrics={
                    'pages_processed': 10,
                    'tables_extracted': 5
                }
            )
            
            # Should return metrics
            assert 'reward' in metrics
            assert metrics['reward'] != 0  # Should calculate non-zero reward
        
    def test_calculate_reward_private_method(self, selector):
        """Test reward calculation (private method)"""
        # Access private method for testing
        reward_fn = selector._calculate_reward
        
        # Test successful processing
        reward = reward_fn(
            processing_time=2.0,
            accuracy_score=0.9,
            resource_usage=0.5,
            quality_achieved=0.9,
            quality_required=0.85,
            time_constraint=5.0,
            resource_constraint=0.8
        )
        assert reward > 0  # Should be positive
        
        # Test poor performance
        reward = reward_fn(
            processing_time=10.0,  # Much slower
            accuracy_score=0.5,    # Poor accuracy
            resource_usage=0.9,    # High resource usage
            quality_achieved=0.5,
            quality_required=0.85,
            time_constraint=5.0,   # Exceeded time
            resource_constraint=0.8  # Exceeded resources
        )
        assert reward < 0  # Should be negative
        
    def test_save_and_load_model(self, selector, tmp_path):
        """Test model persistence"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)
            
            # Train the model
            selector.set_mode("train")
            for i in range(20):
                result = selector.select_strategy(pdf_path)
                selector.update_from_result(
                    document_path=pdf_path,
                    strategy=ProcessingStrategy(i % 4),
                    processing_time=np.random.uniform(1, 5),
                    accuracy_score=np.random.uniform(0.7, 0.95)
                )
                
        # Save model
        save_path = tmp_path / "saved_model"
        selector.save_model(save_path)
        
        # Create new selector and load model
        new_selector = ProcessingStrategySelector(
            model_path=save_path,
            exploration_rate=0.1,
            enable_tracking=True
        )
        new_selector.load_model(save_path)
        
        # Both should make similar predictions
        with patch.object(selector.feature_extractor, 'extract') as mock_extract1,              patch.object(new_selector.feature_extractor, 'extract') as mock_extract2:
            
            test_features = np.random.rand(10)
            mock_extract1.return_value = test_features
            mock_extract2.return_value = test_features
            
            result1 = selector.select_strategy(pdf_path)
            result2 = new_selector.select_strategy(pdf_path)
            
            # Strategies should match in eval mode
            selector.set_mode("eval")
            new_selector.set_mode("eval")
            
            result1 = selector.select_strategy(pdf_path)
            result2 = new_selector.select_strategy(pdf_path)
            assert result1['strategy'] == result2['strategy']
        
    def test_get_metrics(self, selector, tmp_path):
        """Test metrics collection"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)
            
            # Perform some selections and updates
            for _ in range(10):
                result = selector.select_strategy(pdf_path)
                selector.update_from_result(
                    document_path=pdf_path,
                    strategy=result['strategy'],
                    processing_time=np.random.uniform(1, 5),
                    accuracy_score=np.random.uniform(0.7, 0.95)
                )
                
        metrics = selector.get_metrics()
        
        assert "total_selections" in metrics
        assert "average_reward" in metrics
        assert "exploration_rate" in metrics
        assert metrics["total_selections"] >= 10


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
        selector = ProcessingStrategySelector(
            model_path=tmp_path / "model",
            exploration_rate=0.1,
            enable_tracking=True
        )
        
        # Create mock document
        doc_path = tmp_path / "document.pdf"
        doc_path.write_bytes(b"Mock PDF")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)
            
            # Select strategy
            result = selector.select_strategy(
                document_path=doc_path,
                quality_requirement=0.85,
                time_constraint=5.0,
                resource_constraint=0.8
            )
            strategy = result['strategy']
            
            # Process document with selected strategy
            process_result = mock_processor.process(doc_path, strategy=strategy)
            
            # Update selector with results
            update_metrics = selector.update_from_result(
                document_path=doc_path,
                strategy=strategy,
                processing_time=process_result["processing_time"],
                accuracy_score=process_result["accuracy"],
                quality_requirement=0.85
            )
            
            # Verify the process completed
            assert process_result["text"] is not None
            assert selector.get_metrics()["total_selections"] >= 1
            assert 'reward' in update_metrics


class TestSafeDeployment:
    """Test safe deployment features"""
    
    def test_fallback_mechanism(self, tmp_path):
        """Test fallback to rule-based selection"""
        from marker.rl_integration.deployment import SafeStrategyDeployment
        
        # Create selector that will fail
        selector = ProcessingStrategySelector(
            model_path=tmp_path / "model",
            exploration_rate=0.1
        )
        
        # Create safe deployment wrapper
        safe_deployer = SafeStrategyDeployment(
            rl_selector=selector,
            fallback_strategy=ProcessingStrategy.STANDARD_OCR,
            rollout_percentage=0.5
        )
        
        doc_path = tmp_path / "test.pdf"
        doc_path.write_bytes(b"Mock PDF")
        
        # Test that it works even if RL fails
        with patch.object(selector, 'select_strategy', side_effect=Exception("RL failed")):
            strategy = safe_deployer.select_strategy(doc_path)
            assert strategy == ProcessingStrategy.STANDARD_OCR
            
    def test_gradual_rollout(self, tmp_path):
        """Test gradual rollout of RL selection"""
        from marker.rl_integration.deployment import SafeStrategyDeployment
        
        selector = ProcessingStrategySelector(
            model_path=tmp_path / "model",
            exploration_rate=0.1
        )
        
        # Create safe deployment with 30% rollout
        safe_deployer = SafeStrategyDeployment(
            rl_selector=selector,
            fallback_strategy=ProcessingStrategy.STANDARD_OCR,
            rollout_percentage=0.3
        )
        
        doc_path = tmp_path / "test.pdf"
        doc_path.write_bytes(b"Mock PDF")
        
        # Run many selections
        rl_count = 0
        fallback_count = 0
        
        for _ in range(1000):
            mock_result = {'strategy': ProcessingStrategy.HYBRID_SMART, 'confidence': 0.9}
            with patch.object(selector, 'select_strategy', return_value=mock_result):
                strategy = safe_deployer.select_strategy(doc_path)
                if strategy == ProcessingStrategy.HYBRID_SMART:
                    rl_count += 1
                else:
                    fallback_count += 1
                    
        # Should be roughly 30% RL, 70% fallback
        rl_percentage = rl_count / (rl_count + fallback_count)
        assert 0.25 <= rl_percentage <= 0.35


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
