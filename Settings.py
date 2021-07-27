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
    SentenceSeparator: str

class Settings:
    """ Loads data from settings.json into the bot """
    
    PATH = os.path.join(os.getcwd(), "settings.json")
    
    DEFAULTS: SettingsData = {
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
        "EnableGenerateCommand": True,
        "SentenceSeparator": " - ",
        "AllowGenerateParams": True,
        "GenerateCommands": ["!generate", "!g"]
    }

    def __init__(self, bot) -> None:
        """Initialize the MarkovChain bot instance with the contents of the settings file

        Args:
            bot (MarkovChain): The MarkovChain bot instance.
        """
        settings = Settings.read_settings()
        bot.set_settings(settings)
    
    @staticmethod
    def read_settings() -> dict:
        """Read the settings file and return the contents as a dict.

        Updates the settings file from an old version, if needed.

        Raises:
            ValueError: Whenever the settings.json file is not valid JSON.
            FileNotFoundError: Whenever the settings file was not found. 
                Will generate a new default settings file.

        Returns:
            dict: The contents of the settings.json file.
        """
        # Potentially update the settings structure used to the newest version
        Settings.update_v2()

        try:
            # Try to load the file using json.
            # And pass the data to the Bot class instance if this succeeds.
            with open(Settings.PATH, "r") as f:
                text_settings = f.read()
                settings: SettingsData = json.loads(text_settings)
                Settings.update_v1(settings)

                # Check if any settings keys are missing, and if so, write the defaults
                # to the settings.json
                if settings.keys() != Settings.DEFAULTS.keys():
                    missing_keys = set(Settings.DEFAULTS.keys()) - set(settings.keys())
                    # Log the missing keys
                    logger.info(f"The following keys were missing from {Settings.PATH}: {', '.join(map(repr, missing_keys))}.")
                    logger.info(f"These defaults of these values were used, and added to {Settings.PATH}. Default behaviour will not change.")

                    # Add missing defaults
                    settings = {**Settings.DEFAULTS, **settings}
                    Settings.write_settings_file(settings)

                return settings

        except ValueError:
            logger.error("Error in settings file.")
            raise ValueError("Error in settings file.")

        except FileNotFoundError:
            Settings.write_default_settings_file()
            raise ValueError("Please fix your settings file that was just generated.")

    @staticmethod
    def update_v1(settings: SettingsData) -> None:
        """Update settings file to remove the BannedWords field, in favor for a blacklist.txt file.

        Args:
            settings (SettingsData): [description]
        """
        # "BannedWords" is only a key in the settings in older versions.
        # We moved to a separate file for blacklisted words.
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
    def update_v2() -> None:
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
            # If settings.txt does not exist, then we're not on an old version.
            pass

    @staticmethod
    def write_default_settings_file() -> None:
        """Create a standardised settings file with default values."""
        Settings.write_settings_file(Settings.DEFAULTS)

    @staticmethod
    def write_settings_file(settings: SettingsData) -> None:
        with open(Settings.PATH, "w") as f:
            f.write(json.dumps(settings, indent=4, separators=(",", ": ")))

    @staticmethod
    def update_cooldown(cooldown: int) -> None:
        """Update the "Cooldown" value in the settings file.

        Args:
            cooldown (int): The integer representing the amount of seconds of cooldown 
                between outputted generations.
        """
        with open(Settings.PATH, "r") as f:
            settings = f.read()
            data = json.loads(settings)

        data["Cooldown"] = cooldown

        with open(Settings.PATH, "w") as f:
            f.write(json.dumps(data, indent=4, separators=(",", ": ")))

    @staticmethod
    def get_channel() -> str:
        """Get the "Channel" value from the settings file.

        Returns:
            str: The name of the Channel described in the settings file. 
                Stripped of "#" and converted to lowercase.
        """
        settings = Settings.read_settings()
        return settings["Channel"].replace("#", "").lower()