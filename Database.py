
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
        sql = """
        CREATE TABLE IF NOT EXISTS WhisperIgnore (
            username TEXT,
            PRIMARY KEY (username)
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
    
    def add_whisper_ignore(self, username):
        self.execute("INSERT OR IGNORE INTO WhisperIgnore(username) SELECT ?", (username,))
    
    def check_whisper_ignore(self, username):
        return self.execute("SELECT username FROM WhisperIgnore WHERE username = ?;", (username,), fetch=True)

    def remove_whisper_ignore(self, username):
        self.execute("DELETE FROM WhisperIgnore WHERE username = ?", (username,))

    def add_start(self, out):
        # Add 1 to the count for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovStart SET count = count+1 WHERE output1 = ? AND output2 = ?", (out[0], out[1]))
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovStart(output1, output2, count) SELECT ?, ?, 1;", (out[0], out[1]))

    def add_rule(self, *args):
        # Potentially interesting: Remove case sensitivity for keys to improve average choice
        #arg = [arg.lower() if index < (len(args[0]) - 1) else arg for index, arg in enumerate(args[0])]

        # For all cases where the arguments are all the same, we want to check if the odds of recursion is < 50% 
        # And if it is, we can add the arguments.
        if self.checkEqual(args[0]):
            if self.checkOdds(args[0][0]):
                return

        # Add 1 to the count for the specific out. However, only if this out already exists in the db.
        self.execute("UPDATE MarkovGrammar SET count = count+1 WHERE input1 = ? AND input2 = ? AND output1 = ?", args[0])
        # Try to insert it anew. If it already exists there will be a Key constraint error, which will be ignored.
        self.execute("INSERT OR IGNORE INTO MarkovGrammar(input1, input2, output1, count) SELECT ?, ?, ?, 1;", args[0])
    
    def checkEqual(self, l):
        # Check if a list contains of items that are all identical
        return not l or l.count(l[0]) == len(l)

    def checkOdds(self, arg):
        # Check if the odds of recursion are larger than 50%
        total = self.execute("SELECT SUM(count) FROM MarkovGrammar WHERE input1=? AND input2=?;", (arg, arg), fetch=True)
        recursion_case = self.execute("SELECT count FROM MarkovGrammar WHERE input1=? AND input2=? AND output1=?;", (arg, arg, arg), fetch=True)
        # If total is empty, then we don't want to add a recursive case 
        if len(total) == 0:
            return True
        # If recursion_case is empty but total isn't, then we do want to add a recursive case
        if len(recursion_case) == 0:
            return False
        # Otherwise return if recursion_case is more or equal to 50% of all cases
        return recursion_case[0][0] / total[0][0] >= 0.5

    def get_next(self, *args):
        # Get all items
        data = self.execute("SELECT output1, count FROM MarkovGrammar where input1=? AND input2=?;", args[0], fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        if len(data) == 0:
            return None
        return self.pick_word(data)
    
    def get_next_single(self, inp):
        # Get all items
        data = self.execute("SELECT input2, count FROM MarkovGrammar where input1=?;", (inp,), fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        if len(data) == 0:
            return None
        return [inp] + [self.pick_word(data)]

    def get_next_single_start(self, inp):
        # Get all items
        data = self.execute("SELECT output2, count FROM MarkovStart where output1=?;", (inp,), fetch=True)
        # Return a word picked from the data, using count as a weighting factor
        if len(data) == 0:
            return None
        return [inp] + [self.pick_word(data)]

    def pick_word(self, data):
        # Add each item "count" times
        start_list = [tup[0] for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        return random.choice(start_list)

    def get_start(self):
        # TODO Prevent having to ask for all items
        # Get all items
        data = self.execute("SELECT * FROM MarkovStart;", fetch=True)
        # Add each item "count" times
        start_list = [list(tup[:-1]) for tup in data for _ in range(tup[-1])]
        # Pick a random starting key from this weighted list
        return random.choice(start_list)