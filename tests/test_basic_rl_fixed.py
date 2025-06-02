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
    metadata={"quality_requirement": 0.8}
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

print("\n✅ Basic RL integration test passed!")
