
import sqlite3, glob, string

# This small and messy script *should* update the old database into one that works with the new 
# The old versions are not immediately deleted, just in case

class Database:
    def __init__(self, channel):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"
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

#for db_file in glob.glob("*cubiedev.db"):
channel = "Cubiedev"
d = Database(channel)
for sql in sql_list:
    d.add_execute_queue(sql)
d.execute_commit()