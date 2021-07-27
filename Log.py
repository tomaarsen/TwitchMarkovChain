import logging
import os
import json
import logging.config


class Log():
    def __init__(self, main_file: str):
        # Dynamically change size set up for name in the logger
        this_file = os.path.basename(main_file)

        from Settings import Settings

        # If you have a logging config like me, use it
        if "PYTHON_LOGGING_CONFIG" in os.environ:
            logging.config.fileConfig(os.environ.get("PYTHON_LOGGING_CONFIG"),
                                      defaults={"logfilename": this_file.replace(".py", "_") + Settings.get_channel() + ".log"},
                                      disable_existing_loggers=False)
        else:
            # If you don't, use a standard config that outputs some INFO in the console
            logging.basicConfig(level=logging.INFO,
                                format=f'[%(asctime)s] [%(name)s] [%(levelname)-8s] - %(message)s')
