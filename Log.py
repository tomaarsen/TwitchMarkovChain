import logging, os, json
import logging.config

class Log():
    def __init__(self, main_file):
        # Dynamically change size set up for name in the logger
        here = os.path.abspath(os.path.dirname(main_file))
        this_file = os.path.basename(main_file)
        
        # "root" is already 4
        max_name_size = 4
        for fname in os.listdir(here):
            if fname.endswith(".py") and fname != this_file:
                # Offset my 3 due to .py
                if max_name_size + 3 < len(fname):
                    max_name_size = len(fname) - 3

        # If you have a logging config like me, use it
        if "PYTHON_LOGGING_CONFIG" in os.environ:
            logging.config.fileConfig(os.environ.get("PYTHON_LOGGING_CONFIG"), defaults={"logfilename": this_file.replace(".py", "_") + Log.get_channel() + ".log"})
        else:
            # If you don't, use a standard config that outputs some INFO in the console
            logging.basicConfig(level=logging.INFO, format=f'[%(asctime)s] [%(name)-{max_name_size}s] [%(levelname)-8s] - %(message)s')

    @staticmethod
    def get_channel():
        try:
            with open(os.path.join(os.getcwd(), "settings.txt"), "r") as f:
                settings = f.read()
                data = json.loads(settings)
                return data["Channel"].replace("#", "").lower()
        
        except FileNotFoundError:
            from Settings import Settings
            Settings.write_default_settings_file()
            raise ValueError("Please fix your settings.txt file that was just generated.")