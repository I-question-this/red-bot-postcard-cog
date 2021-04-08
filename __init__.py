# Set up Dad bot
from .postcard import PostCard
def setup(bot):
    bot.add_cog(PostCard(bot))
