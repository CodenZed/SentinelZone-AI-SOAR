"""Real loopback HTTP acceptance with an isolated SQLite DB and no external security systems."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import shutil
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = tempfile.mkdtemp(prefix='ai-soar-standalone-')
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        secret = secrets.token_urlsafe(40)
        env = {**os.environ, 'APP_ENV': 'test', 'DATABASE_URL': f'sqlite:///{Path(directory) / "demo.db"}',
               'CORE_MODE': 'standalone', 'CORE_TENANT_ID': '', 'CORE_API_TOKEN': '', 'AI_PROVIDER': 'mock',
               'SOAR_EXECUTOR': 'dry_run', 'BOOTSTRAP_TOKEN': secret, 'ENABLE_DEMO': 'true',
               'COOKIE_SECURE': 'false', 'PUBLIC_ORIGIN': f'http://127.0.0.1:{port}', 'WEB_PORT': str(port)}
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT, env=env, check=True)
        process = subprocess.Popen([sys.executable, 'scripts/serve_dev.py'], cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as c:
                for _ in range(150):
                    try:
                        if c.get('/health').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.05)
                else:
                    raise RuntimeError('HTTP startup failed')
                assert 'SentinelZone' in c.get('/').text
                assert c.get('/app.mjs').status_code == 200
                passwords = {r: secrets.token_urlsafe(24) for r in ('admin','analyst','operator')}
                assert c.post('/v1/auth/bootstrap', json={'tenant_id':'example-org','name':'admin',
                    'password':passwords['admin'],'bootstrap_token':secret}).status_code == 201

                def login(role):
                    c.cookies.clear()
                    result=c.post('/v1/auth/login', json={'tenant_id':'example-org','name':role,'password':passwords[role]})
                    assert result.status_code == 200, result.text
                    return {'X-CSRF-Token':c.cookies.get('sz_csrf')}

                headers=login('admin')
                for role in ('analyst','operator'):
                    result=c.post('/v1/users',headers=headers,json={'name':role,'role':role,'password':passwords[role]})
                    assert result.status_code == 201, result.text
                headers=login('analyst')
                demo=c.post('/v1/demo',headers=headers)
                assert demo.status_code == 201, demo.text
                incident_id=demo.json()['incidents'][0]['id']
                run=c.post('/v1/ai/analyze',headers=headers,json={'incident_id':incident_id})
                assert run.status_code == 201 and run.json()['trusted'] and run.json()['data_mode']=='TEST'
                result=c.post('/v1/actions',headers=headers,json={'incident_id':incident_id,'action_type':'BLOCK_IP',
                                  'target':'192.0.2.25','playbook_id':'SZ-PB-001'})
                assert result.status_code == 201, result.text
                action_id=result.json()['proposal_id']
                assert c.post(f'/v1/actions/{action_id}/approve',headers=headers,json={}).status_code == 403
                headers=login('operator')
                assert c.post(f'/v1/actions/{action_id}/approve',headers=headers,json={}).status_code == 200
                execution=c.post(f'/v1/actions/{action_id}/execute',headers=headers).json()
                assert execution['dry_run'] and execution['verification_result'] is True
                assert c.post(f'/v1/actions/{action_id}/execute',headers=headers).status_code == 409
                rollback=c.post(f'/v1/actions/{action_id}/rollback',headers=headers).json()
                assert rollback['restoration_verified'] and rollback['status']=='RESTORED'
                assert len(c.get('/v1/audit').json()['items']) >= 10
                print('PASS: standalone HTTP + UI assets, bootstrap, sessions, users, TEST ingestion, mock AI, independent approval, DRY RUN execution/verification, rollback/restoration, audit')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == '__main__':
    main()
