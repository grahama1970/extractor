"""Setup script for the llm_call validation package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="llm-validation-loop",
    version="0.1.0",
    author="Marker Contributors",
    author_email="marker@example.com",
    description="A flexible validation loop system for LLM calls with retry and plugin support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/VikParuchuri/marker",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "litellm>=1.0.0",
        "pydantic>=2.0.0",
        "loguru>=0.6.0",
        "rapidfuzz>=3.0.0",
        "redis>=4.0.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "beautifulsoup4>=4.12.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.20.0",
            "black>=22.0.0",
            "isort>=5.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "sphinx-autodoc-typehints>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "llm-validate=marker.llm_call.cli.app:app",
        ],
    },
)