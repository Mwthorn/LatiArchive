import asyncio
import discord
import json
import os
import shutil
import urllib.request
import requests

from zipfile import ZipFile
from aiohttp import web
from discord import Embed
from discord.ext import commands
from discord.ext.commands import CommandNotFound
from os import listdir
from os.path import isfile, join

"""
Packages to install:
- request (python3.8 -m pip install requests)
- discord (python3.8 -m pip install -U discord.py[voice])

asyncio requires Python 3.7 or higher (3.8 is preferred) 
    (Instructions: https://tecadmin.net/install-python-3-8-ubuntu/)

Keep it running without terminal open:
nohup python3.8 Lati_Archive.py &
nohup python3.8 -u ./Lati_Archive.py > Lati_Archive.log &

Shutdown program:
ps -ef | grep Lati_Archive.py
kill 2 <PID>
kill 2 14398

Running normally from terminal:
python3.8 Lati_Archive.py
"""

# TODO: Create a default config_file if it does not exists
with open('data/config.json', encoding="utf8") as json_file:
    config_file = json.load(json_file)

lati_bot = commands.Bot(command_prefix='!')
lati_bot.remove_command('help')

custom_global_obj = type('', (), {})()
custom_global_obj.dict = {}
custom_global_obj.dict.setdefault("lati_archive", {})
custom_global_obj.dict["lati_archive"].setdefault("selected_id", None)
custom_global_obj.dict["lati_archive"].setdefault("edited_embed", None)


def is_url_image(image_url):
    image_formats = ("image/png", "image/jpeg", "image/jpg")
    r = requests.head(image_url)
    return r.headers["content-type"] in image_formats


def zip_lati_archive():
    try:
        shutil.rmtree('data/lati_archive.zip')
    except FileNotFoundError:
        print("Zip File not found. Resuming...")
    except NotADirectoryError:
        print("Zip File not found. Resuming...")
    zip_obj = ZipFile('data/lati_archive.zip', 'w')
    for folder in os.listdir("data/lati_archive"):
        for art_file in os.listdir("data/lati_archive/" + folder):
            zip_obj.write('data/lati_archive/' + folder + "/" + art_file)
    zip_obj.close()


def get_web_page(url):
    response = urllib.request.urlopen(url)
    url_data = response.read()
    text = url_data.decode('utf-8')

    # return (data,json.loads(text))
    return text


async def download_image(feedback_channel, image_filepath, image_url):
    async with feedback_channel.typing():
        try:
            os.mkdir(image_filepath)
            img_data = requests.get(image_url).content
            with open(image_filepath + "/image.png", 'wb') as img_handler:
                # TODO: Maybe save image as original filename ?
                img_handler.write(img_data)
        except OSError:
            # TODO: Automatically retry
            custom_global_obj.dict["lati_archive"]["selected_id"] = None
            my_embed = discord.Embed(title="Error: Failed downloading", color=0xaa0000,
                                     description="Something happened when saving the image. "
                                                 "This will usually work if tried again.")
            await feedback_channel.send(embed=my_embed)
            return False
    return True


@lati_bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    print("CTX: ", ctx)
    raise error


@lati_bot.event
async def on_ready():
    print('lati bot ready')


@lati_bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    if before.channel.id not in config_file["channels"]["allowed_text_channels"]:
        return
    print(len(before.embeds))
    print(len(after.embeds))
    if before.content == after.content:
        args = after.content.split(" ")
        if len(args) >= 2 and len(before.embeds) == 0 and len(after.embeds) > 0:
            print("EmbedCheck1")
            if after.content.startswith("!art") and after.content.split(" ")[1] in ["save", "create", "archive"]:
                print("EmbedCheck2")
                if after.embeds:
                    custom_global_obj.dict["lati_archive"]["edited_embed"] = after.embeds


