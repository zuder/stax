# -*- mode: python -*-

block_cipher = None


a = Analysis(['stax.py'],
             pathex=['./'],
             binaries=None,
             datas=[('/home/py/py-env/2.7/lib/python2.7/site-packages/os_service_types/data/service-types.json','os_service_types/data/')],
             hiddenimports=['setuptools.msvc'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='stax',
          debug=False,
          strip=False,
          upx=True,
          console=False ) 
