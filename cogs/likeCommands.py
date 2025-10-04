import discord
from discord.ext import commands, tasks
import aiohttp
from datetime import datetime
import json, os, asyncio
from dotenv import load_dotenv
import pytz

load_dotenv()
API_URL = os.getenv("API_URL")
CONFIG_FILE = "like_channels.json"
IST = pytz.timezone("Asia/Kolkata")   # Indian Standard Time

# 👇 set your fixed channel ID here
FIXED_CHANNEL_ID = 1417932595911590050   # replace with your channel ID

# Set up intents
intents = discord.Intents.default()  # Default intents
intents.message_content = True       # Enable message content intent
intents.members = True               # Enable server members intent

class LikeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_host = API_URL
        self.config_data = self.load_config()
        self.cooldowns = {}
        self.session = aiohttp.ClientSession()
        self.auto_like_task.start()

    # ================= CONFIG =================
    def load_config(self):
        default_config = {"uids": [], "auto_time": "07:30"}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("uids", [])
                    loaded_config.setdefault("auto_time", "07:30")
                    return loaded_config
            except json.JSONDecodeError:
                print("⚠️ Config file corrupted. Resetting.")
        self.save_config(default_config)
        return default_config

    def save_config(self, config_to_save=None):
        data = config_to_save if config_to_save else self.config_data
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, CONFIG_FILE)

    # ================= AUTO LIKE =================
    @tasks.loop(minutes=1)
    async def auto_like_task(self):
        now = datetime.now(IST).strftime("%H:%M")
        if now == self.config_data.get("auto_time", "07:30"):
            channel = self.bot.get_channel(FIXED_CHANNEL_ID)
            if channel:
                await channel.send("⚡ Starting daily auto-like...")

                for entry in self.config_data["uids"]:
                    uid = entry["uid"]
                    server = entry["server"]
                    await self.send_like_request(channel, uid, server)
                    await asyncio.sleep(3)  # avoid API spam

    async def send_like_request(self, channel, uid, server):
        url = f"{self.api_host}/like?uid={uid}&server={server}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    embed = discord.Embed(
                        title="FREE FIRE AUTO LIKE",
                        color=0x2ECC71 if data.get("status") == 1 else 0xE74C3C,
                        timestamp=datetime.now()
                    )
                    if data.get("status") == 1:
                        embed.description = (
                            f"✅ Daily like sent!\n\n"
                            f"**UID:** {uid}\n"
                            f"**Player:** {data.get('player','Unknown')}\n"
                            f"**Added:** +{data.get('likes_added', 0)}\n"
                            f"**Before:** {data.get('likes_before','N/A')}\n"
                            f"**After:** {data.get('likes_after','N/A')}"
                        )
                    else:
                        embed.description = f"UID {uid} has already received max likes today."
                    await channel.send(embed=embed)
                else:
                    await channel.send(f"⚠️ API error for UID {uid} (status {response.status})")
        except Exception as e:
            await channel.send(f"❌ Error auto-liking UID {uid}: {e}")

    # ================== COMMANDS ==================
    async def check_channel(self, ctx):
        """Only allow commands in fixed channel"""
        return ctx.channel.id == FIXED_CHANNEL_ID

    @commands.hybrid_command(name="add", description="Add a UID to daily auto-like")
    async def add_uid(self, ctx: commands.Context, uid: str, server: str):
        if not await self.check_channel(ctx):
            return  # 🚫 do nothing outside fixed channel

        self.config_data["uids"].append({"uid": uid, "server": server})
        self.save_config()
        await ctx.send(f"✅ UID {uid} (server {server}) added to auto-like list.")

    @commands.hybrid_command(name="remove", description="Remove a UID from daily auto-like")
    async def remove_uid(self, ctx: commands.Context, uid: str):
        if not await self.check_channel(ctx):
            return  # 🚫 do nothing outside fixed channel

        before = len(self.config_data["uids"])
        self.config_data["uids"] = [u for u in self.config_data["uids"] if u["uid"] != uid]
        self.save_config()
        if len(self.config_data["uids"]) < before:
            await ctx.send(f"✅ UID {uid} removed from auto-like list.")
        else:
            await ctx.send(f"⚠️ UID {uid} not found in list.")

    @commands.hybrid_command(name="listuid", description="Show all UIDs in auto-like list")
    async def list_uid(self, ctx: commands.Context):
        if not await self.check_channel(ctx):
            return  # 🚫 do nothing outside fixed channel

        if not self.config_data["uids"]:
            await ctx.send("📭 No UIDs saved for auto-like yet.")
            return
        msg = "**📋 Daily Auto-Like UIDs:**\n"
        for entry in self.config_data["uids"]:
            msg += f"- UID: {entry['uid']} | Server: {entry['server']}\n"
        await ctx.send(msg)

    @commands.hybrid_command(name="settime", description="Set daily auto-like time (HH:MM IST)")
    async def set_time(self, ctx: commands.Context, time: str):
        if not await self.check_channel(ctx):
            return  # 🚫 do nothing outside fixed channel

        try:
            datetime.strptime(time, "%H:%M")
            self.config_data["auto_time"] = time
            self.save_config()
            await ctx.send(f"✅ Auto-like time updated to {time} IST.")
        except ValueError:
            await ctx.send("❌ Invalid time format. Use HH:MM (24h). Example: 07:30")

    # ✅ Manual like command
    @commands.command(name="like", help="Manually send like to a Free Fire player")
    async def like_command(self, ctx: commands.Context, server: str, uid: str):
        if not await self.check_channel(ctx):
            return  # 🚫 do nothing outside fixed channel

        await self.send_like_request(ctx.channel, uid, server)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())


async def setup(bot):
    await bot.add_cog(LikeCommands(bot))
