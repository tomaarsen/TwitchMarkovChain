
from TwitchWebsocket import TwitchWebsocket
from nltk.tokenize import sent_tokenize
import time, logging

from Log import Log
Log(__file__)

from Settings import Settings
from Database import Database

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
        self.db = Database(self.chan)

        self.ws = TwitchWebsocket(host=self.host, 
                                  port=self.port,
                                  chan=self.chan,
                                  nick=self.nick,
                                  auth=self.auth,
                                  callback=self.message_handler,
                                  capability=None,
                                  live=True)

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
                
                if m.message.startswith("!generate"):
                    if self.prev_message_t + self.cooldown < time.time():
                        # Get params
                        params = m.message.split(" ")[1:]
                        # Generate an actual sentence
                        sentence = self.generate(params)
                        logging.info(sentence)
                        self.ws.send_message(sentence)
                    else:
                        logging.info(f"Cooldown hit with {self.prev_message_t + self.cooldown - time.time():0.2f}s remaining")
                    
                elif self.checkIfCommand(m.message):
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

        #TODO If Params are sent, test Start first

        if len(params) > 0:
            if self.checkIfCommand(params[0]):
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
    
    def checkIfCommand(self, message):
        # Don't store commands, except /me
        return message.startswith(("!", "/", ".")) and not message.startswith("/me")

if __name__ == "__main__":
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