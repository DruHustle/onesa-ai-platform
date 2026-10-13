# Robot database schema

Generated from pinned `robot_api/main.py` local DDL and `robot_api/turso.py` remote staging journal DDL. No live records or credential export. Local sessions and safety state remain process-local with Turso; only bounded task history and the exclusive owner lease persist remotely. Restart starts stopped and cancels unfinished execution. The adapter supports separately verified staging and production bindings; source support does not qualify hosted production durability.

```sql
CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, csrf TEXT, expires REAL, name TEXT);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, owner TEXT, proposal TEXT, state TEXT,
                reason TEXT, created REAL, position REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS safety (
                id INTEGER PRIMARY KEY CHECK(id=1), stopped INTEGER NOT NULL);
            INSERT OR IGNORE INTO safety VALUES(1,1);

-- Environment-scoped remote journal; local sessions/safety are not uploaded.
CREATE TABLE IF NOT EXISTS robot_simulation_lease_v1 (id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS robot_simulation_tasks_v1 (id TEXT PRIMARY KEY,owner TEXT NOT NULL,proposal TEXT NOT NULL,state TEXT NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL,position REAL NOT NULL DEFAULT 0);
```
