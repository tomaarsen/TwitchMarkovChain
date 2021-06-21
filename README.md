# TwitchMarkovChain

Twitch Bot for generating messages based on what it learned from chat

---

## Explanation

When the bot has started, it will start listening to chat messages in the channel listed in the `settings.txt` file. Any chat message not sent by a denied user will be learned from. Whenever someone then requests a message to be generated, a [Markov Chain](https://en.wikipedia.org/wiki/Markov_chain) will be used with the learned data to generate a sentence. **Note that the bot is unaware of the meaning of any of its inputs and outputs. This means it can use bad language if it was taught to use bad language by people in chat. You can add a list of banned words it should never learn or say. Use at your own risk.**

Whenever a message is deleted from chat, it's contents will be unlearned at 5 times the rate a normal message is learned from.
The bot will avoid learning from commands, or from messages containing links.

---

## How it works

### Sentence Parsing

To explain how the bot works, I will provide an example situation with two messages that are posted in Twitch chat. The messages are:

> Curly fries are the worst kind of fries
> Loud people are the reason I don't go to the movies anymore

Let's start with the first sentence and parse it like the bot will. To do so, we will split up the sentence in sections of `keyLength + 1` words. As `keyLength` has been set to `2` in the [Settings](#settings) section, each section has `3` words.

```txt
Curly fries are the worst kind of fries
[Curly fries:are]
      [fries are:the]
            [are the:worst]
                [the worst:kind]
                    [worst kind:of]
                          [kind of:fries]
```

For each of these sections of three words, the last word is considered the output, while all other words it are considered inputs.
These words are then turned into a variation of a [Grammar](https://en.wikipedia.org/wiki/Formal_grammar):

```txt
"Curly fries" -> "are"
"fries are"   -> "the"
"are the"     -> "worst"
"the worst"   -> "kind"
"worst kind"  -> "of"
"kind of"     -> "fries"
```

This can be considered a mathematical function that, when given input "the worst", will output "kind".
In order for the program to know where sentences begin, we also add the first `keyLength` words to a seperate Database table, where a list of possible starts of sentences reside.

This exact same process is applied to the second sentence as well. After doing so, the resulting grammar (and our corresponding database table) looks like:

```txt
"Curly fries" -> "are"
"fries are"   -> "the"
"are the"     -> "worst" | "reason"
"the worst"   -> "kind"
"worst kind"  -> "of"
"kind of"     -> "fries"
"Loud people" -> "are"
"people are"  -> "the"
"the reason"  -> "I"
"reason I"    -> "don't"
"I don't"     -> "go"
"don't go"    -> "to"
"go to"       -> "the"
"to the"      -> "movies"
"the movies"  -> "anymore"
```

and in the database table for starts of sentences:

```txt
"Curly fries"
"Loud people"
```

Note that the | is considered to be _"or"_. In the case of the bold text above, it could be read as: if the given input is "are the", then the output is either _"worst"_ **or** _"reason"_.

In practice, more frequent phrases will have higher precedence. The more often a phrase is said, the more likely it is to be generated.

---

### Generation

When a message is generated with `!generate`, a random start of a sentence is picked from the database table of starts of sentences. In our example the randomly picked start is _"Curly fries"_.

Now, in a loop:

- The output for the input is generated via the grammar.
- And the input for the next iteration in the loop is shifted:
  - Remove the first word from the input.
  - Add the new output word to the end of the input.

So, the input starts as _"Curly Fries"_. The output for this input is generated via the grammar, which gives us _"are"_. Then, the input is updated. _"Curly"_ is removed, and _"are"_ is added to the input. The new input for the next iteration will be _"Fries are"_ as a result. This process repeats until no more words can be generated, or if a word limit is reached.

A more programmatic example of this would be this:

```python
# This initial sentence is either from the database for starts of sentences,
# or from words passed in Twitch chat
sentence = ["Curly", "fries"]
for i in range(sentence_length):
    # Generate a word using last 2 words in the partial sentence,
    # and append it to the partial sentence
    sentence.append(generate(sentence[-2:]))
```

It's common for an input sequence to have multiple possible outputs, as we can see in the bold part of the previous grammar. This allows learned information from multiple messages to be merged into one message. For instance, some potential outputs from the given example are

> Curly fries are the reason I don't go to the movies anymore

or

> Loud people are the worst kind of fries

---

## Commands

Chat members can generate chat-like messages using the following commands (Note that they are aliases):

```txt
!generate [words]
!g [words]
```

Example:

```txt
!g Curly
```

Result (for example):

```txt
Curly fries are the reason I don't go to the movies anymore
```

- The bot will, when given this command, try to complete the start of the sentence which was given.
  - If it cannot, an appropriate error message will be sent to chat.
- Any number of words may be given, including none at all.
- Everyone can use it.

Furthermore, chat members can find a link to [How it works](#how-it-works) by using one of the following commands:

```txt
!ghelp
!genhelp
!generatehelp
```

The use of this command makes the bot post this message in chat:

> Learn how this bot generates sentences here: <https://github.com/CubieDev/TwitchMarkovChain#how-it-works>

---

### Streamer commands

All of these commands can be whispered to the bot account, or typed in chat.
To disable the bot from generating messages, while still learning from regular chat messages:

```txt
!disable
```

After disabling the bot, it can be re-enabled using:

```txt
!enable
```

Changing the cooldown between generations is possible with one of the following two commands:

```txt
!setcooldown <seconds>
!setcd <seconds>
```

Example:

```txt
!setcd 30
```

Which sets the cooldown between generations to 30 seconds.

---

### Moderator commands

All of these commands must be whispered to the bot account.
Moderators (and the broadcaster) can modify the blacklist to prevent the bot learning words it shouldn't.
To add `word` to the blacklist, a moderator can whisper the bot:

```txt
!blacklist <word>
```

Similarly, to remove `word` from the blacklist, a moderator can whisper the bot:

```txt
!whitelist <word>
```

And to check whether `word` is already on the blacklist or not, a moderator can whisper the bot:

```txt
!check <word>
```

---

## Settings

This bot is controlled by a `settings.txt` file, which has the following structure:

```json
{
  "Host": "irc.chat.twitch.tv",
  "Port": 6667,
  "Channel": "#<channel>",
  "Nickname": "<name>",
  "Authentication": "oauth:<auth>",
  "DeniedUsers": ["StreamElements", "Nightbot", "Moobot", "Marbiebot"],
  "Cooldown": 20,
  "KeyLength": 2,
  "MaxSentenceWordAmount": 25,
  "HelpMessageTimer": 7200,
  "AutomaticGenerationTimer": -1
}
```

| **Parameter**            | **Meaning**                                                                                                                                                                                                                                  | **Example**                                           |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Host                     | The URL that will be used. Do not change.                                                                                                                                                                                                    | "irc.chat.twitch.tv"                                  |
| Port                     | The Port that will be used. Do not change.                                                                                                                                                                                                   | 6667                                                  |
| Channel                  | The Channel that will be connected to.                                                                                                                                                                                                       | "#CubieDev"                                           |
| Nickname                 | The Username of the bot account.                                                                                                                                                                                                             | "CubieB0T"                                            |
| Authentication           | The OAuth token for the bot account.                                                                                                                                                                                                         | "oauth:pivogip8ybletucqdz4pkhag6itbax"                |
| DeniedUsers              | The list of bot account who's messages should not be learned from. The bot itself it automatically added to this.                                                                                                                            | ["StreamElements", "Nightbot", "Moobot", "Marbiebot"] |
| Cooldown                 | A cooldown in seconds between successful generations. If a generation fails (eg inputs it can't work with), then the cooldown is not reset and another generation can be done immediately.                                                   | 20                                                    |
| KeyLength                | A technical parameter which, in my previous implementation, would affect how closely the output matches the learned inputs. In the current implementation the database structure does not allow this parameter to be changed. Do not change. | 2                                                     |
| MaxSentenceWordAmount    | The maximum number of words that can be generated. Prevents absurdly long and spammy generations.                                                                                                                                            | 25                                                    |
| MinSentenceWordAmount    | The minimum number of words that can be generated. Additional sentences will begin a message is lower than this number. Prevents very small messages. -1 to disable                                                                          | -1                                                    |
| HelpMessageTimer         | The amount of seconds between sending help messages that links to [How it works](#how-it-works). -1 for no help messages.                                                                                                                    | 7200                                                  |
| AutomaticGenerationTimer | The amount of seconds between sending a generation, as if someone wrote `!g`. -1 for no automatic generations.                                                                                                                               | -1                                                    |
| AllowedUsers             | A list of users with heightened permissions. Gives these users the same power as the channel owner, allowing them to bypass cooldowns, set cooldowns, disable or enable the bot, etc.                                                        | ["CubieDev", "Limmy"]                                 |
| WhisperCooldown          | Prevents the bot from attempting to whisper users the remaining cooldown.                                                                                                                                                                    | true                                                  |
| EnableGenerateCommand    | Globally enables/disables the generate command                                                                                                                                                                                               | true                                                  |

_Note that the example OAuth token is not an actual token, but merely a generated string to give an indication what it might look like._

I got my real OAuth token from <https://twitchapps.com/tmi/>.

---

### Blacklist

You may add words to a blacklist by adding them on a separate line in `blacklist.txt`. Each word is case insensitive. By default, this file only contains `<start>` and `<end>`, which are required for the current implementation.

Words can also be added or removed from the blacklist via whispers, as is described in the [Moderator Command](#moderator-commands) section.

---

## Requirements

- [Python 3.6+](https://www.python.org/downloads/)
- [Module requirements](requirements.txt)
  - Install these modules using `pip install -r requirements.txt` in the commandline.

Among these modules is my own [TwitchWebsocket](https://github.com/tomaarsen/TwitchWebsocket) wrapper, which makes making a Twitch chat bot a lot easier.
This repository can be seen as an implementation using this wrapper.

---

## Other Twitch Bots

- [TwitchAIDungeon](https://github.com/CubieDev/TwitchAIDungeon)
- [TwitchGoogleTranslate](https://github.com/CubieDev/TwitchGoogleTranslate)
- [TwitchCubieBotGUI](https://github.com/CubieDev/TwitchCubieBotGUI)
- [TwitchCubieBot](https://github.com/CubieDev/TwitchCubieBot)
- [TwitchRandomRecipe](https://github.com/CubieDev/TwitchRandomRecipe)
- [TwitchUrbanDictionary](https://github.com/CubieDev/TwitchUrbanDictionary)
- [TwitchRhymeBot](https://github.com/CubieDev/TwitchRhymeBot)
- [TwitchWeather](https://github.com/CubieDev/TwitchWeather)
- [TwitchDeathCounter](https://github.com/CubieDev/TwitchDeathCounter)
- [TwitchSuggestDinner](https://github.com/CubieDev/TwitchSuggestDinner)
- [TwitchPickUser](https://github.com/CubieDev/TwitchPickUser)
- [TwitchSaveMessages](https://github.com/CubieDev/TwitchSaveMessages)
- [TwitchMMLevelPickerGUI](https://github.com/CubieDev/TwitchMMLevelPickerGUI) (Mario Maker 2 specific bot)
- [TwitchMMLevelQueueGUI](https://github.com/CubieDev/TwitchMMLevelQueueGUI) (Mario Maker 2 specific bot)
- [TwitchPackCounter](https://github.com/CubieDev/TwitchPackCounter) (Streamer specific bot)
- [TwitchDialCheck](https://github.com/CubieDev/TwitchDialCheck) (Streamer specific bot)
- [TwitchSendMessage](https://github.com/CubieDev/TwitchSendMessage) (Meant for debugging purposes)
