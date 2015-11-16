from setuptools import setup

setup(
    name = 'wamopacker',
    version = '0.0.1',
    description = 'packer tool.',
    #TODO
    # long_description = '',
    license = 'MIT',
    author = 'Warren Moore',
    author_email = 'warren@wamonite.com',
    url = 'https://github.com/wamonite/wamopacker',
    #TODO
    # classifiers = [
    # ],
    packages = ['wamopacker'],
    entry_points = dict(console_scripts = ['wamopacker=wamopacker.script:run']),
    package_data = {
        '': ['LICENSE', 'requirements.txt'],
        'wamopacker': ['data/templates/*']
    },
    #TODO
    # install_requires = [],
    # setup_requires = [],
    # tests_require = [],
    zip_safe = False
)
