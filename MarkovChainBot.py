
from typing import List, Tuple

from TwitchWebsocket import Message, TwitchWebsocket
from nltk.tokenize import sent_tokenize
import socket, time, logging, re, string

from Settings import Settings, SettingsData
from Database import Database
from Timer import LoopingTimer
from Tokenizer import detokenize, tokenize

from Log import Log
Log(__file__)

logger = logging.getLogger(__name__)

class MarkovChain:
    def __init__(self):
        self.prev_message_t = 0
        self._enabled = True
        # This regex should detect similar phrases as links as Twitch does
        self.link_regex = re.compile("\w+\.[a-z]{2,}")
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

    def set_settings(self, settings: SettingsData):
        """Fill class instance attributes based on the settings file.

        Args:
            settings (SettingsData): The settings dict with information from the settings file.
        """
        self.host = settings["Host"]
        self.port = settings["Port"]
        self.chan = settings["Channel"]
        self.nick = settings["Nickname"]
        self.auth = settings["Authentication"]
        self.denied_users = [user.lower() for user in settings["DeniedUsers"]] + [self.nick.lower()]
        self.allowed_users = [user.lower() for user in settings["AllowedUsers"]]
        self.cooldown = settings["Cooldown"]
        self.key_length = settings["KeyLength"]
        self.max_sentence_length = settings["MaxSentenceWordAmount"]
        self.min_sentence_length = settings["MinSentenceWordAmount"]
        self.help_message_timer = settings["HelpMessageTimer"]
        self.automatic_generation_timer = settings["AutomaticGenerationTimer"]
        self.whisper_cooldown = settings["WhisperCooldown"]
        self.enable_generate_command = settings["EnableGenerateCommand"]
        self.sent_separator = settings["SentenceSeparator"]
        self.allow_generate_params = settings["AllowGenerateParams"]
        self.generate_commands = tuple(settings["GenerateCommands"])

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
                if m.message.startswith("!enable") and self.check_if_permissions(m):
                    if self._enabled:
                        self.ws.send_whisper(m.user, "The generate command is already enabled.")
                    else:
                        self.ws.send_whisper(m.user, "Users can now use generate command again.")
                        self._enabled = True
                        logger.info("Users can now use generate command again.")

                elif m.message.startswith("!disable") and self.check_if_permissions(m):
                    if self._enabled:
                        self.ws.send_whisper(m.user, "Users can now no longer use generate command.")
                        self._enabled = False
                        logger.info("Users can now no longer use generate command.")
                    else:
                        self.ws.send_whisper(m.user, "The generate command is already disabled.")

                elif m.message.startswith(("!setcooldown", "!setcd")) and self.check_if_permissions(m):
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
                    if not self.enable_generate_command and not self.check_if_permissions(m):
                        return

                    if not self._enabled:
                        if not self.db.check_whisper_ignore(m.user):
                            self.send_whisper(m.user, "The !generate has been turned off. !nopm to stop me from whispering you.")
                        return

                    cur_time = time.time()
                    if self.prev_message_t + self.cooldown < cur_time or self.check_if_permissions(m):
                        if self.check_filter(m.message):
                            sentence = "You can't make me say that, you madman!"
                        else:
                            params = tokenize(m.message)[2:] if self.allow_generate_params else None
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
                        logger.info(f"Cooldown hit with {self.prev_message_t + self.cooldown - cur_time:0.2f}s remaining.")
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
                    self.ws.send_whisper(m.user, "You will no longer be sent whispers. Type !yespm to reenable. ")

                elif m.message == "!yespm":
                    logger.debug(f"Removing {m.user} from Do Not Whisper.")
                    self.db.remove_whisper_ignore(m.user)
                    self.ws.send_whisper(m.user, "You will again be sent whispers. Type !nopm to disable again. ")

                # Note that I add my own username to this list to allow me to manage the 
                # blacklist in channels of my bot in channels I am not modded in.
                # I may modify this and add a "allowed users" field in the settings file.
                elif m.user.lower() in self.mod_list + ["cubiedev"] + self.allowed_users:
                    # Adding to the blacklist
                    if self.check_if_our_command(m.message, "!blacklist"):
                        if len(m.message.split()) == 2:
                            # TODO: Remove newly blacklisted word from the Database
                            word = m.message.split()[1].lower()
                            self.blacklist.append(word)
                            logger.info(f"Added `{word}` to Blacklist.")
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
                                logger.info(f"Removed `{word}` from Blacklist.")
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
                #    logger.error(f"This bot message was deleted: \"{m.message}\"")

        except Exception as e:
            logger.exception(e)

    def generate(self, params: List[str] = None) -> "Tuple[str, bool]":
        """Given an input sentence, generate the remainder of the sentence using the learned data.

        Args:
            params (List[str]): A list of words to use as an input to use as the start of generating.
        
        Returns:
            Tuple[str, bool]: A tuple of a sentence as the first value, and a boolean indicating
                whether the generation succeeded as the second value.
        """
        if params is None:
            params = []

        # List of sentences that will be generated. In some cases, multiple sentences will be generated,
        # e.g. when the first sentence has less words than self.min_sentence_length.
        sentences = [[]]

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
            sentences[0] = params.copy()

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
            sentences[0] = key.copy()

        else: # if there are no params
            # Get starting key
            key = self.db.get_start()
            if key:
                # Copy this for the sentence
                sentences[0] = key.copy()
            else:
                # If nothing's ever been said
                return "There is not enough learned information yet.", False
        
        # Counter to prevent infinite loops (i.e. constantly generating <END> while below the 
        # minimum number of words to generate)
        i = 0
        while self.sentence_length(sentences) < self.max_sentence_length and i < self.max_sentence_length * 2:
            # Use key to get next word
            if i == 0:
                # Prevent fetching <END> on the first word
                word = self.db.get_next_initial(i, key)
            else:
                word = self.db.get_next(i, key)

            i += 1

            if word == "<END>" or word == None:
                # Break, unless we are before the min_sentence_length
                if i < self.min_sentence_length:
                    key = self.db.get_start()
                    # Ensure that the key can be generated. Otherwise we still stop.
                    if key:
                        # Start a new sentence
                        sentences.append([])
                        for entry in key:
                            sentences[-1].append(entry)
                        continue
                break

            # Otherwise add the word
            sentences[-1].append(word)
            
            # Shift the key so on the next iteration it gets the next item
            key.pop(0)
            key.append(word)
        
        # If there were params, but the sentence resulting is identical to the params
        # Then the params did not result in an actual sentence
        # If so, restart without params
        if len(params) > 0 and params == sentences[0]:
            return "I haven't yet learned what to do with \"" + detokenize(params[-self.key_length:]) + "\"", False

        return self.sent_separator.join(detokenize(sentence) for sentence in sentences), True

    def sentence_length(self, sentences: List[List[str]]) -> int:
        """Given a list of tokens representing a sentence, return the number of words in there.

        Args:
            sentences (List[List[str]]): List of lists of tokens that make up a sentence,
                where a token is a word or punctuation. For example:
                [['Hello', ',', 'you', "'re", 'Tom', '!'], ['Yes', ',', 'I', 'am', '.']]
                This would return 6.

        Returns:
            int: The number of words in the sentence.
        """
        count = 0
        for sentence in sentences:
            for token in sentence:
                if token not in string.punctuation and token[0] != "'":
                    count += 1
        return count

    def extract_modifiers(self, emotes: str) -> List[str]:
        """Extract emote modifiers from emotes, such as the the horizontal flip.

        Args:
            emotes (str): String containing all emotes used in the message.
        
        Returns:
            List[str]: List of strings that show modifiers, such as "_HZ" for horizontal flip.
        """
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
        """Write blacklist.txt given a list of banned words.

        Args:
            blacklist (List[str]): The list of banned words to write.
        """
        logger.debug("Writing Blacklist...")
        with open("blacklist.txt", "w") as f:
            f.write("\n".join(sorted(blacklist, key=lambda x: len(x), reverse=True)))
        logger.debug("Written Blacklist.")

    def set_blacklist(self) -> None:
        """Read blacklist.txt and set `self.blacklist` to the list of banned words."""
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
        """Send a Help message to the connected chat, as long as the bot wasn't disabled."""
        if self._enabled:
            logger.info("Help message sent.")
            try:
                self.ws.send_message("Learn how this bot generates sentences here: https://github.com/CubieDev/TwitchMarkovChain#how-it-works")
            except socket.OSError as error:
                logger.warning(f"[OSError: {error}] upon sending help message. Ignoring.")

    def send_automatic_generation_message(self) -> None:
        """Send an automatic generation message to the connected chat.
        
        As long as the bot wasn't disabled, just like if someone typed "!g" in chat.
        """
        if self._enabled:
            sentence, success = self.generate()
            if success:
                logger.info(sentence)
                # Try to send a message. Just log a warning on fail
                try:
                    self.ws.send_message(sentence)
                except socket.OSError as error:
                    logger.warning(f"[OSError: {error}] upon sending automatic generation message. Ignoring.")
            else:
                logger.info("Attempted to output automatic generation message, but there is not enough learned information yet.")

    def send_whisper(self, user: str, message: str) -> None:
        """Optionally send a whisper, only if "WhisperCooldown" is True.
        
        Args:
            user (str): The user to potentially whisper.
            message (str): The message to potentially whisper
        """
        if self.whisper_cooldown:
            self.ws.send_whisper(user, message)

    def check_filter(self, message: str) -> bool:
        """Returns True if message contains a banned word.
        
        Args:
            message (str): The message to check.
        """
        for word in tokenize(message):
            if word.lower() in self.blacklist:
                return True
        return False

    def check_if_our_command(self, message: str, *commands: "Tuple[str]") -> bool:
        """True if the first "word" of the message is in the tuple of commands

        Args:
            message (str): The message to check for a command.
            commands (Tuple[str]): A tuple of commands.

        Returns:
            bool: True if the first word in message is one of the commands.
        """
        return message.split()[0] in commands

    def check_if_generate(self, message: str) -> bool:
        """True if the first "word" of the message is one of the defined generate commands.

        Args:
            message (str): The message to check for the generate command (i.e !generate or !g).
        
        Returns:
            bool: True if the first word in message is a generate command.
        """
        return self.check_if_our_command(message, *self.generate_commands)
    
    def check_if_other_command(self, message: str) -> bool:
        """True if the message is any command, except /me. 

        Is used to avoid learning and generating commands.

        Args:
            message (str): The message to check.

        Returns:
            bool: True if the message is any potential command (starts with a '!', '/' or '.')
                with the exception of /me.
        """
        return message.startswith(("!", "/", ".")) and not message.startswith("/me")
    
    def check_if_permissions(self, m: Message) -> bool:
        """True if the user has heightened permissions.
        
        E.g. permissions to bypass cooldowns, update settings, disable the bot, etc.
        True for the streamer themselves, and the users set as the allowed users.

        Args:
            m (Message): The Message object that was sent from Twitch. 
                Has `user` and `channel` attributes.
        """
        return m.user == m.channel or m.user in self.allowed_users

    def check_link(self, message: str) -> bool:
        """True if `message` contains a link.

        Args:
            message (str): The message to check for a link.

        Returns:
            bool: True if the message contains a link.
        """
        return self.link_regex.search(message)

if __name__ == "__main__":
    MarkovChain()
