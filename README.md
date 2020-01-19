# TwitchMarkovChain
Twitch Bot for generating messages based on what it learned from chat 

---
## Branch Reasoning

This branch exists solely for storing converters which transform Databases from older versions to the newest version.
For new users, these will not be needed. 

---
## Versions
There have been three versions of the database.

### Version 1
Two tables, one for the starts of sentences, and one for the rest of the sentences. Both of these tables were case sensitive. 

### Version 2
Two tables, one for the starts of sentences, and one for the rest of the sentences. 
These tables are not case sensitive. This allows the bot to expand "I know" if it has already learned how to respond to "i Know", without having to first apply expensive normalisation.

### Version 3
72 tables, 37 for the starts of sentences, and 37 for the rest of the sentences.<br>
For each of the two types of tables, the following distribution exists:<br>
* 26 tables identified by a letter from the alphabet. 
* 10 tables identified by a number.
* 1 table identified by something else.

The first character of the first word is tested against the identifier.<br>
Splitting up the tables has increased the performance of this bot on my Raspberry Pi, as it only has 1GB of ram. Querying massive tables proved too intensive for it.

---

## Converters

`ModifyDatabase.py` transforms a database from Version 1 to Version 2.<br>
`ModifyDatabase2.py` transforms a database from Version 2 to Version 3, the current version.<br>

Use these scripts only when converting between these databases. Using them recklessly may permanently delete the database's contents.