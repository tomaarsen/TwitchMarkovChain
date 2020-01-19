
import sqlite3, glob

# This small and messy script *should* update the old database into one that works with the new 
# The old versions are not immediately deleted, just in case

sql = [
"ALTER TABLE MarkovStart RENAME TO _MarkovStart_old;",
"CREATE TABLE IF NOT EXISTS MarkovStart (\
    word1 TEXT COLLATE NOCASE, \
    word2 TEXT COLLATE NOCASE, \
    occurances INTEGER, \
    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)\
);",
"INSERT INTO MarkovStart (word1, word2, occurances)\
  SELECT output1, output2, count\
  FROM _MarkovStart_old;",
\
"ALTER TABLE MarkovGrammar RENAME TO _MarkovGrammar_old;",
"CREATE TABLE IF NOT EXISTS MarkovGrammar (\
    word1 TEXT COLLATE NOCASE,\
    word2 TEXT COLLATE NOCASE,\
    word3 TEXT COLLATE NOCASE,\
    occurances INTEGER,\
    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)\
);",
"INSERT INTO MarkovGrammar (word1, word2, word3, occurances)\
  SELECT input1, input2, output1, count\
  FROM _MarkovGrammar_old;",
]

def execute(db_file, sql, values=None, fetch=False):
    with sqlite3.connect(db_file) as conn:
        cur = conn.cursor()
        if values is None:
            cur.execute(sql)
        else:
            cur.execute(sql, values)
        conn.commit()
        if fetch:
            return cur.fetchall()

for db_file in glob.glob("*.db"):
    for s in sql:
        execute(db_file, s)