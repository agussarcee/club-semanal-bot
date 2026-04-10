import discord
from discord.ext import commands
from discord import app_commands
import requests
from youtubesearchpython import VideosSearch
import os
import json
import time

async def autocomplete_peliculas(
    interaction: discord.Interaction,
    current: str
):
    if not current:
        return []

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": current,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    choices = []

    for movie in data["results"][:8]:
        titulo = movie["title"]
        anio = movie["release_date"][:4] if movie["release_date"] else "?"

        choices.append(
            app_commands.Choice(
                name=f"{titulo} ({anio})",
                value=titulo
            )
        )

    return choices

TOKEN = os.getenv("TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ARCHIVO_PROPUESTAS = "propuestas.json"

def cargar_propuestas():
    try:
        with open(ARCHIVO_PROPUESTAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def guardar_propuestas():
    with open(ARCHIVO_PROPUESTAS, "w", encoding="utf-8") as f:
        json.dump(lista_propuestas, f, ensure_ascii=False, indent=2)

lista_propuestas = cargar_propuestas()

@bot.event
async def on_ready():
    await tree.sync()
    print("Club Semanal conectado como " + str(bot.user))

@bot.command()
async def ping(ctx):
    await ctx.send("🎬 Club Semanal está funcionando!")

@bot.command()
async def pelicula(ctx, *, nombre):
    
    url = "https://api.themoviedb.org/3/search/movie"
    
    params = {
        "api_key": TMDB_API_KEY,
        "query": nombre,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if len(data["results"]) == 0:
        await ctx.send("No encontré esa película 😢")
        return

    movie = data["results"][0]
    movie_id = movie["id"]

    titulo = movie["title"]
    titulo_original = movie["original_title"]

    if titulo != titulo_original:
        titulo_mostrar = f"{titulo} ({titulo_original})"
    else:
        titulo_mostrar = titulo

    descripcion = movie["overview"]
    rating = movie["vote_average"]
    fecha = movie["release_date"][:4]
    
    poster_path = movie["poster_path"]
    poster_url = "https://image.tmdb.org/t/p/w500" + poster_path

    proveedores_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"

    params_proveedores = {
        "api_key": TMDB_API_KEY
    }

    response_proveedores = requests.get(proveedores_url, params=params_proveedores)
    data_proveedores = response_proveedores.json()

    plataformas = []

    if "AR" in data_proveedores["results"]:
        if "flatrate" in data_proveedores["results"]["AR"]:
            for p in data_proveedores["results"]["AR"]["flatrate"]:
                plataformas.append(p["provider_name"])

    if len(plataformas) == 0:
        plataformas_texto = "No disponible en streaming en Argentina"
    else:
        plataformas_texto = ", ".join(plataformas)

    query = f"{titulo} {fecha} trailer"
    query = query.replace(" ", "+")

    trailer_url = f"https://www.youtube.com/results?search_query={query}"

    mensaje = f"""
    
    📺 Dónde verla en Argentina:
    {plataformas_texto}

    📅 Año: {fecha}
    ⭐ Rating: {rating}

    📝 {descripcion}

    ▶ Trailer:
    {trailer_url}
    """

    embed = discord.Embed(
        title=f"🎬 {titulo_mostrar}",
        color=0x00ffcc
)

    # Poster grande debajo del título
    embed.set_image(url=poster_url)

    # Dónde verla
    embed.add_field(
        name="📺 Dónde verla",
        value=plataformas_texto,
        inline=False
    )

    # Año
    embed.add_field(
        name="📅 Año",
        value=fecha,
        inline=True
    )

    # Rating
    embed.add_field(
        name="⭐ Rating",
        value=rating,
        inline=True
    )

    # Descripción
    embed.add_field(
        name="📝 Descripción",
        value=descripcion[:500] + "..." if len(descripcion) > 500 else descripcion,
        inline=False
    )

    # Trailer
    embed.add_field(
        name="▶ Trailer",
        value=trailer_url,
        inline=False
    )

    embed.add_field(
    name=" ",
    value="──────────",
    inline=False
)

    await ctx.send(embed=embed)

@tree.command(name="proponer", description="Proponer una película")
@app_commands.autocomplete(nombre=autocomplete_peliculas)

async def proponer(interaction: discord.Interaction, nombre: str):

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": nombre,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if len(data["results"]) == 0:
        await interaction.response.send_message("No encontré esa película 😢", ephemeral=True)
        return

    movie = data["results"][0]

    titulo = movie["title"]
    titulo_original = movie["original_title"]

    if titulo != titulo_original:
        titulo_mostrar = f"{titulo} ({titulo_original})"
    else:
        titulo_mostrar = titulo

    for peli in lista_propuestas:
        if peli["titulo"].lower() == titulo_mostrar.lower():
            await interaction.response.send_message("⚠ Esa película ya fue propuesta.", ephemeral=True)
            return

    lista_propuestas.append({
        "titulo": titulo_mostrar,
        "busqueda": nombre
    })

    guardar_propuestas()

    await interaction.response.send_message(
        f"🎬 **{titulo_mostrar}** fue agregada a las propuestas.",
        ephemeral=True
    )

@bot.command()
async def propuestas(ctx):

    await ctx.message.delete()

    if len(lista_propuestas) == 0:
        await ctx.author.send("No hay propuestas todavía.")
        return

    mensaje = "🍿 **Películas propuestas**\n\n"

    for i, peli in enumerate(lista_propuestas, start=1):
        mensaje += f"{i}. {peli['titulo']}\n"

    await ctx.author.send(mensaje)

@bot.command()
async def preview(ctx, *numeros):

    await ctx.message.delete()

    if len(numeros) == 0:
        await ctx.author.send("Tenés que indicar los números de las películas.")
        return

    seleccionadas = []

    for n in numeros:
        try:
            index = int(n) - 1
        except:
            continue

        if index < len(lista_propuestas):
            seleccionadas.append(lista_propuestas[index])

    if len(seleccionadas) == 0:
        await ctx.author.send("No encontré esas propuestas.")
        return

    await ctx.author.send("🎬 **Preview de publicación**")

    for peli in seleccionadas:
        await pelicula(ctx.author, nombre=peli["busqueda"])

@bot.command()
async def publicar(ctx, *numeros):

    await ctx.message.delete()

    if len(numeros) == 0:
        await ctx.send("Tenés que indicar los números de las películas.")
        return

    seleccionadas = []

    for n in numeros:
        index = int(n) - 1

        if index < len(lista_propuestas):
            seleccionadas.append(lista_propuestas[index])

    if len(seleccionadas) == 0:
        await ctx.send("No encontré esas propuestas.")
        return

    await ctx.send("🍿 **Posibles películas de esta semana**")

    titulos_encuesta = [p["titulo"] for p in seleccionadas]

    for peli in seleccionadas:
        await pelicula(ctx, nombre=peli["busqueda"])

    for peli in seleccionadas:
        lista_propuestas.remove(peli)

    guardar_propuestas()

    poll = discord.Poll(
    question="¿Cuál vemos esta semana?",
    duration=24
    )

    for titulo in titulos_encuesta:
        poll.add_answer(text=titulo)

    await ctx.send(poll=poll)


time.sleep(5)

bot.run(TOKEN)
