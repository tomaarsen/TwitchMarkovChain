
import sqlite3, glob, string

# This small and messy script *should* update the old database into one that works with the new 
# The old versions are not immediately deleted, just in case

class Database:
    def __init__(self, db_file):
        self.db_name = db_file
        self._execute_queue = []
    
    def add_execute_queue(self, sql, values=None):
        if values is not None:
            self._execute_queue.append([sql, values])
        else:
            self._execute_queue.append([sql])
    
    def execute_commit(self, fetch=False):
        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()
            cur.execute("begin")
            for sql in self._execute_queue:
                cur.execute(*sql)
            self._execute_queue.clear()
            if fetch:
                return cur.fetchall()

sql_list = []
for character in (list(string.ascii_uppercase + string.digits)):
    sql_list.append(f"""
    CREATE TABLE IF NOT EXISTS MarkovGrammar{character} (
        word1 TEXT COLLATE NOCASE,
        word2 TEXT COLLATE NOCASE,
        word3 TEXT COLLATE NOCASE,
        occurances INTEGER,
        PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
    );
    """)
    sql_list.append(f"""
    INSERT INTO MarkovGrammar{character} SELECT word1, word2, word3, occurances FROM MarkovGrammar WHERE word1 LIKE "{character}%"
    """)
    sql_list.append(f"""
    DELETE FROM MarkovGrammar WHERE word1 LIKE "{character}%"
    """)

    sql_list.append(f"""
    CREATE TABLE IF NOT EXISTS MarkovStart{character} (
        word1 TEXT COLLATE NOCASE, 
        word2 TEXT COLLATE NOCASE, 
        occurances INTEGER, 
        PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
    );
    """)
    sql_list.append(f"""
    INSERT INTO MarkovStart{character} SELECT word1, word2, occurances FROM MarkovStart WHERE word1 LIKE "{character}%"
    """)
    sql_list.append(f"""
    DELETE FROM MarkovStart WHERE word1 LIKE "{character}%"
    """)

character = "Other"
sql_list.append(f"""
CREATE TABLE IF NOT EXISTS MarkovGrammar{character} (
    word1 TEXT COLLATE NOCASE,
    word2 TEXT COLLATE NOCASE,
    word3 TEXT COLLATE NOCASE,
    occurances INTEGER,
    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
);
""")
sql_list.append(f"""
INSERT INTO MarkovGrammar{character} SELECT word1, word2, word3, occurances FROM MarkovGrammar
""")
sql_list.append(f"""
DELETE FROM MarkovGrammar
""")

sql_list.append(f"""
CREATE TABLE IF NOT EXISTS MarkovStart{character} (
    word1 TEXT COLLATE NOCASE, 
    word2 TEXT COLLATE NOCASE, 
    occurances INTEGER, 
    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
);
""")
sql_list.append(f"""
INSERT INTO MarkovStart{character} SELECT word1, word2, occurances FROM MarkovStart
""")
sql_list.append(f"""
DELETE FROM MarkovStart
""")

sql_list.append("DROP TABLE MarkovGrammar")
sql_list.append("DROP TABLE MarkovStart")

for db_file in glob.glob("*.db"):
    d = Database(db_file)
    for sql in sql_list:
        d.add_execute_queue(sql)
    try:
        d.execute_commit()
    except sqlite3.OperationalError:
        # MarkovGrammar/MarkovStart no longer exist
        pass