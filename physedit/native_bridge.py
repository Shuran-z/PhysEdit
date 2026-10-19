"""Stream a CPU forward-model session through an SSH-forwarded Unix socket."""
import argparse
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


def connect(path):
    client = socket.socket(socket.AF_UNIX)
    client.connect(str(path))
    def upload():
        try:
            while True:
                chunk = sys.stdin.buffer.read1(65536)
                if not chunk:
                    break
                client.sendall(chunk)
        except OSError:
            pass
        finally:
            try:
                client.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    sender = threading.Thread(target=upload, daemon=True)
    sender.start()
    try:
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    finally:
        client.close()


def serve(path, command):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError('existing_native_socket_retained')
    capacity = threading.Semaphore(2)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            with capacity:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=sys.stderr.buffer)
                def upload():
                    try:
                        while True:
                            chunk = self.request.recv(65536)
                            if not chunk:
                                break
                            process.stdin.write(chunk)
                            process.stdin.flush()
                    except (OSError, BrokenPipeError):
                        pass
                    finally:
                        process.stdin.close()
                threading.Thread(target=upload, daemon=True).start()
                try:
                    while True:
                        chunk = process.stdout.read1(65536)
                        if not chunk:
                            break
                        self.request.sendall(chunk)
                    process.wait(timeout=30)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
    try:
        with Server(str(path), Handler) as server:
            os.chmod(path, 0o600)
            server.serve_forever()
    finally:
        path.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    c = sub.add_parser('connect')
    c.add_argument('--socket', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--socket', required=True)
    s.add_argument('--command-json', required=True)
    args = p.parse_args(argv)
    if args.mode == 'connect':
        connect(args.socket)
    else:
        data = json.loads(Path(args.command_json).read_text())
        command = data['command'] if isinstance(data, dict) else data
        if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
            raise ValueError('native_command_must_be_argv')
        serve(args.socket, command)
    return 0


if __name__ == '__main__':
    sys.exit(main())
