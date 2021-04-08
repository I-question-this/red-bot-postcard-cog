import discord
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
_DEFAULT_GLOBAL = {"posts": {}}
_DEFAULT_GUILD = {"registered_channel_id": None}

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
            self.update_postcards()
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


    @commands.is_owner()
    @commands.command()
    async def postcard(self, ctx:commands.Context):
        """Get today's postcard"""
        today = await self.todays_postcard()
        if today is None:
            await ctx.send("Not yet posted today")
        else:
            contents = dict(
                    title = today["title"],
                    description = interpret_post_html(today["summary"])
                    )
            embed = discord.Embed.from_dict(contents)
            embed.set_image(url="https://www.mezzacotta.net/postcard/comics/comic.png")
            await ctx.send(embed=embed)

