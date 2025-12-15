from setuptools import setup, find_packages

setup(
    name="sample-package",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "flask>=2.3.0",
        "requests>=2.28.0",
        "numpy~=1.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black",
        ]
    }
)
