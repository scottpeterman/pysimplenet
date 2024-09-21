from setuptools import setup, find_packages
from pkg_resources import parse_requirements
import os

# Function to parse requirements.txt
def parse_requirements_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return [str(req) for req in parse_requirements(f)]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pysimplenet",  # Replace with your actual project name
    version="0.1.0",  # Replace with your actual version
    author="Scott Peterman",
    author_email="scottpeterman@gmail.com",
    description="Pysimplenet, automation tools for network engineers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scottpeterman/pysimplenet",  # Replace with your project URL
    license="GPLv3",  # License field specifying GNU GPLv3
    packages=find_packages(exclude=['tests', 'dist', 'build', '*.egg-info']),  # Excluding non-package directories
    include_package_data=True,  # Includes files specified in MANIFEST.in
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',  # Specify your Python version
    install_requires=parse_requirements_file('requirements.txt'),
    entry_points={
        'console_scripts': [
            'pysshpass=pysshpass.__main__:main',
            'simplenet=simplenet.cli.simplenet:main',
            'vsndebug=simplenet.gui.vsndebug:main',
            'simplenet-gui=simplenet.gui.main_gui:main',

        ],
    },
    package_data={
        # Include package data files, such as images, templates, etc.
        'simplenet.gui.pyeasyedit': ['images/*.png', 'images/*.jpg', 'images/*.ico'],  # Example
        'simplenet.templates': ['*.ttp'],
        'project.drivers': ['*.yml', '*.yaml'],
        'project.vars': ['*.yml', '*.yaml'],
    },
    zip_safe=False,  # Forcing unzipped installation if needed for some cases
)
