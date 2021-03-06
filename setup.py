from setuptools import setup

with open('README.rst', 'r') as f:
    readme = f.read()

setup(
    name = 'packermate',
    version = '0.17.0',
    description = 'Generate and run Packer build configurations from a simple YAML definition',
    long_description = readme,
    license = 'MIT',
    author = 'Warren Moore',
    author_email = 'warren@wamonite.com',
    url = 'https://github.com/wamonite/packermate',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities'
    ],
    packages = ['packermate'],
    entry_points = dict(console_scripts = ['packermate=packermate.script:run']),
    package_data = {
        '': [
            'LICENSE',
        ],
        'packermate': [
            'data/*.json',
            'data/templates/*.template'
        ]
    },
    install_requires = [
        'pyaml',
        'semantic_version',
        'requests',
    ],
    extras_require = {
        'AWS':  [
            "boto3"
        ]
    },
    zip_safe = False
)
