"""
Elefante - Local AI Memory System
Setup configuration for package installation
"""

from setuptools import find_packages, setup
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""


def requirements(section: str) -> list[str]:
    """Return exact runtime or development requirements from the canonical file.

    Release bundles and the installer use the hash-checked lock. Package metadata
    cannot carry hashes, but it must still describe the same direct versions and
    must never silently widen a security-reviewed dependency range.
    """
    requested = "runtime" if section == "runtime" else "development"
    active = "runtime"
    values: list[str] = []
    for raw_line in (Path(__file__).parent / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("# Development Dependencies"):
            active = "development"
            continue
        if not line or line.startswith("#") or active != requested:
            continue
        values.append(line)
    return values

setup(
    name="elefante",
    version="2.14.0",
    author="Elefante Contributors",
    author_email="elefante@proton.me",
    description="Local AI Memory System with Vector and Graph Storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ElefanteAI/elefante",
    # Runtime commands use ``python -m src.mcp...``. Include the namespace
    # itself so an installed wheel has the same import contract as a checkout.
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.11",
    install_requires=requirements("runtime"),
    extras_require={
        "dev": requirements("development"),
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json"],
    },
    zip_safe=False,
)
