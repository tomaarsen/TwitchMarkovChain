import json, os, logging
from typing import List
try:
    from typing import TypedDict
except ImportError:
    TypedDict = object

logger = logging.getLogger(__name__)

class SettingsData(TypedDict):
    Host: str
    Port: int
    Channel: str
    Nickname: str
    Authentication: str
    DeniedUsers: List[str]
    AllowedUsers: List[str]
    Cooldown: int
    KeyLength: int
    MaxSentenceWordAmount: int
    MinSentenceWordAmount: int
    HelpMessageTimer: int
    AutomaticGenerationTimer: int
    WhisperCooldown: bool
    EnableGenerateCommand: bool

class Settings:
    """ Loads data from settings.json into the bot """
    
    PATH = os.path.join(os.getcwd(), "settings.json")
    
    DEFAULTS = {
        "Host": "irc.chat.twitch.tv",
        "Port": 6667,
        "Channel": "#<channel>",
        "Nickname": "<name>",
        "Authentication": "oauth:<auth>",
        "DeniedUsers": ["StreamElements", "Nightbot", "Moobot", "Marbiebot"],
        "AllowedUsers": [],
        "Cooldown": 20,
        "KeyLength": 2,
        "MaxSentenceWordAmount": 25,
        "MinSentenceWordAmount": -1,
        "HelpMessageTimer": 60 * 60 * 5, # 18000 seconds, 5 hours
        "AutomaticGenerationTimer": -1,
        "WhisperCooldown": True,
        "EnableGenerateCommand": True
    }

    def __init__(self, bot):
        settings = Settings.read_settings()
        bot.set_settings(settings)
    
    @staticmethod
    def read_settings():
        # Potentially update the settings structure used to the newest version
        Settings.update_v2()

        try:
            # Try to load the file using json.
            # And pass the data to the Bot class instance if this succeeds.
            with open(Settings.PATH, "r") as f:
                text_settings = f.read()
                settings: SettingsData = json.loads(text_settings)
                # "BannedWords" is only a key in the settings in older versions.
                # We moved to a separate file for blacklisted words.
                Settings.update_v1(settings)

                return settings

        except ValueError:
            logger.error("Error in settings file.")
            raise ValueError("Error in settings file.")

        except FileNotFoundError:
            Settings.write_default_settings_file()
            raise ValueError("Please fix your settings file that was just generated.")

    @staticmethod
    def update_v1(settings: SettingsData):
        """Update settings file to remove the BannedWords field, in favor for a blacklist.txt file."""
        if "BannedWords" in settings:
            logger.info("Updating Blacklist system to new version...")
            try:
                with open("blacklist.txt", "r+") as f:
                    logger.info("Moving Banned Words to the blacklist.txt file...")
                    # Read the data, and split by word or phrase, then add BannedWords
                    banned_list = f.read().split("\n") + settings["BannedWords"]
                    # Remove duplicates and sort by length, longest to shortest
                    banned_list = sorted(list(set(banned_list)), key=lambda x: len(x), reverse=True)
                    # Clear file, and then write in the new data
                    f.seek(0)
                    f.truncate(0)
                    f.write("\n".join(banned_list))
                    logger.info("Moved Banned Words to the blacklist.txt file.")
            
            except FileNotFoundError:
                with open("blacklist.txt", "w") as f:
                    logger.info("Moving Banned Words to a new blacklist.txt file...")
                    # Remove duplicates and sort by length, longest to shortest
                    banned_list = sorted(list(set(settings["BannedWords"])), key=lambda x: len(x), reverse=True)
                    f.write("\n".join(banned_list))
                    logger.info("Moved Banned Words to a new blacklist.txt file.")
            
            # Remove BannedWords list from data dictionary, and then write it to the settings file
            del settings["BannedWords"]

            with open(Settings.PATH, "w") as f:
                f.write(json.dumps(settings, indent=4, separators=(",", ": ")))
            
            logger.info("Updated Blacklist system to new version.")

    @staticmethod
    def update_v2():
        """Converts `settings.txt` to `settings.json`, and adds missing new fields."""
        try:
            # Try to load the old settings.txt file using json.
            with open("settings.txt", "r") as f:
                settings = f.read()
                data: SettingsData = json.loads(settings)
                # Add missing fields from Settings.DEFAULT to data
                corrected_data = {**Settings.DEFAULTS, **data}
            
            # Write the new settings file
            with open(Settings.PATH, "w") as f:
                f.write(json.dumps(corrected_data, indent=4, separators=(",", ": ")))

            os.remove("settings.txt")

            logger.info("Updated Settings system to new version. See \"settings.json\" for new fields, and README.md for information on these fields.")

        except FileNotFoundError:
            pass

    @staticmethod
    def write_default_settings_file():
        # If the file is missing, create a standardised settings.json file
        # With all parameters required.
        with open(Settings.PATH, "w") as f:
            f.write(json.dumps(Settings.DEFAULTS, indent=4, separators=(",", ": ")))

    @staticmethod
    def update_cooldown(cooldown: int):
        with open(Settings.PATH, "r") as f:
            settings = f.read()
            data = json.loads(settings)
        data["Cooldown"] = cooldown
        with open(Settings.PATH, "w") as f:
            f.write(json.dumps(data, indent=4, separators=(",", ": ")))

    @classmethod
    def get_channel(cls):
        settings = Settings.read_settings()
        return settings["Channel"].replace("#", "").lower()