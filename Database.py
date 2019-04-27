
import sqlite3, logging, random
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, channel):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"

        sql = """
        CREATE TABLE IF NOT EXISTS MarkovStart (
            output1 TEXT,
            output2 TEXT,
            count INTEGER,
            PRIMARY KEY (output1, output2)
        )
        """
        self.create_db(sql)
        sql = """
        CREATE TABLE IF NOT EXISTS MarkovGrammar (
            input1 TEXT,
            input2 TEXT,
            output1 TEXT,
            count INTEGER,
            PRIMARY KEY (input1, input2, output1)
        )
        """
        self.create_db(sql)
    
    def create_db(self, sql):
        logger.debug("Creating Database...")
        self.execute(sql)
        logger.debug("Database created.")

    def execute(self, sql, values=None, fetch=False):
        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()
            if values is None:
                cur.execute(sql)
            else:
                cur.execute(sql, values)
            conn.commit()
            if fetch:
                return cur.fetchall()
    
    def add_start(self, out):
        # Add 1 to the count for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovStart SET count = count+1 WHERE output1 = ? AND output2 = ?", (out[0], out[1]))
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovStart(output1, output2, count) SELECT ?, ?, 1;", (out[0], out[1]))

    def add_rule(self, *args):
        # Potentially interesting: Remove case sensitivity for keys to improve average choice
        #arg = [arg.lower() if index < (len(args[0]) - 1) else arg for index, arg in enumerate(args[0])]

        # Only if not all arguments are identical will the values be entered into the system.
        # This prevents: LUL + LUL -> LUL
        # Which could be a cause of recursion.
        if self.checkEqual(args[0]):
            return

        # Add 1 to the count for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovGrammar SET count = count+1 WHERE input1 = ? AND input2 = ? AND output1 = ?", args[0])
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovGrammar(input1, input2, output1, count) SELECT ?, ?, ?, 1;", args[0])
    
    def checkEqual(self, l):
        return not l or l.count(l[0]) == len(l)

    def get_next(self, *args):
        #return self.execute("SELECT word3 FROM MarkovChain WHERE word1=? AND word2=? ORDER BY RANDOM() LIMIT 1;", args[0], fetch=True)
        # Get all items
        data = self.execute("SELECT output1, count FROM MarkovGrammar where input1=? AND input2=?;", args[0], fetch=True)
        # Add each item "count" times
        start_list = [tup[0] for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        if len(start_list) == 0:
            return None
        return random.choice(start_list)
    
    def get_next_single(self, inp):
        # Get all items
        data = self.execute("SELECT input2, count FROM MarkovGrammar where input1=?;", (inp,), fetch=True)
        # Add each item "count" times
        start_list = [tup[0] for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        if len(start_list) == 0:
            return None
        return [inp] + [random.choice(start_list)]

    def get_start(self):
        #return list(self.execute("SELECT word2, word3 FROM MarkovChain WHERE word1='<START>' ORDER BY RANDOM() LIMIT 1;", fetch=True)[0])
        #return list(self.execute("SELECT output1, output2 FROM MarkovStart ORDER BY RANDOM() LIMIT 1;", fetch=True)[0])
        # Get all items
        data = self.execute("SELECT * FROM MarkovStart;", fetch=True)
        # Add each item "count" times
        start_list = [list(tup[:-1]) for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        return random.choice(start_list)