
from TwitchWebsocket import TwitchWebsocket
from nltk.tokenize import sent_tokenize
import json, random, logging, os, sqlite3, time

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
            #filename=log_file,
            level=logging.DEBUG,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
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
                                data["BannedWords"],
                                data["Cooldown"],
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
                                    "BannedWords": ["<START>", "<END>"],
                                    "Cooldown": 20,
                                    "KeyLength": 2
                                }
                f.write(json.dumps(standard_dict, indent=4, separators=(',', ': ')))
                raise ValueError("Please fix your settings.txt file that was just generated.")

class Database:
    def __init__(self):
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

class MarkovChain:
    def __init__(self):
        self.host = None
        self.port = None
        self.chan = None
        self.nick = None
        self.auth = None
        self.denied_users = None
        self.banned_words = None
        self.cooldown = 20
        self.key_length = 2
        self.prev_message_t = 0
        
        # Fill previously initialised variables with data from the settings.txt file
        Settings(self)
        self.db = Database()

        self.ws = TwitchWebsocket(self.host, self.port, self.message_handler, live=True)
        self.ws.login(self.nick, self.auth)
        self.ws.join_channel(self.chan)

    def set_settings(self, host, port, chan, nick, auth, denied_users, banned_words, cooldown, key_length):
        self.host = host
        self.port = port
        self.chan = chan
        self.nick = nick
        self.auth = auth
        self.denied_users = [user.lower() for user in denied_users] + [self.nick.lower()]
        self.banned_words = [word.lower() for word in banned_words]
        self.cooldown = cooldown
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
                
                if "ACTION" in m.message:
                    print(m)

                if m.message.startswith("!generate") and self.prev_message_t + self.cooldown < time.time():
                    # Get params
                    params = m.message.split(" ")[1:]
                    # Generate an actual sentence
                    sentence = self.generate(params)
                    logging.info(sentence)
                    self.ws.send_message(sentence)
                    

                # Don't store commands
                elif m.message.startswith(("!", "/", ".")):
                    return
                    
                else:
                    if self.containsBannedWord(m.message):
                        return

                    sentences = sent_tokenize(m.message)
                    for sentence in sentences:
                        # Get all seperate words
                        words = sentence.split(" ")

                        # If the sentence is too short, ignore it and move on to the next.
                        if len(words) <= self.key_length:
                            continue

                        # Add a new starting point for a sentence to the <START>
                        #self.db.add_rule(["<START>"] + [words[x] for x in range(self.key_length)])
                        self.db.add_start([words[x] for x in range(self.key_length)])
                        
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
                        # Add <END> at the end of the sentence
                        self.db.add_rule(key + ["<END>"])

        except Exception as e:
            logging.exception(e)
            
    def generate(self, params=[]):

        if len(params) > 0:
            if params[0].startswith(("!", "/", ".")):
                return "You can't make me do commands, you madman!"

        if len(params) > 1:
            key = params[-self.key_length:]
            # Copy the entire params for the sentence
            sentence = params.copy()
        elif len(params) == 1:
            key = self.db.get_next_single(params[0])
            if key == None:
                # If there is no word to go after our param word, then just generate a sentence without parameters
                #return self.generate()

                # Return a message that this word hasn't been learned yet
                return f"I haven't yet extracted \"{params[0]}\" from chat."
            # Copy this for the sentence
            sentence = key.copy()
        else:
            # Get starting key
            key = self.db.get_start()
            # Copy this for the sentence
            sentence = key.copy()
        
        for _ in range(20):
            # Use key to get next word
            word = self.db.get_next(key)

            # Return if next word is the END
            if word == "<END>" or word == None:
                break

            # Otherwise add the word
            sentence.append(word)
            
            # Modify the key so on the next iteration it gets the next item
            key.pop(0)
            key.append(word)
        
        # If there were params, but the sentence resulting is identical to the params
        # Then the params did not result in an actual sentence
        # If so, restart without params
        if len(params) > 0 and params == sentence:
            #return self.generate()
            return "I haven't yet learned what to do with \"" + " ".join(params[-self.key_length:]) + "\""

        # Reset cooldown if a message was actually generated
        self.prev_message_t = time.time()

        return " ".join(sentence)

    def containsBannedWord(self, message):
        # Check if message contains any banned word
        low_mes = message.lower()
        #return True in [banned in low_mes for banned in self.banned_words]
        for banned in self.banned_words:
            if banned in low_mes:
                return True
        return False

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