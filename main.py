import os
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from discord.ext import commands
import discord

TOKEN = os.environ["DISCORD_TOKEN"]

conn = sqlite3.connect('users.db')

with open("continents.csv", "r") as f:
    relations = f.read().splitlines()
    relations = [rel.split(",") for rel in relations]
    continents = set([rel[0] for rel in relations])
    countries = [rel[1] for rel in relations]

c = conn.cursor()
# Create table
c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='users' ''')

# if the count is 1, then table exists
if c.fetchone()[0] == 1:
    print('Table exists. Skipping new table creation.')
else:
    print('Table does not exist. Creating new table.')
    c.execute('''CREATE TABLE users
                 (discord id, osu username, rank, bws_rank, country, last updated)''')
    print('Created users table.')

prefix = "?"

client = commands.Bot(command_prefix=prefix, case_insensitive=True)


def find_user_in_db(discord_id):
    discord_id = (discord_id,)
    c.execute('''SELECT * FROM users where 'discord id'=?''', discord_id)

    return c.fetchone()


def get_users_in_db():
    c.execute('''SELECT * FROM users''')

    return c.fetchall()


def add_user_to_db(discord_id, osu_details):
    osu_username = osu_details["username"]
    user_rank = osu_details["statistics"]["pp_rank"]
    user_badges = len(osu_details["badges"])
    # Standard bws rank = rank^(0.9937^(badges^2))
    bws_rank = max(1, int(pow(user_rank, (pow(0.9937, pow(user_badges, 2))))))
    user_country = osu_details["country"]["name"]
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
              (discord_id, osu_username, user_rank, bws_rank, user_country, updated))
    conn.commit()

    return


def delete_user_from_db(discord_id):
    discord_id = (discord_id,)
    c.execute('''DELETE FROM users WHERE 'discord id'=?''', discord_id)
    conn.commit()

    return


@client.event
async def on_command_error(self, *args, **kwargs):
    await self.send(args[0])
    return


@client.command(name='pingmenot')
async def tourney_ping_off(ctx):
    """
    Stops pinging you when a new tournament is announced...
    """

    user = find_user_in_db(ctx.author.id)
    if user[0] != 1:
        await ctx.send(
            f"{ctx.author.mention} you are not even being notified.\n If you want to be notified use `{prefix}pingme`.")

    delete_user_from_db(ctx.author.id)

    await ctx.send(f"{ctx.author.mention} you won't be notified ever again unless you type `{prefix}pingme` again.")
    return


@client.command(name='pingme')
async def tourney_ping_on(ctx, osu_username):
    """
    Pings you when a new tournament is announced! (If you are in the rank range)
    Usage: *pingme Cookiezi - (You will be notified when a tournament is announced that Cookiezi can join)
    osu_username: Your osu! nickname or id (If your name contains spaces, put it in quotation marks)
    """
    user_discord_id = ctx.author.id

    user_data, _ = get_osu_user_web_profile(osu_username)
    add_user_to_db(user_discord_id, user_data)

    await ctx.send(
        f"{ctx.author.mention} you will be notified when a new tournament is announced for `{osu_username}`!\n"
        f"Type `{prefix}pingmenot` to stop it.")
    return


@client.event
async def on_message(message):
    await client.process_commands(message)

    conyohs_guild = client.get_guild(429869970109759498)
    everyone_roles = [discord.utils.get(conyohs_guild.roles, id=429885559406592012),
                      discord.utils.get(conyohs_guild.roles, id=494159199576522752),
                      discord.utils.get(conyohs_guild.roles, id=494159310285307917)]
    channel_id = message.channel.id
    if not (channel_id == 519217032709931018 or channel_id == 676411865592758272 or channel_id == 587819824449585152):
        return

    lines = message.content.lower().splitlines()
    ping_list = []

    def populate_ping_list(ping_list, rank_text, regions):
        rank_text = rank_text.replace("*", "")
        bws = False

        if "(bws)" in rank_text:
            rank_text = rank_text.replace("(bws)", "")
            bws = True

        if "(" in rank_text:
            open_parentheses = rank_text.find("(")
            rank_text = rank_text[:open_parentheses]

        rank_text = rank_text.rstrip()
        if rank_text.endswith("+"):
            max_rank = int(rank_text.replace("+", "").replace(",", ""))
            min_rank = 10000000
        else:
            max_rank = int(rank_text.split("-")[0].replace(",", ""))
            min_rank = int(rank_text.split("-")[1].replace(",", ""))

        if len(regions) == 0:
            if bws:
                c.execute("SELECT * FROM users WHERE bws_rank<? AND bws_rank>?", (min_rank, max_rank))
            else:
                c.execute("SELECT * FROM users WHERE rank<? AND rank>?", (min_rank, max_rank))
        else:
            arguments = [min_rank, max_rank]
            if bws:
                statement = "SELECT * FROM users WHERE bws_rank<? AND bws_rank>? "
            else:
                statement = "SELECT * FROM users WHERE bws_rank<? AND bws_rank>? "
            for country in regions:
                arguments.append(country)
                statement += "AND country=? "

            c.execute(statement, arguments)

        for p in c.fetchall():
            ping_list.append(p[0])

        return ping_list

    regions = []
    region = "international"
    for line in lines:
        if not line.find("region:") == -1:
            line = line.replace("*", "")
            region = line.split("region:")[1]
            region = region.strip()

    if region in continents:
        for rel in relations:
            if rel[0] == region:
                regions.append(rel[1])
    elif region in countries:
        regions.append(region)

    rank_range_found = False
    ping_everyone = False
    for line_no, line in enumerate(lines):
        idx = line.find("rank range:")
        if not idx == -1:
            rank_range = line[idx + 11:]

            if "no rank limit" in rank_range:
                ping_everyone = True
                break

            if len(rank_range) < 3:
                for multiline in lines[line_no + 1:]:
                    try:
                        rank_text = multiline.split("|")[1]
                        ping_list = populate_ping_list(ping_list, rank_text, regions)
                    except:
                        break
                    rank_range_found = True
                break
            else:
                ping_list = populate_ping_list(ping_list, rank_range, regions)
                rank_range_found = True
                break

    if not rank_range_found:
        return

    if len(ping_list) == 0:
        return

    ping_text = ""
    if not ping_everyone:
        for user in ping_list:
            ping_text += f" {client.get_user(user).mention}"
    else:
        for role in everyone_roles:
            ping_text += f"{role.mention}"

    ping_text += f"You can join this tournament!\n " \
                 f"If you want to be notified for tournaments, use `?pingme`" \
                 f" \nIf you don't want to be notified, you can turn me off by using `?pingmenot`"

    await message.channel.send(ping_text)

    return


def get_osu_user_web_profile(osu_username):
    osu_username = osu_username.replace("_", " ")
    r = requests.get(f"https://osu.ppy.sh/users/{osu_username}")

    soup = BeautifulSoup(r.text, 'html.parser')
    try:
        json_user = soup.find(id="json-user").string
        json_achievements = soup.find(id="json-achievements").string
    except AttributeError:
        raise Exception(f"Couldn't find `{osu_username}` on osu!")
    user_dict = json.loads(json_user)
    achievements_dict = json.loads(json_achievements)

    return user_dict, achievements_dict


client.run(TOKEN)
