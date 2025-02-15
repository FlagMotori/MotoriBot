from config_vars import *
import discord
from discord.ext import commands
from prettytable import PrettyTable
import string
import requests
import sys
import traceback
import json
sys.path.append("..")

# All commands relating to server specific CTF data
# Credentials provided for pulling challenges from the CTFd platform are NOT stored in the database.
# they are stored in a pinned message in the discord channel.


def in_ctf_category():
    async def tocheck(ctx):
        # A check for ctf context specific commands
        if teamdb[str(ctx.guild.id)].find_one({'name': str(ctx.message.channel.category)}):
            return True
        else:
            await ctx.send("You must be in a created ctf channel to use ctf commands!")
            return False
    return commands.check(tocheck)


def strip_string(tostrip, whitelist):
    # A string validator to correspond with a provided whitelist.
    stripped = ''.join([ch for ch in tostrip if ch in whitelist])
    return stripped.strip()


class InvalidProvider(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class CredentialsNotFound(Exception):
    pass


class NonceNotFound(Exception):
    pass


def getChallenges(url, username, password):
    # Pull challenges from a ctf hosted with the commonly used CTFd platform using provided credentials
    fingerprint = "Powered by CTFd"
    s = requests.session()
    if url[-1] == "/":
        url = url[:-1]
    r = s.get(f"{url}/login")
    if fingerprint not in r.text:
        raise InvalidProvider(
            "CTF is not based on CTFd, cannot pull challenges.")
    else:
        # Get the nonce from the login page.
        try:
            nonce = r.text.split("csrfNonce': \"")[1].split('"')[0]
        except:  # sometimes errors happen here, my theory is that it is different versions of CTFd
            try:
                nonce = r.text.split("name=\"nonce\" value=\"")[
                    1].split('">')[0]
            except:
                raise NonceNotFound(
                    "Was not able to find the nonce token from login, please >report this along with the ctf url.")
        # Login with the username, password, and nonce
        r = s.post(f"{url}/login", data={"name": username,
                   "password": password, "nonce": nonce})
        if "Your username or password is incorrect" in r.text:
            raise InvalidCredentials("Invalid login credentials")
        r_chals = s.get(f"{url}/api/v1/challenges")
        all_challenges = r_chals.json()
        r_solves = s.get(f"{url}/api/v1/teams/me/solves")
        team_solves = r_solves.json()
        if 'success' not in team_solves:
            # ctf is user based.  There is a flag on CTFd for this (userMode), but it is not present in all versions, this way seems to be.
            r_solves = s.get(f"{url}/api/v1/users/me/solves")
            team_solves = r_solves.json()

        solves = []
        if team_solves['success'] is True:
            for solve in team_solves['data']:
                cat = solve['challenge']['category']
                name = solve['challenge']['name']
                solves.append(name)
        if all_challenges['success'] is True:
            # Create a dictionary to store challenges by category
            challenges_by_category = {}
            for chal in all_challenges['data']:
                cat = chal['category']
                name = chal['name']
                # print(name)
                # print(strip_string(name, whitelist))
                # Create a list for the category if it doesn't exist in the dictionary
                if cat not in challenges_by_category:
                    challenges_by_category[cat] = []
                if name not in solves:
                    challenges_by_category[cat].append((name, 'Unsolved'))
                else:
                    challenges_by_category[cat].append((name, 'Solved'))
        else:
            raise Exception("Error making request")
        # Returns all the new challenges and their corresponding statuses in a dictionary compatible with the structure that would happen with 'normal' useage.
        return challenges_by_category


class CTF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def ctf(self, ctx):
        if ctx.invoked_subcommand is None:
            # If the subcommand passed does not exist, its type is None
            ctf_commands = list(
                set([c.qualified_name for c in CTF.walk_commands(self)][1:]))
            # update this to include params
            await ctx.send(f"Current ctf commands are: {', '.join(ctf_commands)}")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_role('Organizer')
    @ctf.command(aliases=["new"])
    async def create(self, ctx, ctf_name):
        category = discord.utils.get(ctx.guild.categories, name=ctf_name)
        if category is None:  # Checks if category exists, if it doesn't it will create it.
            await ctx.guild.create_category(name=ctf_name)
            category = discord.utils.get(ctx.guild.categories, name=ctf_name)
            await category.set_permissions(ctx.guild.me, read_messages=True, send_messages=True, speak=True)

        if ctf_name[0] == '-':
            # edge case where channel names can't start with a space (but can end in one)
            ctf_name = ctf_name[1:]

        # There cannot be 2 spaces (which are converted to '-') in a row when creating a channel.  This makes sure these are taken out.
        while '--' in ctf_name:
            ctf_name = ctf_name.replace('--', '-')

        role = await ctx.guild.create_role(name=ctf_name, mentionable=True)
        channel = await ctx.guild.create_text_channel(name="Main", category=category)
        # Override default permissions
        await channel.set_permissions(ctx.guild.default_role, read_messages=False)
        # Allow access for specified role
        await channel.set_permissions(role, read_messages=True)
        server = teamdb[str(ctx.guild.id)]
        ctf_info = {'name': ctf_name, 'challenges': {}}
        server.update_one({'name': ctf_name}, {"$set": ctf_info}, upsert=True)
        # Give a visual confirmation of completion.
        await ctx.message.add_reaction("✅")

    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @commands.has_role('Organizer')
    @ctf.command()
    @in_ctf_category()
    async def delete(self, ctx):
        # Delete role from server, delete entry from db
        cat_name = str(ctx.message.channel.category)
        try:
            role = discord.utils.get(
                ctx.guild.roles, name=str(ctx.message.channel.category))
            await role.delete()
            await ctx.send(f"`{role.name}` role deleted")
        except:  # role most likely already deleted with archive
            await ctx.send(f"The deletion of the Discord role failed.")
        try:
            # Check if the category exists in the database
            category_data = teamdb[str(ctx.guild.id)].find_one(
                {'name': str(ctx.message.channel.category)})

            if category_data:
                # Delete the channels in the category
                category = discord.utils.get(
                    ctx.guild.categories, name=str(ctx.message.channel.category))
                for channel in category.channels:
                    await channel.delete()

                # Delete the category itself
                await category.delete()

                # Remove the category from the database
                teamdb[str(ctx.guild.id)].delete_one({'name': cat_name})

                await ctx.send(f"`{str(ctx.message.channel.category)}` and its channels deleted.")
            else:
                await ctx.send(f"`{str(ctx.message.channel.category)}` not found in the database.")
        except Exception as e:
            print(e)

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command()
    async def join(self, ctx, name):
        # Give the user the role of {name} ctf.
        role = discord.utils.get(
            ctx.guild.roles, name=name)
        user = ctx.message.author
        await user.add_roles(role)
        await ctx.send(f"{user} has joined the {str(ctx.message.channel)} team!")

    @commands.bot_has_permissions(manage_roles=True)
    @ctf.command()
    @in_ctf_category()
    async def leave(self, ctx):
        # Remove from the user the role of the ctf channel they're currently in.
        role = discord.utils.get(
            ctx.guild.roles, name=str(ctx.message.channel.category))
        user = ctx.message.author
        await user.remove_roles(role)
        await ctx.send(f"{user} has left the {str(ctx.message.channel.category)} ctf.")

    @ctf.group(aliases=["chal", "chall", "challenges"])
    @in_ctf_category()
    async def challenge(self, ctx):
        pass

    @challenge.command(aliases=["a"])
    @in_ctf_category()
    async def add(self, ctx, chall_name):
        server = teamdb[str(ctx.guild.id)]
        ctf = server.find_one({'name': str(ctx.message.channel.category)})
        challenges = ctf['challenges']
        channel = str(ctx.message.channel)
        if challenges.get(channel):
            challenges[channel].update(
                {chall_name: {'status': 'Unsolved', 'members': []}})
        else:
            challenges[channel] = {chall_name: {
                'status': 'Unsolved', 'members': []}}
        ctf_info = {'name': str(ctx.message.channel.category),
                    'challenges': challenges}
        server.update_one({'name': str(ctx.message.channel.category)},
                          {"$set": ctf_info}, upsert=True)
        msg = await ctx.send(f"`{chall_name}` has been added to the challenge list for `{channel}, adding thread...`")
        await msg.create_thread(name=chall_name)

    @staticmethod
    def updateChallenge(ctx, chall_name, status):
        # Update the db with a new challenge and its status
        server = teamdb[str(ctx.guild.id)]
        ctf = server.find_one({'name': str(ctx.message.channel.category)})
        challenges = ctf['challenges'][str(ctx.message.channel.parent)]
        # If challenge already exist...
        members = challenges[chall_name]['members']
        if ctx.message.author.name not in members:
            members.append(ctx.message.author.name)
        challenges[chall_name] = {
            'status': status, 'members': members}
        ctf_info = {'name': str(ctx.message.channel.category),
                    'challenges': ctf['challenges']
                    }
        server.update_one({'name': str(ctx.message.channel.category)},
                          {"$set": ctf_info}, upsert=True)
        return members

    @challenge.command(aliases=['s', 'solve'])
    @in_ctf_category()
    async def solved(self, ctx):
        if isinstance(ctx.message.channel, discord.Thread):
            name = str(ctx.message.channel.name).replace("Working-", "")
            name = name.replace("Solved-", "")
            working = CTF.updateChallenge(ctx, name, 'Solved')
            await ctx.send(f":triangular_flag_on_post: `{ctx.message.channel.name}` has been solved by `{', '.join(working)}`")
            await ctx.message.channel.edit(name="Solved-"+name)
        else:
            await ctx.send("send your request in thread.")

    @challenge.command(aliases=['w'])
    @in_ctf_category()
    async def working(self, ctx):
        if isinstance(ctx.message.channel, discord.Thread):
            name = str(ctx.message.channel.name).replace("Working-", "")
            name = name.replace("Solved-", "")
            working = CTF.updateChallenge(ctx, name, 'Working')
            await ctx.send(f"`{', '.join(working)}` {'is' if len(working) == 1 else 'are'} working on `{ctx.message.channel.name}`!")
            await ctx.message.channel.edit(name="Working-"+name)
        else:
            await ctx.send("send your request in thread.")

    @challenge.command(aliases=['r', 'delete', 'd'])
    @in_ctf_category()
    @commands.has_role('Organizer')
    async def remove(self, ctx, name):
        # Typos can happen (remove a ctf challenge from the list)
        ctf = teamdb[str(ctx.guild.id)].find_one(
            {'name': str(ctx.message.channel.category)})
        challenges = ctf['challenges']
        challenges[ctx.message.channel.name].pop(name, None)
        ctf_info = {'name': str(ctx.message.channel.category),
                    'challenges': challenges
                    }
        teamdb[str(ctx.guild.id)].update_one(
            {'name': str(ctx.message.channel.category)}, {"$set": ctf_info})
        await ctx.send(f"Removed `{name}`")

    @challenge.command(aliases=['stat'])
    @in_ctf_category()
    @commands.has_role('Organizer')
    async def stats(self, ctx):
        myTable = PrettyTable(['player', 'working', 'solved'])
        ctf = teamdb[str(ctx.guild.id)].find_one(
            {'name': str(ctx.message.channel.category)})
        challenges = ctf['challenges']
        player_stats = {}
        for _, category in challenges.items():
            for _, chal in category.items():
                for player in chal['members']:
                    if player not in player_stats:
                        player_stats[player] = [0, 0]
                    if chal['status'] == 'Working':
                        player_stats[player][0] += 1
                    elif chal['status'] == 'Solved':
                        player_stats[player][1] += 1
        sorted_player_stats = sorted(
            player_stats.items(), key=lambda x: x[1][1], reverse=True)
        for player, data in sorted_player_stats:
            myTable.add_row([player, data[0], data[1]])

        await ctx.send(f"```{myTable}```")

    @challenge.command(aliases=['get', 'ctfd'])
    @in_ctf_category()
    async def pull(self, ctx, url=None, user=None, passw=None):
        # Pull challenges from a ctf hosted on the CTFd platform
        if url and user and passw:
            try:
                ctfd_challs = getChallenges(url, user, passw)
                structured_data = {}
                for category, challenges in ctfd_challs.items():
                    category_dict = {}
                    for challenge_name, status in challenges:
                        category_dict[challenge_name] = {
                            "status": status,
                            "members": []
                        }
                    structured_data[category] = category_dict
                ctf = teamdb[str(ctx.guild.id)].find_one(
                    {'name': str(ctx.message.channel.category)})
                try:  # If there are existing challenges already...
                    challenges = ctf['challenges']
                    challenges.update_one(structured_data)
                except:
                    ctf_info = {'name': str(ctx.message.channel.category),
                                'challenges': structured_data
                                }
                    teamdb[str(ctx.guild.id)].update_one(
                        {'name': str(ctx.message.channel.category)}, {"$set": ctf_info}, upsert=True)
                role = discord.utils.get(
                    ctx.guild.roles, name=str(ctx.message.channel.category))
                channel_names = [
                    x.name for x in ctx.message.channel.category.channels]
                new_channels, new_challenges = 0, 0
                for channel_name, challenges in ctfd_challs.items():
                    # Create a category for each channel_name
                    if channel_name not in channel_names:
                        new_channels += 1
                        channel = await ctx.guild.create_text_channel(channel_name, category=ctx.message.channel.category)
                        await channel.set_permissions(ctx.guild.default_role, read_messages=False)
                        # Allow access for specified role
                        await channel.set_permissions(role, read_messages=True)
                    else:
                        channel = discord.utils.get(
                            ctx.guild.channels, name=channel_name)
                    threads = [x.name for x in channel.threads]
                    for challenge_name in challenges:
                        # Create a thread for the challenge
                        if challenge_name[0] not in threads:
                            new_challenges += 1
                            msg = await channel.send(f"`{challenge_name[0]}` Thread:")
                            await msg.create_thread(name=challenge_name[0])
                await ctx.send(f"Added {new_channels} {'Channels' if new_channels > 1 else 'Channel'} and {new_challenges} {'threads' if new_challenges > 1 else 'thread'}.")
                await ctx.message.add_reaction("✅")
            except InvalidProvider as ipm:
                await ctx.send(ipm)
            except InvalidCredentials as icm:
                await ctx.send(icm)
            except NonceNotFound as nnfm:
                await ctx.send(nnfm)
            except requests.exceptions.MissingSchema:
                await ctx.send("Supply a valid url in the form: `http(s)://ctfd.url`")
            except:
                traceback.print_exc()
        else:
            role = discord.utils.get(
                ctx.guild.roles, name=str(ctx.message.channel.category))
            with open("./constants.json", "r") as json_file:
                data = json.load(json_file)
                categories = data["categories"]
            for c in categories:
                channel = await ctx.guild.create_text_channel(name=c, category=ctx.message.channel.category)
                # Override default permissions
                await channel.set_permissions(ctx.guild.default_role, read_messages=False)
                # Allow access for specified role
                await channel.set_permissions(role, read_messages=True)

    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @ctf.command(aliases=['login'])
    @in_ctf_category()
    async def setcreds(self, ctx, username, password):
        # Creates a pinned message with the credntials supplied by the user
        pinned = await ctx.message.channel.pins()
        for pin in pinned:
            if "CTF credentials set." in pin.content:
                # Look for previously pinned credntials, and remove them if they exist.
                await pin.unpin()
        msg = await ctx.send(f"CTF credentials set. name:{username} password:{password}")
        await msg.pin()

    @commands.bot_has_permissions(manage_messages=True)
    @ctf.command(aliases=['getcreds'])
    @in_ctf_category()
    async def creds(self, ctx):
        # Send a message with the credntials
        pinned = await ctx.message.channel.pins()
        try:
            user_pass = CTF.get_creds(pinned)
            await ctx.send(f"name:`{user_pass[0]}` password:`{user_pass[1]}`")
        except CredentialsNotFound as cnfm:
            await ctx.send(cnfm)

    @staticmethod
    def get_creds(pinned):
        for pin in pinned:
            if "CTF credentials set." in pin.content:
                user_pass = pin.content.split("name:")[1].split(" password:")
                return user_pass
        raise CredentialsNotFound(
            "Set credentials with `>ctf setcreds \"username\" \"password\"`")

    @staticmethod
    def gen_page(challengelist):
        # Function for generating each page (message) for the list of challenges in a ctf.
        challenge_page = ""
        challenge_pages = []
        for c in challengelist:
            # Discord message sizes cannot exceed 2000 characters.
            # This will create a new message every 2k characters.
            if not len(challenge_page + c) >= 1989:
                challenge_page += c
                if c == challengelist[-1]:  # if it is the last item
                    challenge_pages.append(challenge_page)

            elif len(challenge_page + c) >= 1989:
                challenge_pages.append(challenge_page)
                challenge_page = ""
                challenge_page += c

        # print(challenge_pages)
        return challenge_pages

    @challenge.command(aliases=['ls', 'l'])
    @in_ctf_category()
    async def list(self, ctx):
        # list the challenges in the current ctf.
        try:
            ctf_challenge_list = []
            server = teamdb[str(ctx.guild.id)]
            ctf = server.find_one({'name': str(ctx.message.channel.category)})
            output = {}
            for cat, d in ctf['challenges'].items():
                output[cat] = []
                for chall, _ in d.items():
                    output[cat].append((chall+":"+_['status']))

            # Convert the data to a formatted JSON string
            json_str = json.dumps(output, indent=2, ensure_ascii=False)

            # Define a maximum character limit for each chunk
            max_chunk_chars = 1950

            # Split the JSON string into chunks without splitting words
            chunks = []
            current_chunk = "```json\n"
            for line in json_str.splitlines():
                if len(current_chunk) + len(line) <= max_chunk_chars:
                    current_chunk += line + "\n"  # Add 6 extra characters for "```json```"
                else:
                    chunks.append(current_chunk)
                    current_chunk = "```json\n" + line + "\n"

            # Add the last chunk if it's not empty
            if current_chunk:
                chunks.append(current_chunk)

            # Send each chunk as a separate message
            for chunk in chunks:
                await ctx.send(chunk + "```")
        except KeyError:  # If nothing has been added to the challenges list
            await ctx.send("Add some challenges with `>ctf challenge add \"challenge name\"`")
        except:
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(CTF(bot))
