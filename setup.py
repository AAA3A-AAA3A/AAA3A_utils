import setuptools
import json

with open("README.md", mode="r") as f:
    long_description = f.read()

with open("AAA3A_utils/version.json", mode="r") as f:
    data = json.loads(f.read())
version = data["version"]

setuptools.setup(
    name="AAA3A_utils",
    version=version,
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
