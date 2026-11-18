"""Fail-closed CLI; output directories are strictly new-only."""
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .engine import compare
from .io import InputError, read_json
from .report import render_html

class Parser(argparse.ArgumentParser):
    def error(self,message): raise InputError('arguments: '+message)


def parser():
    p=Parser(prog='schema-boundary',description='Find schema compatibility counterexamples inside an explicit finite JSON domain.')
    p.add_argument('--version',action='version',version='%(prog)s '+__version__)
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compare',help='find source-accepted, target-rejected JSON')
    c.add_argument('source',type=Path); c.add_argument('target',type=Path)
    c.add_argument('--domain',type=Path,help='JSON domain options (see README)')
    c.add_argument('--output',type=Path,help='new directory for report.json/report.html/witness.json')
    c.add_argument('--accept-bounded',action='store_true',help='explicitly allow bounded-compatible to exit 0 instead of 3')
    c.add_argument('--timeout-ms',type=int,default=5000)
    c.add_argument('--rlimit',type=int,default=2000000)
    return p


def main(argv=None):
    try:
        args=parser().parse_args(argv)
        if args.output:
            if args.output.exists() or args.output.is_symlink(): raise InputError('output directory already exists; nothing is overwritten')
            if not args.output.parent.is_dir(): raise InputError('output parent does not exist')
        report=compare(read_json(args.source),read_json(args.target),domain=read_json(args.domain) if args.domain else None,
                       timeout_ms=args.timeout_ms,rlimit=args.rlimit)
        text=json.dumps(report,ensure_ascii=True,indent=2,allow_nan=False)+'\n'
        page=render_html(report)
        if args.output:
            # mkdir is the exclusive ownership operation. Never replace existing
            # files. I/O failure may leave a partial newly-created directory.
            args.output.mkdir()
            files={'report.json':text,'report.html':page}
            if report['status']=='counterexample': files['witness.json']=report['witness_json']+'\n'
            for name,body in files.items():
                with (args.output/name).open('x',encoding='utf8',newline='\n') as f: f.write(body)
        sys.stdout.write(text)
        status=report['status']
        if status=='bounded-compatible': return 0 if args.accept_bounded else 3
        return {'counterexample':1,'empty-source':4}.get(status,2)
    except (InputError,OSError,ValueError) as exc:
        message=(exc.strerror or type(exc).__name__) if isinstance(exc,OSError) else str(exc)
        sys.stdout.write(json.dumps({'schema_version':1,'status':'error','reason':message},ensure_ascii=True)+'\n')
        return 2

if __name__=='__main__': raise SystemExit(main())
