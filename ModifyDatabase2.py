
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

# " UNION ".join([f"SELECT * FROM MarkovGrammar{c}" for c in list(string.ascii_uppercase + string.digits) + ["Other"]])
# SELECT * FROM MarkovGrammarA UNION SELECT * FROM MarkovGrammarB UNION SELECT * FROM MarkovGrammarC UNION SELECT * FROM MarkovGrammarD UNION SELECT * FROM MarkovGrammarE UNION SELECT * FROM MarkovGrammarF UNION SELECT * FROM MarkovGrammarG UNION SELECT * FROM MarkovGrammarH UNION SELECT * FROM MarkovGrammarI UNION SELECT * FROM MarkovGrammarJ UNION SELECT * FROM MarkovGrammarK UNION SELECT * FROM MarkovGrammarL UNION SELECT * FROM MarkovGrammarM UNION SELECT * FROM MarkovGrammarN UNION SELECT * FROM MarkovGrammarO UNION SELECT * FROM MarkovGrammarP UNION SELECT * FROM MarkovGrammarQ UNION SELECT * FROM MarkovGrammarR UNION SELECT * FROM MarkovGrammarS UNION SELECT * FROM MarkovGrammarT UNION SELECT * FROM MarkovGrammarU UNION SELECT * FROM MarkovGrammarV UNION SELECT * FROM MarkovGrammarW UNION SELECT * FROM MarkovGrammarX UNION SELECT * FROM MarkovGrammarY UNION SELECT * FROM MarkovGrammarZ UNION SELECT * FROM MarkovGrammar0 UNION SELECT * FROM MarkovGrammar1 UNION SELECT * FROM MarkovGrammar2 UNION SELECT * FROM MarkovGrammar3 UNION SELECT * FROM MarkovGrammar4 UNION SELECT * FROM MarkovGrammar5 UNION SELECT * FROM MarkovGrammar6 UNION SELECT * FROM MarkovGrammar7 UNION SELECT * FROM MarkovGrammar8 UNION SELECT * FROM MarkovGrammar9 UNION SELECT * FROM MarkovGrammarOther
# " UNION ".join([f"SELECT * FROM MarkovStart{c}" for c in list(string.ascii_uppercase + string.digits) + ["Other"]])
# SELECT * FROM MarkovStartA UNION SELECT * FROM MarkovStartB UNION SELECT * FROM MarkovStartC UNION SELECT * FROM MarkovStartD UNION SELECT * FROM MarkovStartE UNION SELECT * FROM MarkovStartF UNION SELECT * FROM MarkovStartG UNION SELECT * FROM MarkovStartH UNION SELECT * FROM MarkovStartI UNION SELECT * FROM MarkovStartJ UNION SELECT * FROM MarkovStartK UNION SELECT * FROM MarkovStartL UNION SELECT * FROM MarkovStartM UNION SELECT * FROM MarkovStartN UNION SELECT * FROM MarkovStartO UNION SELECT * FROM MarkovStartP UNION SELECT * FROM MarkovStartQ UNION SELECT * FROM MarkovStartR UNION SELECT * FROM MarkovStartS UNION SELECT * FROM MarkovStartT UNION SELECT * FROM MarkovStartU UNION SELECT * FROM MarkovStartV UNION SELECT * FROM MarkovStartW UNION SELECT * FROM MarkovStartX UNION SELECT * FROM MarkovStartY UNION SELECT * FROM MarkovStartZ UNION SELECT * FROM MarkovStart0 UNION SELECT * FROM MarkovStart1 UNION SELECT * FROM MarkovStart2 UNION SELECT * FROM MarkovStart3 UNION SELECT * FROM MarkovStart4 UNION SELECT * FROM MarkovStart5 UNION SELECT * FROM MarkovStart6 UNION SELECT * FROM MarkovStart7 UNION SELECT * FROM MarkovStart8 UNION SELECT * FROM MarkovStart9 UNION SELECT * FROM MarkovStartOther