
import json, os

class Settings:
    """ Loads data from settings.txt into the bot """
    
    PATH = os.path.join(os.getcwd(), "settings.txt")
    
    def __init__(self, bot):
        try:
            # Try to load the file using json.
            # And pass the data to the Bot class instance if this succeeds.
            with open(Settings.PATH, "r") as f:
                settings = f.read()
                data = json.loads(settings)
                bot.set_settings(data["Host"],
                                data["Port"],
                                data["Channel"],
                                data["Nickname"],
                                data["Authentication"],
                                data["DeniedUsers"],
                                data["BannedWords"],
                                data["Cooldown"],
                                data["KeyLength"],
                                data["MaxSentenceWordAmount"])

        except ValueError:
            logger.error("Error in settings file.")
            raise ValueError("Error in settings file.")

        except FileNotFoundError:
            # If the file is missing, create a standardised settings.txt file
            # With all parameters required.
            with open(Settings.PATH, "w") as f:
                standard_dict = {
                                    "Host": "irc.chat.twitch.tv",
                                    "Port": 6667,
                                    "Channel": "#<channel>",
                                    "Nickname": "<name>",
                                    "Authentication": "oauth:<auth>",
                                    "DeniedUsers": ["StreamElements", "Nightbot", "Moobot", "Marbiebot"],
                                    "BannedWords": ["<START>", "<END>"],
                                    "Cooldown": 20,
                                    "KeyLength": 2,
                                    "MaxSentenceWordAmount": 25
                                }
                f.write(json.dumps(standard_dict, indent=4, separators=(",", ": ")))
                raise ValueError("Please fix your settings.txt file that was just generated.")
    
    @staticmethod
    def update_cooldown(cooldown):
        with open(Settings.PATH, "r") as f:
            settings = f.read()
            data = json.loads(settings)
        data["Cooldown"] = cooldown
        with open(Settings.PATH, "w") as f:
            f.write(json.dumps(data, indent=4, separators=(",", ": ")))

    @staticmethod
    def get_channel():
        with open(Settings.PATH, "r") as f:
            settings = f.read()
            data = json.loads(settings)
            return data["Channel"].replace("#", "").lower()
