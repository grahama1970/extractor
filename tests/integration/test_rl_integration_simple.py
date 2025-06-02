"""Simple test for RL integration - matches actual implementation"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

# Import the RL components
from marker.rl_integration import (
    ProcessingStrategySelector,
    ProcessingStrategy,
    DocumentFeatureExtractor
)


class TestBasicIntegration:
    """Test basic RL integration functionality"""
    
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
        
    def test_select_strategy_basic(self, selector, tmp_path):
        """Test basic strategy selection"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)  # 10 features
            
            # Select strategy
            result = selector.select_strategy(
                document_path=pdf_path,
                quality_requirement=0.85,
                time_constraint=None,
                resource_constraint=None
            )
            
            # Check result structure
            assert 'strategy' in result
            assert 'confidence' in result
            assert isinstance(result['strategy'], ProcessingStrategy)
            assert 0 <= result['confidence'] <= 1
        
    def test_update_basic(self, selector, tmp_path):
        """Test basic update functionality"""
        # Create a dummy PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"Mock PDF content")
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            mock_extract.return_value = np.random.rand(10)
            
            # Provide feedback
            metrics = selector.update_from_result(
                document_path=pdf_path,
                strategy=ProcessingStrategy.ADVANCED_OCR,
                processing_time=2.0,
                accuracy_score=0.9,
                quality_requirement=0.85
            )
            
            # Should return metrics
            assert 'reward' in metrics
            assert isinstance(metrics['reward'], float)
    
    def test_save_and_load(self, selector, tmp_path):
        """Test model persistence"""
        # Save model
        save_path = tmp_path / "saved_model"
        selector.save_model(save_path)
        
        # Check files were created
        assert save_path.exists()
        
        # Create new selector and load
        new_selector = ProcessingStrategySelector(
            model_path=save_path,
            exploration_rate=0.1,
            enable_tracking=True
        )
        new_selector.load_model(save_path)
        
        # Should work without errors
        assert new_selector.agent is not None


class TestRealWorldScenario:
    """Test realistic usage scenario"""
    
    def test_processing_workflow(self, tmp_path):
        """Test complete document processing workflow"""
        # Create selector
        selector = ProcessingStrategySelector(
            model_path=tmp_path / "model",
            exploration_rate=0.2,
            enable_tracking=True
        )
        
        # Create test documents
        doc_paths = []
        for i in range(5):
            doc_path = tmp_path / f"document_{i}.pdf"
            doc_path.write_bytes(b"Mock PDF content " + str(i).encode())
            doc_paths.append(doc_path)
        
        # Mock feature extraction
        with patch.object(selector.feature_extractor, 'extract') as mock_extract:
            # Process multiple documents
            results = []
            for i, doc_path in enumerate(doc_paths):
                # Different features for each document
                mock_extract.return_value = np.random.rand(10)
                
                # Select strategy
                result = selector.select_strategy(
                    document_path=doc_path,
                    quality_requirement=0.8 + i * 0.02
                )
                
                # Simulate processing results
                processing_time = np.random.uniform(1, 5)
                accuracy = np.random.uniform(0.7, 0.95)
                
                # Update with feedback
                update_metrics = selector.update_from_result(
                    document_path=doc_path,
                    strategy=result['strategy'],
                    processing_time=processing_time,
                    accuracy_score=accuracy,
                    quality_requirement=0.8 + i * 0.02
                )
                
                results.append({
                    'doc': doc_path.name,
                    'strategy': result['strategy'].name,
                    'confidence': result['confidence'],
                    'reward': update_metrics['reward']
                })
            
            # Verify processing completed
            assert len(results) == 5
            assert all('strategy' in r for r in results)
            assert all('reward' in r for r in results)
            
            # Get final metrics
            metrics = selector.get_metrics()
            assert metrics['total_selections'] >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
