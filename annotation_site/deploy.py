"""Package this app and six real media files; deploy through the existing SSH alias."""
import argparse
import datetime
import json
import subprocess
import tarfile
from pathlib import Path


def run(args,**kw):return subprocess.run(args,check=True,capture_output=True,**kw)


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='tx173');p.add_argument('--package',required=True);p.add_argument('--output',required=True)
    p.add_argument('--jump');a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stage='/home/ubuntu/phylabel-staging-'+stamp;archive=out/('release-'+stamp+'.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:
        source=Path(__file__).resolve().parent
        for f in source.rglob('*'):
            if f.is_file() and not any(x in f.parts for x in ('__pycache__','.private','data')):
                tar.add(f,arcname='annotation_site/'+f.relative_to(source).as_posix())
        tar.add(Path(a.package),arcname='package')
    run(['ssh',*(['-J',a.jump] if a.jump else []),a.host,'mkdir','-p',stage])
    run(['scp',*(['-J',a.jump] if a.jump else []),str(archive),a.host+':'+stage+'/release.tar.gz'])
    run(['ssh',*(['-J',a.jump] if a.jump else []),a.host,'tar','-xzf',stage+'/release.tar.gz','-C',stage])
    result=run(['ssh',*(['-J',a.jump] if a.jump else []),a.host,'sudo','python3',stage+'/annotation_site/install_remote.py',stage,stamp],text=True)
    print(result.stdout)
    report=json.loads(result.stdout.strip().splitlines()[-1])
    (out/'deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if report.get('created_accounts')==0:return
    invitations=run(['ssh',*(['-J',a.jump] if a.jump else []),a.host,'sudo','cat',report['private_invitations']]).stdout
    if json.loads(invitations):
        target=out/'invitations.private.json'
        if target.exists():target=out/('invitations-'+stamp+'.private.json')
        target.write_bytes(invitations);target.chmod(0o600)


if __name__=='__main__':main()
