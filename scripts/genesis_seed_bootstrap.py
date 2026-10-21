"""Explicit supplemental RNG control; never overwrite a renderer's fixed seed."""
import argparse
from pathlib import Path
import runpy
import sys


def install_seed_control(genesis,seed):
    original=genesis.init
    def initialize(*args,**kwargs):
        if args:raise ValueError('seed control requires named Genesis init arguments')
        existing=kwargs.get('seed')
        if existing is not None and existing!=seed:raise ValueError('renderer declares a different seed')
        return original(seed=seed,**{k:v for k,v in kwargs.items() if k!='seed'})
    genesis.init=initialize


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',required=True,type=int)
    parser.add_argument('renderer');parser.add_argument('arguments',nargs=argparse.REMAINDER);args=parser.parse_args()
    if not 0<=args.seed<2**31:parser.error('seed must be in [0, 2**31)')
    import genesis
    install_seed_control(genesis,args.seed)
    renderer=Path(args.renderer).resolve();sys.path.insert(0,str(renderer.parent))
    sys.argv=[str(renderer)]+args.arguments
    print('[seed_control] supplemental declared seed='+str(args.seed)+'; original production seed not recovered',flush=True)
    runpy.run_path(str(renderer),run_name='__main__')


if __name__=='__main__':main()
