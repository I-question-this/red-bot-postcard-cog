# Set up Dad bot
from .postcard import PostCard
async def setup(bot):
    await bot.add_cog(PostCard(bot))
