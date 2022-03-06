import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="AAA3A_utils",
    version="1.0.0",
    author="AAA3A",
    author_email=None,
    description="Utils for AAA3A-cogs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AAA3A-AAA3A/AAA3A_utils",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: MIT",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8.1",
)
