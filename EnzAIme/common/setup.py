from setuptools import setup, find_packages

setup(
    name="enzaime_core",
    version="0.1.0",
    description="Shared core logic (config, scoring, mutation, embeddings, model) for ENZAIme",
    packages=find_packages(),
    python_requires=">=3.9",
)