@lati_bot.event
async def on_message(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel):
        return
    if isinstance(message.channel, discord.GroupChannel):
        return
    if message.content.startswith("!"):
        cmd = message.content.split("!", 1)[1].split(" ")[0]
    else:
        return
    args = message.content.split(" ")
    feedback_channel = message.channel
    channel_id = message.channel.id
    if channel_id in config_file["channels"]["allowed_text_channels"]:
        if cmd in ["shutdown", "exit", "luk"]:
            await feedback_channel.send("Shutting down...")
            raise SystemExit
        if cmd in ["art"]:
            if len(args) <= 1:
                return await feedback_channel.send("!art (save/info/title/desc/tags/author)")
                # TODO: Add further details on sub-commands
            if args[1] in ["create", "save", "archive"]:
                custom_global_obj.dict["lati_archive"]["edited_embed"] = None
                if len(args) <= 2:
                    if not message.attachments:
                        return await feedback_channel.send("Use `!art save (url or attach image to message)`")
                    url = message.attachments[0].url
                else:
                    url = args[2]
                if not url.startswith("http"):
                    return await feedback_channel.send("This requires a http or https link")

                with open('data/lati_archive.json', encoding="utf8") as file:
                    lati_file = json.load(file)

                for key in lati_file["art"].keys():
                    if url == lati_file["art"][key]["source"]["page"]:
                        return await feedback_channel.send("That link has already been archived as ID: **" +
                                                           key + "**")
                    elif url == lati_file["art"][key]["source"]["direct"]:
                        return await feedback_channel.send("That link has already been archived as ID: **" +
                                                           key + "**")
                    elif url == lati_file["art"][key]["source"]["preview"]:
                        return await feedback_channel.send("That link has already been archived as ID: **" +
                                                           key + "**")
                # TODO: Create a temp.json file is it does not exists
                with open('data/temp.json') as json_temp_file:
                    temp_data = json.load(json_temp_file)
                id_selected = str(temp_data["lati_art_id"])

                lati_file["art"].setdefault(id_selected, {
                    "title": None,
                    "description": None,
                    "tags": [],
                    "creators": [],
                    "backup_caches": [],
                    "source": {
                        "page": None,
                        "direct": None,
                        "preview": None
                    }
                })

                custom_global_obj.dict["lati_archive"]["selected_id"] = id_selected
                aquired_info = {
                    "title": None,
                    "description": None,
                    "tags": [],
                    "creators": None,
                    "direct_url": None,
                    "page_url": None
                }

                image_filepath = "data/lati_archive/" + id_selected
                if is_url_image(url):
                    lati_file["art"][id_selected]["source"]["direct"] = url
                    aquired_info["direct_url"] = "Link to image (Direct)"
                    if not await download_image(feedback_channel, image_filepath, url):
                        return
                    # TODO: Check if image file contains additional info (After downloaded)
                else:
                    lati_file["art"][id_selected]["source"]["page"] = url
                    aquired_info["page_url"] = "Link to art Page"
                    if "deviantart.com" in url:
                        result = get_web_page(url)
                        # TODO: Do something about predefined pages
                    elif "furaffinity.net" in url:
                        result = get_web_page(url)
                        # TODO: Do something about predefined pages
                    check_embed = None
                    if message.embeds:
                        print("Detected embeds: " + str(len(message.embeds)))
                        check_embed = message.embeds[0]
                    else:
                        async with feedback_channel.typing():
                            await asyncio.sleep(5)
                            if custom_global_obj.dict["lati_archive"]["edited_embed"] is not None:
                                check_embed = custom_global_obj.dict["lati_archive"]["edited_embed"][0]
                                print("Detected embeds from edit: " +
                                      str(len(custom_global_obj.dict["lati_archive"]["edited_embed"])))
                    if check_embed is not None:
                        if check_embed.title != Embed.Empty:
                            lati_file["art"][id_selected]["title"] = check_embed.title
                            aquired_info["title"] = "Title (Embed)"
                            for check_tag in config_file["lati_archive"]["check_tags"]:
                                check_str = check_embed.title.lower()
                                if check_tag in check_str:
                                    aquired_info["tags"].append(check_tag)
                        if check_embed.description != Embed.Empty:
                            lati_file["art"][id_selected]["description"] = check_embed.description
                            aquired_info["description"] = "Description (Embed)"
                            for check_tag in config_file["lati_archive"]["check_tags"]:
                                check_str = check_embed.description.lower()
                                if check_tag in check_str:
                                    aquired_info["tags"].append(check_tag)
                        if check_embed.image != Embed.Empty and check_embed.image.url != Embed.Empty:
                            image = check_embed.image.__dict__
                            lati_file["art"][id_selected]["source"]["preview"] = image["url"]
                            aquired_info["direct_url"] = "Link to direct file (Embed image)"
                            if not await download_image(feedback_channel, image_filepath, image["url"]):
                                return
                        elif check_embed.thumbnail != Embed.Empty and check_embed.thumbnail.url != Embed.Empty:
                            image = check_embed.thumbnail.__dict__
                            lati_file["art"][id_selected]["source"]["preview"] = image["url"]
                            aquired_info["direct_url"] = "Link to direct file (Embed thumbnail)"
                            if not await download_image(feedback_channel, image_filepath, image["url"]):
                                return
                        if check_embed.author != Embed.Empty:
                            if check_embed.author.name != Embed.Empty and check_embed.author.url != Embed.Empty:
                                author_dict = {
                                    "name": check_embed.author.name,
                                    "contacts": {
                                        "website": check_embed.author.url
                                    }
                                }
                                lati_file["art"][id_selected]["creators"].append(author_dict)
                                aquired_info["creators"] = "Author & profile page (Embed)"

                missing_info = []
                if aquired_info["title"] is None:
                    missing_info.append("Title\n  `!art title (Some title)`")
                if aquired_info["description"] is None:
                    missing_info.append("Description\n  `!art desc (Some description)`")
                if not aquired_info["tags"]:
                    missing_info.append("Tags\n  `!art tags (latios,latias,hug,example,tags)`")
                if aquired_info["creators"] is None:
                    missing_info.append("Author (Highly recommended to include credits)" +
                                        "\n  `!art author (name) (profile link)`")
                if aquired_info["page_url"] is None:
                    missing_info.append("Page (Where did the art come from?)\n  `!art page (link or place)`")

                detected_info = []
                for key in aquired_info.keys():
                    if key == "tags":
                        if aquired_info[key]:
                            detected_info.append("Tags: " + ",".join(aquired_info[key]))
                    elif aquired_info[key] is not None:
                        detected_info.append(aquired_info[key])
                desc = "Saved art to the archive with id: **" + id_selected + "**"
                my_embed = discord.Embed(title="Successfully added art to archive!", color=0x00ff00, description=desc)

                if aquired_info["direct_url"] is None:
                    # missing_info.append("Image URL\n  `!art image (url)`")
                    custom_global_obj.dict["lati_archive"]["selected_id"] = None
                    my_embed = discord.Embed(title="Error: No Image found", color=0xaa0000,
                                             description="No image was detected from this link. "
                                                         "Try again with the same link "
                                                         "or the direct link to the image if possible.")
                    await feedback_channel.send(embed=my_embed)
                    return
                lati_file["art"][id_selected]["backup_caches"].append("https://api.casualcade.dk/lati_archive/" +
                                                                      id_selected)

                if detected_info:
                    print(detected_info)
                    my_embed.add_field(name="Automatically detected & saved:",
                                       value="- " + "\n- ".join(detected_info),
                                       inline=False)
                if missing_info:
                    my_embed.add_field(name="Missing optional information:",
                                       value="- " + "\n- ".join(missing_info),
                                       inline=False)
                with open('data/lati_archive.json', 'w') as archive_file:
                    try:
                        json.dump(lati_file, archive_file, indent=4)
                    except TypeError:
                        print(lati_file)
                await feedback_channel.send(embed=my_embed)
                with open('data/temp.json') as json_temp_file:
                    temp_data = json.load(json_temp_file)
                temp_data["lati_art_id"] += 1
                with open('data/temp.json', 'w') as f:
                    json.dump(temp_data, f, indent=4)
            elif args[1] in ["title"]:
                print("TODO")
                # TODO: Set title to selected ID
            elif args[2] in ["description"]:
                print("TODO")
                # TODO Add description to selected ID
            elif args[2] in ["tags"]:
                print("TODO")
                # TODO Add tags to selected ID
            elif args[2] in ["author"]:
                print("TODO")
                # TODO Add author to selected ID
            elif args[2] in ["image", "direct", "preview"]:
                print("TODO")
                # TODO Add image (+ download) to selected ID
            elif args[1] in ["choose", "select", "get", "info", "display", "show"]:
                with open('data/lati_archive.json', encoding="utf8") as file:
                    lati_file = json.load(file)
                if args[2] not in lati_file["art"].keys():
                    return await feedback_channel.send("This ID does not exists.")
                id_selected = args[2]
                custom_global_obj.dict["lati_archive"]["selected_id"] = id_selected
                title = lati_file["art"][id_selected]["title"]
                if title is None:
                    title = "Unknown title (Default)"
                description = lati_file["art"][id_selected]["description"]
                if description is None:
                    description = "Unknown description (Default)"
                url = lati_file["art"][id_selected]["source"]["url"]
                embed = discord.Embed(title="[" + title + "](" + url
                                            + ")", description=description)
                direct_link = lati_file["art"][id_selected]["source"]["direct"]
                preview_link = lati_file["art"][id_selected]["source"]["preview"]
                backup = lati_file["art"][id_selected]["backup_caches"]
                if direct_link is not None:
                    embed.set_image(url=direct_link)
                elif preview_link is not None:
                    embed.set_image(url=direct_link)
                elif backup:
                    embed.set_image(url=backup[0])
                else:
                    embed.add_field(name="No cache of the image found",
                                    value="[Link to art](" + url + ")",
                                    inline=True)
                await feedback_channel.send(embed=embed)


