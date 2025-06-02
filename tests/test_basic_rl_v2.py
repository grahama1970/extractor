#!/usr/bin/env python3
from pathlib import Path
import numpy as np
from marker.rl_integration import ProcessingStrategySelector, ProcessingStrategy
from graham_rl_commons import RLState

# Test basic initialization
print("Testing RL integration...")

# Create selector with correct parameters
selector = ProcessingStrategySelector(
    model_path=Path("./test_model"),
    exploration_rate=0.1
)

print(f"✓ Selector initialized")
print(f"  Feature extractor: {selector.feature_extractor}")
print(f"  Agent: {selector.agent}")

# Test feature extraction with dummy data
features = np.random.rand(10).astype(np.float32)  # 10 features as expected
print(f"\n✓ Created dummy features: shape={features.shape}")

# Create RLState object
state = RLState(
    features=features,
    context={"quality_requirement": 0.8}
)

# Test strategy selection  
strategy = selector.select_strategy(state, None)
print(f"\n✓ Selected strategy: {strategy}")

# Test reward calculation
reward = selector.calculate_reward(
    processing_time=2.0,
    accuracy_score=0.9,
    resource_usage=0.5,
    expected_time=3.0,
    expected_accuracy=0.85
)
print(f"\n✓ Calculated reward: {reward:.3f}")

# Test with a real PDF file path (without actually processing)
test_pdf = Path("/tmp/test.pdf")
if not test_pdf.exists():
    # Create a dummy PDF for testing
    test_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

try:
    # Extract features from file
    file_features = selector.feature_extractor.extract_from_file(test_pdf)
    print(f"\n✓ Extracted features from file: shape={file_features.shape}")
    
    # Create state with quality requirement
    file_state = RLState(
        features=np.append(file_features, 0.8),  # Add quality requirement
        context={"file_path": str(test_pdf)}
    )
    
    # Select strategy for the file
    file_strategy = selector.select_strategy(file_state, None)
    print(f"✓ Selected strategy for file: {file_strategy}")
    
except Exception as e:
    print(f"\n⚠️  File processing test failed: {e}")

print("\n✅ Basic RL integration test completed!")
