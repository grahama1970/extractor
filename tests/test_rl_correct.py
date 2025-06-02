#!/usr/bin/env python3
from pathlib import Path
import numpy as np
from marker.rl_integration import ProcessingStrategySelector, ProcessingStrategy

# Test basic initialization
print("Testing marker RL integration...")

# Create selector with correct parameters
selector = ProcessingStrategySelector(
    model_path=Path("./test_model"),
    exploration_rate=0.1
)

print(f"✓ Selector initialized")
print(f"  Feature extractor: {selector.feature_extractor}")
print(f"  Agent: {selector.agent}")

# Create a test PDF file
test_pdf = Path("/tmp/test_marker.pdf")
# Create a minimal valid PDF
pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000229 00000 n\n0000000327 00000 n\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n445\n%%EOF"
test_pdf.write_bytes(pdf_content)

print(f"\n✓ Created test PDF: {test_pdf}")

# Test strategy selection
try:
    result = selector.select_strategy(
        document_path=test_pdf,
        quality_requirement=0.85,
        time_constraint=5.0
    )
    
    print(f"\n✓ Strategy selection result:")
    print(f"  Strategy: {result.get('strategy')}")
    print(f"  Confidence: {result.get('confidence', 'N/A')}")
    print(f"  Features shape: {result.get('features', []).shape if isinstance(result.get('features'), np.ndarray) else 'N/A'}")
    
except Exception as e:
    print(f"\n✗ Strategy selection failed: {e}")
    import traceback
    traceback.print_exc()

# Test reward calculation
try:
    reward = selector.calculate_reward(
        processing_time=2.0,
        accuracy_score=0.9,
        resource_usage=0.5,
        expected_time=3.0,
        expected_accuracy=0.85
    )
    print(f"\n✓ Calculated reward: {reward:.3f}")
except Exception as e:
    print(f"\n✗ Reward calculation failed: {e}")

# Test metrics
try:
    metrics = selector.get_metrics()
    print(f"\n✓ Metrics retrieved:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
except Exception as e:
    print(f"\n✗ Metrics retrieval failed: {e}")

# Clean up
test_pdf.unlink(missing_ok=True)

print("\n✅ marker RL integration test completed!")
