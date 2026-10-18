"""A persistent CPU-only forward-model connection, with no reference-video cache."""
import base64
import copy
import json
import queue
import subprocess
import threading
import uuid
import zlib
from pathlib import Path

import numpy as np

from .runners.media_contract import sha256


class ForwardModel:
    def __init__(self, runtime, physics, times, output):
        if not isinstance(runtime, dict) or set(runtime) != {'command'}:
            raise ValueError('native_runtime_requires_command')
        command = runtime['command']
        if not isinstance(command, list) or not command or any(not isinstance(v, str) for v in command):
            raise ValueError('native_runtime_command_must_be_argv')
        packet = copy.deepcopy(physics)
        packet['output_name'] = 'inverse_' + uuid.uuid4().hex
        if packet.get('target') != 'gravity' or packet.get('known_gravity') is not None:
            raise ValueError('native_target_must_be_unknown_gravity')
        self.root = Path(output)
        self.errors = (self.root / 'native_stderr.log').open('x')
        self.log = (self.root / 'native_stdout.log').open('x')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.errors, text=True, bufsize=1)
        self.lines = queue.Queue()
        def collect():
            for line in self.process.stdout:
                self.lines.put(line)
            self.lines.put(None)
        threading.Thread(target=collect, daemon=True).start()
        self.count = len(times)
        self.send(dict(physics=packet, observation_times_s=list(times)))
        try:
            ready = self.receive()
            if (ready.get('state') != 'ready' or not ready.get('CPU_only') or ready.get('GPU_devices') != [] or
                    ready.get('worker_sha256') != sha256(Path(__file__).with_name('native_physx_worker.py'))):
                raise ValueError('native_worker_binding_or_CPU_scope_mismatch')
            self.ready = ready
            self.body_count = len(ready['body_order'])
            (self.root / 'native_ready.json').write_text(json.dumps(ready, indent=2))
        except BaseException:
            self.close()
            raise

    def send(self, data):
        self.process.stdin.write(json.dumps(data, allow_nan=False) + '\n')
        self.process.stdin.flush()

    def receive(self):
        while True:
            line = self.lines.get(timeout=120)
            if line is None:
                raise RuntimeError('native_forward_process_ended: ' + str(self.process.poll()))
            self.log.write(line)
            self.log.flush()
            if line.startswith('__PHYSX_INVERSE__'):
                message = json.loads(line[len('__PHYSX_INVERSE__'):])
                if message.get('state') == 'failure':
                    raise RuntimeError('native_forward_failure: ' + message.get('traceback', ''))
                return message

    def evaluate(self, value):
        self.send(dict(value=float(value)))
        result = self.receive()
        if result.get('state') != 'evaluated' or result.get('value') != float(value):
            raise ValueError('native_forward_candidate_mismatch')
        if result.get('shape') != [self.count, self.body_count, 7]:
            raise ValueError('native_forward_observation_scope_mismatch')
        raw = zlib.decompress(base64.b64decode(result['poses_f64_zlib_base64']))
        poses = np.frombuffer(raw, dtype='<f8').reshape(result['shape'])
        if not np.isfinite(poses).all():
            raise ValueError('native_forward_nonfinite_pose')
        return poses

    def close(self):
        try:
            if self.process.poll() is None:
                self.send(dict(close=True))
                self.process.stdin.close()
                self.process.wait(timeout=30)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            if self.process.poll() is None:
                self.process.terminate()
        finally:
            self.log.close()
            self.errors.close()
