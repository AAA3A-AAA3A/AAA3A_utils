import setuptools  # isort:skip

import os
import re

with open("README.md", mode="r") as f:
    long_description = f.read()

with open(
    os.path.join(os.path.join(os.path.dirname(__file__), "AAA3A_utils"), "__version__.py"), mode="r"
) as file:
    content = file.read()
__version__ = float(
    re.compile(r"__version__\s*=\s*(?P<version>\d+\.\d+)").search(content).groupdict()["version"]
)

setuptools.setup(
    name="AAA3A_utils",
    version=str(__version__),
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
        "colorama",
    ],
)
