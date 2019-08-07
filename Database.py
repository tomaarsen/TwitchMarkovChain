
import sqlite3, logging, random, string
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, channel):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"
        self._start_queue = []
        self._rule_queue = []

        # TODO: Punctuation insensitivity.
        # My ideas for such an implementation have increased the generation time by ~5x. 
        # This was not worth it for me. I may revisit this at some point.

        sql = """
        CREATE TABLE IF NOT EXISTS MarkovStart (
            word1 TEXT COLLATE NOCASE, 
            word2 TEXT COLLATE NOCASE, 
            occurances INTEGER, 
            PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
        );
        """
        self.create_db(sql)
        for character in (string.ascii_lowercase + string.digits):
            sql = f"""
            CREATE TABLE IF NOT EXISTS {character}MarkovGrammar (
                word1 TEXT COLLATE NOCASE,
                word2 TEXT COLLATE NOCASE,
                word3 TEXT COLLATE NOCASE,
                occurances INTEGER,
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
            );
            """
            self.create_db(sql)
        sql = """
        CREATE TABLE IF NOT EXISTS WhisperIgnore (
            username TEXT,
            PRIMARY KEY (username)
        );
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
    
    def executemany(self, sql, values, fetch=False):
        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()
            cur.executemany(sql, values)
            conn.commit()
            if fetch:
                return cur.fetchall()
    
    def add_whisper_ignore(self, username):
        self.execute("INSERT OR IGNORE INTO WhisperIgnore(username) SELECT ?", (username,))
    
    def check_whisper_ignore(self, username):
        return self.execute("SELECT username FROM WhisperIgnore WHERE username = ?;", (username,), fetch=True)

    def remove_whisper_ignore(self, username):
        self.execute("DELETE FROM WhisperIgnore WHERE username = ?", (username,))

    """
    def add_start(self, out):
        # Add 1 to the occurances for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovStart SET occurances = occurances+1 WHERE word1 = ? AND word2 = ?", (out[0], out[1]))
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovStart(word1, word2, occurances) SELECT ?, ?, 1;", (out[0], out[1]))
        
    def add_rule(self, *args):
        # Potentially interesting: Remove case sensitivity for keys to improve average choice
        #arg = [arg.lower() if index < (len(args[0]) - 1) else arg for index, arg in enumerate(args[0])]

        # For all cases where the arguments are all the same, we want to check if the odds of recursion is < 50% 
        # And if it is, we can add the arguments.
        if self.check_equal(args[0]):
            if self.check_odds(args[0][0]):
                return

        # Add 1 to the occurances for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovGrammar SET occurances = occurances+1 WHERE word1 = ? AND word2 = ? AND word3 = ?", args[0])
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovGrammar(word1, word2, word3, occurances) SELECT ?, ?, ?, 1;", args[0])
    
    def check_equal(self, l):
        # Check if a list contains of items that are all identical
        return not l or l.count(l[0]) == len(l)

    def check_odds(self, arg):
        # Check if the odds of recursion are larger than 50%
        total = self.execute("SELECT SUM(occurances) FROM MarkovGrammar WHERE word1 = ? AND word2 = ?;", (arg, arg), fetch=True)
        recursion_case = self.execute("SELECT occurances FROM MarkovGrammar WHERE word1 = ? AND word2 = ? AND word3 = ?;", (arg, arg, arg), fetch=True)
        # If total is empty, then we don't want to add a recursive case 
        if len(total) == 0:
            return True
        # If recursion_case is empty but total isn't, then we do want to add a recursive case
        if len(recursion_case) == 0:
            return False
        # Otherwise return if recursion_case is more or equal to 50% of all cases
        return recursion_case[0][0] / total[0][0] >= 0.5
    """

    def get_next(self, *args):
        # Get all items
        data = self.execute("SELECT word3, occurances FROM MarkovGrammar where word1 = ? AND word2 = ?;", args[0], fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        print("Data length:", len(data), "with args", args)
        if len(data) == 0:
            return None
        return self.pick_word(data)
    
    def get_next_single(self, inp):
        # Get all items
        data = self.execute("SELECT word2, occurances FROM MarkovGrammar where word1 = ?;", (inp,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [inp] + [self.pick_word(data)]

    def get_next_single_start(self, inp):
        # Get all items
        data = self.execute("SELECT word2, occurances FROM MarkovStart where word1 = ?;", (inp,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [inp] + [self.pick_word(data)]

    def pick_word(self, data):
        # Add each item "occurances" times
        start_list = [tup[0] for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        return random.choice(start_list)

    def get_start(self):
        # TODO Prevent having to ask for all items
        # Get all items
        data = self.execute("SELECT * FROM MarkovStart;", fetch=True)
        
        # Add each item "occurances" times
        start_list = [list(tup[:-1]) for tup in data for _ in range(tup[-1])]
        
        # If nothing has ever been said
        if len(start_list) == 0:
            return ["There is no learned information yet", ""]

        # Pick a random starting key from this weighted list
        return random.choice(start_list)

    def add_rule_queue(self, item):
        # Filter out recursive case.
        if len(item) == 3 and item[0] == item[1] == item[2]:
            return
        self._rule_queue.append(item)
        
    def add_start_queue(self, item):
        self._start_queue.append(item)
    
    def commit_rules(self):
        if len(self._rule_queue) == 0:
            return
        self.executemany('INSERT OR REPLACE INTO MarkovGrammar (word1, word2, word3, occurances)\
        VALUES (?, ?, ?, coalesce((SELECT occurances + 1 FROM MarkovGrammar WHERE word1 = ? AND word2 = ? AND word3 = ?),1))', [rule + rule for rule in self._rule_queue])
        self._rule_queue.clear()

    def commit_start(self):
        if len(self._start_queue) == 0:
            return
        self.executemany('INSERT OR REPLACE INTO MarkovStart (word1, word2, occurances)\
        VALUES (?, ?, coalesce((SELECT occurances + 1 FROM MarkovStart WHERE word1 = ? AND word2 = ?),1))', [start + start for start in self._start_queue])
        self._start_queue.clear()
