"""A800 evaluation host: physics-only runs must not create an OpenGL/EGL context (the container has no NVIDIA EGL
vendor library for the 595 driver). When genesis.vis.rasterizer is imported, Rasterizer.build is replaced by a version
that keeps the scene-graph context but does not start pyrender's OffscreenRenderer; destroy() tolerates the missing
renderer. Only rendering is affected; the rigid-body solver is untouched. Active when this directory is on PYTHONPATH."""
import importlib.abc, importlib.util, sys

TARGET = 'genesis.vis.rasterizer'


def _patch(mod):
    R = mod.Rasterizer

    def build(self):
        if self._context is None:
            return
        self._renderer = None
        self.visualizer = self._context.visualizer

    orig_destroy = R.destroy

    def destroy(self):
        if getattr(self, '_renderer', None) is None:
            return
        return orig_destroy(self)

    R.build, R.destroy = build, destroy


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != TARGET:
            return None
        for f in sys.meta_path:
            if f is self or not hasattr(f, 'find_spec'):
                continue
            spec = f.find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                orig = spec.loader.exec_module

                def exec_module(module, _orig=orig):
                    _orig(module)
                    _patch(module)
                spec.loader.exec_module = exec_module
                return spec
        return None


sys.meta_path.insert(0, _Finder())
