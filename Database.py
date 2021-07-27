
import sqlite3
import logging
import random
import string
from typing import Any, List, Optional, Tuple
logger = logging.getLogger(__name__)


class Database:

    """
    The database created is called `MarkovChain_{channel}.db`, 
    and populated with 27 + 27^2 = 756 tables. Firstly, 27 tables with the structure of
    "MarkovStart{char}", i.e. called:
    > MarkovStartA
    > MarkovStartB
    > ...
    > MarkovStartZ
    > MarkovStart_
    These tables store the first two words of a sentence, alongside a "count" frequency. 
    The suffix of the table name is the first character of the first word in the entry.

    For example, from a sentence "I am the developer of this bot", "I am" is learned by creating
    or updating an entry in MarkovStartI where the first word is "I", the second word is "am",
    and the "count" value increments every time the sequence "I am" was learned.

    If instead we learn, "[he said hello]", then "[he said" is learned by creating or updating
    an entry in MarkovStart_.



    Alongside the MarkovStart... tables, there are 729 tables called "MarkovGrammar{char}{char}",
    i.e. called:
    > MarkovGrammarAA
    > MarkovGrammarAB
    > ...
    > MarkovGrammarAZ
    > MarkovGrammarA_
    > MarkovGrammarBA
    > MarkovGrammarBB
    > ...
    > MarkovGrammar_Z
    > MarkovGrammar__
    These tables store 3-grams, alongside a "count" frequency of this 3-gram. The suffix of the 
    table name is the first character of the first word in the 3-gram, with the first character
    of the second word in the 3-gram.

    If we revisit the example of "I am the developer of this bot", we learn the following 3-grams:
    > "I am the"
    > "am the developer"
    > "the developer of"
    > "developer of this"
    > "of this bot"
    > "this bot <END>"
    The 3-gram "am the developer" will be placed in MarkovGrammarAT, by creating or updating an entry
    where the first word is "am", the second is "the", and the third "developer", while the "count"
    frequency is incremented every time the 3-gram "am the developer" is learned.



    The core of the knowledge base are the MarkovGrammar tables, which can be used to create 
    functions that take a certain number of words as input, and then generate a new word. For example:
    Given "I am", we can use the MarkovGrammarIA table to look for entries that have "I" as the first word,
    and "am" as the second word. If there are multiple options, we can use the "count" frequency as
    weights to pick an appropriate "next word".



    Important notes:
    - Learning is *case sensitive*. The 3-gram "YOU ARE A" will become a different entry than "you are a". 
      This is most important when learning emotes, where the distinction between "Kappa" and "kappa" truly is important.
    - Generating is *case insensitive*. Generating when using "YOU ARE" as the previous words to use in e.g. self.get_next()
      will get the same results as generating using "you are".

    - Learning and generating is *punctuation insensitive*. Each sentence is tokenized to split commas, dots, apostrophes, etc.
      As a result, the sentence "Hello, I'm Tom!" is tokenized to: ["Hello", ",", "I", "'m", "Tom", "!"]. Then, 3-grams of this
      is learned. 

    - Both learning and generating is *punctuation sensitive*. "Hello, how are" will learn and generate differently than
      "Hello how are", as the first word is taken as "Hello,", which differs from "Hello". 
      A solution is to completely remove punctuation. Before learning, before generating, etc. 
      Essentially ignore that it exists.
      However, this is not entirely desirable. In a perfect world, we would like to learn "hello," 
      and "hello" differently, just like "HELLO" and "hello", but allow generating from "hello"
      to both get results from "hello" and "hello,".
    """

    def __init__(self, channel: str):
        self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"
        self._execute_queue = []

        # Ensure the database is updated to the newest version
        self.update_v1(channel)
        self.update_v2()
        self.update_v3(channel)

        # Create database tables.
        for first_char in list(string.ascii_uppercase) + ["_"]:
            self.add_execute_queue(f"""
            CREATE TABLE IF NOT EXISTS MarkovStart{first_char} (
                word1 TEXT COLLATE NOCASE, 
                word2 TEXT COLLATE NOCASE, 
                count INTEGER, 
                PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
            );
            """, auto_commit=False)
            for second_char in list(string.ascii_uppercase) + ["_"]:
                self.add_execute_queue(f"""
                CREATE TABLE IF NOT EXISTS MarkovGrammar{first_char}{second_char} (
                    word1 TEXT COLLATE NOCASE,
                    word2 TEXT COLLATE NOCASE,
                    word3 TEXT COLLATE NOCASE,
                    count INTEGER,
                    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                );
                """, auto_commit=False)
        sql = """
        CREATE TABLE IF NOT EXISTS WhisperIgnore (
            username TEXT,
            PRIMARY KEY (username)
        );
        """
        self.add_execute_queue(sql)
        self.execute_commit()

        # Used for randomly picking a Markov Grammar if only one word is given
        # Index 0 is for "A", 1 for "B", etc. Then, 26 is for "_"
        self.word_frequency = [11.6, 4.4, 5.2, 3.1, 2.8, 4, 1.6, 4.2, 7.3, 0.5, 0.8, 2.4,
                               3.8, 2.2, 7.6, 4.3, 0.2, 2.8, 6.6, 15.9, 1.1, 0.8, 5.5, 0.1, 0.7, 0.1, 0.5]

    def update_v1(self, channel: str):
        """Update the Database structure from a deprecated version to a newer one.

        Args:
            channel (str): The name of the Twitch channel on which the bot is running.
        """
        # If an old version of the Database is used, update the database
        if ("MarkovGrammarA",) in self.execute("SELECT name FROM sqlite_master WHERE type='table';", fetch=True):

            logger.info("Creating backup before updating Database...")
            # Connect to both the new and backup, backup, and close both

            def progress(status, remaining, total):
                logging.debug(f'Copied {total-remaining} of {total} pages...')
            conn = sqlite3.connect(
                f"MarkovChain_{channel.replace('#', '').lower()}.db")
            back_conn = sqlite3.connect(
                f"MarkovChain_{channel.replace('#', '').lower()}_backup.db")
            with back_conn:
                conn.backup(back_conn, pages=1000, progress=progress)
            conn.close()
            back_conn.close()
            logger.info("Created backup before updating Database...")

            logger.info(
                "Updating Database to new version for improved efficiency...")

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
            self.add_execute_queue(
                "INSERT INTO MarkovGrammar_ SELECT * FROM MarkovGrammarOther;")
            self.add_execute_queue(
                "INSERT INTO MarkovStart_ SELECT * FROM MarkovStartOther;")
            self.add_execute_queue("DROP TABLE MarkovGrammarOther")
            self.add_execute_queue("DROP TABLE MarkovStartOther")
            self.execute_commit()

            # Copy all data from MarkovGrammarx where x is some digit to MarkovGrammar_,
            # Same with MarkovStart.
            for character in (list(string.digits)):
                self.add_execute_queue(
                    f"INSERT INTO MarkovGrammar_ SELECT * FROM MarkovGrammar{character}")
                self.add_execute_queue(f"DROP TABLE MarkovGrammar{character}")
                self.add_execute_queue(
                    f"INSERT INTO MarkovStart_ SELECT * FROM MarkovStart{character}")
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
                    self.add_execute_queue(
                        f"INSERT INTO MarkovGrammar{first_char}{second_char} SELECT * FROM MarkovGrammar{first_char} WHERE word2 LIKE \"{second_char}%\";")
                    self.add_execute_queue(
                        f"DELETE FROM MarkovGrammar{first_char} WHERE word2 LIKE \"{second_char}%\";")

                self.add_execute_queue(f"""
                CREATE TABLE IF NOT EXISTS MarkovGrammar{first_char}_ (
                    word1 TEXT COLLATE NOCASE,
                    word2 TEXT COLLATE NOCASE,
                    word3 TEXT COLLATE NOCASE,
                    occurances INTEGER,
                    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                );
                """)
                self.add_execute_queue(
                    f"INSERT INTO MarkovGrammar{first_char}_ SELECT * FROM MarkovGrammar{first_char};")
                self.add_execute_queue(f"DROP TABLE MarkovGrammar{first_char}")
                self.execute_commit()

            logger.info("Finished Updating Database to new version.")

    def update_v2(self):
        """Update the Database structure from a deprecated version to a newer one.

        This update involves a typo.

        Args:
            channel (str): The name of the Twitch channel on which the bot is running.
        """
        # Resolve typo in Database
        if self.execute("SELECT * FROM PRAGMA_TABLE_INFO('MarkovGrammarAA') WHERE name='occurances';", fetch=True):
            logger.info("Updating Database to new version...")
            for first_char in list(string.ascii_uppercase) + ["_"]:
                for second_char in list(string.ascii_uppercase) + ["_"]:
                    self.execute(
                        f"ALTER TABLE MarkovGrammar{first_char}{second_char} RENAME COLUMN occurances TO count;")
                self.execute(
                    f"ALTER TABLE MarkovStart{first_char} RENAME COLUMN occurances TO count;")
            logger.info("Finished Updating Database to new version.")

    def update_v3(self, channel: str) -> None:
        """Update the Database structure to mark punctuation as a separate word.

        Previously, "Hello," was a valid single word. Now, it would be split as "Hello" and ",".
        This allows people to generate "!g hello", and have the bot generate "hello, how are you?",
        or have "!g it" result in "it's a wonderful day".

        This first copies `MarkovChain_{channel}.db` to `MarkovChain_{channel}_modified.db`.
        This new copy is then modified. The original is never changed, to avoid issues when the
        update is interrupted. As a result, running the program again will just re-attempt the
        update. 

        Upon completing the update, the original database is renamed to 
        `MarkovChain_{channel}_backup.db`, while the newly modified `MarkovChain_{channel}_modified.db`
        is renamed to `MarkovChain_{channel}.db`.

        *This `MarkovChain_{channel}_backup.db` file can safely be deleted, as it is NOT used*

        This function also adds a `Version` table, and sets the version to 3.

        Args:
            channel (str): The name of the Twitch channel on which the bot is running.
        """

        # Get Database version. Throws OperationalError if the Version table does not exist,
        # in which case we definitely want to upgrade.
        try:
            version = self.execute(
                "SELECT version FROM Version ORDER BY version DESC LIMIT 1;", fetch=True)
        except sqlite3.OperationalError:
            version = []

        # Whether to upgrade
        if not version or version[0][0] < 3:
            logger.info(
                "Updating Database to new version - supports better punctuation handling.")

            from shutil import copyfile
            import os
            from Tokenizer import tokenize
            from nltk import ngrams
            channel = channel.replace('#', '').lower()
            copyfile(f"MarkovChain_{channel}.db",
                     f"MarkovChain_{channel}_modified.db")
            logger.info(
                f"Created a copy of the database called \"MarkovChain_{channel}_modified.db\". The update will modify this file.")

            # Temporarily set self.db_name to the modified one
            self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}_modified.db"

            # Create database tables.
            for first_char in list(string.ascii_uppercase) + ["_"]:
                table = f"MarkovStart{first_char}"
                self.add_execute_queue(f"""
                CREATE TABLE IF NOT EXISTS {table}_modified (
                    word1 TEXT COLLATE NOCASE, 
                    word2 TEXT COLLATE NOCASE, 
                    count INTEGER, 
                    PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY)
                );
                """, auto_commit=False)
                for second_char in list(string.ascii_uppercase) + ["_"]:
                    table = f"MarkovGrammar{first_char}{second_char}"
                    self.add_execute_queue(f"""
                    CREATE TABLE IF NOT EXISTS {table}_modified (
                        word1 TEXT COLLATE NOCASE,
                        word2 TEXT COLLATE NOCASE,
                        word3 TEXT COLLATE NOCASE,
                        count INTEGER,
                        PRIMARY KEY (word1 COLLATE BINARY, word2 COLLATE BINARY, word3 COLLATE BINARY)
                    );
                    """, auto_commit=False)
            self.execute_commit()

            def modify_start(table: str) -> None:
                """Read all data from `table`, re-tokenize it, distribute the new first 2 tokens to _modified tables, and drop `table`.

                Args:
                    table (str): The name of the table to work on.
                """
                data = self.execute(f"SELECT * FROM {table};", fetch=True)
                for tup in data:
                    # Remove "count" from tup for now
                    count = tup[-1]
                    tup = tup[:-1]

                    raw_string = " ".join(tup)
                    tokenized = tokenize(raw_string)
                    two_gram = tokenized[:2]
                    # In case there was some issue in the previous Database 
                    if len(two_gram) < 2:
                        continue
                    self.add_execute_queue(f'''
                        INSERT OR REPLACE INTO MarkovStart{self.get_suffix(two_gram[0][0])}_modified (word1, word2, count)
                        VALUES (?, ?, coalesce (
                                (
                                    SELECT count + {count} FROM MarkovStart{self.get_suffix(two_gram[0][0])}_modified
                                    WHERE word1 = ? COLLATE BINARY
                                    AND word2 = ? COLLATE BINARY
                                ),
                                1
                            )
                        )''',
                                           values=two_gram + two_gram,
                                           auto_commit=False)

                self.execute(f"DROP TABLE {table};")

            def modify_grammar(table: str) -> None:
                """Read all data from `table`, re-tokenize it, distribute the new 3-grams to _modified tables, and drop `table`.

                Args:
                    table (str): The name of the table to work on.
                """
                data = self.execute(f"SELECT * FROM {table};", fetch=True)
                for tup in data:
                    # Remove "count" from tup for now
                    count = tup[-1]
                    tup = tup[:-1]

                    # If ends on "<END>", ignore that in in the tuple, as we don't want it to get
                    # tokenized.
                    end = False
                    if tup[-1] == "<END>":
                        end = True
                        tup = tup[:-1]

                    raw_string = " ".join(tup)
                    tokenized = tokenize(raw_string)

                    # Re-add "<END>"
                    if end:
                        tokenized.append("<END>")

                    for ngram in ngrams(tokenized, 3):
                        # Filter out recursive case.
                        if self.check_equal(ngram):
                            continue
                        self.add_execute_queue(f'''
                        INSERT OR REPLACE INTO MarkovGrammar{self.get_suffix(ngram[0][0])}{self.get_suffix(ngram[1][0])}_modified (word1, word2, word3, count)
                        VALUES (?, ?, ?, coalesce (
                                (
                                    SELECT count + {count} FROM MarkovGrammar{self.get_suffix(ngram[0][0])}{self.get_suffix(ngram[1][0])}_modified
                                    WHERE word1 = ? COLLATE BINARY
                                    AND word2 = ? COLLATE BINARY
                                    AND word3 = ? COLLATE BINARY
                                ),
                                1
                            )
                        )''',
                                               values=ngram + ngram,
                                               auto_commit=False)

                self.execute(f"DROP TABLE {table};")

            # Modify all tables
            i = 0
            total = 27 * 27 + 27  # The number of tables to convert
            for first_char in list(string.ascii_uppercase) + ["_"]:
                table = f"MarkovStart{first_char}"
                modify_start(table)
                i += 1
                for second_char in list(string.ascii_uppercase) + ["_"]:
                    table = f"MarkovGrammar{first_char}{second_char}"
                    modify_grammar(table)
                    i += 1
                logger.debug(
                    f"[{i / total * 100:.2f}%] Scheduled updates for the tables for words starting in {first_char}.")
            logger.info("Starting executing table update...")
            self.execute_commit()
            logger.info("Finished executing table update.")

            # Rename the _modified tables to normal tables again
            for first_char in list(string.ascii_uppercase) + ["_"]:
                table = f"MarkovStart{first_char}"
                self.add_execute_queue(
                    f"ALTER TABLE {table}_modified RENAME TO {table};", auto_commit=False)
                for second_char in list(string.ascii_uppercase) + ["_"]:
                    table = f"MarkovGrammar{first_char}{second_char}"
                    self.add_execute_queue(
                        f"ALTER TABLE {table}_modified RENAME TO {table};", auto_commit=False)
            self.execute_commit()

            # Turn the non-modified, old version of the Database into a "_backup.db" file,
            # and turn the modified file into the new main file.
            os.rename(f"MarkovChain_{channel}.db",
                      f"MarkovChain_{channel}_backup.db")
            os.rename(f"MarkovChain_{channel}_modified.db",
                      f"MarkovChain_{channel}.db")

            # Revert to using .db instead of _modified.db
            self.db_name = f"MarkovChain_{channel.replace('#', '').lower()}.db"

            # Add a version entry
            self.execute("""CREATE TABLE IF NOT EXISTS Version (
                    version INTEGER
                );""")
            self.execute("DELETE FROM Version;")
            self.execute("INSERT INTO Version (version) VALUES (3);")

            logger.info(
                f"Renamed original database file \"MarkovChain_{channel}.db\" to \"MarkovChain_{channel}_backup.db\". This file is *not* used, and can safely be deleted.")
            logger.info(
                f"Renamed updated database file \"MarkovChain_{channel}_modified.db\" to \"MarkovChain_{channel}.db\".")
            logger.info(
                f"This updated \"MarkovChain_{channel}.db\" will be used to drive the Twitch bot.")

    def add_execute_queue(self, sql: str, values: Tuple[Any] = None, auto_commit: bool = True) -> None:
        """Add query and corresponding values to a queue, to be executed all at once.

        This entire queue can be executed with `self.execute_commit`, 
        and the queue is automatically executed if there are more than 25 waiting queries.

        Args:
            sql (str): The SQL query to add, potentially with "?" for where 
                a value ought to be filled in.
            values ([Tuple[Any]], optional): Optional tuple of values to replace "?" in SQL queries.
                Defaults to None.
        """
        if values is not None:
            self._execute_queue.append([sql, values])
        else:
            self._execute_queue.append([sql])
        # Commit these executes if there are more than 25 queries
        if auto_commit and len(self._execute_queue) > 25:
            self.execute_commit()

    def execute_commit(self, fetch: bool = False) -> Any:
        """Execute the SQL queries added to the queue with `self.add_execute_queue`.

        Args:
            fetch (bool, optional): Whether to return the fetchall() of the SQL queries.
                Defaults to False.

        Returns:
            Any: The returned values from the SQL queries if `fetch` is true, otherwise None.
        """
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

    def execute(self, sql: str, values: Tuple[Any] = None, fetch: bool = False):
        """Execute the SQL query with the corresponding values, potentially returning a result.

        Args:
            sql (str): The SQL query to add, potentially with "?" for where 
                a value ought to be filled in.
            values ([Tuple[Any]], optional): Optional tuple of values to replace "?" in SQL queries.
                Defaults to None.
            fetch (bool, optional): Whether to return the fetchall() of the SQL queries.
                Defaults to False.

        Returns:
            Any: The returned values from the SQL queries if `fetch` is true, otherwise None.
        """
        with sqlite3.connect(self.db_name) as conn:
            cur = conn.cursor()
            if values is None:
                cur.execute(sql)
            else:
                cur.execute(sql, values)
            conn.commit()
            if fetch:
                return cur.fetchall()

    def get_suffix(self, character: str) -> str:
        """Transform a character into a member of string.ascii_lowercase or "_".

        Args:
            character (str): The character to normalize.

        Returns:
            str: The normalized character
        """
        if character.lower() in string.ascii_lowercase:
            return character.upper()
        return "_"

    def add_whisper_ignore(self, username: str) -> None:
        """Add `username` to the WhisperIgnore table, indicating that they do not wish to be whispered.

        Args:
            username (str): The username of the user who no longer wants to be whispered.
        """
        self.execute("""
            INSERT OR IGNORE INTO WhisperIgnore(username)
            SELECT ?;""",
                     values=(username,)
                     )

    def check_whisper_ignore(self, username: str) -> List[Tuple[str]]:
        """Returns a non-empty list only if `username` is in the WhisperIgnore table.

        Otherwise, returns an empty list. Is used to ensure that a user who doesn't want to be
        whispered is never whispered.

        Args:
            username (str): The username of the user to check.

        Returns:
            List[Tuple[str]]: Either an empty list, or [('test_user',)]. 
                Allows the use of `if not check_whisper_ignore(user): whisper(user)`
        """
        return self.execute("""
            SELECT username FROM WhisperIgnore
            WHERE username = ?;""",
                            values=(username,),
                            fetch=True)

    def remove_whisper_ignore(self, username: str) -> None:
        """Remove `username` from the WhisperIgnore table, indicating that they want to be whispered again.

        Args:
            username (str): The username of the user who wants to be whispered again.
        """
        self.execute("""
            DELETE FROM WhisperIgnore
            WHERE username = ?;""",
                     values=(username,))

    def check_equal(self, l: List[Any]) -> bool:
        """True if `l` consists of items that are all identical

        Useful for checking if we're learning that a sequence of the same words leads to the same word, 
        which can cause infinite loops when generating.

        Args:
            l (List[Any]): The list of objects for which we want to check if they are all identical.

        Returns:
            bool: True if `l` consists of items that are all identical
        """
        return l[0] * len(l) == l

    def get_next(self, index: int, words: List[str]) -> Optional[str]:
        """Generate the next word in the sentence using learned data, given the previous `key_length` words.

        `key_length` is set to 2 by default, and cannot easily be changed.

        Args:
            index (int): The index of this new word in the sentence.
            words (List[str]): The previous 2 words.

        Returns:
            Optional[str]: The next word in the sentence, generated given the learned data.
        """
        # Get all items
        data = self.execute(f"""
            SELECT word3, count FROM MarkovGrammar{self.get_suffix(words[0][0])}{self.get_suffix(words[1][0])}
            WHERE word1 = ? AND word2 = ?;""",
                            values=words,
                            fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else self.pick_word(data, index)

    def get_next_initial(self, index: int, words) -> Optional[str]:
        """Generate the next word in the sentence using learned data, given the previous `key_length` words.

        `key_length` is set to 2 by default, and cannot easily be changed.
        Similar to `get_next`, with the exception that it cannot immediately generate "<END>"

        Args:
            index (int): The index of this new word in the sentence.
            words (List[str]): The previous 2 words.

        Returns:
            Optional[str]: The next word in the sentence, generated given the learned data.
        """
        # Get all items
        data = self.execute(f"""
            SELECT word3, count FROM MarkovGrammar{self.get_suffix(words[0][0])}{self.get_suffix(words[1][0])}
            WHERE word1 = ? AND word2 = ? AND word3 != '<END>';""",
                            values=words,
                            fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else self.pick_word(data, index)

    def get_next_single_initial(self, index: int, word: str) -> Optional[List[str]]:
        """Generate the next word in the sentence using learned data, given the previous word.

        Randomly picks a start character for the second word by weighing all uppercase letters and "_" with their word frequency.

        Args:
            index (int): The index of this new word in the sentence.
            word (str): The previous word.

        Returns:
            Optional[List[str]]: The previous and newly generated word in the sentence as a list, generated given the learned data.
                So, the previous word is taken directly the input of this method, and the second word is generated.
        """
        # Randomly pick first character for the second word
        char_two = random.choices(string.ascii_uppercase + '_',
                                  weights=self.word_frequency)[0]
        # Get all items
        data = self.execute(f"""
            SELECT word2, count FROM MarkovGrammar{self.get_suffix(word[0])}{char_two}
            WHERE word1 = ? AND word2 != '<END>';""",
                            values=(word,),
                            fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else [word] + [self.pick_word(data, index)]

    def get_next_single_start(self, word: str) -> Optional[List[str]]:
        """Generate the second word in the sentence using learned data, given the very first word in the sentence.

        Args:
            word (str): The first word in the sentence.

        Returns:
            Optional[List[str]]: The first and second word in the sentence as a list, generated given the learned data.
                So, the first word is taken directly the input of this method, and the second word is generated.
        """
        # Get all items
        data = self.execute(f"""
            SELECT word2, count FROM MarkovStart{self.get_suffix(word[0])}
            WHERE word1 = ?;""",
                            values=(word,),
                            fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        return None if len(data) == 0 else [word] + [self.pick_word(data)]

    def pick_word(self, data: List[Tuple[str, int]], index: int = 0) -> str:
        """Randomly pick a word from `data` with word frequency as the weight.

        `index` is further used to decrease the weight of the <END> token for the first 15 words
        in the sequence, and then increase the weight after the 15th index.

        Args:
            data ([type]): A list of word - frequency pairs, e.g. 
                [('"the', 1), ('long', 1), ('well', 5), ('an', 2), ('a', 3), ('much', 1)]
            index (int, optional): The index of the newly generated word in the sentence.
                Used for modifying how often the <END> token occurs. Defaults to 0.

        Returns:
            str: The pseudo-randomly picked word.
        """
        return random.choices(data,
                              weights=[
                                  tup[-1] * ((index+1)/15)
                                  if tup[0] == "<END>" else
                                  tup[-1]
                                  for tup in data
                              ]
                              )[0][0]

    def get_start(self) -> List[str]:
        """Get a list of two words that mark as the start of a sentence.

        This is randomly gathered from MarkovStart{character}.

        Returns:
            List[str]: A list of two starting words, such as ["I", "am"].
        """
        # Find one character start from
        character = random.choices(list(string.ascii_lowercase) + ["_"],
                                   weights=self.word_frequency,
                                   k=1)[0]

        # Get all first word, second word, frequency triples,
        # e.g. [("I", "am", 3), ("You", "are", 2), ...]
        data = self.execute(
            f"SELECT * FROM MarkovStart{character};",
            fetch=True)

        # If nothing has ever been said
        if len(data) == 0:
            return []

        # Return a (weighted) randomly chosen 2-gram
        return list(random.choices(data,
                                   weights=[tup[-1] for tup in data],
                                   k=1)[0][:-1])

    def add_rule_queue(self, item: List[str]) -> None:
        """Adds a rule to the queue, ready to be entered into the knowledge base, given a 3-gram `item`.

        The rules on the queue are added with `self.add_execute_queue`, 
        which automatically executes the queries in the queue when there are enough queries waiting.

        Whenever `item` consists of three identical words, e.g. ["Kappa", "Kappa", "Kappa"], then 
        we perform no learning. If we did, this could cause infinite recursion in generation.

        Args:
            item (List[str]): A 3-gram, e.g. ['How', 'are', 'you']. This is learned by placing this
                in the MarkovGrammarHA table, where it can be seen as: 
                *Given ["How", "are"], then "you" is a potential output*
                The frequency of this word as an output is then incremented, 
                allowing for weighted picking of outputs.
        """
        # Filter out recursive case.
        if self.check_equal(item):
            return
        if "" in item:  # prevent adding invalid rules. Ideally this wouldn't trigger, but it seems to happen rarely.
            logger.warning(
                f"Failed to add item to rules. Item contains empty string: {item!r}")
            return
        self.add_execute_queue(f'''
            INSERT OR REPLACE INTO MarkovGrammar{self.get_suffix(item[0][0])}{self.get_suffix(item[1][0])} (word1, word2, word3, count)
            VALUES (?, ?, ?, coalesce(
                (
                    SELECT count + 1 FROM MarkovGrammar{self.get_suffix(item[0][0])}{self.get_suffix(item[1][0])}
                    WHERE word1 = ? COLLATE BINARY AND word2 = ? COLLATE BINARY AND word3 = ? COLLATE BINARY
                ),
                1)
            )''',
                               values=item + item)

    def add_start_queue(self, item: List[str]) -> None:
        """Adds a rule to the queue, ready to be entered into the knowledge base, given a 2-gram `item`.

        The rules on the queue are added with `self.add_execute_queue`, 
        which automatically executes the queries in the queue when there are enough queries waiting.

        Args:
            item (List[str]): A 2-gram, e.g. ['How', 'are']. This is learned by placing this
                in the MarkovStartH table, where it can be randomly (with frequency as weight)
                picked as a start of a sentence.
        """
        self.add_execute_queue(f'''
            INSERT OR REPLACE INTO MarkovStart{self.get_suffix(item[0][0])} (word1, word2, count)
            VALUES (?, ?, coalesce(
                (
                    SELECT count + 1 FROM MarkovStart{self.get_suffix(item[0][0])}
                    WHERE word1 = ? COLLATE BINARY AND word2 = ? COLLATE BINARY
                ),
                1)
            )''',
                               values=item + item)

    def unlearn(self, message: str) -> None:
        """Remove frequency of 3-grams from `message` from the knowledge base.

        Useful when a message is deleted - usually we want the bot to say those things less frequently.
        The frequency count for each of the 3-grams is reduced by 5, i.e. the message is unlearned by 5
        times the rate that a message is learned.

        If this means the frequency for the 3-gram becomes negative,
        we delete the 3-gram from the knowledge base entirely.

        Args:
            message (str): The message to unlearn.
        """
        words = message.split(" ")
        # Construct 3-grams
        tuples = [(words[i], words[i+1], words[i+2])
                  for i in range(0, len(words) - 2)]

        # Unlearn start of sentence from MarkovStart
        if len(words) > 1:
            # Reduce "count" by 5
            self.add_execute_queue(f'''
                UPDATE MarkovStart{self.get_suffix(words[0][0])}
                SET count = count - 5
                WHERE word1 = ? AND word2 = ?;''',
                                   values=(words[0], words[1],))
            # Delete if count is now less than 0.
            self.add_execute_queue(f'''
                DELETE FROM MarkovStart{self.get_suffix(words[0][0])}
                WHERE word1 = ? AND word2 = ? AND count <= 0;''',
                                   values=(words[0], words[1],))

        # Unlearn all 3 word sections from Grammar
        for (word1, word2, word3) in tuples:
            # Reduce "count" by 5
            self.add_execute_queue(f'''
                UPDATE MarkovGrammar{self.get_suffix(word1[0])}{self.get_suffix(word2[0])}
                SET count = count - 5
                WHERE word1 = ? AND word2 = ? AND word3 = ?;''',
                                   values=(word1, word2, word3,))
            # Delete if count is now less than 0.
            self.add_execute_queue(f'''
                DELETE FROM MarkovGrammar{self.get_suffix(word1[0])}{self.get_suffix(word2[0])}
                WHERE word1 = ? AND word2 = ? AND word3 = ? AND count <= 0;''',
                                   values=(word1, word2, word3, ))

        self.execute_commit()
