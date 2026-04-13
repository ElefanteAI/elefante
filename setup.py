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
    version="2.2.1",
    author="Elefante Contributors",
    author_email="elefante@proton.me",
    description="Local AI Memory System with Vector and Graph Storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ElefanteAI/elefante",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11,<3.12",
    install_requires=[
        "numpy>=1.26.0",
        "pydantic>=2.0.0,<3.0.0",
        "pyyaml>=6.0.0,<7.0.0",
        "chromadb==1.3.5",
        "fastapi==0.124.0",
        "uvicorn==0.38.0",
        "python-multipart>=0.0.9",
        "kuzu==0.11.3",
        "sentence-transformers==2.7.0",
        "mcp==1.23.1",
        "python-dotenv>=1.0.0,<2.0.0",
        "structlog>=24.1.0,<25.0.0",
        "aiosqlite>=0.19.0",
        "regex>=2023.12.25",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0,<24.0.0",
            "mypy>=1.5.0,<2.0.0",
            "ruff>=0.1.0,<0.2.0",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json"],
    },
    zip_safe=False,
)

