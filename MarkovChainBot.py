
from TwitchWebsocket import TwitchWebsocket
from nltk.tokenize import sent_tokenize
import json, random, logging, os, sqlite3

class Logging:
    def __init__(self):
        # Either of the two will be empty depending on OS
        prefix = "/".join(os.path.dirname(os.path.realpath(__file__)).split("/")[:-1]) + "\\".join(os.path.dirname(os.path.realpath(__file__)).split("\\")[:-1]) 
        prefix += "/Logging/"
        try:
            os.mkdir(prefix)
        except FileExistsError:
            pass
        log_file = prefix + os.path.basename(__file__).split('.')[0] + ".txt"
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # Spacer
        logging.info("")

class Settings:
    def __init__(self, bot):
        logging.debug("Loading settings.txt file...")
        try:
            # Try to load the file using json.
            # And pass the data to the GoogleTranslate class instance if this succeeds.
            with open("settings.txt", "r") as f:
                settings = f.read()
                data = json.loads(settings)
                bot.set_settings(data['Host'],
                                data['Port'],
                                data['Channel'],
                                data['Nickname'],
                                data['Authentication'],
                                data['DeniedUsers'],
                                data['KeyLength'])
                logging.debug("Settings loaded into Bot.")
        except ValueError:
            logging.error("Error in settings file.")
            raise ValueError("Error in settings file.")
        except FileNotFoundError:
            # If the file is missing, create a standardised settings.txt file
            # With all parameters required.
            logging.error("Please fix your settings.txt file that was just generated.")
            with open('settings.txt', 'w') as f:
                standard_dict = {
                                    "Host": "irc.chat.twitch.tv",
                                    "Port": 6667,
                                    "Channel": "#<channel>",
                                    "Nickname": "<name>",
                                    "Authentication": "oauth:<auth>",
                                    "DeniedUsers": ["StreamElements", "Nightbot", "Moobot", "Marbiebot"],
                                    "KeyLength": 2
                                }
                f.write(json.dumps(standard_dict, indent=4, separators=(',', ': ')))
                raise ValueError("Please fix your settings.txt file that was just generated.")

class Database:
    def __init__(self):
        self.create_db()
    
    def create_db(self):
        sql = """
        CREATE TABLE IF NOT EXISTS MarkovChain (
            word1 TEXT,
            word2 TEXT,
            word3 TEXT
        )
        """
        logging.debug("Creating Database...")
        self.execute(sql)
        logging.debug("Database created.")

    def execute(self, sql, values=None, fetch=False):
        with sqlite3.connect("MarkovChain.db") as conn:
            cur = conn.cursor()
            if values is None:
                cur.execute(sql)
            else:
                cur.execute(sql, values)
            conn.commit()
            if fetch:
                return cur.fetchall()
    
    def add_rule(self, *args):
        # Potentially interesting: Remove case sensitivity for keys to improve average choice
        #arg = [arg.lower() if index < (len(args[0]) - 1) else arg for index, arg in enumerate(args[0])]

        # Only if not all arguments are identical will the values be entered into the system.
        # This prevents: LUL + LUL -> LUL
        # Which could be a cause of recursion.
        prev = None
        for a in args[0]:
            if a != prev and prev is not None:
                self.execute("INSERT INTO MarkovChain(word1, word2, word3) VALUES (?, ?, ?)", args[0])
                return
            prev = a

    def get_next(self, *args):
        return self.execute("SELECT word3 FROM MarkovChain WHERE word1=? AND word2=? ORDER BY RANDOM() LIMIT 1;", args[0], fetch=True)

    def get_start(self):
        return list(self.execute("SELECT word2, word3 FROM MarkovChain WHERE word1='<START>' ORDER BY RANDOM() LIMIT 1;", fetch=True)[0])

class MarkovChain:
    def __init__(self):
        self.host = None
        self.port = None
        self.chan = None
        self.nick = None
        self.auth = None
        self.denied_users = None
        self.key_length = None
        
        # Fill previously initialised variables with data from the settings.txt file
        Settings(self)
        self.db = Database()

        self.ws = TwitchWebsocket(self.host, self.port, self.message_handler, live=True)
        self.ws.login(self.nick, self.auth)
        self.ws.join_channel(self.chan)

    def set_settings(self, host, port, chan, nick, auth, denied_users, key_length):
        self.host = host
        self.port = port
        self.chan = chan
        self.nick = nick
        self.auth = auth
        self.denied_users = [user.lower() for user in denied_users] + [self.nick.lower()]
        self.key_length = key_length

    def message_handler(self, m):
        try:
            if m.type == "366":
                logging.info(f"Successfully joined channel: #{m.channel}")

            elif m.type == "NOTICE":
                logging.info(m.message)

            elif m.type == "PRIVMSG":
                # Ignore bot messages
                if m.user.lower() in self.denied_users:
                    return
                
                if m.message.startswith("!generate"):
                    # Generate an actual sentence
                    sentence = self.generate()
                    logging.info(sentence)
                    self.ws.send_message(sentence)
                    
                else:
                    sentences = sent_tokenize(m.message)
                    for sentence in sentences:
                        # Get all seperate words
                        words = sentence.split(" ")

                        # If the sentence is too short, ignore it and move on to the next.
                        if len(words) <= self.key_length:
                            continue

                        # Add a new starting point for a sentence to the <START>
                        self.db.add_rule(["<START>"] + [words[x] for x in range(self.key_length)])
                        
                        # Create Key variable which will be used as a key in the Dictionary for the grammar
                        key = list()
                        for word in words:
                            # Set up key for first use
                            if len(key) < self.key_length:
                                key.append(word)
                                continue
                            
                            self.db.add_rule(key + [word])
                            
                            # Remove the first word, and add the current word,
                            # so that the key is correct for the next word.
                            key.pop(0)
                            key.append(word)

        except Exception as e:
            logging.exception(e)
            
    def generate(self):
        # Get starting key
        key = self.db.get_start()
        # Copy this to start of sentence
        sentence = key.copy()
        for _ in range(20):
            # Use key to get next word
            wordtuple = self.db.get_next(key)
            # If there is no next word, break
            if not len(wordtuple):
                break

            # Get next word from the wordtuple, and add it to the sentence
            word = wordtuple[0][0]
            sentence.append(word)
            
            # Modify the key so on the next iteration it gets the next item
            key.pop(0)
            key.append(word)
        
        return " ".join(sentence)

if __name__ == "__main__":
    Logging()
    MarkovChain()

"""
Potential TODO:
Make keys case insensitive. eg "it" and "It" would get grouped.

SQL to get the average amount of choices. The higher, the more unique sentences it will create.
SELECT AVG(choices) FROM
(
	SELECT COUNT(word3) as choices
	FROM MarkovChain
	GROUP BY word1, word2
) myData
"""
