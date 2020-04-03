
from TwitchWebsocket import TwitchWebsocket
from nltk.tokenize import sent_tokenize
import time, logging, re, string

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
        self.cooldown = 20
        self.key_length = 2
        self.max_sentence_length = 20
        self.prev_message_t = 0
        self._enabled = True
        # This regex should detect similar phrases as links as Twitch does
        self.link_regex = re.compile("\w+\.[a-z]{2,}")
        # Make a translation table for removing punctuation efficiently
        self.punct_trans_table = str.maketrans("", "", string.punctuation)
        # List of moderators used in blacklist modification, includes broadcaster
        self.mod_list = []
        self.set_blacklist()

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

    def set_settings(self, host, port, chan, nick, auth, denied_users, cooldown, key_length, max_sentence_length):
        self.host = host
        self.port = port
        self.chan = chan
        self.nick = nick
        self.auth = auth
        self.denied_users = [user.lower() for user in denied_users] + [self.nick.lower()]
        self.cooldown = cooldown
        self.key_length = key_length
        self.max_sentence_length = max_sentence_length

    def message_handler(self, m):
        try:
            if m.type == "366":
                logging.info(f"Successfully joined channel: #{m.channel}")
                # Get the list of mods used for modifying the blacklist
                logging.info("Fetching mod list...")
                self.ws.send_message("/mods")

            elif m.type == "NOTICE":
                # Check whether the NOTICE is a response to our /mods request
                if m.message.startswith("The moderators of this channel are:"):
                    string_list = m.message.replace("The moderators of this channel are:", "").strip()
                    self.mod_list = [m.channel] + string_list.split(", ")
                    logging.info(f"Fetched mod list. Found {len(self.mod_list) - 1} mods.")
                elif m.message == "There are no moderators of this channel.":
                    self.mod_list = [m.channel]
                    logging.info(f"Fetched mod list. Found no mods.")
                # If it is not, log this NOTICE
                else:
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

                    cur_time = time.time()
                    if self.prev_message_t + self.cooldown < cur_time or self.check_if_streamer(m):
                        if self.check_filter(m.message):
                            sentence = "You can't make me say that, you madman!"
                        else:
                            params = m.message.split(" ")[1:]
                            # Generate an actual sentence
                            sentence = self.generate(params)
                        logging.info(sentence)
                        self.ws.send_message(sentence)
                    else:
                        if not self.db.check_whisper_ignore(m.user):
                            self.ws.send_whisper(m.user, f"Cooldown hit: {self.prev_message_t + self.cooldown - cur_time:0.2f} out of {self.cooldown:.0f}s remaining. !nopm to stop these cooldown pm's.")
                        logging.info(f"Cooldown hit with {self.prev_message_t + self.cooldown - cur_time:0.2f}s remaining")

                # Ignore the message if it is deemed a command
                elif self.check_if_other_command(m.message):
                    return
                
                # Ignore the message if it contains a link.
                elif self.check_link(m.message):
                    return
                    
                # Ignore the message if any word in the sentence is on the ban filter
                elif self.check_filter(m.message):
                    logging.warning(f"Sentence contained blacklisted word or phrase:\"{m.message}\"")
                    return
                
                else:
                    # Try to split up sentences. Requires nltk's 'punkt' resource
                    try:
                        sentences = sent_tokenize(m.message)
                    # If 'punkt' is not downloaded, then download it, and retry
                    except LookupError:
                        logging.debug("Downloading required punkt resource...")
                        import nltk
                        nltk.download('punkt')
                        logging.debug("Downloaded required punkt resource.")
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

                # Note that I add my own username to this list to allow me to manage the 
                # blacklist in channels of my bot in channels I am not modded in.
                # I may modify this and add a "allowed users" field in the settings file.
                elif m.user.lower() in self.mod_list + ["cubiedev"]:
                    # Adding to the blacklist
                    if self.check_if_our_command(m.message, "!blacklist"):
                        if len(m.message.split()) == 2:
                            # TODO: Remove newly blacklisted word from the Database
                            word = m.message.split()[1].lower()
                            self.blacklist.append(word)
                            logging.info(f"Added `{word}` to Blacklist.")
                            self.write_blacklist(self.blacklist)
                            self.ws.send_whisper(m.user, "Added word to Blacklist.")
                        else:
                            self.ws.send_whisper(m.user, "Expected Format: `!blacklist word` to add `word` to the blacklist")

                    # Removing from the blacklist
                    elif self.check_if_our_command(m.message, "!whitelist"):
                        if len(m.message.split()) == 2:
                            word = m.message.split()[1].lower()
                            try:
                                self.blacklist.remove(word)
                                logging.info(f"Removed `{word}` from Blacklist.")
                                self.write_blacklist(self.blacklist)
                                self.ws.send_whisper(m.user, "Removed word from Blacklist.")
                            except ValueError:
                                self.ws.send_whisper(m.user, "Word was already not in the blacklist.")
                        else:
                            self.ws.send_whisper(m.user, "Expected Format: `!whitelist word` to remove `word` from the blacklist.")
                    
                    # Checking whether a word is in the blacklist
                    elif self.check_if_our_command(m.message, "!check"):
                        if len(m.message.split()) == 2:
                            word = m.message.split()[1].lower()
                            if word in self.blacklist:
                                self.ws.send_whisper(m.user, "This word is in the Blacklist.")
                            else:
                                self.ws.send_whisper(m.user, "This word is not in the Blacklist.")
                        else:
                            self.ws.send_whisper(m.user, "Expected Format: `!check word` to check whether `word` is on the blacklist.")

            elif m.type == "CLEARMSG":
                # If a message is deleted, its contents will be unlearned
                # or rather, the "occurances" attribute of each combinations of words in the sentence
                # is reduced by 5, and deleted if the occurances is now less than 1. 
                self.db.unlearn(m.message)
                
                # TODO: Think of some efficient way to check whether it was our message that got deleted.
                # If the bot's message was deleted, log this as an error
                #if m.user.lower() == self.nick.lower():
                #    logging.error(f"This bot message was deleted: \"{m.message}\"")

        except Exception as e:
            logging.exception(e)
            
    def generate(self, params):

        # Check for commands or recursion, eg: !generate !generate
        if len(params) > 0:
            if self.check_if_other_command(params[0]):
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
                key = self.db.get_next_single_initial(0, params[0])
                if key == None:
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
                word = self.db.get_next_initial(i, key)
            else:
                word = self.db.get_next(i, key)

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

    def write_blacklist(self, blacklist):
        logging.debug("Writing Blacklist...")
        with open("blacklist.txt", "w") as f:
            f.write("\n".join(sorted(blacklist, key=lambda x: len(x), reverse=True)))
        logging.debug("Written Blacklist.")

    def set_blacklist(self) -> None:
        logging.debug("Loading Blacklist...")
        try:
            with open("blacklist.txt", "r") as f:
                self.blacklist = [l.replace("\n", "") for l in f.readlines()]
                logging.debug("Loaded Blacklist.")
        
        except FileNotFoundError:
            logging.warning("Loading Blacklist Failed!")
            self.blacklist = ["<start>", "<end>"]
            self.write_blacklist(self.blacklist)

    def check_filter(self, message) -> bool:
        # Returns True if message contains a banned word.
        for word in message.translate(self.punct_trans_table).lower().split():
            if word in self.blacklist:
                return True
        return False

    def check_if_our_command(self, message: str, *commands: "Tuple(str)") -> bool:
        # True if the first "word" of the message is either exactly command, or in the tuple of commands
        return message.split()[0] in commands

    def check_if_generate(self, message) -> bool:
        # True if the first "word" of the message is either !generate or !g.
        return self.check_if_our_command(message, "!generate", "!g")
    
    def check_if_other_command(self, message) -> bool:
        # Don't store commands, except /me
        return message.startswith(("!", "/", ".")) and not message.startswith("/me")
    
    def check_if_streamer(self, m) -> bool:
        # True if the user is the streamer
        return m.user == m.channel

    def check_link(self, message) -> bool:
        # True if message contains a link
        return self.link_regex.search(message)

if __name__ == "__main__":
    MarkovChain()
