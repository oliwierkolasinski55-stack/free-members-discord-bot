import discord
import requests
import json
import os
import asyncio
from discord.ext import commands
from urllib.parse import urlencode

# ===== CONFIG =====
with open("config.json", "r") as f:
    config = json.load(f)

BOT_TOKEN = config["token"]
CLIENT_ID = config["id"]
CLIENT_SECRET = config["secret"]

REDIRECT_URI = "https://parrotgames.free.nf/discord-redirect.html"
AUTH_FILE = "auths.txt"

# ===== BOT =====
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== TOKEN HELPERS =====
def refresh_access_token(refresh_token):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    r = requests.post("https://discord.com/api/v10/oauth2/token", data=data)
    return r.json() if r.status_code == 200 else None


def update_token(user_id, access, refresh):
    if not os.path.exists(AUTH_FILE):
        return
    lines = []
    with open(AUTH_FILE, "r") as f:
        for l in f:
            if l.startswith(user_id + ","):
                lines.append(f"{user_id},{access},{refresh}\n")
            else:
                lines.append(l)
    with open(AUTH_FILE, "w") as f:
        f.writelines(lines)


def get_valid_token(user_id, access, refresh):
    test = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access}"}
    )
    if test.status_code == 200:
        return access

    new = refresh_access_token(refresh)
    if not new:
        return None

    update_token(user_id, new["access_token"], new["refresh_token"])
    return new["access_token"]

# ===== COMMANDS =====

@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def get_token(ctx):
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds.join",
        "prompt": "consent",
    }
    url = f"https://discord.com/oauth2/authorize?{urlencode(params)}"
    await ctx.send(
        f"🔐 **AUTH LINK**\n"
        f"{url}\n\n"
        f"Po zalogowaniu użyj:\n"
        f"`!auth KOD`"
    )


@bot.hybrid_command()
@commands.has_permissions(administrator=True)
async def auth(ctx, code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    r = requests.post("https://discord.com/api/v10/oauth2/token", data=data)
    if r.status_code != 200:
        await ctx.send("❌ Nieprawidłowy kod.")
        return

    tokens = r.json()
    user_id = str(ctx.author.id)

    lines = []
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            for l in f:
                if not l.startswith(user_id + ","):
                    lines.append(l)

    lines.append(f"{user_id},{tokens['access_token']},{tokens['refresh_token']}\n")

    with open(AUTH_FILE, "w") as f:
        f.writelines(lines)

    await ctx.send("✅ Token zapisany.")


@bot.hybrid_command()
async def djoin(ctx, server_id: str):
    if not os.path.exists(AUTH_FILE):
        await ctx.send("❌ Brak użytkowników.")
        return

    users = []
    with open(AUTH_FILE, "r") as f:
        for line in f:
            p = line.strip().split(",")
            if len(p) >= 3:
                users.append({
                    "id": p[0],
                    "access": p[1],
                    "refresh": p[2],
                })

    total = len(users)
    msg = await ctx.send(
        f"🤖 **DJOIN STARTED**\n"
        f"👥 Użytkowników: {total}"
    )

    ok = 0
    fail = 0
    refreshed = 0

    for i, u in enumerate(users):
        token = get_valid_token(u["id"], u["access"], u["refresh"])
        if not token:
            fail += 1
            continue

        if token != u["access"]:
            refreshed += 1

        r = requests.put(
            f"https://discord.com/api/v10/guilds/{server_id}/members/{u['id']}",
            headers={
                "Authorization": f"Bot {BOT_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"access_token": token},
        )

        if r.status_code in (201, 204):
            ok += 1
        else:
            fail += 1

        if i % 10 == 0:
            await msg.edit(
                content=
                f"🤖 **DJOIN IN PROGRESS**\n"
                f"👥 {total}\n"
                f"✅ {ok} | ❌ {fail} | 🔄 {refreshed}"
            )

        await asyncio.sleep(1)

    await msg.edit(
        content=
        f"✅ **DJOIN FINISHED**\n"
        f"👥 {total}\n"
        f"✅ {ok} | ❌ {fail} | 🔄 {refreshed}"
    )


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Brak uprawnień (admin).")
    else:
        raise error


bot.run(BOT_TOKEN)
