"""
Elefante - Local AI Memory System
Setup configuration for package installation
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="elefante",
    version="1.6.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Local AI Memory System with Vector and Graph Storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/elefante",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "chromadb>=0.4.22",
        "kuzu>=0.1.0",
        "sentence-transformers>=2.2.2",
        "mcp>=1.0.0",
        "aiohttp>=3.9.0",
        "numpy>=1.24.0",
        "pydantic>=2.5.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "structlog>=23.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.12.0",
            "mypy>=1.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "elefante=src.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json"],
    },
    zip_safe=False,
)

# Made with Bob
