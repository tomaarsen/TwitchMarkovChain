
from typing import List, Tuple
from Log import Log
Log(__file__)

from TwitchWebsocket import Message, TwitchWebsocket
from nltk.tokenize import sent_tokenize
import socket, time, logging, re, string

from Settings import Settings, SettingsData
from Database import Database
from Timer import LoopingTimer

logger = logging.getLogger(__name__)

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
        self.help_message_timer = 7200
        self.automatic_generation_timer = -1
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

        # Set up daemon Timer to send help messages
        if self.help_message_timer > 0:
            if self.help_message_timer < 300:
                raise ValueError("Value for \"HelpMessageTimer\" in must be at least 300 seconds, or a negative number for no help messages.")
            t = LoopingTimer(self.help_message_timer, self.send_help_message)
            t.start()
        
        # Set up daemon Timer to send automatic generation messages
        if self.automatic_generation_timer > 0:
            if self.automatic_generation_timer < 30:
                raise ValueError("Value for \"AutomaticGenerationMessage\" in must be at least 30 seconds, or a negative number for no automatic generations.")
            t = LoopingTimer(self.automatic_generation_timer, self.send_automatic_generation_message)
            t.start()

        self.ws = TwitchWebsocket(host=self.host, 
                                  port=self.port,
                                  chan=self.chan,
                                  nick=self.nick,
                                  auth=self.auth,
                                  callback=self.message_handler,
                                  capability=["commands", "tags"],
                                  live=True)
        self.ws.start_bot()

    def set_settings(self, data: SettingsData):
        self.host = data["Host"]
        self.port = data["Port"]
        self.chan = data["Channel"]
        self.nick = data["Nickname"]
        self.auth = data["Authentication"]
        self.denied_users = [user.lower() for user in data["DeniedUsers"]] + [self.nick.lower()]
        self.bot_owner = data["BotOwner"].lower()
        self.cooldown = data["Cooldown"]
        self.key_length = data["KeyLength"]
        self.max_sentence_length = data["MaxSentenceWordAmount"]
        self.help_message_timer = data["HelpMessageTimer"]
        self.automatic_generation_timer = data["AutomaticGenerationTimer"]
        self.should_whisper = data["ShouldWhisper"]
        self.enable_generate_command = data["EnableGenerateCommand"]

    def message_handler(self, m: Message):
        try:
            if m.type == "366":
                logger.info(f"Successfully joined channel: #{m.channel}")
                # Get the list of mods used for modifying the blacklist
                logger.info("Fetching mod list...")
                self.ws.send_message("/mods")

            elif m.type == "NOTICE":
                # Check whether the NOTICE is a response to our /mods request
                if m.message.startswith("The moderators of this channel are:"):
                    string_list = m.message.replace("The moderators of this channel are:", "").strip()
                    self.mod_list = [m.channel] + string_list.split(", ")
                    logger.info(f"Fetched mod list. Found {len(self.mod_list) - 1} mods.")
                elif m.message == "There are no moderators of this channel.":
                    self.mod_list = [m.channel]
                    logger.info(f"Fetched mod list. Found no mods.")
                # If it is not, log this NOTICE
                else:
                    logger.info(m.message)

            elif m.type in ("PRIVMSG", "WHISPER"):
                if m.message.startswith("!enable") and self.check_if_streamer(m):
                    if self._enabled:
                        self.send_whisper(m.user, "The generate command is already enabled.")
                    else:
                        self.send_whisper(m.user, "Users can now use generate command again.")
                        self._enabled = True
                        logger.info("Users can now use generate command again.")

                elif m.message.startswith("!disable") and self.check_if_streamer(m):
                    if self._enabled:
                        self.send_whisper(m.user, "Users can now no longer use generate command.")
                        self._enabled = False
                        logger.info("Users can now no longer use generate command.")
                    else:
                        self.send_whisper(m.user, "The generate command is already disabled.")

                elif m.message.startswith(("!setcooldown", "!setcd")) and self.check_if_streamer(m):
                    split_message = m.message.split(" ")
                    if len(split_message) == 2:
                        try:
                            cooldown = int(split_message[1])
                        except ValueError:
                            self.send_whisper(m.user, f"The parameter must be an integer amount, eg: !setcd 30")
                            return
                        self.cooldown = cooldown
                        Settings.update_cooldown(cooldown)
                        self.send_whisper(m.user, f"The !generate cooldown has been set to {cooldown} seconds.")
                    else:
                        self.send_whisper(m.user, f"Please add exactly 1 integer parameter, eg: !setcd 30.")

            if m.type == "PRIVMSG":

                # Ignore bot messages
                if m.user.lower() in self.denied_users:
                    return
                
                if self.check_if_generate(m.message):
                    if not self.enable_generate_command and not self.check_if_streamer(m):
                        return

                    if not self._enabled:
                        if not self.db.check_whisper_ignore(m.user):
                            self.send_whisper(m.user, "The !generate has been turned off. !nopm to stop me from whispering you.")
                        return

                    cur_time = time.time()
                    if self.prev_message_t + self.cooldown < cur_time or self.check_if_streamer(m):
                        if self.check_filter(m.message):
                            sentence = "You can't make me say that, you madman!"
                        else:
                            params = m.message.split(" ")[1:]
                            # Generate an actual sentence
                            sentence, success = self.generate(params)
                            if success:
                                # Reset cooldown if a message was actually generated
                                self.prev_message_t = time.time()
                        logger.info(sentence)
                        self.ws.send_message(sentence)
                    else:
                        if not self.db.check_whisper_ignore(m.user):
                            self.send_whisper(m.user, f"Cooldown hit: {self.prev_message_t + self.cooldown - cur_time:0.2f} out of {self.cooldown:.0f}s remaining. !nopm to stop these cooldown pm's.")
                        logger.info(f"Cooldown hit with {self.prev_message_t + self.cooldown - cur_time:0.2f}s remaining")
                    return
                
                # Send help message when requested.
                elif m.message.startswith(("!ghelp", "!genhelp", "!generatehelp")):
                    self.send_help_message()

                # Ignore the message if it is deemed a command
                elif self.check_if_other_command(m.message):
                    return
                
                # Ignore the message if it contains a link.
                elif self.check_link(m.message):
                    return

                if "emotes" in m.tags:
                    # If the list of emotes contains "emotesv2_", then the message contains a bit emote, 
                    # and we choose not to learn from those messages.
                    if "emotesv2_" in m.tags["emotes"]:
                        return

                    # Replace modified emotes with normal versions, 
                    # as the bot will never have the modified emotes unlocked at the time.
                    for modifier in self.extract_modifiers(m.tags["emotes"]):
                        m.message = m.message.replace(modifier, "")

                # Ignore the message if any word in the sentence is on the ban filter
                if self.check_filter(m.message):
                    logger.warning(f"Sentence contained blacklisted word or phrase:\"{m.message}\"")
                    return
                
                else:
                    # Try to split up sentences. Requires nltk's 'punkt' resource
                    try:
                        sentences = sent_tokenize(m.message.strip())
                    # If 'punkt' is not downloaded, then download it, and retry
                    except LookupError:
                        logger.debug("Downloading required punkt resource...")
                        import nltk
                        nltk.download('punkt')
                        logger.debug("Downloaded required punkt resource.")
                        sentences = sent_tokenize(m.message.strip())

                    for sentence in sentences:
                        # Get all seperate words
                        words = sentence.split(" ")
                        # Double spaces will lead to invalid rules. We remove empty words here
                        if "" in words:
                            words = [word for word in words if word]
                            
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
                    
            elif m.type == "WHISPER":
                # Allow people to whisper the bot to disable or enable whispers.
                if m.message == "!nopm":
                    logger.debug(f"Adding {m.user} to Do Not Whisper.")
                    self.db.add_whisper_ignore(m.user)
                    self.send_whisper(m.user, "You will no longer be sent whispers. Type !yespm to reenable. ")

                elif m.message == "!yespm":
                    logger.debug(f"Removing {m.user} from Do Not Whisper.")
                    self.db.remove_whisper_ignore(m.user)
                    self.send_whisper(m.user, "You will again be sent whispers. Type !nopm to disable again. ")

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
                            logger.info(f"Added `{word}` to Blacklist.")
                            self.write_blacklist(self.blacklist)
                            self.send_whisper(m.user, "Added word to Blacklist.")
                        else:
                            self.send_whisper(m.user, "Expected Format: `!blacklist word` to add `word` to the blacklist")

                    # Removing from the blacklist
                    elif self.check_if_our_command(m.message, "!whitelist"):
                        if len(m.message.split()) == 2:
                            word = m.message.split()[1].lower()
                            try:
                                self.blacklist.remove(word)
                                logger.info(f"Removed `{word}` from Blacklist.")
                                self.write_blacklist(self.blacklist)
                                self.send_whisper(m.user, "Removed word from Blacklist.")
                            except ValueError:
                                self.send_whisper(m.user, "Word was already not in the blacklist.")
                        else:
                            self.send_whisper(m.user, "Expected Format: `!whitelist word` to remove `word` from the blacklist.")
                    
                    # Checking whether a word is in the blacklist
                    elif self.check_if_our_command(m.message, "!check"):
                        if len(m.message.split()) == 2:
                            word = m.message.split()[1].lower()
                            if word in self.blacklist:
                                self.send_whisper(m.user, "This word is in the Blacklist.")
                            else:
                                self.send_whisper(m.user, "This word is not in the Blacklist.")
                        else:
                            self.send_whisper(m.user, "Expected Format: `!check word` to check whether `word` is on the blacklist.")

            elif m.type == "CLEARMSG":
                # If a message is deleted, its contents will be unlearned
                # or rather, the "occurances" attribute of each combinations of words in the sentence
                # is reduced by 5, and deleted if the occurances is now less than 1. 
                self.db.unlearn(m.message)
                
                # TODO: Think of some efficient way to check whether it was our message that got deleted.
                # If the bot's message was deleted, log this as an error
                #if m.user.lower() == self.nick.lower():
                #    logger.error(f"This bot message was deleted: \"{m.message}\"")

        except Exception as e:
            logger.exception(e)
            
    def generate(self, params: List[str]) -> "Tuple[str, bool]":

        # Check for commands or recursion, eg: !generate !generate
        if len(params) > 0:
            if self.check_if_other_command(params[0]):
                return "You can't make me do commands, you madman!", False

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
                    return f"I haven't extracted \"{params[0]}\" from chat yet.", False
            # Copy this for the sentence
            sentence = key.copy()

        else: # if there are no params
            # Get starting key
            key = self.db.get_start()
            if key:
                # Copy this for the sentence
                sentence = key.copy()
            else:
                # If nothing's ever been said
                return "There is not enough learned information yet.", False
        
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
            return "I haven't yet learned what to do with \"" + " ".join(params[-self.key_length:]) + "\"", False

        return " ".join(sentence), True

    def extract_modifiers(self, emotes: str) -> list:
        output = []
        try:
            while emotes:
                u_index = emotes.index("_")
                c_index = emotes.index(":", u_index)
                output.append(emotes[u_index:c_index])
                emotes = emotes[c_index:]
        except ValueError:
            pass
        return output

    def write_blacklist(self, blacklist: List[str]) -> None:
        logger.debug("Writing Blacklist...")
        with open("blacklist.txt", "w") as f:
            f.write("\n".join(sorted(blacklist, key=lambda x: len(x), reverse=True)))
        logger.debug("Written Blacklist.")

    def set_blacklist(self) -> None:
        logger.debug("Loading Blacklist...")
        try:
            with open("blacklist.txt", "r") as f:
                self.blacklist = [l.replace("\n", "") for l in f.readlines()]
                logger.debug("Loaded Blacklist.")
        
        except FileNotFoundError:
            logger.warning("Loading Blacklist Failed!")
            self.blacklist = ["<start>", "<end>"]
            self.write_blacklist(self.blacklist)

    def send_help_message(self) -> None:
        # Send a Help message to the connected chat, as long as the bot wasn't disabled
        if self._enabled:
            logger.info("Help message sent.")
            try:
                self.ws.send_message("Learn how this bot generates sentences here: https://github.com/CubieDev/TwitchMarkovChain#how-it-works")
            except socket.OSError as error:
                logger.warning(f"[OSError: {error}] upon sending help message. Ignoring.")

    def send_automatic_generation_message(self) -> None:
        # Send an automatic generation message to the connected chat, 
        # as long as the bot wasn't disabled, just like if someone
        # typed "!g" in chat.
        if self._enabled:
            sentence, success = self.generate([])
            if success:
                logger.info(sentence)
                # Try to send a message. Just log a warning on fail
                try:
                    self.ws.send_message(sentence)
                except socket.OSError as error:
                    logger.warning(f"[OSError: {error}] upon sending automatic generation message. Ignoring.")
            else:
                logger.info("Attempted to output automatic generation message, but there is not enough learned information yet.")

    def send_whisper(self, user: str, message: str):
        if self.should_whisper:
            self.ws.send_whisper(user, message)
        return

    def check_filter(self, message: str) -> bool:
        # Returns True if message contains a banned word.
        for word in message.translate(self.punct_trans_table).lower().split():
            if word in self.blacklist:
                return True
        return False

    def check_if_our_command(self, message: str, *commands: "Tuple[str]") -> bool:
        # True if the first "word" of the message is either exactly command, or in the tuple of commands
        return message.split()[0] in commands

    def check_if_generate(self, message: str) -> bool:
        # True if the first "word" of the message is either !generate or !g.
        return self.check_if_our_command(message, "!generate", "!g")
    
    def check_if_other_command(self, message: str) -> bool:
        # Don't store commands, except /me
        return message.startswith(("!", "/", ".")) and not message.startswith("/me")
    
    def check_if_streamer(self, m: Message) -> bool:
        # True if the user is the streamer
        return m.user == m.channel or self.check_if_owner(m)

    def check_if_owner(self, m: Message) -> bool:
        return m.user == self.bot_owner;

    def check_link(self, message: str) -> bool:
        # True if message contains a link
        return self.link_regex.search(message)

if __name__ == "__main__":
    MarkovChain()
