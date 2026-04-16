# csv_viewer.spec - 軽量化最適構成

import os
import glob
import json
import tempfile
import sysconfig
from PyInstaller.utils.hooks import collect_submodules

project_dir = os.path.abspath(".")
block_cipher = None

# version.json からバージョン情報を読み込み、EXE に埋め込む Version Resource を生成
with open(os.path.join(project_dir, 'version.json'), encoding='utf-8') as _f:
    _vdata = json.load(_f)
_v = _vdata['version']
_vt_str = ', '.join(str(int(x)) for x in _v.split('.')) + ', 0'
_copyright = _vdata['copyright'].replace('\u00a9', '(C)')  # © → (C)

_version_info_txt = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({_vt_str}),
    prodvers=({_vt_str}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', u'{_vdata["author"]}'),
         StringStruct('FileDescription', u'{_vdata["app_name"]}'),
         StringStruct('FileVersion', u'{_v}'),
         StringStruct('InternalName', u'{_vdata["app_name"]}'),
         StringStruct('LegalCopyright', u'{_copyright}'),
         StringStruct('OriginalFilename', u'{_vdata["app_name"]}.exe'),
         StringStruct('ProductName', u'{_vdata["app_name"]}'),
         StringStruct('ProductVersion', u'{_v}')])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
_version_file = os.path.join(tempfile.gettempdir(), 'csview_version_info.txt')
with open(_version_file, 'w', encoding='utf-8') as _f:
    _f.write(_version_info_txt)

