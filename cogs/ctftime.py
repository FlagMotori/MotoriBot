import re
import sys
from datetime import *
import discord
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style
from dateutil.parser import parse  # pip install python-dateutil
from discord.ext import commands, tasks
from config_vars import *

sys.path.append("..")

# All commands for getting data from ctftime.org (a popular platform for finding CTF events)


class CtfTime(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.upcoming_l = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"
        }
        self.updateDB.start()  # pylint: disable=no-member


    async def cog_command_error(self, ctx, error):
        print(error)


    def cog_unload(self):
        self.updateDB.cancel()  # pylint: disable=no-member


    @tasks.loop(minutes=30.0, reconnect=True)
    async def updateDB(self):
        # Every 30 minutes, this will grab the 5 closest upcoming CTFs from ctftime.org and update my db with it.
        # I do this because there is no way to get current ctfs from the api, but by logging all upcoming ctfs [cont.]
        # I can tell by looking at the start and end date if it's currently running or not using unix timestamps.
        now = datetime.utcnow()
        unix_now = int(now.replace(tzinfo=timezone.utc).timestamp())
        upcoming = 'https://ctftime.org/api/v1/events/'
        limit = '5'  # Max amount I can grab the json data for
        response = requests.get(upcoming, headers=self.headers, params=limit)
        jdata = response.json()

        info = []
        for num, i in enumerate(jdata):  # Generate list of dicts of upcoming ctfs
            ctf_title = jdata[num]['title']
            (ctf_start, ctf_end) = (parse(jdata[num]['start'].replace('T', ' ').split(
                '+', 1)[0]), parse(jdata[num]['finish'].replace('T', ' ').split('+', 1)[0]))
            (unix_start, unix_end) = (int(ctf_start.replace(tzinfo=timezone.utc).timestamp(
            )), int(ctf_end.replace(tzinfo=timezone.utc).timestamp()))
            dur_dict = jdata[num]['duration']
            (ctf_hours, ctf_days) = (
                str(dur_dict['hours']), str(dur_dict['days']))
            ctf_link = jdata[num]['url']
            ctf_image = jdata[num]['logo']
            ctf_format = jdata[num]['format']
            ctf_place = jdata[num]['onsite']
            if not ctf_place:
                ctf_place = 'Online'
            else:
                ctf_place = 'Onsite'

            ctf = {
                'name': ctf_title,
                'start': unix_start,
                'end': unix_end,
                'dur': ctf_days+' days, '+ctf_hours+' hours',
                'url': ctf_link,
                'img': ctf_image,
                'format': ctf_place+' '+ctf_format
            }
            info.append(ctf)

        got_ctfs = []
        for ctf in info:  # If the document doesn't exist: add it, if it does: update it.
            query = ctf['name']
            ctfs.update_one({'name': query}, {"$set": ctf}, upsert=True)
            got_ctfs.append(ctf['name'])
        print(Fore.WHITE + f"{datetime.now()}: " +
              Fore.GREEN + f"Got and updated {got_ctfs}")
        print(Style.RESET_ALL)

        for ctf in ctfs.find():  # Delete ctfs that are over from the db
            if ctf['end'] < unix_now:
                ctfs.remove({'name': ctf['name']})


    @updateDB.before_loop
    async def before_updateDB(self):
        await self.bot.wait_until_ready()


    @commands.group()
    async def ctftime(self, ctx):

        if ctx.invoked_subcommand is None:
            # If the subcommand passed does not exist, its type is None
            ctftime_commands = list(
                set([c.qualified_name for c in CtfTime.walk_commands(self)][1:]))
            await ctx.reply(f"Current ctftime commands are: {', '.join(ctftime_commands)}")


    @ctftime.command(aliases=['now', 'running'])
    async def current(self, ctx):
        # Send discord embeds of the currently running ctfs.
        now = datetime.utcnow()
        unix_now = int(now.replace(tzinfo=timezone.utc).timestamp())
        running = False

        for ctf in ctfs.find():
            if ctf['start'] < unix_now and ctf['end'] > unix_now:  # Check if the ctf is running
                running = True
                embed = discord.Embed(
                    title=':red_circle: ' + ctf['name']+' IS LIVE', description=ctf['url'], color=15874645)
                start = datetime.utcfromtimestamp(
                    ctf['start']).strftime('%Y-%m-%d %H:%M:%S') + ' UTC'
                end = datetime.utcfromtimestamp(ctf['end']).strftime(
                    '%Y-%m-%d %H:%M:%S') + ' UTC'
                if ctf['img'] != '':
                    embed.set_thumbnail(url=ctf['img'])
                else:
                    embed.set_thumbnail(
                        url="https://pbs.twimg.com/profile_images/2189766987/ctftime-logo-avatar_400x400.png")
                    # CTFtime logo

                embed.add_field(name='Duration', value=ctf['dur'], inline=True)
                embed.add_field(
                    name='Format', value=ctf['format'], inline=True)
                embed.add_field(name='Timeframe', value=start +
                                ' -> '+end, inline=True)
                await ctx.channel.send(embed=embed)

        if running is False:  # No ctfs were found to be running
            await ctx.reply("No CTFs currently running! Check out >ctftime countdown, and >ctftime upcoming to see when ctfs will start!")


    @ctftime.command(aliases=["next"])
    async def upcoming(self, ctx, amount=None):
        # Send embeds of upcoming ctfs from ctftime.org, using their api.
        if not amount:
            amount = 3
        upcoming_ep = "https://ctftime.org/api/v1/events/"
        default_image = "https://pbs.twimg.com/profile_images/2189766987/ctftime-logo-avatar_400x400.png"
        r = requests.get(upcoming_ep, headers=self.headers,
                         params={'limit': amount})

        upcoming_data = r.json()

        for ctf in range(0, int(amount)):
            ctf_title = upcoming_data[ctf]["title"]
            ctf_link = upcoming_data[ctf]["url"]
            ctftime_url = upcoming_data[ctf]["ctftime_url"]
            embed = discord.Embed(title=ctf_title, 
                                url=ctftime_url, 
                                description=ctf_link, 
                                color=int("f23a55", 16),
                                timestamp=datetime.now())

            teamID = upcoming_data[ctf]["organizers"][0]['id']
            teamName = upcoming_data[ctf]["organizers"][0]['name']
            teamLogo = requests.get(f"https://ctftime.org/api/v1/teams/{teamID}/", headers=self.headers).json()['logo']
            embed.set_author(name=teamName, url=f"https://ctftime.org/team/{teamID}", icon_url=teamLogo)

            ctf_image = upcoming_data[ctf]["logo"]
            if ctf_image:
                embed.set_thumbnail(url=ctf_image)
            else:
                embed.set_thumbnail(url=default_image)

            ts = int(datetime.strptime(upcoming_data[ctf]["start"], '%Y-%m-%dT%X%z').timestamp())
            embed.add_field(name="Start", value=f"<t:{ts}:F> <t:{ts}:R>", inline=False)

            ts = int(datetime.strptime(upcoming_data[ctf]["finish"], '%Y-%m-%dT%X%z').timestamp())
            embed.add_field(name="Finish", value=f"<t:{ts}:F> <t:{ts}:R>", inline=False)

            ctf_place = "Onsite" if upcoming_data[ctf]["onsite"] else "Online"
            ctf_format = upcoming_data[ctf]["format"]
            embed.add_field(name="Format", value=f"{ctf_place} {ctf_format}" , inline=True)

            ctf_days = upcoming_data[ctf]["duration"]["days"]
            ctf_hours = upcoming_data[ctf]["duration"]["hours"]
            embed.add_field(name="Duration", value=f"{ctf_days} days, {ctf_hours} hours", inline=True)

            embed.add_field(name="Weight", value=f"{upcoming_data[ctf]['weight']}" , inline=True)

            embed.set_footer(text=f"Information requested by: {ctx.author.display_name}")
            await ctx.channel.send(embed=embed)


    @ctftime.command(aliases=["leaderboard"])
    async def top(self, ctx, year=None, country=None):
        # Send a message of the ctftime.org leaderboards from a supplied year (defaults to current year).

        # Default to current year
        year = year or str(datetime.today().year)
        top_ep = f"https://ctftime.org/stats/{year}/"
        if country:
            country = country.strip().upper()
            if len(country) != 2 :
                await ctx.reply("Country code is not valid. [format: XX or XXX]")
                return
            top_ep += country

        leaderboards = ""
        r = requests.get(top_ep, headers=self.headers)
        if r.status_code != 200:
            await ctx.reply("Error retrieving data, please report this with `>report \"what happened\"`")
        else:
            try:
                soup = BeautifulSoup(r.text, 'html.parser')

                start = 2*bool(country)
                for team in soup.find_all('tr')[1:11]:
                    tds = team.find_all('td')
                    rank = tds[start].text
                    teamname = tds[2+start].text
                    score = tds[4+start-bool(country)].text

                    if team != 9:
                        # This is literally just for formatting.  I'm sure there's a better way to do it but I couldn't think of one :(
                        # If you know of a better way to do this, do a pull request or msg me and I'll add  your name to the cool list
                        leaderboards += f"\n[{rank.zfill(2)}]    {teamname}: {score}"
                    else:
                        leaderboards += f"\n[{rank.zfill(2)}]   {teamname}: {score}\n"

                await ctx.reply(f":triangular_flag_on_post:  **{year}{' '+country if country else ''} CTFtime Leaderboards**```ini\n{leaderboards}```")
            except KeyError:
                await ctx.reply("Please supply a valid year.")
                # LOG THIS


    @ctftime.command()
    async def timeleft(self, ctx):
        # Send the specific time that ctfs that are currently running have left.
        now = datetime.utcnow()
        unix_now = int(now.replace(tzinfo=timezone.utc).timestamp())
        running = False
        for ctf in ctfs.find():
            if ctf['start'] < unix_now and ctf['end'] > unix_now:  # Check if the ctf is running
                running = True
                time = ctf['end'] - unix_now
                days = time // (24 * 3600)
                time = time % (24 * 3600)
                hours = time // 3600
                time %= 3600
                minutes = time // 60
                time %= 60
                seconds = time
                await ctx.reply(f"```ini\n{ctf['name']} ends in: [{days} days], [{hours} hours], [{minutes} minutes], [{seconds} seconds]```\n{ctf['url']}")

        if not running:
            await ctx.reply('No ctfs are running! Use >ctftime upcoming or >ctftime countdown to see upcoming ctfs')


    @ctftime.command()
    async def countdown(self, ctx, params=None):
        # Send the specific time that upcoming ctfs have until they start.
        now = datetime.utcnow()
        unix_now = int(now.replace(tzinfo=timezone.utc).timestamp())

        if params is None:
            self.upcoming_l = []
            index = ""
            for ctf in ctfs.find():
                if ctf['start'] > unix_now:
                    # if the ctf start time is in the future...
                    self.upcoming_l.append(ctf)
            for i, c in enumerate(self.upcoming_l):
                index += f"\n[{i + 1}] {c['name']}\n"

            await ctx.reply(f"Type >ctftime countdown <number> to select.\n```ini\n{index}```")
        else:
            if self.upcoming_l != []:
                x = int(params) - 1
                time = self.upcoming_l[x]['start'] - unix_now
                days = time // (24 * 3600)
                time = time % (24 * 3600)
                hours = time // 3600
                time %= 3600
                minutes = time // 60
                time %= 60
                seconds = time

                await ctx.reply(f"```ini\n{self.upcoming_l[x]['name']} starts in: [{days} days], [{hours} hours], [{minutes} minutes], [{seconds} seconds]```\n{self.upcoming_l[x]['url']}")
            else:  # TODO: make this a function, too much repeated code here.
                for ctf in ctfs.find():
                    if ctf['start'] > unix_now:
                        self.upcoming_l.append(ctf)
                x = int(params) - 1
                time = self.upcoming_l[x]['start'] - unix_now
                days = time // (24 * 3600)
                time = time % (24 * 3600)
                hours = time // 3600
                time %= 3600
                minutes = time // 60
                time %= 60
                seconds = time

                await ctx.reply(f"```ini\n{self.upcoming_l[x]['name']} starts in: [{days} days], [{hours} hours], [{minutes} minutes], [{seconds} seconds]```\n{self.upcoming_l[x]['url']}")


    @ctftime.command()
    async def team(self, ctx, team=None, year=None):
        if not team:
            await ctx.reply(f":warning: please select team")
            return
        
        msg = await ctx.reply(f"Looking id for team {team}...")
        team_id = self.get_team_id(team)

        if team_id <= 0 and team.isnumeric():
            team_id = int(team)

        if team_id <= 0:
            await msg.edit(content=f":warning: Unknown team `{team}`.")
            return

        if not year:
            year = datetime.now().year
        
        await msg.edit(content=f"Looking up scores for {team} with id {team_id}...")

        teamName, table = self.get_scores(team_id, year)
        team = teamName if teamName else team
        if not table:
            await msg.edit(content=f"Team `{team}` has not played any events.")
            return
        table = [
            line[:2] + line[3:4] for line in table
        ]  # remove CTF points column, not interesting

        unscored = [
            line for line in table if line[2] == "0.000*"
        ]  # add unscored events to the bottom

        table = [line for line in table if line[2] != "0.000*"][
            :11
        ]  # get top 10 (+1 header)
        score = round(sum([float(line[2]) for line in table[1:]]), 3)

        if len(unscored) > 0:
            table.append(["", "", ""])
            table += unscored

        table.append(["", "", "", ""])
        table.append(["TOTAL", "", "", str(score)])  # add final line with total score

        table[0].insert(0, "Nr.")
        count = 1
        for line in table[1:-2]:  # add number column for easy counting
            line.insert(0, f"[{str(count).zfill(2)}]" if line[0] else "")
            if line[0]:
                count += 1

        out = f":triangular_flag_on_post:  **Top 10 events for {team} in {year}**"
        out += "```glsl\n"
        out += format_table(table)
        out += "\n```"
        await msg.edit(content=out)


    def get_team_id(self, team_name):
        ses = requests.Session()
        url = "https://ctftime.org/stats/"
        response = ses.get(url, headers=self.headers)
        token = response.cookies['csrftoken']
        
        url = "https://ctftime.org/team/list/"
        headers = {"Referer": "https://ctftime.org/stats/"}
        headers.update(self.headers)
        response = ses.post(
            url,
            data={"team_name": team_name, "csrfmiddlewaretoken": token},
            headers=headers,
        )
        team_id = response.url.split("/")[-1]
        if team_id.isnumeric():
            return int(team_id)
        return -1


    def get_scores(self, team_id, year=None):
        url = f"https://ctftime.org/team/{team_id}"
        r = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        div = soup.find("div", {"id": f"rating_{year}"})
        if not div:
            return None, None
        
        table = [ [ td.text.strip().replace("\t", " ") for td in tr.find_all("td")[1:]] for tr in div.find_all("tr")[1:] ]
        table.sort(key=lambda l: float(l[3].replace("*", "")), reverse=True)
        column_names = ["Place", "Event", "CTF Points", "Rating Points"]
        table = [column_names] + table

        teamName = soup.find("div", {"class": f"page-header"}).text.strip()

        return teamName, table


def format_table(table, seperator="      "):
    widths = [max(len(line[i]) for line in table) for i in range(len(table[0]))]
    return "\n".join([seperator.join([c.ljust(w) for w, c in zip(widths, line)]) for line in table])


async def setup(bot):
    await bot.add_cog(CtfTime(bot))
