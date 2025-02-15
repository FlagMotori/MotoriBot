import asyncio
import os
import discord
from discord.ext import commands
import config_vars
import help_info

command_prefix = "./"  # unix like :)
bot = commands.Bot(command_prefix=command_prefix,
                   allowed_mentions=discord.AllowedMentions(
                       everyone=False, users=False, roles=False),
                   intents=discord.Intents.all())

help_info.set_prefix(command_prefix)

# The default help command is removed so a custom one can be added.
bot.remove_command('help')

# Each extension corresponds to a file within the cogs directory.  Remove from the list to take away the functionality.
extensions = ['ctf', 'ctftime', 'configuration',
              'encoding', 'cipher', 'utility']
# List of names reserved for those who gave cool ideas or reported something interesting.
# please don't spam me asking to be added.  if you send something interesting to me i will add you to the list.
# If your name is in the list and you use the command '>amicool' you'll get a nice message.
cool_names = ['nullpxl', 'Yiggles', 'JohnHammond', 'voidUpdate', 'Michel Ney', 'theKidOfArcrania', 'l14ck3r0x01', 'hasu', 'KFBI',
              'mrFu', 'warlock_rootx', 'd347h4ck', 'tourpan', 'careless_finch', 'fumenoid', '_wh1t3r0se_', 'The_Crazyman', '0x0elliot']
# This is intended to be circumvented; the idea being that people will change their names to people in this list just so >amicool works for them, and I think that's funny.


@bot.event
async def on_ready():
    print(f"{bot.user.name} - Online")
    print(f"discord.py {discord.__version__}\n")
    print("-------------------------------")

    await bot.change_presence(activity=discord.Game(name=f"{command_prefix}help | {command_prefix}source"))


@bot.command()
async def help(ctx, page=None):
    # Custom help command.  Each main category is set as a 'page'.
    if page == 'ctftime':
        emb = discord.Embed(description=help_info.ctftime_help, colour=4387968)
        emb.set_author(name='CTFTime Help')
    elif page == 'ctf':
        emb = discord.Embed(description=help_info.ctf_help, colour=4387968)
        emb.set_author(name='CTF Help')
    elif page == 'config':
        emb = discord.Embed(description=help_info.config_help, colour=4387968)
        emb.set_author(name='Configuration Help')
    elif page == 'utility':
        emb = discord.Embed(description=help_info.utility_help, colour=4387968)
        emb.set_author(name='Utilities Help')
    else:
        emb = discord.Embed(description=help_info.help_page, colour=4387968)
        emb.set_author(name='Help')

    await attach_embed_info(ctx, emb)
    await ctx.reply(embed=emb)


async def attach_embed_info(ctx=None, embed=None):
    embed.set_thumbnail(url=f'{bot.user.avatar.url}')
    return embed


@bot.command()
async def source(ctx):
    # Sends the github link of the bot.
    await ctx.send(help_info.src)

@bot.command()
async def sync(ctx):
    print("sync command")
    await bot.tree.sync()
    await ctx.send('Command tree synced.')
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Missing a required argument.  Do >help")
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You do not have the appropriate permissions to run this command.")
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.reply("I don't have sufficient permissions!")
    else:
        print("error not caught")
        print(error)


@bot.command()
async def request(ctx, feature):
    # Bot sends a dm to creator with the name of the user and their request.
    creator = await bot.fetch_user(230827776637272064)
    authors_name = str(ctx.author)
    await creator.send(f''':pencil: {authors_name}: {feature}''')
    await ctx.reply(f''':pencil: Thanks, "{feature}" has been requested!''')


@bot.command()
async def report(ctx, error_report):
    # Bot sends a dm to creator with the name of the user and their report.
    creator = await bot.fetch_user(230827776637272064)
    authors_name = str(ctx.author)
    await creator.send(f''':triangular_flag_on_post: {authors_name}: {error_report}''')
    await ctx.reply(f''':triangular_flag_on_post: Thanks for the help, "{error_report}" has been reported!''')


@bot.command()
async def amicool(ctx):
    authors_name = str(ctx.author).split("#")[0]
    if authors_name in cool_names:
        await ctx.reply('You are very cool :]')
    else:
        await ctx.reply('lolno\nPsst, kid.  Want to be cool?  Find an issue and report it or request a feature!')


async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
            except Exception as e:
                print(f'Failed to load cogs : {e}')


async def main():
    async with bot:
        await load_extensions()
        await bot.start(config_vars.discord_token)

if __name__ == '__main__':
    asyncio.run(main())