# mypyc ランタイム (.pyd) を site-packages 直下から収集
# charset_normalizer 等が mypyc コンパイル済みの場合、ランタイムが
# パッケージ外に置かれるため collect_submodules では捕捉できない
# sysconfig で実行中の Python 環境のパスを取得（ローカル venv / CI どちらでも動作）
_site_pkgs = sysconfig.get_paths()['purelib']
_mypyc_bins = [
    (p, '.')
    for p in glob.glob(os.path.join(_site_pkgs, '*__mypyc*.pyd'))
]

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=_mypyc_bins,
    datas=[
        ('assets/app_icon.ico', 'assets'),
        ('version.json', '.'),
    ],
    hiddenimports=[
        # PyQt6使用モジュールのみ（余分なWebEngineや3D除外）
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtSql',
        'PyQt6.QtSvg',  # 設定ダイアログの SVG アイコン描画に必要

        'pyzipper',  # 暗号化ZIP対応
        *collect_submodules('Crypto'),  # pyzipper AES暗号化の依存 (pycryptodome)

        *collect_submodules('charset_normalizer'),

        # XML対応（sqliteの内部、plistlibの依存など）
        'xml',
        'xml.etree.ElementTree',
    ],
    excludes=[
        # DuckDB（SQLite LIKEフォールバックに置き換え済み）
        'duckdb',
        # chardet（アプリは charset_normalizer のみ使用）
        'chardet',

        # 不使用のPyQt6拡張群
        'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtWebSockets', 'PyQt6.QtNetwork',
        'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuickWidgets',
        'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtXml',
        'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender',

        # 不要なデータ分析・画像・機械学習・科学計算系
        'pandas', 'scipy', 'numpy', 'matplotlib', 'seaborn',
        'sklearn', 'tensorflow', 'keras', 'torch',
        'cv2', 'PIL', 'skimage', 'imageio', 'xgboost',
        'bokeh', 'altair', 'plotly', 'dask',

        # GUI系や対話ツール
        'tkinter', 'tk', 'tcl', '_tkinter',
        'IPython', 'jupyter', 'notebook', 'ipykernel',

        # その他未使用の標準ライブラリやツール群
        'email', 'http', 'html', 'cgi', 'curses', 'readline', 'smtplib',
        'turtle', 'asyncio', 'unittest', 'doctest', 'profile', 'pdb',
        'test', 'pytz', 'dateutil', 'jinja2', 'sympy', 'networkx', 'babel',
        'multiprocessing', 'concurrent', 'xmlrpc',
        'ftplib', 'poplib', 'imaplib', 'mailbox', 'wsgiref',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ------------------------------------------------------------------
# a.datas フィルタリング（不要なQt6リソースを除外）
# ------------------------------------------------------------------

_KEEP_PLUGINS = {'platforms', 'sqldrivers', 'styles', 'imageformats', 'iconengines', 'tls', 'generic'}

def _norm(p):
    return p.replace('\\', '/').lower()

filtered_datas = []
for name, src, typ in a.datas:
    n = _norm(name)
    if 'pyqt6/qt6/translations/' in n:
        continue
    if 'pyqt6/qt6/qml/' in n:
        continue
    if 'pyqt6/qt6/qsci/' in n:
        continue
    if 'pyqt6/qt6/plugins/' in n:
        after_plugins = n.split('pyqt6/qt6/plugins/')[-1]
        plugin_cat = after_plugins.split('/')[0]
        if plugin_cat not in _KEEP_PLUGINS:
            continue
    filtered_datas.append((name, src, typ))

a.datas = filtered_datas

# ------------------------------------------------------------------
# a.binaries フィルタリング（不要なQt6/FFmpeg DLL を除外）
# ------------------------------------------------------------------
#
# 除外方針（不特定多数配布のため保守的に設定）:
#   - 除外する: QtMultimedia 依存の FFmpeg DLL、QML/Quick/Quick3D/Pdf/Designer 系
#   - 残す   : opengl32sw.dll（GPU非搭載PC用フォールバック）
#              d3dcompiler_47.dll（Qt6 RHI / D3D11 シェーダーコンパイラ）
#              Qt6Core/Gui/Widgets/Sql/OpenGL（動作に必須）
#
_EXCLUDE_BINS = {
    # FFmpeg（Qt6Multimedia が除外済みなので不要）
    'avcodec-61.dll',
    'avformat-61.dll',
    'avutil-59.dll',
    'swresample-5.dll',
    'swscale-8.dll',
    # QML / Quick 系
    'qt6qml.dll',
    'qt6qmlmodels.dll',
    'qt6qmlworkerscript.dll',
    'qt6qmllocalstorage.dll',
    'qt6qmlxmllistmodel.dll',
    'qt6quick.dll',
    'qt6quickcontrols2.dll',
    'qt6quickcontrols2basic.dll',
    'qt6quickcontrols2basicstyleimpl.dll',
    'qt6quickcontrols2fusion.dll',
    'qt6quickcontrols2fusionstyleimpl.dll',
    'qt6quickcontrols2imagine.dll',
    'qt6quickcontrols2imaginestyleimpl.dll',
    'qt6quickcontrols2material.dll',
    'qt6quickcontrols2materialstyleimpl.dll',
    'qt6quickcontrols2universal.dll',
    'qt6quickcontrols2universalstyleimpl.dll',
    'qt6quickcontrols2impl.dll',
    'qt6quickdialogs2.dll',
    'qt6quickdialogs2quickimpl.dll',
    'qt6quickdialogs2utils.dll',
    'qt6quicktemplates2.dll',
    'qt6quicklayouts.dll',
    'qt6quickparticles.dll',
    # Quick3D 系
    'qt6quick3d.dll',
    'qt6quick3dassetimport.dll',
    'qt6quick3dassetutils.dll',
    'qt6quick3deffects.dll',
    'qt6quick3dhelpers.dll',
    'qt6quick3diblbaker.dll',
    'qt6quick3dparticles.dll',
    'qt6quick3dphysics.dll',
    'qt6quick3dphysicshelpers.dll',
    'qt6quick3druntimerender.dll',
    'qt6quick3dutils.dll',
    'qt6labswavefrontmesh.dll',
    # PDF / Designer（実行時不要）
    'qt6pdf.dll',
    'qt6pdfquick.dll',
    'qt6designer.dll',
    'qt6designercomponents.dll',
    # シェーダーツール（RHI本体 d3dcompiler_47.dll を残せば不要）
    'qt6shadertools.dll',
}

a.binaries = [
    (name, src, typ) for name, src, typ in a.binaries
    if os.path.basename(src).lower() not in _EXCLUDE_BINS
]

# ------------------------------------------------------------------

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CSView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=True,
    icon='assets/app_icon.ico',
    version=_version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'msvcp140.dll',
        'python*.dll',
    ],
    name='CSView'
)
