
from TwitchWebsocket import TwitchWebsocket
from nltk.tokenize import sent_tokenize
import time, logging, re

from Log import Log
from Settings import Settings
Log(__file__, Settings.get_channel())

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
        self.max_sentence_length = 20
        self.prev_message_t = 0
        self._enabled = True
        self.link_regex = re.compile("((https?\:\/\/)(www\.)?|(www\.))([A-Za-z0-9]{3,}\.[^\s]*)")
        self.feedback_regex = re.compile("(bot|cubie|b0t|lul|poggers|pepehands)", flags=re.I)
        self.feedback_time = 30
        
        # Fill previously initialised variables with data from the settings.txt file
        Settings(self)
        self.db = Database(self.chan)

        self.ws = TwitchWebsocket(host=self.host, 
                                  port=self.port,
                                  chan=self.chan,
                                  nick=self.nick,
                                  auth=self.auth,
                                  callback=self.message_handler,
                                  capability=["commands"],
                                  live=True)
        self.ws.start_bot()

    def set_settings(self, host, port, chan, nick, auth, denied_users, banned_words, cooldown, key_length, max_sentence_length):
        self.host = host
        self.port = port
        self.chan = chan
        self.nick = nick
        self.auth = auth
        self.denied_users = [user.lower() for user in denied_users] + [self.nick.lower()]
        self.banned_words = [word.lower() for word in banned_words]
        self.cooldown = cooldown
        self.key_length = key_length
        self.max_sentence_length = max_sentence_length

    def message_handler(self, m):
        try:
            if m.type == "366":
                logging.info(f"Successfully joined channel: #{m.channel}")

            elif m.type == "NOTICE":
                logging.info(m.message)

            elif m.type in ("PRIVMSG", "WHISPER"):
                if m.message.startswith("!enable") and self.check_if_streamer(m):
                    if self._enabled:
                        self.ws.send_whisper(m.user, "The !generate is already enabled.")
                    else:
                        self.ws.send_whisper(m.user, "Users can now !generate message again.")
                        self._enabled = True

                elif m.message.startswith("!disable") and self.check_if_streamer(m):
                    if self._enabled:
                        self.ws.send_whisper(m.user, "Users can now no longer use !generate.")
                        self._enabled = False
                    else:
                        self.ws.send_whisper(m.user, "The !generate is already disabled.")

                elif m.message.startswith(("!setcooldown", "!setcd")) and self.check_if_streamer(m):
                    split_message = m.message.split(" ")
                    if len(split_message) == 2:
                        try:
                            cooldown = int(split_message[1])
                        except ValueError:
                            self.ws.send_whisper(m.user, f"The parameter must be an integer amount, eg: !setcd 30")
                            return
                        self.cooldown = cooldown
                        Settings.update_cooldown(cooldown)
                        self.ws.send_whisper(m.user, f"The !generate cooldown has been set to {cooldown} seconds.")
                    else:
                        self.ws.send_whisper(m.user, f"Please add exactly 1 integer parameter, eg: !setcd 30.")

            if m.type == "PRIVMSG":

                # Ignore bot messages
                if m.user.lower() in self.denied_users:
                    return
                
                if self.check_if_generate(m.message):
                    if not self._enabled:
                        if not self.db.check_whisper_ignore(m.user):
                            self.ws.send_whisper(m.user, "The !generate has been turned off. !nopm to stop me from whispering you.")
                        return

                    if self.prev_message_t + self.cooldown < time.time() or self.check_if_streamer(m):
                        # Get params
                        params = m.message.split(" ")[1:]
                        # Generate an actual sentence
                        sentence = self.generate(params)
                        self.ws.send_message(sentence)
                        logging.info(sentence)
                        self.db.log(sentence)
                    else:
                        if not self.db.check_whisper_ignore(m.user):
                            self.ws.send_whisper(m.user, f"Cooldown hit: {self.prev_message_t + self.cooldown - time.time():0.2f} out of {self.cooldown:.0f}s remaining. !nopm to stop these cooldown pm's.")
                        logging.info(f"Cooldown hit with {self.prev_message_t + self.cooldown - time.time():0.2f}s remaining")

                # Ignore the message if it is deemed a command
                elif self.check_if_command(m.message):
                    return
                    
                # Ignore the message if any word in the sentence is on the ban filter
                elif self.check_filter(m.message):
                    return
                
                # Ignore the message if it contains a link.
                elif self.check_link(m.message):
                    return
                
                else:
                    sentences = sent_tokenize(m.message)
                    for sentence in sentences:
                        # Get all seperate words
                        words = sentence.split(" ")
                        
                        # If the sentence is too short, ignore it and move on to the next.
                        if len(words) <= self.key_length:
                            continue
                        
                        # Add a new starting point for a sentence to the <START>
                        #self.db.add_rule(["<START>"] + [words[x] for x in range(self.key_length)])
                        self.db.add_start_queue([words[x] for x in range(self.key_length)])
                        
                        # Create Key variable which will be used as a key in the Dictionary for the grammar
                        key = list()
                        for word in words:
                            # Set up key for first use
                            if len(key) < self.key_length:
                                key.append(word)
                                continue
                            
                            self.db.add_rule_queue(key + [word])
                            
                            # Remove the first word, and add the current word,
                            # so that the key is correct for the next word.
                            key.pop(0)
                            key.append(word)
                        # Add <END> at the end of the sentence
                        self.db.add_rule_queue(key + ["<END>"])
                    self.db.execute_commit()

                    # In addition to learning, we will try to see if this message was feedback on a previous generation
                    if self.check_feedback(m.message):
                        self.db.feedback()
                    
            elif m.type == "WHISPER":
                # Allow people to whisper the bot to disable or enable whispers.
                if m.message == "!nopm":
                    logging.debug(f"Adding {m.user} to Do Not Whisper.")
                    self.db.add_whisper_ignore(m.user)
                    self.ws.send_whisper(m.user, "You will no longer be sent whispers. Type !yespm to reenable. ")

                elif m.message == "!yespm":
                    logging.debug(f"Removing {m.user} from Do Not Whisper.")
                    self.db.remove_whisper_ignore(m.user)
                    self.ws.send_whisper(m.user, "You will again be sent whispers. Type !nopm to disable again. ")

            elif m.type == "CLEARMSG":
                # If a message is deleted, its contents will be unlearned
                # or rather, the "occurances" attribute of each combinations of words in the sentence
                # is reduced by 5, and deleted if the occurances is now less than 1. 
                self.db.unlearn(m.message)
            else:
                print(m)

        except Exception as e:
            logging.exception(e)
            
    def generate(self, params):

        # Check for commands or recursion, eg: !generate !generate
        if len(params) > 0:
            if self.check_if_command(params[0]):
                return "You can't make me do commands, you madman!"

        # Get the starting key and starting sentence.
        # If there is more than 1 param, get the last 2 as the key.
        # Note that self.key_length is fixed to 2 in this implementation
        if len(params) > 1:
            key = params[-self.key_length:]
            # Copy the entire params for the sentence
            sentence = params.copy()

        elif len(params) == 1:
            # First we try to find if this word was once used as the first word in a sentence:
            key = self.db.get_next_single_start(params[0])
            if key == None:
                # If this failed, we try to find the next word in the grammar as a whole
                key = self.db.get_next_single_initial(params[0])
                if key == None:
                    # If there is no word to go after our param word, then just generate a sentence without parameters
                    # We don't do this anymore
                    #return self.generate()

                    # Return a message that this word hasn't been learned yet
                    return f"I haven't extracted \"{params[0]}\" from chat yet."
            # Copy this for the sentence
            sentence = key.copy()

        else: # if there are no params
            # Get starting key
            key = self.db.get_start()
            # Copy this for the sentence
            sentence = key.copy()
        
        for i in range(self.max_sentence_length - self.key_length):
            # Use key to get next word
            if i == 0:
                # Prevent fetching <END> on the first go
                word = self.db.get_next_initial(key)
            else:
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
            return "I haven't yet learned what to do with \"" + " ".join(params[-self.key_length:]) + "\""

        # Reset cooldown if a message was actually generated
        self.prev_message_t = time.time()

        return " ".join(sentence)

    def check_filter(self, message) -> bool:
        # Check if message contains any banned word
        low_mes = message.lower()
        #return True in [banned in low_mes for banned in self.banned_words]
        for banned in self.banned_words:
            if banned in low_mes:
                return True
        return False

    def check_if_generate(self, message) -> bool:
        # True if the first "word" of the message is either !generate or !g.
        return message.split()[0] in ("!generate", "!g")
    
    def check_if_command(self, message) -> bool:
        # Don't store commands, except /me
        return message.startswith(("!", "/", ".")) and not message.startswith("/me")
    
    def check_if_streamer(self, m) -> bool:
        # True if the user is the streamer
        return m.user == m.channel

    def check_link(self, message) -> bool:
        # True if message contains a link
        return self.link_regex.search(message)

    def check_feedback(self, message) -> bool:
        # True if message may contain feedback on a previous generation
        return time.time() < self.prev_message_t + self.feedback_time and self.feedback_regex.search(message)

if __name__ == "__main__":
    MarkovChain()
