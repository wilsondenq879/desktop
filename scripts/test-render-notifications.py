"""A dropped phone/socket or optional report write must not lose a real PNG."""
import asyncio,importlib.util,os,re,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('WEBUI_SECRET_KEY','synthetic-notification-test-only')
os.environ['OPENWEBUI_FIREWORKS_SKILL_ROOT']=str(ROOT/'resources/openwebui-managed-skills/fireworks-tech-graph')
spec=importlib.util.spec_from_file_location('notification_renderer',ROOT/'scripts/openwebui-fireworks-renderer-tool.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

async def main():
    async def offline(event):raise ConnectionError('synthetic disconnected UI')
    save=Path.write_text
    def no_report(path,*args,**kwargs):
        if path.name.endswith('.report.json'):raise OSError('synthetic optional report failure')
        return save(path,*args,**kwargs)
    with tempfile.TemporaryDirectory(prefix='notification-artifact-test-') as directory:
        os.environ['OPENWEBUI_FIREWORKS_OUTPUT_DIR']=directory
        req=SimpleNamespace(state=SimpleNamespace(fireworks_diagram={}))
        with patch.object(Path,'write_text',no_report):
            result=await module.Tools().render_technical_architecture('通知斷線測試',
                [{'id':'a','label':'工作站 A','level':0},{'id':'b','label':'工作站 B','level':1}],
                [{'from':'a','to':'b','direction':'both'}],__event_emitter__=offline,__request__=req)
        assert result.startswith('![') and req.state.fireworks_diagram['artifact']==result
        token=re.search(r'/([0-9]+-[a-f0-9]+)\.png',result)[1]
        assert (Path(directory)/(token+'.png')).read_bytes().startswith(b'\x89PNG')
    print('PASS: disconnected notifications + optional diagnostic failure preserve validated real artifact and request state')

asyncio.run(main())
