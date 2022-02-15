import converter

from setuptools import find_packages, setup

with open("README.md", encoding='utf-8') as file:
    read_me_description = file.read()

setup(
    name="converter",
    version=converter.__version__,
    author="Julia Los",
    author_email="los.julia.v@gmail.com",
    description="Currency converter",
    long_description=read_me_description,
    long_description_content_type="text/markdown",
    url='https://github.com/JuliaLos/CurrencyConverter',
    packages=find_packages(exclude=['tests']),
    install_requires=['matplotlib>=3.5.1', 'requests>=2.27.1'],
    python_requires='>=3.9',
    entry_points={
        'console_scripts': [
            'converter = converter.converter:main',
        ],
    },
    license='MIT',
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
)
