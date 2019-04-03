# TwitchMarkovChain
Twitch bot for generating messages based on what it learned from chat 

---
# Explanation
When the bot has started, it will start listening to chat messages in the channel listed in the settings.txt file. Any chat message not sent by a denied user will be learned from. Whenever someone then requests a message to be generated, a [Markov Chain](https://en.wikipedia.org/wiki/Markov_chain) will be used with the learned data to generate a sentence. <b> Note that the bot is unaware of the meaning of any of its inputs and outputs. This means it can use bad language if it was taught to use bad language by people in chat. Use at your own risk. </b>

---

# Usage
Command:
<pre><b>!generate</b></pre>
Result (for example):
<pre><b>that little thing is pinky</b></pre>
Everyone can use it. 

---

# Settings
This bot is controlled by a settings.txt file, which looks like:
```
{
    "Host": "irc.chat.twitch.tv",
    "Port": 6667,
    "Channel": "#<channel>",
    "Nickname": "<name>",
    "Authentication": "oauth:<auth>",
    "DeniedUsers": [
        "StreamElements",
        "Nightbot",
        "Moobot",
        "Marbiebot"
    ],
    "KeyLength": 2
}
```

| **Parameter**        | **Meaning** | **Example** |
| -------------------- | ----------- | ----------- |
| Host                 | The URL that will be used. Do not change.                         | "irc.chat.twitch.tv" |
| Port                 | The Port that will be used. Do not change.                        | 6667 |
| Channel              | The Channel that will be connected to.                            | "#CubieDev" |
| Nickname             | The Username of the bot account.                                  | "CubieB0T" |
| Authentication       | The OAuth token for the bot account.                              | "oauth:pivogip8ybletucqdz4pkhag6itbax" |
| DeniedUsers | The list of bot account who's messages should not be learned from | ["StreamElements", "Nightbot", "Moobot", "Marbiebot"] |
| KeyLength | A technical parameter which, in my previous implementation, would affect how closely the output matches the learned inputs. In the current implementation the database structure does not allow this parameter to be changed. Do not change. | 2 | 

*Note that the example OAuth token is not an actual token, but merely a generated string to give an indication what it might look like.*

I got my real OAuth token from https://twitchapps.com/tmi/.

---
# Note

Note also that this bot creates a folder called "Logging" parallel to the folder this script exists in, where the logging information of this script is stored. This is perhaps not ideal for most users, but works well in my case, as it allows all of my bot's logs to be stored in one location, where I can easily access them.

---

# Other Twitch Bots

* [TwitchGoogleTranslate](https://github.com/CubieDev/TwitchGoogleTranslate)
* [TwitchCubieBot](https://github.com/CubieDev/TwitchCubieBot)
* [TwitchPickUser](https://github.com/CubieDev/TwitchPickUser)
* [TwitchPackCounter](https://github.com/CubieDev/TwitchPackCounter)
* [TwitchSaveMessages](https://github.com/CubieDev/TwitchSaveMessages)
* [TwitchDialCheck](https://github.com/CubieDev/TwitchDialCheck) (Streamer specific bot)
