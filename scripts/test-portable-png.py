"""Exercise the no-Cairo path used by a fresh Windows installation."""
import importlib.util
import struct
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph/scripts'))
from png_export import export_png

real_find=importlib.util.find_spec
def without_cairo(name,*args,**kwargs):
    return None if name=='cairosvg' else real_find(name,*args,**kwargs)

with tempfile.TemporaryDirectory(prefix='portable-png-test-') as folder:
    source=Path(folder)/'source.svg';output=Path(folder)/'output.png'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200" viewBox="0 0 400 200"><rect width="400" height="200" fill="#0B0F17"/><text x="20" y="100" fill="white" font-family="PingFang TC,Microsoft JhengHei,sans-serif">繁體中文 Network</text></svg>')
    with patch('importlib.util.find_spec',side_effect=without_cairo),patch('shutil.which',return_value=None):
        result=export_png(source,output,800)
    assert result['renderer']=='resvg_py' and struct.unpack('>II',output.read_bytes()[16:24])==(800,400)
    try:export_png(source,output,32769)
    except ValueError:pass
    else:raise AssertionError('Unbounded raster allocation')
print('PASS: no Cairo/GTK, real resvg binary PNG, exact dimensions, pixel budget')
