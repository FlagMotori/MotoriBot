import random
import json
from discord.ext import commands

# This can be thought of as a miscellaneous category (anything 'utility' based.)


class Utility(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['char'])
    async def characters(self, ctx, string):
        await ctx.reply(len(string))

    @commands.command(aliases=['wc'])
    async def wordcount(self, ctx, *args):
        await ctx.reply(len(args))

    @commands.command(aliases=['rev'])
    async def reverse(self, ctx, message):
        await ctx.reply(message[::-1])

    @commands.command()
    async def counteach(self, ctx, message):
        # Count the amount of characters in a string.
        count = {}
        for char in message:
            if char in count:
                count[char] += 1
            else:
                count[char] = 1
        await ctx.reply(f"```{json.dumps(count, indent=4)}```")

    @commands.command(aliases=['head'])
    async def magicb(self, ctx, filetype):
        # Get the magic bytes from a filetype
        with open('magic.json') as file:
            alldata = json.load(file)
        fileType = filetype.strip().lower()
        try:
            mime = alldata[fileType]['mime']
            signs = '\n'.join(map(lambda s: f"- `{s}`", alldata[fileType]['signs']))
            await ctx.reply(f"{mime}:\n{signs}", mention_author=True)
        except:  # if the filetype is not in magicb.json...
            await ctx.reply(f"{filetype} not found :(  If you think this filetype should be included please do `>request \"magicb {filetype}\"`")

    @commands.command()
    async def twitter(self, ctx, twituser):
        await ctx.reply(f"https://twitter.com/{twituser}")

    @commands.command()
    async def github(self, ctx, gituser):
        await ctx.reply(f"https://github.com/{gituser}")

    @commands.command(aliases=['5050', 'flip'])
    async def cointoss(self, ctx):
        await ctx.reply('heads' if random.randint(0, 1) else 'tails')
    
    @commands.command(aliases=['up'])
    async def ping(self, ctx):
        await ctx.message.delete()
        await ctx.send("I'm UP!", delete_after=10, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Utility(bot))