async def handler(request_data):
    print("[API Handler] Request from " + request_data.remote +
          " path: " + request_data.path_qs + " " + request_data.content_type + " " + request_data.content_type)
    if request_data.path == "/favicon.ico":
        return web.FileResponse("data/favicon.ico")
    elif request_data.path == "/lati_archive/":
        return web.FileResponse("data/lati_archive.json")
    elif request_data.path == "/lati_archive/everything":
        return web.FileResponse("data/lati_archive.zip")
    elif request_data.path.startswith("/lati_archive/"):
        selected_id = request_data.path.split("lati_archive/")[1]
        path = "data/lati_archive/" + str(selected_id)
        print("Should check folder: " + path)
        if os.path.isdir(path):
            onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
            print("Should check file: " + onlyfiles[0])
            if onlyfiles:
                return web.FileResponse(path + "/" + onlyfiles[0])
    return web.Response(text="Nothing here...")


async def main():
    errored = False
    try:
        server = web.Server(handler)
        runner = web.ServerRunner(server)
        await runner.setup()
        host = config_file["web_host"]
        port = config_file["web_port"]
        site = web.TCPSite(runner, host, port)
        await site.start()
        print("======= Serving on http://" + host + ":" + str(port) + "/ ======")
    except OSError:
        errored = True
    if errored:
        server = web.Server(handler)
        runner = web.ServerRunner(server)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8080)
        await site.start()
        print("======= Serving on http://127.0.0.1:8080/ ======")
    # pause here for very long time by serving HTTP requests and
    # waiting for keyboard interruption
    # await asyncio.sleep(100 * 3600)


if __name__ == '__main__':
    zip_lati_archive()
    loop = asyncio.get_event_loop()
    loop.create_task(lati_bot.start(config_file["discord_bot_token"]))
    loop.run_until_complete(main())
    loop.run_forever()
