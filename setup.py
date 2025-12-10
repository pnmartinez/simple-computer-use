from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="llm-pc-control",
    version="0.4.4",
    author="LLM PC Control Team",
    author_email="pablonavaber@hotmail.com",
    description="Control your computer with natural language commands using LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pnmartinez/llm-pc-control",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11,<3.13",  # Updated for Python 3.11/3.12 migration
    install_requires=[
        "pyautogui>=0.9.53",
        "pillow>=10.3.0",  # Updated for Python 3.11/3.12
        "numpy>=1.26.0",  # Updated: required for Python 3.12 compatibility
        "opencv-python>=4.9.0",  # Updated for better numpy 1.26+ compatibility
        "easyocr>=1.6.0",
        # paddleocr removed - not used in current codebase (see ANALISIS_PADDLEPADDLE.md)
        "ollama>=0.1.0",
        "requests>=2.25.0",
        "tqdm>=4.60.0",
    ],
    # Entry point removed - application uses 'python -m llm_control voice-server' instead
    # entry_points={
    #     "console_scripts": [
    #         "llm-pc-control=llm_control.cli:main",
    #     ],
    # },
) 