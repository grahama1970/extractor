# No Sandbox Verification

This document confirms runtime capabilities for this Codex CLI session.

- approval_policy: `never`
- sandbox_mode: `danger-full-access`
- network_access: `enabled`
- cwd: `/home/graham/workspace/experiments/extractor`

## Summary

- Network: Successfully reached a public endpoint with HTTP 200.
- Filesystem: Read outside workspace and wrote to `/tmp` successfully.
- Database: Created and queried a local SQLite database in `/tmp`.

## Evidence

### Network check
Command:
```
curl -sS -o /dev/null -w 'HTTP %{http_code} from %{remote_ip} (type:%{content_type}, bytes:%{size_download})\n' https://example.com
```
Output:
```
HTTP 200 from 23.220.75.245 (type:text/html, bytes:1256)
```

### Filesystem check
Commands and output:
```
ls -ld / /etc /tmp
# =>
drwxr-xr-x  24 root root   4096 Jul  2 14:25 /
drwxr-xr-x 184 root root  12288 Aug 30 06:13 /etc
drwxrwxrwt 699 root root 528384 Aug 30 20:33 /tmp

head -n 3 /etc/os-release
# =>
PRETTY_NAME="Ubuntu 24.04.2 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"

echo 'codex_write_ok' > /tmp/codex_fs_check.txt && ls -l /tmp/codex_fs_check.txt && cat /tmp/codex_fs_check.txt
# =>
-rw-rw-r-- 1 graham graham 15 Aug 30 20:33 /tmp/codex_fs_check.txt
codex_write_ok
```

### Database (SQLite) check
Command:
```
python - << 'PY'
import sqlite3, os
path = '/tmp/codex_net_check.db'
conn = sqlite3.connect(path)
c = conn.cursor()
c.execute('CREATE TABLE t(x int)')
c.executemany('INSERT INTO t(x) VALUES(?)', [(1,), (2,), (3,)])
conn.commit()
val = c.execute('SELECT sum(x) FROM t').fetchone()[0]
conn.close()
print('sqlite_sum=', val)
print('db_path=', path)
print('db_exists=', os.path.exists(path))
PY
ls -l /tmp/codex_net_check.db
```
Output:
```
sqlite_sum= 6
db_path= /tmp/codex_net_check.db
db_exists= True
-rw-r--r-- 1 graham graham 8192 Aug 30 20:33 /tmp/codex_net_check.db
```

## Notes
- Remote database connectivity is available via general network access; supply credentials and drivers (e.g., `psycopg`, `mysqlclient`) as needed.
- No sandbox restrictions were observed: reading system files and writing to `/tmp` succeeded.
