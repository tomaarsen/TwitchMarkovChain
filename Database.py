
import sqlite3, logging, random, string, time
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, channel):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"
        #self._start_queue = []
        #self._rule_queue = []
        self._execute_queue = []

        # TODO: Punctuation insensitivity.
        # My ideas for such an implementation have increased the generation time by ~5x. 
        # This was not worth it for me. I may revisit this at some point.

        #'''
        start_t = time.time()
        sql = """
        CREATE TABLE IF NOT EXISTS MarkovStart (
            word1 TEXT COLLATE NOCASE, 
            word2 TEXT COLLATE NOCASE, 
            occurances INTEGER, 
            PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
        );
        """
        self.add_execute_queue(sql)
        for character in (list(string.ascii_uppercase + string.digits) + ["Other"]):
            sql = f"""
            CREATE TABLE IF NOT EXISTS MarkovGrammar{character} (
                word1 TEXT COLLATE NOCASE,
                word2 TEXT COLLATE NOCASE,
                word3 TEXT COLLATE NOCASE,
                occurances INTEGER,
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
            );
            """
            self.add_execute_queue(sql)
        sql = """
        CREATE TABLE IF NOT EXISTS WhisperIgnore (
            username TEXT,
            PRIMARY KEY (username)
        );
        """
        self.add_execute_queue(sql)
        self.execute_commit()
        print(f"{time.time() - start_t:.4f}s execute time")
        #'''
    
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
                #print(sql)
                cur.execute(*sql)
            self._execute_queue.clear()
            if fetch:
                return cur.fetchall()

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
    
    """
    def executemany(self, sql, values, fetch=False):
        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()
            cur.executemany(sql, values)
            conn.commit()
            if fetch:
                return cur.fetchall()
    """
    
    def get_suffix(self, character):
        if character.lower() in (string.ascii_lowercase + string.digits):
            return character.upper()
        return "Other"

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
    
    """
    def check_equal(self, l):
        # Check if a list contains of items that are all identical
        return not l or l.count(l[0]) == len(l)

    """
    def check_odds(self, arg):
        # Check if the odds of recursion are larger than 50%
        total = self.execute(f"SELECT SUM(occurances) FROM MarkovGrammar{self.get_suffix(arg[0])} WHERE word1 = ? AND word2 = ?;", (arg, arg), fetch=True)
        recursion_case = self.execute(f"SELECT occurances FROM MarkovGrammar{self.get_suffix(arg[0])} WHERE word1 = ? AND word2 = ? AND word3 = ?;", (arg, arg, arg), fetch=True)
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
        data = self.execute(f"SELECT word3, occurances FROM MarkovGrammar{self.get_suffix(args[0][0][0])} where word1 = ? AND word2 = ?;", args[0], fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        #print("Data length:", len(data), "with args", args)
        if len(data) == 0:
            return None
        return self.pick_word(data)
    
    def get_next_single(self, word):
        # Get all items
        data = self.execute(f"SELECT word2, occurances FROM MarkovGrammar{self.get_suffix(word[0])} where word1 = ?;", (word,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [word] + [self.pick_word(data)]

    def get_next_single_start(self, word):
        # Get all items
        data = self.execute("SELECT word2, occurances FROM MarkovStart where word1 = ?;", (word,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [word] + [self.pick_word(data)]

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
        if self.check_equal(item):
            return
        #if self.check_equal(item):
        #    if self.check_odds(item[0]):
        #        return
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovGrammar{self.get_suffix(item[0][0])} (word1, word2, word3, occurances) VALUES (?, ?, ?, coalesce((SELECT occurances + 1 FROM MarkovGrammar{self.get_suffix(item[0][0])} WHERE word1 = ? AND word2 = ? AND word3 = ?), 1))', values=item + item)
        
    def add_start_queue(self, item):
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovStart (word1, word2, occurances) VALUES (?, ?, coalesce((SELECT occurances + 1 FROM MarkovStart WHERE word1 = ? AND word2 = ?), 1))', values=item + item)
    
    """
    def commit_rules(self):
        if len(self._rule_queue) == 0:
            return
        self.executemany('INSERT OR REPLACE INTO MarkovGrammar (word1, word2, word3, occurances)\
        VALUES (?, ?, ?, coalesce((SELECT occurances + 1 FROM MarkovGrammar WHERE word1 = ? AND word2 = ? AND word3 = ?),1))', [rule + rule for rule in self._rule_queue])
        self._rule_queue.clear()

    def commit_start(self):
        if len(self._start_queue) == 0:
            return
        self.add_execute_queue('INSERT OR REPLACE INTO MarkovStart (word1, word2, occurances)\
        VALUES (?, ?, coalesce((SELECT occurances + 1 FROM MarkovStart WHERE word1 = ? AND word2 = ?),1))', [start + start for start in self._start_queue])
        self._start_queue.clear()
    """

#if __name__ == "__main__":
#    d = Database("Cubiedev".lower())
    """
    data = [("I", "am", "a"), ("I", "am", "your"), ("I", "would", "be"), ("I", "don't", "like")]
    for tup in data:
        d.add_execute_queue(f'INSERT OR REPLACE INTO MarkovGrammar{tup[0][0]} (word1, word2, word3, occurances)\
            VALUES (?, ?, ?, coalesce((SELECT occurances + 1 FROM MarkovGrammar{tup[0][0]} WHERE word1 = ? AND word2 = ? AND word3 = ?),1))', tup)
    """
