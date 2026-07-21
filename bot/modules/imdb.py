#!/usr/bin/env python3
from contextlib import suppress
from re import findall, IGNORECASE, search

from imdbinfo import search_title, get_movie, get_akas
from pycountry import countries as conn

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty

from bot import bot, LOGGER, user_data, config_dict
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, deleteMessage
from bot.helper.ext_utils.bot_utils import get_readable_time, sync_to_async
from bot.helper.telegram_helper.button_build import ButtonMaker

IMDB_GENRE_EMOJI = {
    "Action": "🚀",
    "Adult": "🔞",
    "Adventure": "🌋",
    "Animation": "🎠",
    "Biography": "📜",
    "Comedy": "🪗",
    "Crime": "🔪",
    "Documentary": "🎞",
    "Drama": "🎭",
    "Family": "👨‍👩‍👧‍👦",
    "Fantasy": "🫧",
    "Film Noir": "🎯",
    "Game Show": "🎮",
    "History": "🏛",
    "Horror": "🧟",
    "Musical": "🎻",
    "Music": "🎸",
    "Mystery": "🧳",
    "News": "📰",
    "Reality-TV": "🖥",
    "Romance": "🥰",
    "Sci-Fi": "🌠",
    "Short": "📝",
    "Sport": "⛳",
    "Talk-Show": "👨‍🍳",
    "Thriller": "🗡",
    "War": "⚔",
    "Western": "🪩",
}
LIST_ITEMS = 4


async def imdb_search(_, message):
    if " " in message.text:
        k = await sendMessage(message, "<code>Searching IMDB ...</code>")
        title = message.text.split(" ", 1)[1]
        user_id = message.from_user.id
        buttons = ButtonMaker()
        
        # Check if it's an IMDB URL
        if result := search(r"tt(\d+)", title, IGNORECASE):
            movieid = result.group(1)
            movie = await sync_to_async(get_movie, movieid)
            if movie:
                buttons.ibutton(
                    f"🎬 {movie.title} ({getattr(movie, 'year', 'N/A')})",
                    f"imdb {user_id} movie {movieid}",
                )
            else:
                return await editMessage(k, "<i>No Results Found</i>")
        else:
            movies = await sync_to_async(get_poster, title, bulk=True)
            if not movies:
                return await editMessage(
                    k, "<i>No Results Found</i>, Try Again or Use <b>Title ID</b>"
                )
            for movie in movies:
                buttons.ibutton(
                    f"🎬 {movie.title} ({getattr(movie, 'year', 'N/A')})",
                    f"imdb {user_id} movie {movie.id}",
                )
        buttons.ibutton("🚫 Close 🚫", f"imdb {user_id} close")
        await editMessage(
            k, "<b><i>Here What I found on IMDb.com</i></b>", buttons.build_menu(1)
        )
    else:
        await sendMessage(
            message,
            "<i>Send Movie / TV Series Name along with /imdb Command or send IMDB URL</i>",
        )


