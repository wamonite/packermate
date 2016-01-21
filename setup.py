from setuptools import setup

with open('README.rst', 'r') as f:
    readme = f.read()

setup(
    name = 'wamopacker',
    version = '0.6.0',
    description = 'Generate and run Packer build configurations from a simple YAML definition',
    long_description = readme,
    license = 'MIT',
    author = 'Warren Moore',
    author_email = 'warren@wamonite.com',
    url = 'https://github.com/wamonite/wamopacker',
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
    packages = ['wamopacker'],
    entry_points = dict(console_scripts = ['wamopacker=wamopacker.script:run']),
    package_data = {
        '': [
            'LICENSE',
        ],
        'wamopacker': [
            'data/*.json',
            'data/templates/*.template'
        ]
    },
    install_requires = [
        'pyaml',
    ],
    setup_requires = [
        'pytest-runner',
    ],
    tests_require = [
        'pytest-cov'
    ],
    zip_safe = False
)
