from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('sqlalchemy')
datas = collect_data_files('sqlalchemy')

# Eksplicitno dodaj problematične module
hiddenimports += [
    'sqlalchemy.ext.declarative',
    'sqlalchemy.ext.baked',
    'sqlalchemy.sql.default_comparator',
]
