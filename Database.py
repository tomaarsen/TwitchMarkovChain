
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

        for character in (list(string.ascii_uppercase + string.digits) + ["Other"]):
            sql = f"""
            CREATE TABLE IF NOT EXISTS MarkovStart{character} (
                word1 TEXT COLLATE NOCASE, 
                word2 TEXT COLLATE NOCASE, 
                occurances INTEGER, 
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
            );
            """
            self.add_execute_queue(sql)
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
                #print("Executing ", *sql)
                cur.execute(*sql)
            self._execute_queue.clear()
            cur.execute("commit")
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

    def check_equal(self, l):
        # Check if a list contains of items that are all identical
        return not l or l.count(l[0]) == len(l)

    def get_next(self, *args):
        # Get all items
        data = self.execute(f"SELECT word3, occurances FROM MarkovGrammar{self.get_suffix(args[0][0][0])} WHERE word1 = ? AND word2 = ?;", args[0], fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return self.pick_word(data)

    def get_next_initial(self, *args):
        # Get all items
        data = self.execute(f"SELECT word3, occurances FROM MarkovGrammar{self.get_suffix(args[0][0][0])} WHERE word1 = ? AND word2 = ? AND word3 != '<END>';", args[0], fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return self.pick_word(data)
    
    def get_next_single(self, word):
        # Get all items
        data = self.execute(f"SELECT word2, occurances FROM MarkovGrammar{self.get_suffix(word[0])} WHERE word1 = ?;", (word,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [word] + [self.pick_word(data)]
    
    def get_next_single_initial(self, word):
        # Get all items
        data = self.execute(f"SELECT word2, occurances FROM MarkovGrammar{self.get_suffix(word[0])} WHERE word1 = ? AND word2 != '<END>';", (word,), fetch=True)
        # Return a word picked from the data, using occurances as a weighting factor
        if len(data) == 0:
            return None
        return [word] + [self.pick_word(data)]

    def get_next_single_start(self, word):
        # Get all items
        data = self.execute(f"SELECT word2, occurances FROM MarkovStart{self.get_suffix(word[0])} WHERE word1 = ?;", (word,), fetch=True)
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
        # Find one character start from
        character = random.choice(list(string.ascii_lowercase + string.digits) + ["Other"])

        # Get all items
        data = self.execute(f"SELECT * FROM MarkovStart{character};", fetch=True)
        
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
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovGrammar{self.get_suffix(item[0][0])} (word1, word2, word3, occurances) VALUES (?, ?, ?, coalesce((SELECT occurances + 1 FROM MarkovGrammar{self.get_suffix(item[0][0])} WHERE word1 = ? AND word2 = ? AND word3 = ?), 1))', values=item + item)
        
    def add_start_queue(self, item):
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovStart{self.get_suffix(item[0][0])} (word1, word2, occurances) VALUES (?, ?, coalesce((SELECT occurances + 1 FROM MarkovStart{self.get_suffix(item[0][0])} WHERE word1 = ? AND word2 = ?), 1))', values=item + item)
    
    def unlearn(self, message):
        words = message.split(" ")
        tuples = [(words[i], words[i+1], words[i+2]) for i in range(0, len(words) - 2)]
        # Unlearn start of sentence from MarkovStart
        if len(words) > 1:
            # Reduce "occurances" by 5
            self.add_execute_queue(f'UPDATE MarkovStart{self.get_suffix(words[0][0])} SET occurances = occurances - 5 WHERE word1 = ? AND word2 = ?;', values=(words[0], words[1], ))
            # Delete if occurances is now less than 0.
            self.add_execute_queue(f'DELETE FROM MarkovStart{self.get_suffix(words[0][0])} WHERE word1 = ? AND word2 = ? AND occurances <= 0;', values=(words[0], words[1], ))
        # Unlearn all 3 word sections from Grammar
        for (word1, word2, word3) in tuples:
            # Reduce "occurances" by 5
            self.add_execute_queue(f'UPDATE MarkovGrammar{self.get_suffix(word1[0])} SET occurances = occurances - 5 WHERE word1 = ? AND word2 = ? AND word3 = ?;', values=(word1, word2, word3, ))
            # Delete if occurances is now less than 0.
            self.add_execute_queue(f'DELETE FROM MarkovGrammar{self.get_suffix(word1[0])} WHERE word1 = ? AND word2 = ? AND word3 = ? AND occurances <= 0;', values=(word1, word2, word3, ))
        self.execute_commit()
