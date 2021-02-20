# rbhopdog

discord.py bot that uses primarily the strafes.net api to access data from rbhop/rsurf among other things

Commands:

**!fastecheck username game style**

    Determines if a player is eligible for faste in a given game and style.

**!map game {map_name}**

    Gives info about the given map such as the creator, total play count, and the map's asset ID.

**!mapcount**

    Gives the total map count for bhop and surf.

**!profile username game style**

    Gives a player's rank and skill% in the given game and style.

**!ranks game style page:1**

    Gives 25 ranks in the given game and style at the specified page number (25 ranks per page).

**!recentwrs game style**

    Get a list of the 10 most recent WRs in a given game and style.

**!record user game style {map_name}**

    Get a user's time on a given map and their placement (ex. 31st / 5690).

**!times user game:both style:all page:1**

    Get a list of a user's 25 most recent times. It will try to be smart with the arguments: '!times fiveman1 bhop 2', '!times fiveman1 4', '!times fiveman1', '!times fiveman1 both hsw 7' are all valid. Numbers will be treated as the page number, but they must come after game/style. If the page is set to 'txt', you will get a .txt with every time.

**!user user**

    Gets the username, user ID, and profile picture of a given user. Can be used with discord accounts that have been verified via the RoVer API.

**!wrcount username**

    Gives a count of a user's WRs in every game and style.

**!wrlist username game:both style:all sort:default**

    Lists all of a player's world records. Valid sorts: 'date', 'name', and 'time'. Use 'txt' as an argument to get a .txt file with all WRs ex. !wrlist bhop auto M1nerss txt

**!wrmap game style {map_name} page:1**

    Gives the 25 best times on a given map and style. The page number defaults to 1 (25 records per page). If the map ends in a number you can enclose it in quotes ex. !wrmap bhop auto "Emblem 2"