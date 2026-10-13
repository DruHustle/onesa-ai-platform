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
