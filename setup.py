import setuptools

with open("README.md", mode="r") as f:
    long_description = f.read()

# from .AAA3A_utils.version import __version__  # doesn't work (ImportError: attempted relative import with no known parent package)
__version__ = 1.0

setuptools.setup(
    name="AAA3A_utils",
    version=__version__,
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
    install_requires=[
        "sentry_sdk",
    ],
)
