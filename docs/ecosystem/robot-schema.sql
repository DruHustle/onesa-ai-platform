CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, csrf TEXT, expires REAL, name TEXT);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, owner TEXT, proposal TEXT, state TEXT,
                reason TEXT, created REAL, position REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS safety (
                id INTEGER PRIMARY KEY CHECK(id=1), stopped INTEGER NOT NULL);
            INSERT OR IGNORE INTO safety VALUES(1,1);