def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = findall(r"[1-2]\d{3}$", query, IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = findall(r"[1-2]\d{3}", file, IGNORECASE)
            if year:
                year = list_to_str(year[:1])
        else:
            year = None
            
        movie_results = search_title(title.lower())
        movieid = movie_results.titles if movie_results else []
        if not movieid:
            return None
        if year:
            filtered = (
                list(filter(lambda k: str(k.year or "") == str(year), movieid))
                or movieid
            )
        else:
            filtered = movieid
        movieid = (
            list(filter(lambda k: k.kind in ["movie", "tvSeries"], filtered))
            or filtered
        )
        if bulk:
            return movieid
        if not movieid:
            return None
        movieid = movieid[0].id
    else:
        movieid = query
        
    movie = get_movie(movieid)
    if not movie:
        return None
        
    # Get release date
    if hasattr(movie, "release_date") and movie.release_date:
        date = movie.release_date
    elif hasattr(movie, "year") and movie.year:
        date = movie.year
    else:
        date = "N/A"
    
    # Get plot
    plot = None
    for keyword in ["plot", "summaries", "synopses"]:
        plot_data = getattr(movie, keyword, None)
        if isinstance(plot_data, list) and plot_data:
            plot = plot_data[0]
        elif plot_data:
            plot = plot_data
        if plot:
            break
    
    if plot and len(plot) > 300:
        plot = f"{plot[:300]}..."
    
    # Get trailer
    trailer_list = getattr(movie, "trailers", None)
    trailer = trailer_list[-1] if trailer_list else None
    
    # Get awards
    awards = getattr(movie, "awards", None)
    awards_text = "N/A"
    if awards:
        parts = []
        if hasattr(awards, "wins") and awards.wins:
            parts.append(f"{awards.wins} win{'s' if awards.wins != 1 else ''}")
        if hasattr(awards, "nominations") and awards.nominations:
            parts.append(f"{awards.nominations} nominatio{'n' if awards.nominations == 1 else 'ns'}")
        awards_text = ", ".join(parts) if parts else "N/A"
    
    # Get production companies
    company_credits = getattr(movie, "company_credits", None) or {}
    production = list_to_str([c.name for c in company_credits.get("production", [])]) or "N/A"
    
    # Get kind
    kind = "N/A"
    if hasattr(movie, "is_series") and movie.is_series():
        kind = "Series"
    elif hasattr(movie, "is_episode") and movie.is_episode():
        kind = "Episode"
    elif hasattr(movie, "kind") and movie.kind:
        kind = movie.kind.capitalize()
    
    # Get AKAs
    try:
        akas_data = get_akas(f"tt{movie.imdb_id}")
        aka_list = [a.title for a in akas_data.get("akas", [])[:LIST_ITEMS]]
        aka_text = list_to_str(aka_list) or "N/A"
    except Exception:
        aka_text = list_to_str(getattr(movie, "title_akas", []) or []) or "N/A"
    
    # Get seasons
    seasons = "N/A"
    if hasattr(movie, "info_series") and movie.info_series:
        if hasattr(movie.info_series, "display_seasons") and movie.info_series.display_seasons:
            seasons = len(movie.info_series.display_seasons)
    
    # Get runtime
    duration = getattr(movie, "duration", 0) or 0
    runtime = get_readable_time(int(duration) * 60) if duration else "N/A"
    
    return {
        "title": movie.title,
        "trailer": trailer or "https://imdb.com/",
        "votes": str(getattr(movie, "votes", "N/A") or "N/A"),
        "aka": aka_text,
        "seasons": seasons,
        "box_office": getattr(movie, "worldwide_gross", "N/A") or "N/A",
        "localized_title": getattr(movie, "title_localized", "N/A") or "N/A",
        "kind": kind,
        "imdb_id": f"tt{movie.imdb_id}",
        "cast": list_to_str([i.name for i in getattr(movie, "stars", [])]) or "N/A",
        "runtime": runtime,
        "countries": list_to_hash(getattr(movie, "countries", []) or [], True) or "N/A",
        "certificates": "N/A",  # Not directly available in imdbinfo
        "languages": list_to_hash(getattr(movie, "languages_text", []) or []) or "N/A",
        "director": list_to_str([i.name for i in getattr(movie, "directors", [])]) or "N/A",
        "writer": list_to_str([i.name for i in getattr(movie, "categories", {}).get("writer", [])]) or "N/A",
        "producer": list_to_str([i.name for i in getattr(movie, "categories", {}).get("producer", [])]) or "N/A",
        "composer": list_to_str([i.name for i in getattr(movie, "categories", {}).get("composer", [])]) or "N/A",
        "cinematographer": list_to_str([i.name for i in getattr(movie, "categories", {}).get("cinematographer", [])]) or "N/A",
        "music_team": list_to_str([i.name for i in getattr(movie, "categories", {}).get("music_department", [])]) or "N/A",
        "distributors": "N/A",  # Not directly available in imdbinfo
        "release_date": date,
        "year": str(getattr(movie, "year", "N/A") or "N/A"),
        "genres": list_to_hash(getattr(movie, "genres", []) or [], emoji=True) or "N/A",
        "poster": getattr(movie, "cover_url", "https://telegra.ph/file/5af8d90a479b0d11df298.jpg") or "https://telegra.ph/file/5af8d90a479b0d11df298.jpg",
        "plot": plot or "N/A",
        "rating": f"{getattr(movie, 'rating', 'N/A') or 'N/A'} / 10",
        "url": getattr(movie, "url", f"https://www.imdb.com/title/tt{movieid}"),
        "url_cast": f"https://www.imdb.com/title/tt{movieid}/fullcredits#cast",
        "url_releaseinfo": f"https://www.imdb.com/title/tt{movieid}/releaseinfo",
        "awards": awards_text,
        "production": production,
    }


def list_to_str(k):
    if not k:
        return ""
    elif len(k) == 1:
        return str(k[0])
    elif LIST_ITEMS:
        k = k[: int(LIST_ITEMS)]
        return " ".join(f"{elem}," for elem in k)[:-1] + " ..."
    else:
        return " ".join(f"{elem}," for elem in k)[:-1]


def list_to_hash(k, flagg=False, emoji=False):
    listing = ""
    if not k:
        return ""
    elif len(k) == 1:
        if not flagg:
            if emoji:
                return str(
                    IMDB_GENRE_EMOJI.get(k[0], "")
                    + " #"
                    + k[0].replace(" ", "_").replace("-", "_")
                )
            return str("#" + k[0].replace(" ", "_").replace("-", "_"))
        try:
            conflag = (conn.get(name=k[0])).flag
            return str(f"{conflag} #" + k[0].replace(" ", "_").replace("-", "_"))
        except AttributeError:
            return str("#" + k[0].replace(" ", "_").replace("-", "_"))
    elif LIST_ITEMS:
        k = k[: int(LIST_ITEMS)]
        for elem in k:
            ele = elem.replace(" ", "_").replace("-", "_")
            if flagg:
                with suppress(AttributeError):
                    conflag = (conn.get(name=elem)).flag
                    listing += f"{conflag} "
            if emoji:
                listing += f"{IMDB_GENRE_EMOJI.get(elem, '')} "
            listing += f"#{ele}, "
        return f"{listing[:-2]}"
    else:
        for elem in k:
            ele = elem.replace(" ", "_").replace("-", "_")
            if flagg:
                conflag = (conn.get(name=elem)).flag
                listing += f"{conflag} "
            listing += f"#{ele}, "
        return listing[:-2]


async def imdb_callback(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "movie":
        await query.answer()
        imdb_data = await sync_to_async(get_poster, query=data[3], id=True)
        if not imdb_data:
            await query.answer("Movie not found!", show_alert=True)
            await message.delete()
            return
            
        buttons = []
        if imdb_data["trailer"]:
            if isinstance(imdb_data["trailer"], list):
                buttons.append(
                    [
                        InlineKeyboardButton(
                            "▶️ IMDb Trailer ", url=str(imdb_data["trailer"][-1])
                        )
                    ]
                )
                imdb_data["trailer"] = list_to_str(imdb_data["trailer"])
            else:
                buttons.append(
                    [InlineKeyboardButton("▶️ IMDb Trailer ", url=str(imdb_data["trailer"]))]
                )
        buttons.append(
            [InlineKeyboardButton("🚫 Close 🚫", callback_data=f"imdb {user_id} close")]
        )
        template = ""
        # if int(data[1]) in user_data and user_data[int(data[1])].get('imdb_temp'):
        #    template = user_data[int(data[1])].get('imdb_temp')
        # if not template:
        template = config_dict["IMDB_TEMPLATE"]
        if imdb_data and template != "":
            cap = template.format(
                title=imdb_data["title"],
                trailer=imdb_data["trailer"],
                votes=imdb_data["votes"],
                aka=imdb_data["aka"],
                seasons=imdb_data["seasons"],
                box_office=imdb_data["box_office"],
                localized_title=imdb_data["localized_title"],
                kind=imdb_data["kind"],
                imdb_id=imdb_data["imdb_id"],
                cast=imdb_data["cast"],
                runtime=imdb_data["runtime"],
                countries=imdb_data["countries"],
                certificates=imdb_data["certificates"],
                languages=imdb_data["languages"],
                director=imdb_data["director"],
                writer=imdb_data["writer"],
                producer=imdb_data["producer"],
                composer=imdb_data["composer"],
                cinematographer=imdb_data["cinematographer"],
                music_team=imdb_data["music_team"],
                distributors=imdb_data["distributors"],
                release_date=imdb_data["release_date"],
                year=imdb_data["year"],
                genres=imdb_data["genres"],
                poster=imdb_data["poster"],
                plot=imdb_data["plot"],
                rating=imdb_data["rating"],
                url=imdb_data["url"],
                url_cast=imdb_data["url_cast"],
                url_releaseinfo=imdb_data["url_releaseinfo"],
                **locals(),
            )
        else:
            cap = "No Results"
            
        reply_to = message.reply_to_message
        if not reply_to:
            await message.delete()
            return
            
        if imdb_data.get("poster"):
            try:
                await bot.send_photo(
                    chat_id=reply_to.chat.id,
                    caption=cap,
                    photo=imdb_data["poster"],
                    reply_to_message_id=reply_to.id,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                poster = imdb_data.get("poster").replace(".jpg", "._V1_UX360.jpg")
                await sendMessage(
                    reply_to, cap, InlineKeyboardMarkup(buttons), poster
                )
        else:
            await sendMessage(
                reply_to,
                cap,
                InlineKeyboardMarkup(buttons),
                "https://telegra.ph/file/5af8d90a479b0d11df298.jpg",
            )
        await message.delete()
    else:
        await query.answer()
        await query.message.delete()
        if query.message.reply_to_message:
            await query.message.reply_to_message.delete()


bot.add_handler(
    MessageHandler(
        imdb_search,
        filters=command(BotCommands.IMDBCommand)
        & CustomFilters.authorized
        & ~CustomFilters.blacklisted,
    )
)
bot.add_handler(CallbackQueryHandler(imdb_callback, filters=regex(r"^imdb")))
