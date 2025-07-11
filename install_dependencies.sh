#!/bin/bash
# Install dependencies for extractor project

echo "📦 Installing dependencies for extractor..."
echo "=================================="

# Navigate to extractor directory
cd /home/graham/workspace/experiments/extractor

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Please install uv first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    uv venv --python=3.10.11
fi

# Activate virtual environment
source .venv/bin/activate

# Install project dependencies
echo "📥 Installing project dependencies..."
uv pip install -e .

# Install additional dependencies that might be missing
echo "📥 Installing additional dependencies..."
uv add opencv-python
uv add pymupdf

# Verify installation
echo ""
echo "🔍 Verifying installations..."
python -c "import cv2; print('✅ cv2 version:', cv2.__version__)"
python -c "import fitz; print('✅ PyMuPDF version:', fitz.version)"

echo ""
echo "✅ Dependencies installed successfully!"
echo "🚀 To use extractor, activate the environment:"
echo "   cd /home/graham/workspace/experiments/extractor"
echo "   source .venv/bin/activate"