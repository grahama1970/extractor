#!/usr/bin/env python3
"""Benchmark RL-based strategy selection for marker"""

from pathlib import Path
import time
import numpy as np
from collections import defaultdict
from marker.rl_integration import ProcessingStrategySelector, ProcessingStrategy

def create_test_pdfs(num_docs=10):
    """Create test PDF files with varying characteristics"""
    test_dir = Path("/tmp/marker_benchmark")
    test_dir.mkdir(exist_ok=True)
    
    pdf_files = []
    # Create minimal valid PDFs with different sizes
    base_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000229 00000 n\n0000000327 00000 n\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n445\n%%EOF"
    
    for i in range(num_docs):
        pdf_path = test_dir / f"test_doc_{i}.pdf"
        # Add some variation to simulate different document types
        content = base_pdf + b" " * (i * 100)  # Vary size
        pdf_path.write_bytes(content)
        pdf_files.append(pdf_path)
    
    return pdf_files

def benchmark_strategy_selection():
    """Run benchmark tests on strategy selection"""
    print("🏁 Starting Marker RL Benchmark\n")
    
    # Create test documents
    test_files = create_test_pdfs(20)
    print(f"✓ Created {len(test_files)} test PDF files\n")
    
    # Initialize selector
    selector = ProcessingStrategySelector(
        model_path=Path("./benchmark_model"),
        exploration_rate=0.1,
        enable_tracking=True
    )
    print("✓ Initialized RL selector\n")
    
    # Benchmark different scenarios
    scenarios = [
        {"name": "High Quality", "quality": 0.95, "time_constraint": None},
        {"name": "Fast Processing", "quality": 0.8, "time_constraint": 2.0},
        {"name": "Resource Limited", "quality": 0.85, "resource_constraint": 0.5},
        {"name": "Balanced", "quality": 0.85, "time_constraint": 5.0, "resource_constraint": 0.7}
    ]
    
    for scenario in scenarios:
        print(f"📊 Testing scenario: {scenario['name']}")
        print(f"   Parameters: quality={scenario['quality']}", end="")
        if 'time_constraint' in scenario and scenario['time_constraint']:
            print(f", time≤{scenario['time_constraint']}s", end="")
        if 'resource_constraint' in scenario and scenario['resource_constraint']:
            print(f", resource≤{scenario['resource_constraint']}", end="")
        print()
        
        # Track strategy selections
        strategy_counts = defaultdict(int)
        selection_times = []
        
        for pdf_file in test_files:
            start_time = time.time()
            
            result = selector.select_strategy(
                document_path=pdf_file,
                quality_requirement=scenario['quality'],
                time_constraint=scenario.get('time_constraint'),
                resource_constraint=scenario.get('resource_constraint')
            )
            
            selection_time = time.time() - start_time
            selection_times.append(selection_time)
            strategy_counts[result['strategy'].name] += 1
            
            # Simulate processing and provide feedback
            # In real scenario, this would be actual processing results
            if result['strategy'] == ProcessingStrategy.HYBRID_SMART:
                accuracy = np.random.uniform(0.88, 0.95)
                proc_time = np.random.uniform(2.5, 3.5)
            elif result['strategy'] == ProcessingStrategy.ADVANCED_OCR:
                accuracy = np.random.uniform(0.85, 0.92)
                proc_time = np.random.uniform(3.0, 5.0)
            elif result['strategy'] == ProcessingStrategy.STANDARD_OCR:
                accuracy = np.random.uniform(0.78, 0.88)
                proc_time = np.random.uniform(1.5, 2.5)
            else:  # FAST_PARSE
                accuracy = np.random.uniform(0.65, 0.80)
                proc_time = np.random.uniform(0.5, 1.5)
            
            # Update with feedback
            selector.update_from_result(
                document_path=pdf_file,
                strategy=result['strategy'],
                processing_time=proc_time,
                accuracy_score=accuracy,
                quality_requirement=scenario['quality']
            )
        
        # Report results
        print(f"\n   Results:")
        print(f"   - Avg selection time: {np.mean(selection_times)*1000:.2f}ms")
        print(f"   - Strategy distribution:")
        for strategy, count in sorted(strategy_counts.items()):
            percentage = (count / len(test_files)) * 100
            print(f"     • {strategy}: {count} ({percentage:.1f}%)")
        print()
    
    # Test adaptation over time
    print("🔄 Testing adaptation over time...\n")
    
    # Train on specific pattern: HYBRID_SMART works best for quality > 0.9
    training_file = test_files[0]
    selector.agent.training = True
    
    print("   Training phase (20 iterations):")
    for i in range(20):
        result = selector.select_strategy(training_file, quality_requirement=0.92)
        
        # Give high reward for HYBRID_SMART, lower for others
        if result['strategy'] == ProcessingStrategy.HYBRID_SMART:
            accuracy = 0.94
        else:
            accuracy = 0.75
            
        selector.update_from_result(
            document_path=training_file,
            strategy=result['strategy'],
            processing_time=2.0,
            accuracy_score=accuracy,
            quality_requirement=0.92
        )
    
    # Test learned behavior
    selector.agent.training = False
    strategy_counts = defaultdict(int)
    
    print("\n   Evaluation phase (10 iterations):")
    for i in range(10):
        result = selector.select_strategy(training_file, quality_requirement=0.92)
        strategy_counts[result['strategy'].name] += 1
    
    print("   Strategy selection after training:")
    for strategy, count in sorted(strategy_counts.items()):
        percentage = (count / 10) * 100
        print(f"     • {strategy}: {count} ({percentage:.0f}%)")
    
    # Performance metrics
    print("\n📈 Overall Performance Metrics:")
    print(f"   - Total selections: {len(test_files) * len(scenarios)}")
    print(f"   - Agent steps: {selector.agent.training_steps}")
    print(f"   - Buffer size: {len(selector.agent.memory)}")
    print(f"   - Exploration rate: {selector.agent.epsilon:.3f}")
    
    # Cleanup
    for pdf_file in test_files:
        pdf_file.unlink()
    Path("/tmp/marker_benchmark").rmdir()
    
    print("\n✅ Benchmark completed!")

if __name__ == "__main__":
    benchmark_strategy_selection()
