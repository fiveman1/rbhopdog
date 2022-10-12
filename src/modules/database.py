import aiomysql
import asyncio
import json

# You must first create the database, run this query before creating the tables:
# create database discord_to_roblox;

async def create_database(loop, user, password):
    query = "create database discord_to_roblox;"
    
    conn : aiomysql.Connection = await aiomysql.connect(
        loop=loop, host="127.0.0.1", port=3306, user=user, 
        password=password, autocommit=True
    )

    cur : aiomysql.Cursor = await conn.cursor()
    await cur.execute(query)
    await cur.close()
    conn.close()

async def create_tables(loop, user, password):
    query = """
            create table discord_lookup (
                discord_id bigint unsigned not null,
                roblox_id int unsigned not null,
                primary key (discord_id)
            );
            """
    
    conn : aiomysql.Connection = await aiomysql.connect(
        loop=loop, host="127.0.0.1", port=3306, user=user, 
        password=password, db="discord_to_roblox", autocommit=True
    )

    cur : aiomysql.Cursor = await conn.cursor()
    await cur.execute(query)
    await cur.close()
    conn.close()

async def main(loop):

    with open("config.json") as file:
        config = json.load(file)
    SQL_USER = config["SQL_USER"]
    SQL_PASS = config["SQL_PASS"]

    await create_database(loop, SQL_USER, SQL_PASS)
    await create_tables(loop, SQL_USER, SQL_PASS)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))