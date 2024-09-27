from setuptools import setup, find_packages

setup(
    name='aidigest',
    version='0.1',
    py_modules=['aidigest'],
    install_requires=[
        'aiofiles',
        'python-magic',
    ],
    entry_points={
        'console_scripts': [
            'aidigest=aidigest:main',
        ],
    },
)
