# rbhopdog

discord.py bot that uses primarly strafes.net api among other things

Commands:

**!fastecheck username game style**

    Determines if a player is eligible for faste in a given game and style.

**!mapcount**

    Gives the total map count for bhop and surf.

**!profile username game style**

    Gives a player's rank and skill% in the given game and style.

**!ranks game style page:1**

    Gives 25 ranks in the given game and style at the specified page number (25 ranks per page).

**!recentwrs game style**

    Get a list of the 10 most recent WRs in a given game and style.

**!record user game style {map_name}**

    Get a user's time on a given map.

**!times user game:both style:all page:1**

    Get a list of a user's 25 most recent times. It will try to be smart with the arguments: '!times fiveman1 bhop 2', '!times fiveman1 4', '!times fiveman1', '!times fiveman1 both hsw 7' are all valid. Numbers will be treated as the page number, but they must come after game/style. If the page is set to 'all', you will get a .txt with every time.

**!wrcount username**

    Gives a count of a user's WRs in every game and style.

**!wrlist username game:both style:all sort:default**

    Lists all of a player's world records. Valid sorts: 'date', 'name', and 'time'.

**!wrmap game style {map_name} page:1**

    Gives the 25 best times on a given map and style. The page number defaults to 1 (25 records per page). If the map ends in a number you can enclose it in quotes ex. !wrmap bhop auto "Emblem 2"