# TwitchMarkovChain
Twitch Bot for generating messages based on what it learned from chat 

---
# Explanation
When the bot has started, it will start listening to chat messages in the channel listed in the settings.txt file. Any chat message not sent by a denied user will be learned from. Whenever someone then requests a message to be generated, a [Markov Chain](https://en.wikipedia.org/wiki/Markov_chain) will be used with the learned data to generate a sentence. <b> Note that the bot is unaware of the meaning of any of its inputs and outputs. This means it can use bad language if it was taught to use bad language by people in chat. Use at your own risk. </b>

---

# Usage
<b>Run the MarkovChainBot.py file</b>

Command:
<pre><b>!generate</b></pre>
Result (for example):
<pre><b>that little thing is pinky</b></pre>
Everyone can use it.<br>

Command:
<pre><b>!generate [words]</b></pre>
Example:
<pre><b>!generate That is the</b></pre>
Result (for example):
<pre><b>That is the mouth there?</b></pre>
The bot will, when given this command, try to complete the start of the sentence which was given.<br> 
If it cannot, an appropriate error message will be sent to chat.<br>
Any number of words may be given.<br>
Everyone can use it.<br>

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
    "BannedWords": [
        "<START>",
        "<END>"
    ],
    "Cooldown": 20,
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
| DeniedUsers | The list of bot account who's messages should not be learned from. The bot itself it automatically added to this. | ["StreamElements", "Nightbot", "Moobot", "Marbiebot"] |
| BannedWords | A list of words which should not be added into the Database. The default data is there due to the current implementation. You can add any words you never want the bot to learn. Case insensitive. | [`"<START>", "<END>"`] |
| Cooldown | A cooldown in seconds between successful generations. If a generation fails (eg inputs it can't work with), then the cooldown is not reset and another generation can be done immediately. | 20 |
| KeyLength | A technical parameter which, in my previous implementation, would affect how closely the output matches the learned inputs. In the current implementation the database structure does not allow this parameter to be changed. Do not change. | 2 | 

*Note that the example OAuth token is not an actual token, but merely a generated string to give an indication what it might look like.*

I got my real OAuth token from https://twitchapps.com/tmi/.

---

# Other Twitch Bots

* [TwitchGoogleTranslate](https://github.com/CubieDev/TwitchGoogleTranslate)
* [TwitchCubieBot](https://github.com/CubieDev/TwitchCubieBot)
* [TwitchDeathCounter](https://github.com/CubieDev/TwitchDeathCounter)
* [TwitchSuggestDinner](https://github.com/CubieDev/TwitchSuggestDinner)
* [TwitchPickUser](https://github.com/CubieDev/TwitchPickUser)
* [TwitchSaveMessages](https://github.com/CubieDev/TwitchSaveMessages)
* [TwitchPackCounter](https://github.com/CubieDev/TwitchPackCounter) (Streamer specific bot)
* [TwitchDialCheck](https://github.com/CubieDev/TwitchDialCheck) (Streamer specific bot)
