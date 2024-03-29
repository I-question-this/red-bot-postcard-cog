import discord
from discord.ext import tasks
import feedparser
import logging
import markdownify
import time
import re

from redbot.core import checks, commands, Config
from redbot.core.data_manager import cog_data_path
from redbot.core.bot import Red

from .version import __version__, Version


LOG = logging.getLogger("red.postcard")
_DEFAULT_GLOBAL = {"posts": {}, "last_auto_post_date": None, 
                   "gmt_hour_start": 12}
_DEFAULT_GUILD = {"autopost_channel": None}


def tm_struct_to_string(tm_struct):
    return f"{tm_struct.tm_year}/{tm_struct.tm_mon}/{tm_struct.tm_mday}"


def interpret_post_html(post_html):
    img_p = re.compile("<img.*/>")
    rest = img_p.sub("", post_html)
    return markdownify.markdownify(rest)


def get_posts(rss_url) -> dict:
    # parsing blog feed
    blog_feed = blog_feed = feedparser.parse(rss_url)
      
    # getting lists of blog entries via .entries
    posts = blog_feed.entries
      
    # dictionary for holding posts
    post_list = {}
      
    # iterating over individual posts
    for post in posts:
        temp = dict()
          
        # if any post doesn't have information then throw error.
        temp["title"] = post.title
        temp["link"] = post.link
        temp["summary"] = post.summary
        published = tm_struct_to_string(post.published_parsed)
          
        post_list[published] = temp
      
    return post_list


class PostCard(commands.Cog):
    def __init__(self, bot:Red):
        """Init for the Postcard cog

        Parameters
        ----------
        bot: Red
            The Redbot instance instantiating this cog.
        """
        # Setup
        super().__init__()
        self.bot = bot

        self._conf = Config.get_conf(
                None, 93949998, 
                cog_name=f"{self.__class__.__name__}", force_registration=True
                )
        self._conf.register_global(**_DEFAULT_GLOBAL)
        self._conf.register_guild(**_DEFAULT_GUILD)
        # Start the auto post task
        self.auto_postcard.start()


    def cog_unload(self):
        self.auto_postcard.cancel()


    # Helper Commands
    async def update_postcards(self):
        await self._conf.posts.set(get_posts(
            "https://www.mezzacotta.net/postcard/rss.xml"))


    async def todays_postcard(self):
        # Check what we already have
        todays_date = tm_struct_to_string(time.gmtime())
        posts = await self._conf.posts()
        if todays_date not in posts.keys():
            LOG.info("Retrieving today's postcard")
            await self.update_postcards()
            posts = await self._conf.posts()
        # Return today's post, if it was posted
        return posts.get(todays_date)


    # Commands
    @commands.command()
    async def postcard_version(self, ctx:commands.Context):
        """Return the version number for Postcard"""
        contents = dict(
                title = "Postcard Version Number",
                description = f"{__version__}"
                )
        await ctx.send(embed=discord.Embed.from_dict(contents))


    @commands.command()
    async def postcard(self, ctx:commands.Context):
        """Get today's postcard"""
        today = await self.todays_postcard()
        if today is None:
            await ctx.send("Not yet posted today")
        else:
            await self.post_postcard(today, ctx.channel)


    async def post_postcard(self, post_card: dict, 
            channel:discord.TextChannel) -> None:
        """Post today's postcard"""
        contents = dict(
                title = post_card["title"],
                description = interpret_post_html(post_card["summary"])
                )
        embed = discord.Embed.from_dict(contents)
        embed.set_image(url="https://www.mezzacotta.net/postcard/comics/comic.png")
        await channel.send(embed=embed)


    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def set_postcard_autopost_channel(self, ctx: commands.Context, 
            channel:discord.TextChannel) -> None:
        """Sets which channel the postcard will be auto posted daily.
        Parameters
        ----------
        channel: discord.TextChannel
            The channel that postcards will be auto posted within.
        """
        await self._conf.guild(ctx.guild).autopost_channel.set(channel.id)
        LOG.info(f"In guild {ctx.guild.id} set autopost channel to: "\
                f"{channel.id}")
        contents = dict(
                title = "Set Auto Postcard Channel: Success",
                description = f"Auto Postcard channel set to {channel.name}"
                )
        embed = discord.Embed.from_dict(contents)
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def unset_postcard_autopost_channel(self, ctx: commands.Context) -> None:
        """Unsets the channel the postcard will be auto posted daily.
        """
        await self._conf.guild(ctx.guild).autopost_channel.set(None)
        LOG.info(f"In guild {ctx.guild.id} set autopost channel to: None")
        contents = dict(
                title = "Set Auto Postcard Channel: Success",
                description = "Auto Postcard channel set to None.\n"\
                              "This server will not receive postcards "\
                              "automatically"
                )
        embed = discord.Embed.from_dict(contents)
        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="set_gmt_hour_start")
    async def set_gmt_hour_start(self, ctx: commands.Context, 
            hour:int) -> None:
        """Sets what hour, in GMT time, to start posting the auto post.
        Parameters
        ----------
        hour: int
            The hour in which to start posting the autopost
        """
        if not (0 <= hour <= 23):
            contents = dict(
                    title = "Set GMT Hour Start: Failure",
                    description = f"Must be value [0,23]"
                    )
        else:
            await self._conf.gmt_hour_start.set(hour)
            LOG.info(f"GMT Hour Start set to {hour}")
            contents = dict(
                    title = "Set GMT Hour Start: Success",
                    description = f"GMT Hour Start set to {hour}"
                    )
        embed = discord.Embed.from_dict(contents)
        await ctx.send(embed=embed)


    @tasks.loop(minutes=15)
    async def auto_postcard(self):
        #check if it's too early to post
        if (time.gmtime().tm_hour < await self._conf.gmt_hour_start()):
            return

        last_auto_post_date = await self._conf.last_auto_post_date()
        todays_date = tm_struct_to_string(time.gmtime())
        if last_auto_post_date == todays_date:
            return

        postcard = await self.todays_postcard()
        if postcard is  None:
            return

        LOG.info(f"Auto Posting -- {todays_date}: Available")
        await self._conf.last_auto_post_date.set(todays_date)

        for guild in self.bot.guilds:
            # Get the registered channel for auto postcard posting
            channel_id = await self._conf.guild(guild).autopost_channel()
            if channel_id is not None:
                channel = self.bot.get_channel(channel_id)
                LOG.info(f"Auto Posting -- {todays_date}: Posted in "\
                         f"{guild.name}")
                await self.post_postcard(postcard, channel)


    @auto_postcard.before_loop
    async def before_auto_postcard(self):
        await self.bot.wait_until_ready()
