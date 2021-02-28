
import sqlite3, logging, random, string
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, channel):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"
        self._execute_queue = []

        # TODO: Punctuation insensitivity.
        # My ideas for such an implementation have increased the generation time by ~5x. 
        # This was not worth it for me. I may revisit this at some point.

        # If an old version of the Database is used, update the database
        if ("MarkovGrammarA",) in self.execute("SELECT name FROM sqlite_master WHERE type='table';", fetch=True):
            
            logger.info("Creating backup before updating Database...")
            # Connect to both the new and backup, backup, and close both
            def progress(status, remaining, total):
                logging.debug(f'Copied {total-remaining} of {total} pages...')
            conn = sqlite3.connect(f"MarkovChain_{channel.replace('#', '').lower()}.db")
            back_conn = sqlite3.connect(f"MarkovChain_{channel.replace('#', '').lower()}_backup.db")
            with back_conn:
                conn.backup(back_conn, pages=1000, progress=progress)
            conn.close()
            back_conn.close()
            logger.info("Created backup before updating Database...")
            
            logger.info("Updating Database to new version for improved efficiency...")

            # Rename ...Other to ..._
            self.add_execute_queue(f"""
            CREATE TABLE IF NOT EXISTS MarkovStart_ (
                word1 TEXT COLLATE NOCASE, 
                word2 TEXT COLLATE NOCASE, 
                occurances INTEGER, 
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
            );
            """)
            self.add_execute_queue(f"""
            CREATE TABLE IF NOT EXISTS MarkovGrammar_ (
                word1 TEXT COLLATE NOCASE,
                word2 TEXT COLLATE NOCASE,
                word3 TEXT COLLATE NOCASE,
                occurances INTEGER,
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
            );
            """)
            self.execute_commit()

            # Copy data from Other to _ and remove Other
            self.add_execute_queue("INSERT INTO MarkovGrammar_ SELECT * FROM MarkovGrammarOther;")
            self.add_execute_queue("INSERT INTO MarkovStart_ SELECT * FROM MarkovStartOther;")
            self.add_execute_queue("DROP TABLE MarkovGrammarOther")
            self.add_execute_queue("DROP TABLE MarkovStartOther")
            self.execute_commit()

            # Copy all data from MarkovGrammarx where x is some digit to MarkovGrammar_, 
            # Same with MarkovStart.
            for character in (list(string.digits)):
                self.add_execute_queue(f"INSERT INTO MarkovGrammar_ SELECT * FROM MarkovGrammar{character}")
                self.add_execute_queue(f"DROP TABLE MarkovGrammar{character}")
                self.add_execute_queue(f"INSERT INTO MarkovStart_ SELECT * FROM MarkovStart{character}")
                self.add_execute_queue(f"DROP TABLE MarkovStart{character}")
            self.execute_commit()

            # Split up MarkovGrammarA into MarkovGrammarAA, MarkovGrammarAB, etc.
            for first_char in list(string.ascii_uppercase) + ["_"]:
                for second_char in list(string.ascii_uppercase):
                    self.add_execute_queue(f"""
                    CREATE TABLE IF NOT EXISTS MarkovGrammar{first_char}{second_char} (
                        word1 TEXT COLLATE NOCASE,
                        word2 TEXT COLLATE NOCASE,
                        word3 TEXT COLLATE NOCASE,
                        occurances INTEGER,
                        PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                    );
                    """)
                    self.add_execute_queue(f"INSERT INTO MarkovGrammar{first_char}{second_char} SELECT * FROM MarkovGrammar{first_char} WHERE word2 LIKE \"{second_char}%\";")
                    self.add_execute_queue(f"DELETE FROM MarkovGrammar{first_char} WHERE word2 LIKE \"{second_char}%\";")
                
                self.add_execute_queue(f"""
                CREATE TABLE IF NOT EXISTS MarkovGrammar{first_char}_ (
                    word1 TEXT COLLATE NOCASE,
                    word2 TEXT COLLATE NOCASE,
                    word3 TEXT COLLATE NOCASE,
                    occurances INTEGER,
                    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                );
                """)
                self.add_execute_queue(f"INSERT INTO MarkovGrammar{first_char}_ SELECT * FROM MarkovGrammar{first_char};")
                self.add_execute_queue(f"DROP TABLE MarkovGrammar{first_char}")
                self.execute_commit()
        
            logger.info("Finished Updating Database to new version.")

        # Resolve typo in Database
        if self.execute("SELECT * FROM PRAGMA_TABLE_INFO('MarkovGrammarAA') WHERE name='occurances';", fetch=True):
            logger.info("Updating Database to new version...")
            for first_char in list(string.ascii_uppercase) + ["_"]:
                for second_char in list(string.ascii_uppercase) + ["_"]:
                    self.execute(f"ALTER TABLE MarkovGrammar{first_char}{second_char} RENAME COLUMN occurances TO count;")
                self.execute(f"ALTER TABLE MarkovStart{first_char} RENAME COLUMN occurances TO count;")
            logger.info("Finished Updating Database to new version.")

        for first_char in list(string.ascii_uppercase) + ["_"]:
            self.add_execute_queue(f"""
            CREATE TABLE IF NOT EXISTS MarkovStart{first_char} (
                word1 TEXT COLLATE NOCASE, 
                word2 TEXT COLLATE NOCASE, 
                count INTEGER, 
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
            );
            """)
            for second_char in list(string.ascii_uppercase) + ["_"]:
                self.add_execute_queue(f"""
                CREATE TABLE IF NOT EXISTS MarkovGrammar{first_char}{second_char} (
                    word1 TEXT COLLATE NOCASE,
                    word2 TEXT COLLATE NOCASE,
                    word3 TEXT COLLATE NOCASE,
                    count INTEGER,
                    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                );
                """)
        sql = """
        CREATE TABLE IF NOT EXISTS WhisperIgnore (
            username TEXT,
            PRIMARY KEY (username)
        );
        """
        self.add_execute_queue(sql)
        self.execute_commit()

        # Used for randomly picking a Markov Grammar if only one word is given
        # Index 0 is for "A", 1 for "B", and 26 for everything else
        self.word_frequency = [11.6, 4.4, 5.2, 3.1, 2.8, 4, 1.6, 4.2, 7.3, 0.5, 0.8, 2.4, 3.8, 2.2, 7.6, 4.3, 0.2, 2.8, 6.6, 15.9, 1.1, 0.8, 5.5, 0.1, 0.7, 0.1, 0.5]
    
    def add_execute_queue(self, sql, values=None):
        if values is not None:
            self._execute_queue.append([sql, values])
        else:
            self._execute_queue.append([sql])
        # Commit these executes if there are more than 25 queries
        if len(self._execute_queue) > 25:
            self.execute_commit()
    
    def execute_commit(self, fetch=False):
        if self._execute_queue:
            with sqlite3.connect(self.db_name) as conn:
                cur = conn.cursor()
                cur.execute("begin")
                for sql in self._execute_queue:
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
        if character.lower() in (string.ascii_lowercase):
            return character.upper()
        return "_"

    def add_whisper_ignore(self, username):
        self.execute("INSERT OR IGNORE INTO WhisperIgnore(username) SELECT ?", (username,))
    
    def check_whisper_ignore(self, username):
        return self.execute("SELECT username FROM WhisperIgnore WHERE username = ?;", (username,), fetch=True)

    def remove_whisper_ignore(self, username):
        self.execute("DELETE FROM WhisperIgnore WHERE username = ?", (username,))

    def check_equal(self, l):
        # Check if a list contains of items that are all identical
        return not l or l.count(l[0]) == len(l)

    def get_next(self, index, words):
        # Get all items
        data = self.execute(f"SELECT word3, count FROM MarkovGrammar{self.get_suffix(words[0][0])}{self.get_suffix(words[1][0])} WHERE word1 = ? AND word2 = ?;", words, fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else self.pick_word(data, index)

    def get_next_initial(self, index, words):
        # Get all items
        data = self.execute(f"SELECT word3, count FROM MarkovGrammar{self.get_suffix(words[0][0])}{self.get_suffix(words[1][0])} WHERE word1 = ? AND word2 = ? AND word3 != '<END>';", words, fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else self.pick_word(data, index)
    
    """
    def get_next_single(self, index, word):
        # Get all items
        data = self.execute(f"SELECT word2, count FROM MarkovGrammar{self.get_suffix(word[0])} WHERE word1 = ?;", (word,), fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else [word] + [self.pick_word(data, index)]
    """
    
    def get_next_single_initial(self, index, word):
        # Get all items
        data = self.execute(f"SELECT word2, count FROM MarkovGrammar{self.get_suffix(word[0])}{random.choices(string.ascii_uppercase + '_', weights=self.word_frequency)[0]} WHERE word1 = ? AND word2 != '<END>';", (word,), fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else [word] + [self.pick_word(data, index)]

    def get_next_single_start(self, word):
        # Get all items
        data = self.execute(f"SELECT word2, count FROM MarkovStart{self.get_suffix(word[0])} WHERE word1 = ?;", (word,), fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else [word] + [self.pick_word(data)]

    def pick_word(self, data, index=0):
        # Pick a random starting key from a weighted list
        # Note that the <END> values are weighted based on index.
        return random.choices(data, weights=[tup[1] * ((index+1)/15) if tup[0] == "<END>" else tup[1] for tup in data])[0][0]

    def get_start(self):
        # Find one character start from
        character = random.choice(list(string.ascii_lowercase) + ["_"])

        # Get all items
        data = self.execute(f"SELECT * FROM MarkovStart{character};", fetch=True)
        
        # Add each item "count" times
        start_list = [list(tup[:-1]) for tup in data for _ in range(tup[-1])]
        
        # If nothing has ever been said
        if len(start_list) == 0:
            return []

        # Pick a random starting key from this weighted list
        return random.choice(start_list)

    def add_rule_queue(self, item):
        # Filter out recursive case.
        if self.check_equal(item):
            return
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovGrammar{self.get_suffix(item[0][0])}{self.get_suffix(item[1][0])} (word1, word2, word3, count) VALUES (?, ?, ?, coalesce((SELECT count + 1 FROM MarkovGrammar{self.get_suffix(item[0][0])}{self.get_suffix(item[1][0])} WHERE word1 = ? COLLATE BINARY AND word2 = ? COLLATE BINARY AND word3 = ? COLLATE BINARY), 1))', values=item + item)
        
    def add_start_queue(self, item):
        self.add_execute_queue(f'INSERT OR REPLACE INTO MarkovStart{self.get_suffix(item[0][0])} (word1, word2, count) VALUES (?, ?, coalesce((SELECT count + 1 FROM MarkovStart{self.get_suffix(item[0][0])} WHERE word1 = ? COLLATE BINARY AND word2 = ? COLLATE BINARY), 1))', values=item + item)
    
    def unlearn(self, message):
        words = message.split(" ")
        tuples = [(words[i], words[i+1], words[i+2]) for i in range(0, len(words) - 2)]
        # Unlearn start of sentence from MarkovStart
        if len(words) > 1:
            # Reduce "count" by 5
            self.add_execute_queue(f'UPDATE MarkovStart{self.get_suffix(words[0][0])} SET count = count - 5 WHERE word1 = ? AND word2 = ?;', values=(words[0], words[1], ))
            # Delete if count is now less than 0.
            self.add_execute_queue(f'DELETE FROM MarkovStart{self.get_suffix(words[0][0])} WHERE word1 = ? AND word2 = ? AND count <= 0;', values=(words[0], words[1], ))
        # Unlearn all 3 word sections from Grammar
        for (word1, word2, word3) in tuples:
            # Reduce "count" by 5
            self.add_execute_queue(f'UPDATE MarkovGrammar{self.get_suffix(word1[0])}{self.get_suffix(word2[0])} SET count = count - 5 WHERE word1 = ? AND word2 = ? AND word3 = ?;', values=(word1, word2, word3, ))
            # Delete if count is now less than 0.
            self.add_execute_queue(f'DELETE FROM MarkovGrammar{self.get_suffix(word1[0])}{self.get_suffix(word2[0])} WHERE word1 = ? AND word2 = ? AND word3 = ? AND count <= 0;', values=(word1, word2, word3, ))
        self.execute_commit()
