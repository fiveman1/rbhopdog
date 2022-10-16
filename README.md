# rbhopdog

discord.py bot that uses primarily the strafes.net api to access data from rbhop/rsurf among other things

Commands:

**!aliases**

    Get a list of all game and style aliases.

**!compare {users} {game} {styles} OPTIONAL[txt]**

    Compares users times across a game and styles. ex. !compare fiveman1 auto theinos sw bhop txt; !compare mionrs st0tty cowole surf auto

**!link OPTIONAL[username]**

    Link your Roblox account to your Discord account. Include username to link a new account. Then, omit username to verify the account after linking it. Ex: !link fiveman1, !link. Use !unlink to remove a linked account.

**!map {map_name} OPTIONAL[game]**

    Gives info about the given map such as the creator, total play count, and the map's asset ID.

**!mapcount**

    Gives the total map count for bhop and surf.

**!maps {creator} {page}**

    Gives a list of maps containing {creator} in the creator name. Use 'txt' for the page to get a .txt file with every map.

**!mapstatus {user} {game} {style}**

    Shows what maps a user hasn't completed in a given game and style.

**!pb {user} OPTIONAL[game] {style} {map_name}**

    Get a user's time on a given map and their placement (ex. 31st / 5690).

**!profile {user} {game} {style}**

    Gives a player's rank and skill% in the given game and style.

**!ranks {game} {style} {page=1}**

    Gives 25 ranks in the given game and style at the specified page number (25 ranks per page).

**!recentwrs {game} {style}**

    Get a list of the 10 most recent WRs in a given game and style.

**!times {user} {game=both} {style=all} {sort=date} {page=1}**

    Get a list of a user's 25 most recent times. Valid sorts: 'date', 'name', and 'time'. It will try to be smart with the arguments: '!times fiveman1 bhop 2', '!times fiveman1 4', '!times fiveman1', '!times fiveman1 both hsw 7' are all valid. Numbers will be treated as the page number, but they must come after game/style. If the page is set to 'txt', you will get a .txt with every time.

**!unlink**

    Unlink your Roblox account from your Discord account.

**!user {user}**

    Gets the username, user ID, and profile picture of a given user. Works with IDs.

**!wrcount {user}**

    Gives a count of a user's WRs in every game and style.

**!wrlist {user} {game=both} {style=all} {sort=default} {page=1} OPTIONAL[txt]**

    Lists all of a player's world records. Valid sorts: 'date', 'name', and 'time'. Use 'txt' as an argument to get a .txt file with all WRs ex. !wrlist bhop auto M1nerss txt

**!wrmap OPTIONAL[game] {style} {map_name} {page=1}**

    Gives the 25 best times on a given map and style. The page number defaults to 1 (25 records per page). If the map ends in a number you can enclose it in quotes ex. !wrmap bhop auto "Emblem 2"
